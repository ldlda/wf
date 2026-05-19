from __future__ import annotations

from typing import Any, Protocol

from ..models import AuthRecord, ConnectionConfig
from ..sdk import ToolCallResult


class ToolExecutor(Protocol):
    """Runtime boundary for executing MCP tools from workflow nodes.

    Discovery can stay one-shot, but workflow execution needs this smaller
    protocol so a future persistent runtime pool can replace the current
    adapter without changing generated NodeSpecs.
    """

    async def call_tool(
        self,
        connection: ConnectionConfig,
        auth: AuthRecord | None,
        tool_name: str,
        payload: dict[str, Any],
    ) -> ToolCallResult: ...
