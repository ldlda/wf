from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from mcp.client.session import ClientSession
from mcp.types import CallToolResult

from wf_sources_mcp.sdk import ToolCallResult
from wf_sources_mcp.sdk.converters import tool_result_to_call_result

from ..auth import AuthRecord
from ..models import ConnectionConfig

RawToolCaller = Callable[[str, dict[str, Any]], Awaitable[CallToolResult]]


@dataclass(slots=True)
class PersistentMcpSession:
    """Long-lived MCP execution handle for one configured connection.

    Production sessions use `call_callback` because MCP transports are entered
    inside an AnyIO cancel scope and must be called and closed by that same
    owner task. `client` remains available for simple injected/fake sessions in
    tests. `call_tool()` always normalizes SDK results for workflow nodes.
    """

    connection: ConnectionConfig
    auth: AuthRecord | None
    client: ClientSession | None = None
    call_callback: RawToolCaller | None = None
    close_callback: Callable[[], Awaitable[None]] | None = None

    async def call_tool(
        self, tool_name: str, payload: dict[str, Any]
    ) -> ToolCallResult:
        if self.call_callback is not None:
            result = await self.call_callback(tool_name, payload)
        elif self.client is not None:
            result = await self.client.call_tool(tool_name, payload)
        else:
            raise RuntimeError("persistent MCP session has no tool call transport")
        return tool_result_to_call_result(result)

    async def close(self) -> None:
        """Close the transport/session stack owned by the runtime factory."""
        if self.close_callback is not None:
            await self.close_callback()
