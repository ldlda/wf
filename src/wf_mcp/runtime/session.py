from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from mcp.client.session import ClientSession

from ..models import AuthRecord, ConnectionConfig
from ..sdk import ToolCallResult
from ..sdk.converters import tool_result_to_call_result


@dataclass(slots=True)
class PersistentMcpSession:
    """Long-lived MCP execution handle for one configured connection."""

    connection: ConnectionConfig
    auth: AuthRecord | None
    client: ClientSession
    close_callback: Callable[[], Awaitable[None]] | None = None

    async def call_tool(self, tool_name: str, payload: dict[str, Any]) -> ToolCallResult:
        result = await self.client.call_tool(tool_name, payload)
        return tool_result_to_call_result(result)

    async def close(self) -> None:
        """Close the transport/session stack owned by the runtime factory."""
        if self.close_callback is not None:
            await self.close_callback()
