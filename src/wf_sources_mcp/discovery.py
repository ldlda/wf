from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar

from mcp import McpError
from mcp.types import METHOD_NOT_FOUND

from wf_authoring import NodeSpec
from wf_sources_mcp.auth import AuthRecord
from wf_sources_mcp.catalog import DiscoveredPrompt, DiscoveredResource, DiscoveredTool
from wf_sources_mcp.connections import McpSourceConnection
from wf_sources_mcp.sdk import BackendAdapter, ToolExecutor
from wf_sources_mcp.tool_events import ToolWrapperEventSink
from wf_sources_mcp.tool_wrappers import wrap_discovered_tool

_CapabilityT = TypeVar("_CapabilityT")


@dataclass(slots=True)
class DiscoveredConnectionCapabilities:
    tools: list[DiscoveredTool] = field(default_factory=list)
    resources: list[DiscoveredResource] = field(default_factory=list)
    prompts: list[DiscoveredPrompt] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


async def discover_connection_capabilities(
    *,
    connection: McpSourceConnection,
    auth: AuthRecord | None,
    adapter: BackendAdapter,
) -> DiscoveredConnectionCapabilities:
    tools = await adapter.list_tools(connection, auth)
    resources = await _list_optional_capabilities(
        lambda: adapter.list_resources(connection, auth)
    )
    prompts = await _list_optional_capabilities(
        lambda: adapter.list_prompts(connection, auth)
    )
    metadata = await adapter.get_connection_metadata(connection, auth)
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
        root = _root_exception(exc)
        if isinstance(root, McpError) and root.error.code == METHOD_NOT_FOUND:
            return []
        raise


def _root_exception(exc: BaseException) -> BaseException:
    """Unwrap the first nested exception from MCP task-group ExceptionGroups."""
    current: BaseException = exc
    while isinstance(current, ExceptionGroup) and current.exceptions:
        current = current.exceptions[0]
    return current


def specs_from_discovered_tools(
    *,
    connection: McpSourceConnection,
    auth: AuthRecord | None,
    executor: ToolExecutor,
    tools: list[DiscoveredTool],
    emit_event: ToolWrapperEventSink | None = None,
) -> list[NodeSpec[Any, Any]]:
    return [
        wrap_discovered_tool(
            connection=connection,
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
