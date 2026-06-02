from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from wf_artifacts import (
    DraftWorkspaceStore,
    RunStore,
    WorkflowArtifact,
    WorkflowArtifactCatalogEntry,
    WorkflowArtifactStore,
    WorkflowDeployment,
    artifact_catalog_entry,
)
from wf_authoring import NodeSpec
from wf_core import (
    RunState,
    Workflow,
)
from wf_api.models import RawWorkflowPlan
from wf_platform import (
    CapabilitySource,
)
from ...connections import ConnectionRegistry, parse_connection_id
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
from wf_api.saved_subgraphs import SavedSubgraphTree
from ..admin_capabilities import admin_source
from ..catalog import CombinedCatalog, snapshot_from_specs
from ..discovery import discover_connection_capabilities, specs_from_discovered_tools
from .adapters import require_adapter
from .builtins import builtin_sources
from .source_catalog import SourceCatalogService
from .workflow_runtime import WorkflowRuntimeService


@dataclass(slots=True)
class WfMcpService:
    store: Store
    default_catalog_max_age_seconds: int = 300
    connections: ConnectionRegistry = field(default_factory=ConnectionRegistry)
    adapters: dict[str, BackendAdapter] = field(default_factory=dict)
    event_bus: EventBus = field(default_factory=EventBus)
    include_builtin_specs: bool = True
    artifact_store: WorkflowArtifactStore | None = None
    draft_workspace_store: DraftWorkspaceStore | None = None
    run_store: RunStore | None = None
    tool_executor: ToolExecutor | None = None
    source_catalog: SourceCatalogService = field(init=False)
    workflow_runtime: WorkflowRuntimeService = field(init=False)

    def __post_init__(self) -> None:
        """Install broker-local system specs when enabled.

        Workflow stores are injected by entrypoint/config construction. This service
        must not guess workflow persistence from the MCP catalog/auth store because
        CLI, MCP, and future HTTP frontends may share or swap those stores.
        """
        self.source_catalog = SourceCatalogService(
            store=self.store,
            connection_lookup=self.connections.get,
            connection_list_enabled=self.connections.list_enabled,
            connection_list_all=self.connections.list_all,
            tool_executor_for=self._tool_executor_for,
            load_auth=self.load_auth,
            emit_event=self._record_event,
            default_catalog_max_age_seconds=self.default_catalog_max_age_seconds,
        )
        if self.include_builtin_specs:
            for source in builtin_sources().values():
                self.register_capability_source(source)
        self.register_capability_source(admin_source())
        self.workflow_runtime = WorkflowRuntimeService(
            source_catalog=self.source_catalog,
            artifact_store=self.artifact_store,
            emit_event=self._record_event,
        )

    @property
    def capability_sources(self) -> dict[str, CapabilitySource]:
        """Compatibility view of source catalog state.

        Source ownership is moving into SourceCatalogService. Keep this property
        because workflow APIs and existing tests still consume the service facade.
        """
        return self.source_catalog.capability_sources

    def register_connection(self, connection: ConnectionConfig) -> None:
        parse_connection_id(connection.id)
        if connection.id in RESERVED_CONNECTION_IDS:
            raise ValueError(f"connection id {connection.id!r} is reserved by wf-mcp")
        self.connections.register(connection)
        self.source_catalog.hydrate_connection_source_from_snapshot(connection)
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
                self.source_catalog.hydrate_connection_source_from_snapshot(connection)
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
        self.source_catalog.register_specs(
            connection_id,
            *specs,
            max_age_seconds=max_age_seconds,
            emit_change_events=emit_change_events,
            record_catalog_change_events=lambda source_id, snapshot, reason: (
                self._record_catalog_change_events(
                    source_id,
                    snapshot,
                    reason=reason,
                )
            ),
        )

    def get_catalog(self) -> CombinedCatalog:
        return self.source_catalog.get_catalog()

    def get_planner_catalog(self) -> CombinedCatalog:
        return self.source_catalog.get_planner_catalog()

    def list_sources(self) -> list[dict[str, Any]]:
        return self.source_catalog.list_sources()

    def list_source_summaries(
        self,
        *,
        cursor: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        return self.source_catalog.list_source_summaries(cursor=cursor, limit=limit)

    def inspect_source(self, source_id: str) -> dict[str, Any]:
        return self.source_catalog.inspect_source(source_id)

    def list_available_specs(self) -> list[CatalogNodeEntry]:
        return self.source_catalog.list_available_specs()

    def workflow_artifact_catalog_entry(
        self,
        artifact: WorkflowArtifact,
    ) -> WorkflowArtifactCatalogEntry:
        """Project a saved workflow artifact as a planner catalog entry."""
        return artifact_catalog_entry(artifact)

    def get_connection_snapshot(self, connection_id: str) -> CatalogSnapshot | None:
        return self.source_catalog.get_connection_snapshot(connection_id)

    def connection_statuses(self) -> list[dict[str, Any]]:
        return self.source_catalog.connection_statuses()

    def list_resources(
        self,
        *,
        connection_id: str | None = None,
    ) -> list[CatalogResourceEntry]:
        return self.source_catalog.list_resources(connection_id=connection_id)

    def list_prompts(
        self,
        *,
        connection_id: str | None = None,
    ) -> list[CatalogPromptEntry]:
        return self.source_catalog.list_prompts(connection_id=connection_id)

    def get_resource(self, qualified_name: str) -> CatalogResourceEntry:
        return self.source_catalog.get_resource(qualified_name)

    def get_prompt(self, qualified_name: str) -> CatalogPromptEntry:
        return self.source_catalog.get_prompt(qualified_name)

    async def read_resource(self, qualified_name: str) -> dict[str, Any]:
        local_resource = self.source_catalog.local_documentation_resource(
            qualified_name
        )
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
        local_prompt = self.source_catalog.local_documentation_prompt(qualified_name)
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
        return self.workflow_runtime.compile_plan(plan, node_name_bindings)

    def _prepare_workflow_runtime(
        self,
        plan: RawWorkflowPlan,
        *,
        deployment: WorkflowDeployment | None,
        artifact: WorkflowArtifact | None,
        saved_subgraph_tree: SavedSubgraphTree | None = None,
    ) -> tuple[Workflow, dict[str, Any], dict[str, Any], dict[str, Any]]:
        return self.workflow_runtime.prepare_workflow_runtime(
            plan,
            deployment=deployment,
            artifact=artifact,
            saved_subgraph_tree=saved_subgraph_tree,
        )

    async def run_workflow_from_plan(
        self,
        plan: RawWorkflowPlan,
        workflow_input: dict[str, Any],
        deployment: WorkflowDeployment | None = None,
        artifact: WorkflowArtifact | None = None,
        saved_subgraph_tree: SavedSubgraphTree | None = None,
    ):
        return await self.workflow_runtime.run_workflow_from_plan(
            plan,
            workflow_input,
            deployment=deployment,
            artifact=artifact,
            saved_subgraph_tree=saved_subgraph_tree,
        )

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
        return await self.workflow_runtime.resume_workflow_from_plan(
            plan,
            run,
            resume_payload=resume_payload,
            resume_outcome=resume_outcome,
            deployment=deployment,
            artifact=artifact,
            saved_subgraph_tree=saved_subgraph_tree,
        )

    def list_events(self) -> list[McpEvent]:
        return self.event_bus.list_events()

    def register_capability_source(self, source: CapabilitySource) -> None:
        """Register a capability source as canonical service state."""
        self.capability_sources[source.id] = source

    def _get_qualified_spec(self, qualified_name: str) -> NodeSpec[Any, Any]:
        return self.source_catalog.get_qualified_spec(qualified_name)

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
