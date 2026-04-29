from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from .models import AuthRecord, ConnectionConfig


@dataclass(slots=True)
class DiscoveredTool:
    name: str
    description: str | None
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    outcomes: tuple[str, ...] = ("ok",)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ToolCallResult:
    outcome: str
    output: dict[str, Any] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)


class BackendAdapter(Protocol):
    async def list_tools(
        self,
        connection: ConnectionConfig,
        auth: AuthRecord | None,
    ) -> list[DiscoveredTool]: ...

    async def call_tool(
        self,
        connection: ConnectionConfig,
        auth: AuthRecord | None,
        tool_name: str,
        payload: dict[str, Any],
    ) -> ToolCallResult: ...
