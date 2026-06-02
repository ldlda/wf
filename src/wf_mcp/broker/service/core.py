from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel

from wf_artifacts import (
    DraftWorkspaceStore,
    RunStore,
    WorkflowArtifact,
    WorkflowArtifactCatalogEntry,
    WorkflowArtifactStore,
    WorkflowDeployment,
    artifact_catalog_entry,
)
from wf_authoring import NodeReturn, NodeSpec
from wf_core import (
    NodeUse,
    RunState,
    Workflow,
    execute_workflow_result_async,
    resume_workflow_result_async,
)
from wf_api.models import RawWorkflowPlan
from wf_api.runtime_dependencies import resolve_runtime_dependencies
from wf_platform import (
    CapabilityBuckets,
    CapabilitySource,
    DocumentationPrompt,
    DocumentationResource,
    SourcePermissions,
    SourceVisibility,
    page_items,
)
from ...connections import ConnectionRegistry, parse_connection_id, qualify_node_name
from ...events import EventBus, McpEvent, make_event
from ...models import (
    AuthRecord,
    CatalogNodeEntry,
    CatalogPromptEntry,
    CatalogResourceEntry,
    CatalogSnapshot,
    BrokerConfig,
    ConnectionConfig,
)
from ...sdk import BackendAdapter
from ...runtime import ToolExecutor
from ...shared.errors import error_payload
from ...shared.names import RESERVED_CONNECTION_IDS
from ...storage import Store
from ...workflow.wrappers import _model_from_schema
from wf_api.saved_subgraphs import (
    SavedSubgraphTree,
    prepare_saved_subgraphs,
    resolve_saved_subgraph_tree,
)
from ..admin_capabilities import admin_source
from ..catalog import CombinedCatalog, snapshot_from_specs
from ..discovery import discover_connection_capabilities, specs_from_discovered_tools
from .adapters import require_adapter
from .builtins import builtin_sources
from .specs import get_qualified_spec, qualify_spec


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
    draft_workspace_store: DraftWorkspaceStore | None = None
    run_store: RunStore | None = None
    tool_executor: ToolExecutor | None = None

    def __post_init__(self) -> None:
        """Install broker-local system specs when enabled.

        Workflow stores are injected by entrypoint/config construction. This service
        must not guess workflow persistence from the MCP catalog/auth store because
        CLI, MCP, and future HTTP frontends may share or swap those stores.
        """
        if self.include_builtin_specs:
            for source in builtin_sources().values():
                self.register_capability_source(source)
        self.register_capability_source(admin_source())

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

    def sync_connections_from_config(self, config: BrokerConfig) -> None:
        """Reconcile connection sources after the public server reloads config.

        The public server has two cooperating views: proxy mounts read the live
        file-backed config, while workflow discovery reads this service's source
        registry. Reload must keep those views aligned, or raw proxy tools can be
        enabled while planner-visible workflow capabilities remain disabled.
        """
        next_ids = {connection.id for connection in config.connections}
        previous_ids = set(self.connections.connections)
        for connection_id in previous_ids - next_ids:
            del self.connections.connections[connection_id]
            self.capability_sources.pop(connection_id, None)

        for connection in config.connections:
            parse_connection_id(connection.id)
            if connection.id in RESERVED_CONNECTION_IDS:
                raise ValueError(
                    f"connection id {connection.id!r} is reserved by wf-mcp"
                )
            self.connections.register(connection)
            source = self.capability_sources.get(connection.id)
            if source is None:
                self._hydrate_connection_source_from_snapshot(connection)
            else:
                source.enabled = connection.enabled

    def register_adapter(self, server: str, adapter: BackendAdapter) -> None:
        self.adapters[server] = adapter

    def _tool_executor_for(self, connection: ConnectionConfig) -> ToolExecutor:
        """Return the executor used by generated workflow NodeSpecs.

        Discovery still uses the short-lived adapter path. Generated workflow
        nodes use this executor hook so config-built services can swap in a
        persistent runtime pool for stateful MCP servers.
        """
        if self.tool_executor is not None:
            return self.tool_executor
        return require_adapter(connection, self.adapters)

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
            self.register_capability_source(
                CapabilitySource(
                    id=connection_id,
                    kind="connection",
                    capabilities=CapabilityBuckets(node_specs=qualified_specs),
                    enabled=self.connections.get(connection_id).enabled,
                    visibility=SourceVisibility(
                        planner=True,
                        mcp_client=True,
                        admin_dashboard=True,
                    ),
                    permissions=SourcePermissions(calls_upstream=True),
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

    def list_sources(self) -> list[dict[str, Any]]:
        """Return every capability source with the names it currently owns."""
        return [
            source.as_inventory().model_dump(mode="json")
            for source in sorted(
                self.capability_sources.values(),
                key=lambda source: source.id,
            )
        ]

    def list_source_summaries(
        self,
        *,
        cursor: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Return compact paged source summaries for progressive discovery."""
        summaries = [
            source.as_status().model_dump(mode="json")
            for source in sorted(
                self.capability_sources.values(),
                key=lambda source: source.id,
            )
        ]
        page = page_items(summaries, cursor=cursor, limit=limit)
        return {
            "sources": list(page.items),
            "next_cursor": page.next_cursor,
            "total": page.total,
        }

    def inspect_source(self, source_id: str) -> dict[str, Any]:
        """Return the full source inventory for one exact source id."""
        try:
            source = self.capability_sources[source_id]
        except KeyError as exc:
            raise KeyError(f"unknown source {source_id!r}") from exc
        return source.as_inventory().model_dump(mode="json")

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
        local_resource = self._local_documentation_resource(qualified_name)
        if local_resource is not None:
            self._record_event(
                make_event(
                    "resource_read_completed",
                    capability_id=qualified_name,
                    payload={"uri": local_resource.uri, "source": "local"},
                )
            )
            return {
                "contents": [
                    {
                        "uri": local_resource.uri,
                        "mimeType": local_resource.mime_type,
                        "text": local_resource.text,
                    }
                ]
            }

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
        local_prompt = self._local_documentation_prompt(qualified_name)
        if local_prompt is not None:
            self._record_event(
                make_event(
                    "prompt_get_completed",
                    capability_id=qualified_name,
                    payload={
                        "argument_keys": sorted((arguments or {}).keys()),
                        "source": "local",
                    },
                )
            )
            return {
                "description": local_prompt.description,
                "messages": [
                    {
                        "role": "user",
                        "content": {
                            "type": "text",
                            "text": local_prompt.text,
                        },
                    }
                ],
            }

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

    def _local_documentation_resource(
        self,
        qualified_name: str,
    ) -> DocumentationResource | None:
        """Return a local docs resource from capability sources by qualified name."""
        for source in self.capability_sources.values():
            resource = source.capabilities.resources.get(qualified_name)
            if isinstance(resource, DocumentationResource):
                return resource
        return None

    def _local_documentation_prompt(
        self,
        qualified_name: str,
    ) -> DocumentationPrompt | None:
        """Return a local docs prompt from capability sources by qualified name."""
        for source in self.capability_sources.values():
            prompt = source.capabilities.prompts.get(qualified_name)
            if isinstance(prompt, DocumentationPrompt):
                return prompt
        return None

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
                executor=self._tool_executor_for(connection),
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
                specs=self.capability_sources[connection_id].capabilities.node_specs,
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

    def compile_plan(
        self,
        plan: RawWorkflowPlan,
        node_name_bindings: dict[str, str] | None = None,
    ) -> Workflow:
        node_defs: dict[str, Any] = {}
        bindings = node_name_bindings or {}
        for step in plan.nodes:
            if not isinstance(step, NodeUse):
                continue
            qualified_name = bindings.get(step.node, step.node)
            spec = self._get_qualified_spec(qualified_name)
            node_defs[qualified_name] = spec.to_node_def()

        nodes = []
        for node in plan.nodes:
            payload = node.model_dump(by_alias=True)
            if isinstance(node, NodeUse):
                payload["node"] = bindings.get(node.node, node.node)
            nodes.append(payload)

        payload = {
            "name": plan.name,
            "input_schema": plan.input_schema,
            "state_schema": plan.state_schema,
            "output_schema": plan.output_schema,
            "output": [binding.model_dump(mode="json") for binding in plan.output],
            "outcomes": plan.outcomes,
            "start": plan.start,
            "node_defs": [node.model_dump() for node in node_defs.values()],
            "nodes": nodes,
            "edges": [edge.model_dump(by_alias=True) for edge in plan.edges],
        }
        return Workflow.model_validate(payload)

    def _prepare_workflow_runtime(
        self,
        plan: RawWorkflowPlan,
        *,
        deployment: WorkflowDeployment | None,
        artifact: WorkflowArtifact | None,
        saved_subgraph_tree: SavedSubgraphTree | None = None,
    ) -> tuple[Workflow, dict[str, Any], dict[str, Any], dict[str, Any]]:
        """Resolve bindings once into the executable pieces core expects.

        Saved-run resume must rebuild prepared dependencies from the current
        in-memory service state. Durable resume will need a stricter snapshot,
        but this keeps the current platform boundary explicit.
        """
        plan_node_names = [
            node.node for node in plan.nodes if isinstance(node, NodeUse)
        ]
        runtime_artifact = artifact or WorkflowArtifact(
            id=plan.name,
            version=1,
            title=plan.name,
            input_schema=plan.input_schema,
            output_schema=plan.output_schema,
            outcomes=("completed",),
            plan=plan.model_dump(mode="json", by_alias=True),
        )
        dependencies = resolve_runtime_dependencies(
            artifact=runtime_artifact,
            deployment=deployment,
            sources=self.capability_sources,
            plan_node_names=plan_node_names,
        )
        prepared_subgraphs = {}
        if saved_subgraph_tree is not None:
            tree = saved_subgraph_tree
            prepared_subgraphs = prepare_saved_subgraphs(
                tree=tree,
                deployment=deployment,
                sources=self.capability_sources,
                compile_plan=self.compile_plan,
            )
        elif artifact is not None and self.artifact_store is not None:
            tree = resolve_saved_subgraph_tree(
                root_artifact=artifact,
                artifact_store=self.artifact_store,
            )
            prepared_subgraphs = prepare_saved_subgraphs(
                tree=tree,
                deployment=deployment,
                sources=self.capability_sources,
                compile_plan=self.compile_plan,
            )
        workflow = self.compile_plan(plan, dependencies.node_name_bindings)
        return (
            workflow,
            dependencies.node_registry,
            dependencies.reducers,
            prepared_subgraphs,
        )

    async def run_workflow_from_plan(
        self,
        plan: RawWorkflowPlan,
        workflow_input: dict[str, Any],
        deployment: WorkflowDeployment | None = None,
        artifact: WorkflowArtifact | None = None,
        saved_subgraph_tree: SavedSubgraphTree | None = None,
    ):
        self._record_event(
            make_event(
                "workflow_run_started",
                workflow_name=plan.name,
                payload={"input_keys": sorted(workflow_input.keys())},
            )
        )
        workflow, registry, reducers, prepared_subgraphs = (
            self._prepare_workflow_runtime(
                plan,
                deployment=deployment,
                artifact=artifact,
                saved_subgraph_tree=saved_subgraph_tree,
            )
        )
        run = await execute_workflow_result_async(
            workflow,
            workflow_input,
            registry,
            reducers=reducers,
            subgraphs=prepared_subgraphs,
        )
        self._record_event(
            make_event(
                "workflow_run_completed",
                workflow_name=plan.name,
                payload={"status": run.status.value},
            )
        )
        return run

    async def resume_workflow_from_plan(
        self,
        plan: RawWorkflowPlan,
        run: RunState,
        *,
        resume_payload: dict[str, Any],
        resume_outcome: str = "submitted",
        deployment: WorkflowDeployment | None = None,
        artifact: WorkflowArtifact | None = None,
        saved_subgraph_tree: SavedSubgraphTree | None = None,
    ) -> RunState:
        """Resume one stopped run using its prepared runtime dependency boundary."""
        workflow, registry, reducers, prepared_subgraphs = (
            self._prepare_workflow_runtime(
                plan,
                deployment=deployment,
                artifact=artifact,
                saved_subgraph_tree=saved_subgraph_tree,
            )
        )
        resumed = await resume_workflow_result_async(
            workflow,
            run,
            registry,
            resume_payload=resume_payload,
            resume_outcome=resume_outcome,
            reducers=reducers,
            subgraphs=prepared_subgraphs,
        )
        self._record_event(
            make_event(
                "workflow_run_resumed",
                workflow_name=plan.name,
                payload={"status": resumed.status.value},
            )
        )
        return resumed

    def list_events(self) -> list[McpEvent]:
        return self.event_bus.list_events()

    def register_capability_source(self, source: CapabilitySource) -> None:
        """Register a capability source as canonical service state."""
        self.capability_sources[source.id] = source

    def _hydrate_connection_source_from_snapshot(
        self,
        connection: ConnectionConfig,
    ) -> None:
        """Register one connection source, hydrating specs from snapshot if present."""
        if connection.id in self.capability_sources:
            return

        snapshot = self.store.load_catalog(connection.id)
        specs = {
            entry.qualified_name: self._spec_from_snapshot_entry(entry)
            for entry in (() if snapshot is None else snapshot.nodes)
        }
        description = (
            f"Specs restored from catalog for {connection.id}."
            if specs
            else f"No catalog loaded for {connection.id}."
        )
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
                description=description,
            )
        )

    def _spec_from_snapshot_entry(
        self,
        entry: CatalogNodeEntry,
    ) -> NodeSpec[Any, Any]:
        """Rebuild an executable tool wrapper from a stored catalog node entry.

        Snapshot entries store schema/name metadata, not Python functions. This
        helper reconstructs the same generated NodeSpec shape and routes calls
        through `_tool_executor_for()`, so hydrated specs use the persistent MCP
        runtime when the service has one configured.
        """
        model_prefix = entry.qualified_name.replace(".", "_").replace("-", "_")
        input_model = _model_from_schema(f"{model_prefix}_Input", entry.input_schema)
        output_schema = entry.output_schema
        output_model = _model_from_schema(f"{model_prefix}_Output", output_schema)

        async def invoke_tool(payload: BaseModel) -> NodeReturn[BaseModel]:
            connection = self.connections.get(entry.connection_id)
            auth = self.load_auth(entry.connection_id)
            result = await self._tool_executor_for(connection).call_tool(
                connection,
                auth,
                entry.local_name,
                payload.model_dump(exclude_unset=True),
            )
            return NodeReturn(
                outcome=result.outcome,
                output=output_model.model_validate(result.output),
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
            output_schema_contract=output_schema,
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
