from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar

from mcp import McpError
from mcp.types import METHOD_NOT_FOUND

from wf_authoring import NodeSpec
from wf_sources_mcp.catalog import DiscoveredPrompt, DiscoveredResource, DiscoveredTool
from wf_sources_mcp.connections import (
    McpSourceConnection,
    mcp_source_connection_from_connection_config,
)
from wf_sources_mcp.sdk import BackendAdapter, ToolExecutor

from ..auth import AuthRecord
from ..models import ConnectionConfig
from ..shared import root_exception
from ..workflow import wrap_discovered_tool
from .events import McpEvent

_CapabilityT = TypeVar("_CapabilityT")


@dataclass(slots=True)
class DiscoveredConnectionCapabilities:
    tools: list[DiscoveredTool] = field(default_factory=list)
    resources: list[DiscoveredResource] = field(default_factory=list)
    prompts: list[DiscoveredPrompt] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


async def discover_connection_capabilities(
    *,
    connection: ConnectionConfig,
    auth: AuthRecord | None,
    adapter: BackendAdapter,
) -> DiscoveredConnectionCapabilities:
    # Compatibility boundary: broker callers still pass ConnectionConfig. Runtime
    # internals use McpSourceConnection so the session code can move to
    # wf_sources_mcp in a later slice.
    source_connection = mcp_source_connection_from_connection_config(connection)
    tools = await adapter.list_tools(source_connection, auth)
    resources = await _list_optional_capabilities(
        lambda: adapter.list_resources(source_connection, auth)
    )
    prompts = await _list_optional_capabilities(
        lambda: adapter.list_prompts(source_connection, auth)
    )
    metadata = await adapter.get_connection_metadata(source_connection, auth)
    return DiscoveredConnectionCapabilities(
        tools=tools,
        resources=resources,
        prompts=prompts,
        metadata=metadata,
    )


async def _list_optional_capabilities(
    load: Callable[[], Awaitable[list[_CapabilityT]]],
) -> list[_CapabilityT]:
    """Treat unsupported optional MCP capability families as empty lists.

    Some SDK transports raise ``METHOD_NOT_FOUND`` from inside an
    ``ExceptionGroup`` because the request ran through a task group. Resources
    and prompts are optional families, so only that exact root error means "not
    supported"; every other failure still needs to surface.
    """
    try:
        return await load()
    except Exception as exc:
        root = root_exception(exc)
        if isinstance(root, McpError) and root.error.code == METHOD_NOT_FOUND:
            return []
        raise


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
