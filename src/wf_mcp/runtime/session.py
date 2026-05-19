from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from ..models import AuthRecord, ConnectionConfig
from ..sdk import ToolCallResult


@dataclass(slots=True)
class PersistentMcpSession:
    """Long-lived MCP execution handle for one configured connection."""

    connection: ConnectionConfig
    auth: AuthRecord | None
    client: Any
    close_callback: Callable[[], Awaitable[None]] | None = None

    async def call_tool(self, tool_name: str, payload: dict[str, Any]) -> ToolCallResult:
        return await self.client.call_tool(tool_name, payload)

    async def close(self) -> None:
        """Close this runtime without assuming a specific SDK client shape."""
        if self.close_callback is not None:
            await self.close_callback()
            return
        close = getattr(self.client, "close", None)
        if close is None:
            return
        result = close()
        if hasattr(result, "__await__"):
            await result
