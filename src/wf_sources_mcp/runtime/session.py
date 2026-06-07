from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from mcp.client.session import ClientSession
from pydantic import AnyUrl

from wf_sources_mcp.auth import AuthRecord
from wf_sources_mcp.connections import McpSourceConnection
from wf_sources_mcp.sdk import ToolCallResult
from wf_sources_mcp.sdk.converters import tool_result_to_call_result

RawToolCaller = Callable[[str, dict[str, Any]], Awaitable[ToolCallResult]]
RawResourceReader = Callable[[str], Awaitable[dict[str, Any]]]


@dataclass(slots=True)
class PersistentMcpSession:
    """Long-lived MCP execution handle for one configured connection.

    Production sessions use `call_callback` because MCP transports are entered
    inside an AnyIO cancel scope and must be called and closed by that same
    owner task. `client` remains available for simple injected/fake sessions in
    tests. `call_tool()` always normalizes SDK results for workflow nodes.

    This runtime intentionally exposes only tool calls for now. Shared
    non-tool operations live on `McpSourceClient`; routing them through the
    owner task is a separate runtime-expansion slice.
    """

    connection: McpSourceConnection
    auth: AuthRecord | None
    client: ClientSession | None = None
    call_callback: RawToolCaller | None = None
    read_resource_callback: RawResourceReader | None = None
    close_callback: Callable[[], Awaitable[None]] | None = None

    async def call_tool(
        self, tool_name: str, payload: dict[str, Any]
    ) -> ToolCallResult:
        if self.call_callback is not None:
            return await self.call_callback(tool_name, payload)
        if self.client is not None:
            result = await self.client.call_tool(tool_name, payload)
            return tool_result_to_call_result(result)
        raise RuntimeError("persistent MCP session has no tool call transport")

    async def read_resource(self, uri: str) -> dict[str, Any]:
        """Read an MCP resource through the owner task or injected session."""
        if self.read_resource_callback is not None:
            return await self.read_resource_callback(uri)
        if self.client is not None:
            result = await self.client.read_resource(AnyUrl(uri))
            return result.model_dump(by_alias=True, mode="json", exclude_none=True)
        raise RuntimeError("persistent MCP session has no resource read transport")

    async def close(self) -> None:
        """Close the transport/session stack owned by the runtime factory."""
        if self.close_callback is not None:
            await self.close_callback()
