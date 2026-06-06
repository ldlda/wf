from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from wf_sources_mcp.catalog import DiscoveredPrompt, DiscoveredResource, DiscoveredTool

from ..auth import AuthRecord
from ..models import ConnectionConfig


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

    async def list_resources(
        self,
        connection: ConnectionConfig,
        auth: AuthRecord | None,
    ) -> list[DiscoveredResource]: ...

    async def list_prompts(
        self,
        connection: ConnectionConfig,
        auth: AuthRecord | None,
    ) -> list[DiscoveredPrompt]: ...

    async def get_connection_metadata(
        self,
        connection: ConnectionConfig,
        auth: AuthRecord | None,
    ) -> dict[str, Any]: ...

    async def read_resource(
        self,
        connection: ConnectionConfig,
        auth: AuthRecord | None,
        uri: str,
    ) -> dict[str, Any]: ...

    async def get_prompt(
        self,
        connection: ConnectionConfig,
        auth: AuthRecord | None,
        prompt_name: str,
        arguments: dict[str, str] | None = None,
    ) -> dict[str, Any]: ...

    async def invoke_method(
        self,
        connection: ConnectionConfig,
        auth: AuthRecord | None,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]: ...

    async def send_notification(
        self,
        connection: ConnectionConfig,
        auth: AuthRecord | None,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> None: ...

    async def call_tool(
        self,
        connection: ConnectionConfig,
        auth: AuthRecord | None,
        tool_name: str,
        payload: dict[str, Any],
    ) -> ToolCallResult: ...
