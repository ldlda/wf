from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from mcp.client.session import ClientSession
from pydantic import AnyUrl

from wf_sources_mcp.auth import AuthRecord
from wf_sources_mcp.catalog import DiscoveredPrompt, DiscoveredResource
from wf_sources_mcp.connections import McpSourceConnection
from wf_sources_mcp.sdk import ToolCallResult
from wf_sources_mcp.sdk.converters import tool_result_to_call_result

RawToolCaller = Callable[[str, dict[str, Any]], Awaitable[ToolCallResult]]
RawResourceReader = Callable[[str], Awaitable[dict[str, Any]]]
RawPromptGetter = Callable[
    [str, dict[str, str] | None],
    Awaitable[dict[str, Any]],
]
RawResourceLister = Callable[[], Awaitable[list[DiscoveredResource]]]
RawPromptLister = Callable[[], Awaitable[list[DiscoveredPrompt]]]


@dataclass(slots=True)
class PersistentMcpSession:
    """Long-lived MCP execution handle for one configured connection.

    Production sessions route all MCP operations through the owner-task queue
    for session safety. `client` remains available for simple injected/fake
    sessions in tests. `call_tool()` always normalizes SDK results for workflow
    nodes.
    """

    connection: McpSourceConnection
    auth: AuthRecord | None
    client: ClientSession | None = None
    call_callback: RawToolCaller | None = None
    read_resource_callback: RawResourceReader | None = None
    get_prompt_callback: RawPromptGetter | None = None
    list_resources_callback: RawResourceLister | None = None
    list_prompts_callback: RawPromptLister | None = None
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

    async def get_prompt(
        self,
        prompt_name: str,
        arguments: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Get an MCP prompt through the owner task or injected session."""
        if self.get_prompt_callback is not None:
            return await self.get_prompt_callback(prompt_name, arguments)
        if self.client is not None:
            result = await self.client.get_prompt(prompt_name, arguments)
            return result.model_dump(by_alias=True, mode="json", exclude_none=True)
        raise RuntimeError("persistent MCP session has no prompt transport")

    async def list_resources(self) -> list[DiscoveredResource]:
        """List MCP resources through the owner task or injected session."""
        if self.list_resources_callback is not None:
            return await self.list_resources_callback()
        if self.client is not None:
            from wf_sources_mcp.sdk.converters import resource_to_discovered

            result = await self.client.list_resources()
            return [resource_to_discovered(resource) for resource in result.resources]
        raise RuntimeError("persistent MCP session has no resource list transport")

    async def list_prompts(self) -> list[DiscoveredPrompt]:
        """List MCP prompts through the owner task or injected session."""
        if self.list_prompts_callback is not None:
            return await self.list_prompts_callback()
        if self.client is not None:
            from wf_sources_mcp.sdk.converters import prompt_to_discovered

            result = await self.client.list_prompts()
            return [prompt_to_discovered(prompt) for prompt in result.prompts]
        raise RuntimeError("persistent MCP session has no prompt list transport")

    async def close(self) -> None:
        """Close the transport/session stack owned by the runtime factory."""
        if self.close_callback is not None:
            await self.close_callback()
