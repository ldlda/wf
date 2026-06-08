from __future__ import annotations

import asyncio
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

import anyio
import httpx
from mcp.client.streamable_http import StreamableHTTPError
from mcp.shared.exceptions import McpError

from wf_artifacts import (
    DependencyDiagnostic,
    DiagnosticSeverity,
    WorkflowArtifact,
    WorkflowDeployment,
)
from wf_mcp.broker.discovery import (
    discover_connection_capabilities,
    specs_from_discovered_tools,
)
from wf_mcp.events import McpEvent, make_event
from wf_mcp.models import ConnectionConfig
from wf_mcp.shared.errors import error_payload
from wf_sources_mcp.auth import AuthRecord, connection_auth_diagnostic
from wf_sources_mcp.catalog import snapshot_from_specs
from wf_sources_mcp.catalog.models import CatalogSnapshot
from wf_sources_mcp.connections import (
    mcp_source_connection_from_connection_config,
)
from wf_sources_mcp.sdk import BackendAdapter, StatefulMcpRuntime, ToolExecutor
from wf_sources_mcp.storage import AuthStore, CatalogStore

from .adapters import require_adapter
from .source_catalog import SourceCatalogService

EventSink = Callable[[McpEvent], None]


@dataclass(slots=True)
class UpstreamTransportService:
    """Own upstream MCP adapter/auth operations for the broker service.

    This is not protocol-neutral. It is the MCP transport implementation used by
    admin calls, discovery, generated workflow NodeSpecs, and live source checks.
    """

    auth_store: AuthStore
    catalog_store: CatalogStore
    event_sink: EventSink
    adapters: dict[str, BackendAdapter] = field(default_factory=dict)
    tool_executor: ToolExecutor | None = None
    stateful_runtime: StatefulMcpRuntime | None = None

    def register_adapter(self, server: str, adapter: BackendAdapter) -> None:
        self.adapters[server] = adapter

    def save_auth(self, record: AuthRecord) -> None:
        self.auth_store.save_auth(record)
        self.event_sink(
            make_event(
                "auth_saved",
                connection_id=record.connection_id,
                payload={"scheme": record.scheme},
            )
        )

    def load_auth(self, connection_id: str) -> AuthRecord | None:
        return self.auth_store.load_auth(connection_id)

    def load_connection_auth(self, connection: ConnectionConfig) -> AuthRecord | None:
        """Resolve auth for a connection, preferring explicit source auth_ref.

        Legacy MCP auth records are keyed by connection id. New source registry
        and neutral config entries carry `auth_ref`; keep both paths until the
        old compatibility surface has no callers.
        """

        # Compatibility boundary: broker callers still pass ConnectionConfig.
        # Check legacy metadata for auth_ref first to avoid requiring transport
        # metadata just for auth resolution.
        auth_ref = connection.metadata.get("auth_ref")
        if isinstance(auth_ref, str):
            return self.load_auth(auth_ref)
        return self.load_auth(connection.id)

    def tool_executor_for(self, connection: ConnectionConfig) -> ToolExecutor:
        """Return the executor used by generated workflow NodeSpecs.

        Discovery uses short-lived adapters. Generated workflow nodes use this
        hook so config-built services can swap in a persistent runtime pool for
        stateful MCP servers.
        """
        if self.tool_executor is not None:
            return self.tool_executor
        return require_adapter(connection, self.adapters)

    async def read_resource(
        self,
        connection: ConnectionConfig,
        qualified_name: str,
        uri: str,
    ) -> dict[str, Any]:
        auth = self.load_connection_auth(connection)
        # Compatibility boundary: broker callers still pass ConnectionConfig.
        source_connection = mcp_source_connection_from_connection_config(connection)
        self.event_sink(
            make_event(
                "resource_read_started",
                connection_id=connection.id,
                capability_id=qualified_name,
                payload={"uri": uri},
            )
        )
        if self.stateful_runtime is not None:
            result = await self.stateful_runtime.read_resource(
                source_connection,
                auth,
                uri,
            )
        else:
            adapter = require_adapter(connection, self.adapters)
            result = await adapter.read_resource(source_connection, auth, uri)
        self.event_sink(
            make_event(
                "resource_read_completed",
                connection_id=connection.id,
                capability_id=qualified_name,
                payload={"uri": uri},
            )
        )
        return result

    async def render_prompt(
        self,
        connection: ConnectionConfig,
        qualified_name: str,
        local_name: str,
        arguments: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        auth = self.load_connection_auth(connection)
        # Compatibility boundary: broker callers still pass ConnectionConfig.
        source_connection = mcp_source_connection_from_connection_config(connection)
        self.event_sink(
            make_event(
                "prompt_get_started",
                connection_id=connection.id,
                capability_id=qualified_name,
                payload={"argument_keys": sorted((arguments or {}).keys())},
            )
        )
        if self.stateful_runtime is not None:
            result = await self.stateful_runtime.get_prompt(
                source_connection,
                auth,
                local_name,
                arguments,
            )
        else:
            adapter = require_adapter(connection, self.adapters)
            result = await adapter.get_prompt(source_connection, auth, local_name, arguments)
        self.event_sink(
            make_event(
                "prompt_get_completed",
                connection_id=connection.id,
                capability_id=qualified_name,
                payload={"argument_keys": sorted((arguments or {}).keys())},
            )
        )
        return result

    async def invoke_method(
        self,
        connection: ConnectionConfig,
        method: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        adapter = require_adapter(connection, self.adapters)
        auth = self.load_connection_auth(connection)
        # Compatibility boundary: broker callers still pass ConnectionConfig.
        source_connection = mcp_source_connection_from_connection_config(connection)
        self.event_sink(
            make_event(
                "raw_method_started",
                connection_id=connection.id,
                capability_id=method,
                payload={"params": params or {}},
            )
        )
        result = await adapter.invoke_method(source_connection, auth, method, params)
        self.event_sink(
            make_event(
                "raw_method_completed",
                connection_id=connection.id,
                capability_id=method,
                payload={"result_keys": sorted(result.keys())},
            )
        )
        return result

    async def send_notification(
        self,
        connection: ConnectionConfig,
        method: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> None:
        adapter = require_adapter(connection, self.adapters)
        auth = self.load_connection_auth(connection)
        # Compatibility boundary: broker callers still pass ConnectionConfig.
        source_connection = mcp_source_connection_from_connection_config(connection)
        self.event_sink(
            make_event(
                "raw_notification_started",
                connection_id=connection.id,
                capability_id=method,
                payload={"params": params or {}},
            )
        )
        await adapter.send_notification(source_connection, auth, method, params)
        self.event_sink(
            make_event(
                "raw_notification_completed",
                connection_id=connection.id,
                capability_id=method,
                payload={},
            )
        )

    async def refresh_connection_catalog(
        self,
        connection: ConnectionConfig,
        *,
        source_catalog: SourceCatalogService,
        max_age_seconds: int | None = None,
        default_catalog_max_age_seconds: int = 300,
        record_catalog_change_events: Callable[[str, CatalogSnapshot, str], None],
    ) -> None:
        auth = self.load_connection_auth(connection)
        self.event_sink(
            make_event(
                "catalog_refresh_started",
                connection_id=connection.id,
                payload={"server": connection.server},
            )
        )
        try:
            adapter = require_adapter(connection, self.adapters)
            capabilities = await discover_connection_capabilities(
                connection=connection,
                auth=auth,
                adapter=adapter,
            )
            specs = specs_from_discovered_tools(
                connection=connection,
                auth=auth,
                executor=self.tool_executor_for(connection),
                tools=capabilities.tools,
                emit_event=self.event_sink,
            )
            source_catalog.register_specs(
                connection.id,
                *specs,
                max_age_seconds=max_age_seconds,
                emit_change_events=False,
            )
            snapshot = snapshot_from_specs(
                connection.id,
                specs=source_catalog.capability_sources[
                    connection.id
                ].capabilities.node_specs,
                tool_display_names={
                    tool.name: tool.title for tool in capabilities.tools
                },
                resources=capabilities.resources,
                prompts=capabilities.prompts,
                metadata=capabilities.metadata,
                fetched_at_epoch_ms=int(time.time() * 1000),
                max_age_seconds=max_age_seconds or default_catalog_max_age_seconds,
            )
            self.catalog_store.save_catalog(snapshot)
            record_catalog_change_events(connection.id, snapshot, "catalog_refresh")
            self.event_sink(
                make_event(
                    "catalog_refresh_completed",
                    connection_id=connection.id,
                    payload={
                        "node_count": len(snapshot.nodes),
                        "resource_count": len(snapshot.resources),
                        "prompt_count": len(snapshot.prompts),
                    },
                )
            )
        except Exception as exc:
            self.event_sink(
                make_event(
                    "catalog_refresh_failed",
                    connection_id=connection.id,
                    payload=error_payload(exc),
                )
            )
            raise

    async def deployment_diagnostics(
        self,
        *,
        deployment: WorkflowDeployment,
        artifacts: Sequence[WorkflowArtifact],
        source_catalog: SourceCatalogService,
    ) -> list[DependencyDiagnostic]:
        """Return opt-in diagnostics for bound upstream sources that cannot answer.

        Static deployment validation only checks the last known source catalog.
        This probe intentionally performs live upstream I/O, so MCP tools keep it
        disabled by default and only run it when the caller asks for liveness.
        """
        diagnostics: list[DependencyDiagnostic] = []
        for source_id, logical_ref in _required_live_sources(
            deployment, artifacts
        ).items():
            source = source_catalog.capability_sources.get(source_id)
            if (
                source is None
                or not source.enabled
                or not source.permissions.calls_upstream
            ):
                continue
            try:
                connection = source_catalog.connection_lookup(source_id)
            except KeyError as exc:
                diagnostics.append(
                    _source_unreachable_diagnostic(
                        logical_ref=logical_ref,
                        source_id=source_id,
                        exc=exc,
                    )
                )
                continue
            # Compatibility boundary: broker callers still pass ConnectionConfig.
            source_connection = mcp_source_connection_from_connection_config(connection)
            auth_diagnostic = connection_auth_diagnostic(
                source_connection,
                # The diagnostic helper passes the explicit auth_ref to this
                # loader, matching load_connection_auth's auth_ref-first path.
                load_auth_ref=self.load_auth,
                logical_ref=logical_ref,
            )
            if auth_diagnostic is not None:
                diagnostics.append(auth_diagnostic)
                continue
            try:
                adapter = require_adapter(connection, self.adapters)
                auth = self.load_connection_auth(connection)
                await asyncio.wait_for(
                    adapter.list_tools(source_connection, auth),
                    timeout=LIVE_SOURCE_CHECK_TIMEOUT_SECONDS,
                )
            except _LIVE_SOURCE_CHECK_FAILURES as exc:
                diagnostics.append(
                    _source_unreachable_diagnostic(
                        logical_ref=logical_ref,
                        source_id=source_id,
                        exc=exc,
                    )
                )
        return diagnostics


LIVE_SOURCE_CHECK_TIMEOUT_SECONDS = 8.0
_LIVE_SOURCE_CHECK_FAILURES = (
    TimeoutError,
    OSError,
    anyio.ClosedResourceError,
    anyio.EndOfStream,
    anyio.BrokenResourceError,
    httpx.HTTPError,
    McpError,
    StreamableHTTPError,
)


def _required_live_sources(
    deployment: WorkflowDeployment,
    artifacts: Sequence[WorkflowArtifact],
) -> dict[str, str]:
    """Return concrete upstream source ids to live-check, with one logical ref."""
    bindings = deployment.binding_map()
    required: dict[str, str] = {}
    for artifact in artifacts:
        for logical_ref, capability in artifact.required_capability_map().items():
            source_id = bindings.get(capability.logical_source)
            if source_id is not None:
                required.setdefault(source_id, logical_ref)
    return required


def _source_unreachable_diagnostic(
    *,
    logical_ref: str,
    source_id: str,
    exc: BaseException,
) -> DependencyDiagnostic:
    """Build a liveness diagnostic without catching unrelated probe bugs."""
    return DependencyDiagnostic(
        severity=DiagnosticSeverity.ERROR,
        code="source_unreachable",
        logical_ref=logical_ref,
        bound_source=source_id,
        message=(
            f"Live check for upstream source {source_id!r} failed: "
            f"{type(exc).__name__}: {exc}"
        ),
        repair_hint=(
            "Start or reconnect the source, fix its transport/auth "
            "configuration, or bind this deployment to another source."
        ),
    )
