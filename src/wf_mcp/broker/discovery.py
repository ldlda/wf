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
from wf_sources_mcp.sdk import ToolExecutor

from ..auth import AuthRecord
from ..models import ConnectionConfig
from ..workflow import wrap_discovered_tool
from .events import McpEvent


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
    return [
        wrap_discovered_tool(
            connection=source_connection,
            auth=auth,
            executor=executor,
            tool=tool,
            emit_event=emit_event,
        )
        for tool in tools
    ]


__all__ = [
    "DiscoveredConnectionCapabilities",
    "discover_connection_capabilities",
    "specs_from_discovered_tools",
]
