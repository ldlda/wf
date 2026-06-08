from __future__ import annotations

from collections.abc import Callable
from typing import Any

from wf_authoring import NodeSpec
from wf_sources_mcp.catalog import DiscoveredTool
from wf_sources_mcp.connections import mcp_source_connection_from_connection_config
from wf_sources_mcp.discovery import (
    DiscoveredConnectionCapabilities,
    discover_connection_capabilities,
)
from wf_sources_mcp.discovery import (
    specs_from_discovered_tools as source_specs_from_discovered_tools,
)
from wf_sources_mcp.sdk import ToolExecutor
from wf_sources_mcp.tool_events import ToolWrapperEvent

from ..auth import AuthRecord
from ..models import ConnectionConfig
from .events import McpEvent, make_event


def _project_tool_wrapper_event(event: ToolWrapperEvent) -> McpEvent:
    return make_event(
        event.kind,
        connection_id=event.connection_id,
        capability_id=event.capability_id,
        payload=event.payload,
    )


def specs_from_discovered_tools(
    *,
    connection: ConnectionConfig,
    auth: AuthRecord | None,
    executor: ToolExecutor,
    tools: list[DiscoveredTool],
    emit_event: Callable[[McpEvent], None] | None = None,
) -> list[NodeSpec[Any, Any]]:
    # Compatibility boundary: broker callers still pass ConnectionConfig. Runtime
    # internals use McpSourceConnection so the session code can move to
    # wf_sources_mcp in a later slice.
    source_connection = mcp_source_connection_from_connection_config(connection)

    def emit_tool_event(event: ToolWrapperEvent) -> None:
        if emit_event is not None:
            emit_event(_project_tool_wrapper_event(event))

    return source_specs_from_discovered_tools(
        connection=source_connection,
        auth=auth,
        executor=executor,
        tools=tools,
        emit_event=emit_tool_event if emit_event is not None else None,
    )


__all__ = [
    "DiscoveredConnectionCapabilities",
    "discover_connection_capabilities",
    "specs_from_discovered_tools",
]
