from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from wf_authoring import NodeReturn, NodeSpec, build_async_registry
from wf_artifacts import (
    FileWorkflowArtifactStore,
    WorkflowArtifact,
    WorkflowArtifactCatalogEntry,
    WorkflowArtifactStore,
    artifact_catalog_entry,
)
from wf_core import NodeUse, Workflow, execute_workflow_async

from ...connections import ConnectionRegistry, parse_connection_id, qualify_node_name
from ...events import EventBus, McpEvent, make_event
from ...models import (
    AuthRecord,
    CatalogNodeEntry,
    CatalogPromptEntry,
    CatalogResourceEntry,
    CatalogSnapshot,
    ConnectionConfig,
    RawWorkflowPlan,
)
from ...sdk import BackendAdapter
from ...shared.errors import error_payload
from ...shared.names import RESERVED_CONNECTION_IDS
from ...storage import Store
from ...workflow.wrappers import _model_from_schema
from ..catalog import CombinedCatalog, snapshot_from_specs
from ..discovery import discover_connection_capabilities, specs_from_discovered_tools
from ..admin_capabilities import admin_source
from .adapters import require_adapter
from .builtins import builtin_sources
from .capability_sources import (
    CapabilityBuckets,
    CapabilitySource,
    SourcePermissions,
    SourceVisibility,
)
from .sources import SpecSource
from .specs import get_qualified_spec, qualify_spec


def _store_root(store: Store) -> Path:
    """Return the file root for stores that expose one, else use local default."""
    root = getattr(store, "root", None)
    return root if isinstance(root, Path) else Path(".wf_mcp_store")


@dataclass(slots=True)
class WfMcpService:
    store: Store
    default_catalog_max_age_seconds: int = 300
    connections: ConnectionRegistry = field(default_factory=ConnectionRegistry)
    adapters: dict[str, BackendAdapter] = field(default_factory=dict)
    capability_sources: dict[str, CapabilitySource] = field(default_factory=dict)
    event_bus: EventBus = field(default_factory=EventBus)
    include_builtin_specs: bool = True
    artifact_store: WorkflowArtifactStore | None = None

    def __post_init__(self) -> None:
        """Install broker-local system specs when enabled."""
        if self.artifact_store is None:
            self.artifact_store = FileWorkflowArtifactStore(_store_root(self.store))
        if self.include_builtin_specs:
            for source in builtin_sources(self).values():
                self.register_spec_source(source)
        self.register_capability_source(admin_source())

    @property
    def spec_sources(self) -> dict[str, SpecSource]:
        """Compatibility view of node-spec capability sources."""
        return {
            source.id: SpecSource(
                id=source.id,
                kind=source.kind,
                specs=dict(source.capabilities.node_specs),
                visible=source.enabled and source.visibility.planner,
                mcp_client_visible=source.enabled and source.visibility.mcp_client,
                admin_dashboard_visible=(
                    source.enabled and source.visibility.admin_dashboard
                ),
                safe_for_workflow=source.permissions.safe_for_workflow,
                calls_upstream=source.permissions.calls_upstream,
                mutates_config=source.permissions.mutates_config,
                mutates_auth=source.permissions.mutates_auth,
                description=source.description,
            )
            for source in self.capability_sources.values()
            if source.capabilities.node_specs
        }

    @property
    def specs_by_connection(self) -> dict[str, dict[str, NodeSpec[Any, Any]]]:
        """Compatibility view of source specs keyed by source id."""
        return {
            source.id: dict(source.capabilities.node_specs)
            for source in self.capability_sources.values()
            if source.capabilities.node_specs
        }

    def register_connection(self, connection: ConnectionConfig) -> None:
        parse_connection_id(connection.id)
        if connection.id in RESERVED_CONNECTION_IDS:
            raise ValueError(f"connection id {connection.id!r} is reserved by wf-mcp")
        self.connections.register(connection)
        self._hydrate_connection_source_from_snapshot(connection)
        self._record_event(
            make_event(
                "connection_registered",
                connection_id=connection.id,
                payload={"server": connection.server, "account": connection.account},
            )
        )

    def register_adapter(self, server: str, adapter: BackendAdapter) -> None:
        self.adapters[server] = adapter

    def save_auth(self, record: AuthRecord) -> None:
        self.store.save_auth(record)
        self._record_event(
            make_event(
                "auth_saved",
                connection_id=record.connection_id,
                payload={"scheme": record.scheme},
            )
        )

    def load_auth(self, connection_id: str) -> AuthRecord | None:
        return self.store.load_auth(connection_id)

    def register_specs(
        self,
        connection_id: str,
        *specs: NodeSpec[Any, Any],
        max_age_seconds: int | None = None,
        emit_change_events: bool = True,
    ) -> None:
        self.connections.get(connection_id)
        qualified_specs = {
            qualify_node_name(connection_id, spec.name): qualify_spec(
                connection_id, spec
            )
            for spec in specs
        }
        existing_source = self.capability_sources.get(connection_id)
        if existing_source is not None:
            # Catalog refreshes replace discovered specs, not operator policy.
            existing_source.capabilities.node_specs = qualified_specs
        else:
            self.register_spec_source(
                SpecSource(
                    id=connection_id,
                    kind="connection",
                    specs=qualified_specs,
                    enabled=self.connections.get(connection_id).enabled,
                    mcp_client_visible=True,
                    calls_upstream=True,
                    description=(
                        f"Specs discovered or registered for {connection_id}."
                    ),
                )
            )
        snapshot = snapshot_from_specs(
            connection_id,
            specs=qualified_specs,
            fetched_at_epoch_ms=int(time.time() * 1000),
            max_age_seconds=max_age_seconds or self.default_catalog_max_age_seconds,
        )
        self.store.save_catalog(snapshot)
        self._record_event(
            make_event(
                "specs_registered",
                connection_id=connection_id,
                payload={"node_count": len(qualified_specs)},
            )
        )
        if emit_change_events:
            self._record_catalog_change_events(
                connection_id,
                snapshot,
                reason="specs_registered",
            )

    def get_catalog(self) -> CombinedCatalog:
        snapshots: dict[str, CatalogSnapshot] = {}
        for connection in self.connections.list_enabled():
            snapshot = self.store.load_catalog(connection.id)
            if snapshot is not None:
                snapshots[connection.id] = snapshot
        return CombinedCatalog(snapshots=snapshots)

    def get_planner_catalog(self) -> CombinedCatalog:
        """Return all planner-visible specs, including broker-local sources."""
        snapshots: dict[str, CatalogSnapshot] = {}
        fetched_at_epoch_ms = int(time.time() * 1000)
        for source in self.capability_sources.values():
            if not source.enabled or not source.visibility.planner:
                continue
            stored_snapshot = self.store.load_catalog(source.id)
            snapshots[source.id] = snapshot_from_specs(
                source.id,
                specs=source.capabilities.node_specs,
                tool_display_names={
                    entry.local_name: entry.title for entry in stored_snapshot.nodes
                }
                if stored_snapshot is not None
                else None,
                metadata={
                    "kind": source.kind,
                    "description": source.description,
                }
                if stored_snapshot is None
                else stored_snapshot.metadata,
                fetched_at_epoch_ms=(
                    stored_snapshot.fetched_at_epoch_ms
                    if stored_snapshot is not None
                    else fetched_at_epoch_ms
                ),
                max_age_seconds=(
                    stored_snapshot.max_age_seconds
                    if stored_snapshot is not None
                    else self.default_catalog_max_age_seconds
                ),
            )
            if stored_snapshot is not None:
                # Connection resources/prompts are discovered by the backend catalog,
                # while planner node visibility is governed by capability sources.
                snapshots[source.id].resources = list(stored_snapshot.resources)
                snapshots[source.id].prompts = list(stored_snapshot.prompts)
        return CombinedCatalog(snapshots=snapshots)

    def list_spec_sources(self) -> list[dict[str, Any]]:
        """Return planner spec sources without expanding every node schema."""
        return [
            source.as_status()
            for source in sorted(
                self.capability_sources.values(),
                key=lambda source: source.id,
            )
            if source.capabilities.node_specs
            and source.enabled
            and source.visibility.planner
        ]

    def list_sources(self) -> list[dict[str, Any]]:
        """Return every capability source with the names it currently owns."""
        return [
            source.as_inventory()
            for source in sorted(
                self.capability_sources.values(),
                key=lambda source: source.id,
            )
        ]

    def list_available_specs(self) -> list[CatalogNodeEntry]:
        """Return planner-visible node catalog entries from every visible source."""
        return self.get_planner_catalog().entries()

    def workflow_artifact_catalog_entry(
        self,
        artifact: WorkflowArtifact,
    ) -> WorkflowArtifactCatalogEntry:
        """Project a saved workflow artifact as a planner catalog entry."""
        return artifact_catalog_entry(artifact)

    def get_connection_snapshot(self, connection_id: str) -> CatalogSnapshot | None:
        self.connections.get(connection_id)
        return self.store.load_catalog(connection_id)

    def connection_statuses(self) -> list[dict[str, Any]]:
        statuses: list[dict[str, Any]] = []
        for connection in self.connections.list_all():
            snapshot = self.store.load_catalog(connection.id)
            statuses.append(
                {
                    "connection_id": connection.id,
                    "server": connection.server,
                    "account": connection.account,
                    "enabled": connection.enabled,
                    "has_snapshot": snapshot is not None,
                    "fetched_at_epoch_ms": None
                    if snapshot is None
                    else snapshot.fetched_at_epoch_ms,
                    "max_age_seconds": None
                    if snapshot is None
                    else snapshot.max_age_seconds,
                    "node_count": 0 if snapshot is None else len(snapshot.nodes),
                    "resource_count": 0
                    if snapshot is None
                    else len(snapshot.resources),
                    "prompt_count": 0 if snapshot is None else len(snapshot.prompts),
                }
            )
        return statuses

    def list_resources(
        self,
        *,
        connection_id: str | None = None,
    ) -> list[CatalogResourceEntry]:
        if connection_id is None:
            return self.get_catalog().resource_entries()
        snapshot = self.get_connection_snapshot(connection_id)
        if snapshot is None:
            return []
        return sorted(snapshot.resources, key=lambda entry: entry.qualified_name)

    def list_prompts(
        self,
        *,
        connection_id: str | None = None,
    ) -> list[CatalogPromptEntry]:
        if connection_id is None:
            return self.get_catalog().prompt_entries()
        snapshot = self.get_connection_snapshot(connection_id)
        if snapshot is None:
            return []
        return sorted(snapshot.prompts, key=lambda entry: entry.qualified_name)

    def get_resource(self, qualified_name: str) -> CatalogResourceEntry:
        entry = self.get_catalog().find_resource(qualified_name)
        if entry is None:
            raise KeyError(f"unknown resource {qualified_name!r}")
        return entry

    def get_prompt(self, qualified_name: str) -> CatalogPromptEntry:
        entry = self.get_catalog().find_prompt(qualified_name)
        if entry is None:
            raise KeyError(f"unknown prompt {qualified_name!r}")
        return entry

    async def read_resource(self, qualified_name: str) -> dict[str, Any]:
        resource = self.get_resource(qualified_name)
        connection = self.connections.get(resource.connection_id)
        adapter = require_adapter(connection, self.adapters)
        auth = self.load_auth(resource.connection_id)
        self._record_event(
            make_event(
                "resource_read_started",
                connection_id=resource.connection_id,
                capability_id=qualified_name,
                payload={"uri": resource.uri},
            )
        )
        result = await adapter.read_resource(connection, auth, resource.uri)
        self._record_event(
            make_event(
                "resource_read_completed",
                connection_id=resource.connection_id,
                capability_id=qualified_name,
                payload={"uri": resource.uri},
            )
        )
        return result

    async def invoke_method(
        self,
        connection_id: str,
        method: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        connection = self.connections.get(connection_id)
        adapter = require_adapter(connection, self.adapters)
        auth = self.load_auth(connection_id)
        self._record_event(
            make_event(
                "raw_method_started",
                connection_id=connection_id,
                capability_id=method,
                payload={"params": params or {}},
            )
        )
        result = await adapter.invoke_method(connection, auth, method, params)
        self._record_event(
            make_event(
                "raw_method_completed",
                connection_id=connection_id,
                capability_id=method,
                payload={"result_keys": sorted(result.keys())},
            )
        )
        return result

    async def call_tool(
        self,
        connection_id: str,
        tool_name: str,
        *,
        arguments: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        connection = self.connections.get(connection_id)
        adapter = require_adapter(connection, self.adapters)
        auth = self.load_auth(connection_id)
        capability_id = qualify_node_name(connection_id, tool_name)
        payload = arguments or {}
        self._record_event(
            make_event(
                "tool_call_started",
                connection_id=connection_id,
                capability_id=capability_id,
                payload={"argument_keys": sorted(payload.keys())},
            )
        )
        result = await adapter.call_tool(connection, auth, tool_name, payload)
        self._record_event(
            make_event(
                "tool_call_completed",
                connection_id=connection_id,
                capability_id=capability_id,
                payload={"outcome": result.outcome},
            )
        )
        return {
            "outcome": result.outcome,
            "output": result.output,
            "meta": result.meta,
        }

    async def send_notification(
        self,
        connection_id: str,
        method: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> None:
        connection = self.connections.get(connection_id)
        adapter = require_adapter(connection, self.adapters)
        auth = self.load_auth(connection_id)
        self._record_event(
            make_event(
                "raw_notification_started",
                connection_id=connection_id,
                capability_id=method,
                payload={"params": params or {}},
            )
        )
        await adapter.send_notification(connection, auth, method, params)
        self._record_event(
            make_event(
                "raw_notification_completed",
                connection_id=connection_id,
                capability_id=method,
                payload={},
            )
        )

    async def render_prompt(
        self,
        qualified_name: str,
        *,
        arguments: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        prompt = self.get_prompt(qualified_name)
        connection = self.connections.get(prompt.connection_id)
        adapter = require_adapter(connection, self.adapters)
        auth = self.load_auth(prompt.connection_id)
        self._record_event(
            make_event(
                "prompt_get_started",
                connection_id=prompt.connection_id,
                capability_id=qualified_name,
                payload={"argument_keys": sorted((arguments or {}).keys())},
            )
        )
        result = await adapter.get_prompt(
            connection,
            auth,
            prompt.local_name,
            arguments,
        )
        self._record_event(
            make_event(
                "prompt_get_completed",
                connection_id=prompt.connection_id,
                capability_id=qualified_name,
                payload={"argument_keys": sorted((arguments or {}).keys())},
            )
        )
        return result

    async def refresh_connection_catalog(
        self,
        connection_id: str,
        *,
        max_age_seconds: int | None = None,
    ) -> None:
        connection = self.connections.get(connection_id)
        adapter = require_adapter(connection, self.adapters)

        auth = self.load_auth(connection_id)
        self._record_event(
            make_event(
                "catalog_refresh_started",
                connection_id=connection_id,
                payload={"server": connection.server},
            )
        )
        try:
            capabilities = await discover_connection_capabilities(
                connection=connection,
                auth=auth,
                adapter=adapter,
            )
            specs = specs_from_discovered_tools(
                connection=connection,
                auth=auth,
                adapter=adapter,
                tools=capabilities.tools,
                emit_event=self._record_event,
            )
            self.register_specs(
                connection_id,
                *specs,
                max_age_seconds=max_age_seconds,
                emit_change_events=False,
            )
            snapshot = snapshot_from_specs(
                connection_id,
                specs=self.specs_by_connection.get(connection_id, {}),
                tool_display_names={
                    tool.name: tool.title for tool in capabilities.tools
                },
                resources=capabilities.resources,
                prompts=capabilities.prompts,
                metadata=capabilities.metadata,
                fetched_at_epoch_ms=int(time.time() * 1000),
                max_age_seconds=max_age_seconds or self.default_catalog_max_age_seconds,
            )
            self.store.save_catalog(snapshot)
            self._record_catalog_change_events(
                connection_id,
                snapshot,
                reason="catalog_refresh",
            )
            self._record_event(
                make_event(
                    "catalog_refresh_completed",
                    connection_id=connection_id,
                    payload={
                        "node_count": len(snapshot.nodes),
                        "resource_count": len(snapshot.resources),
                        "prompt_count": len(snapshot.prompts),
                    },
                )
            )
        except Exception as exc:
            self._record_event(
                make_event(
                    "catalog_refresh_failed",
                    connection_id=connection_id,
                    payload=error_payload(exc),
                )
            )
            raise

    def compile_plan(self, plan: RawWorkflowPlan) -> Workflow:
        node_defs: dict[str, Any] = {}
        for step in plan.nodes:
            if step.get("type") != "node":
                continue
            qualified_name = step["node"]
            spec = self._get_qualified_spec(qualified_name)
            node_defs[qualified_name] = spec.to_node_def()

        payload = {
            "name": plan.name,
            "input_schema": plan.input_schema,
            "state_schema": plan.state_schema,
            "output_schema": plan.output_schema,
            "start": plan.start,
            "node_defs": [node.model_dump() for node in node_defs.values()],
            "nodes": plan.nodes,
            "edges": plan.edges,
        }
        return Workflow.model_validate(payload)

    async def run_workflow_from_plan(
        self,
        plan: RawWorkflowPlan,
        workflow_input: dict[str, Any],
    ):
        self._record_event(
            make_event(
                "workflow_run_started",
                workflow_name=plan.name,
                payload={"input_keys": sorted(workflow_input.keys())},
            )
        )
        workflow = self.compile_plan(plan)
        specs = [
            self._get_qualified_spec(node.node)
            for node in workflow.nodes
            if isinstance(node, NodeUse)
        ]
        registry = build_async_registry(*specs)
        run = await execute_workflow_async(workflow, workflow_input, registry)
        self._record_event(
            make_event(
                "workflow_run_completed",
                workflow_name=plan.name,
                payload={"status": run.status.value},
            )
        )
        return run

    def list_events(self) -> list[McpEvent]:
        return self.event_bus.list_events()

    def register_capability_source(self, source: CapabilitySource) -> None:
        """Register a capability source as canonical service state."""
        self.capability_sources[source.id] = source

    def register_spec_source(self, source: SpecSource) -> None:
        """Register a legacy spec source through the capability model."""
        self.register_capability_source(source.as_capability_source())

    def _hydrate_connection_source_from_snapshot(
        self,
        connection: ConnectionConfig,
    ) -> None:
        """Restore planner-visible connection specs from a stored catalog snapshot."""
        if connection.id in self.capability_sources:
            return

        snapshot = self.store.load_catalog(connection.id)
        if snapshot is None or not snapshot.nodes:
            return

        specs = {
            entry.qualified_name: self._spec_from_snapshot_entry(entry)
            for entry in snapshot.nodes
        }
        self.register_capability_source(
            CapabilitySource(
                id=connection.id,
                kind="connection",
                enabled=connection.enabled,
                capabilities=CapabilityBuckets(node_specs=specs),
                visibility=SourceVisibility(
                    planner=True,
                    mcp_client=True,
                    admin_dashboard=True,
                ),
                permissions=SourcePermissions(calls_upstream=True),
                description=f"Specs restored from catalog for {connection.id}.",
            )
        )

    def _spec_from_snapshot_entry(
        self,
        entry: CatalogNodeEntry,
    ) -> NodeSpec[Any, Any]:
        """Rebuild an executable tool wrapper from a stored catalog node entry."""
        model_prefix = entry.qualified_name.replace(".", "_").replace("-", "_")
        input_model = _model_from_schema(f"{model_prefix}_Input", entry.input_schema)
        output_model = _model_from_schema(f"{model_prefix}_Output", entry.output_schema)

        async def invoke_tool(payload: BaseModel) -> NodeReturn[BaseModel]:
            result = await self.call_tool(
                entry.connection_id,
                entry.local_name,
                arguments=payload.model_dump(),
            )
            return NodeReturn(
                outcome=result["outcome"],
                output=output_model.model_validate(result["output"]),
            )

        return NodeSpec(
            name=entry.qualified_name,
            input_model=input_model,
            output_model=output_model,
            outcomes=entry.outcomes,
            fn=invoke_tool,
            description=entry.description,
            is_async=True,
            accepts_context=False,
            input_schema_contract=entry.input_schema,
            output_schema_contract=entry.output_schema,
        )

    def _get_qualified_spec(self, qualified_name: str) -> NodeSpec[Any, Any]:
        return get_qualified_spec(self.capability_sources, qualified_name)

    def _record_event(self, event: McpEvent) -> None:
        self.event_bus.publish(event)

    def _record_catalog_change_events(
        self,
        connection_id: str,
        snapshot: CatalogSnapshot,
        *,
        reason: str,
    ) -> None:
        """Emit local change events that future MCP notifications can project."""
        counts = {
            "node_count": len(snapshot.nodes),
            "resource_count": len(snapshot.resources),
            "prompt_count": len(snapshot.prompts),
        }
        if snapshot.nodes:
            self._record_event(
                make_event(
                    "tools_changed",
                    connection_id=connection_id,
                    payload={"reason": reason, "node_count": counts["node_count"]},
                )
            )
        if snapshot.resources:
            self._record_event(
                make_event(
                    "resources_changed",
                    connection_id=connection_id,
                    payload={
                        "reason": reason,
                        "resource_count": counts["resource_count"],
                    },
                )
            )
        if snapshot.prompts:
            self._record_event(
                make_event(
                    "prompts_changed",
                    connection_id=connection_id,
                    payload={"reason": reason, "prompt_count": counts["prompt_count"]},
                )
            )
        self._record_event(
            make_event(
                "catalog_changed",
                connection_id=connection_id,
                payload={"reason": reason, **counts},
            )
        )
