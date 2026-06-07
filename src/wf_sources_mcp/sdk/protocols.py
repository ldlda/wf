"""Protocol/result contracts for MCP upstream source providers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from wf_sources_mcp.auth import AuthRecord
from wf_sources_mcp.catalog import DiscoveredPrompt, DiscoveredResource, DiscoveredTool
from wf_sources_mcp.connections import McpSourceConnection


@dataclass(slots=True)
class ToolCallResult:
    outcome: str
    output: dict[str, Any] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)


class BackendAdapter(Protocol):
    async def list_tools(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
    ) -> list[DiscoveredTool]: ...

    async def list_resources(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
    ) -> list[DiscoveredResource]: ...

    async def list_prompts(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
    ) -> list[DiscoveredPrompt]: ...

    async def get_connection_metadata(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
    ) -> dict[str, Any]: ...

    async def read_resource(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
        uri: str,
    ) -> dict[str, Any]: ...

    async def get_prompt(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
        prompt_name: str,
        arguments: dict[str, str] | None = None,
    ) -> dict[str, Any]: ...

    async def invoke_method(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]: ...

    async def send_notification(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> None: ...

    async def call_tool(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
        tool_name: str,
        payload: dict[str, Any],
    ) -> ToolCallResult: ...


class ToolExecutor(Protocol):
    """Runtime boundary for executing MCP tools from workflow nodes.

    Discovery can stay one-shot, but workflow execution needs this smaller
    protocol so persistent runtime pools can replace one-shot adapters without
    changing generated NodeSpecs.
    """

    async def call_tool(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
        tool_name: str,
        payload: dict[str, Any],
    ) -> ToolCallResult: ...


class StatefulMcpRuntime(ToolExecutor, Protocol):
    """Stateful execution/read boundary for configured MCP sources.

    Implementations keep source session state across calls. Discovery/catalog
    refresh may still use one-shot adapters by policy.
    """

    async def read_resource(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
        uri: str,
    ) -> dict[str, Any]: ...

    async def get_prompt(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
        prompt_name: str,
        arguments: dict[str, str] | None = None,
    ) -> dict[str, Any]: ...


__all__ = [
    "BackendAdapter",
    "StatefulMcpRuntime",
    "ToolCallResult",
    "ToolExecutor",
]
