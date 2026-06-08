from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from mcp.client.session import ClientSession
from pydantic import AnyUrl

from wf_sources_mcp.auth import AuthRecord
from wf_sources_mcp.catalog import DiscoveredPrompt, DiscoveredResource, DiscoveredTool
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
RawToolLister = Callable[[], Awaitable[list[DiscoveredTool]]]
RawMetadataGetter = Callable[[], Awaitable[dict[str, Any]]]
RawMethodInvoker = Callable[[str, dict[str, Any] | None], Awaitable[dict[str, Any]]]
RawNotificationSender = Callable[[str, dict[str, Any] | None], Awaitable[None]]


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
    list_tools_callback: RawToolLister | None = None
    get_connection_metadata_callback: RawMetadataGetter | None = None
    invoke_method_callback: RawMethodInvoker | None = None
    send_notification_callback: RawNotificationSender | None = None
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

    async def list_tools(self) -> list[DiscoveredTool]:
        """List MCP tools through the owner task or injected session."""
        if self.list_tools_callback is not None:
            return await self.list_tools_callback()
        if self.client is not None:
            from wf_sources_mcp.sdk.converters import tool_to_discovered

            result = await self.client.list_tools()
            return [tool_to_discovered(tool) for tool in result.tools]
        raise RuntimeError("persistent MCP session has no tools list transport")

    async def get_connection_metadata(self) -> dict[str, Any]:
        """Return connection metadata from callback or local connection info."""
        if self.get_connection_metadata_callback is not None:
            return await self.get_connection_metadata_callback()
        transport = self.connection.transport
        return {
            "server": self.connection.provider,
            "transport": transport.kind if transport is not None else None,
        }

    async def invoke_method(
        self,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Invoke a raw MCP method through the owner task or injected session."""
        if self.invoke_method_callback is not None:
            return await self.invoke_method_callback(method, params)
        if self.client is not None:
            from mcp import ClientResult
            from mcp.types import ClientRequest

            result = await self.client.send_request(
                ClientRequest.model_validate({"method": method, "params": params}),
                ClientResult,
            )
            return result.model_dump(by_alias=True, mode="json", exclude_none=True)
        raise RuntimeError("persistent MCP session has no method invoke transport")

    async def send_notification(
        self,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> None:
        """Send an MCP notification through the owner task or injected session."""
        if self.send_notification_callback is not None:
            await self.send_notification_callback(method, params)
            return
        if self.client is not None:
            from mcp.types import ClientNotification

            await self.client.send_notification(
                ClientNotification.model_validate({"method": method, "params": params})
            )
            return
        raise RuntimeError("persistent MCP session has no notification send transport")

    async def close(self) -> None:
        """Close the transport/session stack owned by the runtime factory."""
        if self.close_callback is not None:
            await self.close_callback()
