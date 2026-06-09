from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

from mcp import ClientResult
from mcp.types import (
    CallToolResult,
    ClientNotification,
    ClientRequest,
    GetPromptResult,
    ListPromptsResult,
    ListResourcesResult,
    ListToolsResult,
    ReadResourceResult,
)
from pydantic import AnyUrl

from wf_sources_mcp.connections import McpSourceConnection

if TYPE_CHECKING:
    from wf_sources_mcp.catalog import (
        DiscoveredPrompt,
        DiscoveredResource,
        DiscoveredTool,
    )
    from wf_sources_mcp.sdk.protocols import ToolCallResult


class McpClientSession(Protocol):
    """Subset of MCP SDK ClientSession operations used by source clients.

    This protocol targets the low-level MCP SDK ``ClientSession`` shape, not
    ``fastmcp.client.Client``. FastMCP exposes higher-level convenience methods
    with different return types; if we use it here later, wrap it in an adapter
    instead of pretending it satisfies this session protocol.
    """

    # ClientSession stuff. we dont even use their Pagination system...
    async def list_tools(self) -> ListToolsResult: ...

    async def list_resources(self) -> ListResourcesResult: ...

    async def list_prompts(self) -> ListPromptsResult: ...

    async def read_resource(self, uri: AnyUrl) -> ReadResourceResult: ...

    async def get_prompt(
        self,
        name: str,
        arguments: dict[str, str] | None = None,
        /,
    ) -> GetPromptResult: ...

    # BaseSession stuff. not even complete signature, thats crazy
    async def send_request(
        self,
        request: ClientRequest,
        result_type: type[ClientResult],
    ) -> ClientResult: ...

    async def send_notification(self, notification: ClientNotification) -> None: ...

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
        /,
    ) -> CallToolResult: ...


if TYPE_CHECKING:
    from mcp.client.session import ClientSession as SdkClientSession

    def _typecheck_sdk_client_session(
        session: SdkClientSession,
    ) -> McpClientSession:
        """Static-only guard: MCP SDK ClientSession must satisfy our subset."""
        return session


@dataclass(slots=True)
class McpSourceClient:
    """Operation facade over an initialized MCP SDK ClientSession.

    This class owns SDK operation calls and conversion to wf_sources_mcp DTOs.
    It does not own transport lifetime. One-shot callers enter it through
    `open_mcp_session`; persistent runtime owners may wrap the session inside
    their owner task in a later slice.
    """

    session: McpClientSession
    connection: McpSourceConnection

    async def list_tools(self) -> list[DiscoveredTool]:
        from wf_sources_mcp.sdk.converters import tool_to_discovered

        result: ListToolsResult = await self.session.list_tools()
        return [tool_to_discovered(tool) for tool in result.tools]

    async def list_resources(self) -> list[DiscoveredResource]:
        from wf_sources_mcp.sdk.converters import resource_to_discovered

        result: ListResourcesResult = await self.session.list_resources()
        return [resource_to_discovered(resource) for resource in result.resources]

    async def list_prompts(self) -> list[DiscoveredPrompt]:
        from wf_sources_mcp.sdk.converters import prompt_to_discovered

        result: ListPromptsResult = await self.session.list_prompts()
        return [prompt_to_discovered(prompt) for prompt in result.prompts]

    async def get_connection_metadata(self) -> dict[str, Any]:
        transport = self.connection.transport
        return {
            "server": self.connection.provider,
            "transport": transport.kind if transport is not None else None,
        }

    async def read_resource(self, uri: str) -> dict[str, Any]:
        result = await self.session.read_resource(AnyUrl(uri))
        return result.model_dump(by_alias=True, mode="json", exclude_none=True)

    async def get_prompt(
        self,
        prompt_name: str,
        arguments: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        result = await self.session.get_prompt(prompt_name, arguments)
        return result.model_dump(by_alias=True, mode="json", exclude_none=True)

    async def invoke_method(
        self,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        result = await self.session.send_request(
            ClientRequest.model_validate({"method": method, "params": params}),
            ClientResult,
        )
        return result.model_dump(by_alias=True, mode="json", exclude_none=True)

    async def send_notification(
        self,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> None:
        await self.session.send_notification(
            ClientNotification.model_validate({"method": method, "params": params})
        )

    async def call_tool(
        self,
        tool_name: str,
        payload: dict[str, Any],
    ) -> ToolCallResult:
        from wf_sources_mcp.sdk.converters import tool_result_to_call_result

        result = await self.session.call_tool(tool_name, payload)
        return tool_result_to_call_result(result)


__all__ = ["McpClientSession", "McpSourceClient"]
