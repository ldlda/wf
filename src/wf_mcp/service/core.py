from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from wf_authoring import NodeSpec, build_async_registry
from wf_core import NodeUse, Workflow, execute_workflow_async

from ..sdk import BackendAdapter
from ..catalog import CombinedCatalog, snapshot_from_specs
from ..connections import ConnectionRegistry, parse_connection_id, qualify_node_name
from ..discovery import discover_connection_capabilities, specs_from_discovered_tools
from ..shared.errors import error_payload
from ..events import McpEvent, make_event
from ..models import (
    AuthRecord,
    CatalogPromptEntry,
    CatalogResourceEntry,
    CatalogSnapshot,
    ConnectionConfig,
    RawWorkflowPlan,
)
from ..store import Store
from .adapters import require_adapter
from .specs import get_qualified_spec, qualify_spec


@dataclass(slots=True)
class WfMcpService:
    store: Store
    default_catalog_max_age_seconds: int = 300
    connections: ConnectionRegistry = field(default_factory=ConnectionRegistry)
    adapters: dict[str, BackendAdapter] = field(default_factory=dict)
    specs_by_connection: dict[str, dict[str, NodeSpec[Any, Any]]] = field(
        default_factory=dict
    )
    events: list[McpEvent] = field(default_factory=list)

    def register_connection(self, connection: ConnectionConfig) -> None:
        parse_connection_id(connection.id)
        self.connections.register(connection)
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
    ) -> None:
        self.connections.get(connection_id)
        qualified_specs = {
            qualify_node_name(connection_id, spec.name): qualify_spec(
                connection_id, spec
            )
            for spec in specs
        }
        self.specs_by_connection[connection_id] = qualified_specs
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

    def get_catalog(self) -> CombinedCatalog:
        snapshots: dict[str, CatalogSnapshot] = {}
        for connection in self.connections.list_enabled():
            snapshot = self.store.load_catalog(connection.id)
            if snapshot is not None:
                snapshots[connection.id] = snapshot
        return CombinedCatalog(snapshots=snapshots)

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
        return list(self.events)

    def _get_qualified_spec(self, qualified_name: str) -> NodeSpec[Any, Any]:
        return get_qualified_spec(self.specs_by_connection, qualified_name)

    def _record_event(self, event: McpEvent) -> None:
        self.events.append(event)
