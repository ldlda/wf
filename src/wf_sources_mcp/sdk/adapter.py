from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from mcp import ClientResult
from mcp.types import (
    ClientNotification,
    ClientRequest,
    ListPromptsResult,
    ListResourcesResult,
    ListToolsResult,
)
from pydantic import AnyUrl

from wf_sources_mcp.auth import AuthRecord
from wf_sources_mcp.catalog import DiscoveredPrompt, DiscoveredResource, DiscoveredTool
from wf_sources_mcp.client import open_mcp_session
from wf_sources_mcp.connections import McpSourceConnection

from .converters import (
    prompt_to_discovered,
    resource_to_discovered,
    tool_result_to_call_result,
    tool_to_discovered,
)
from .protocols import BackendAdapter, ToolCallResult


class McpSdkAdapter(BackendAdapter):
    """One-shot MCP client adapter for upstream MCP source operations.

    This adapter intentionally opens a fresh SDK session per operation. Stateful
    workflow tool execution is handled by `wf_sources_mcp.runtime`; discovery
    and admin operations use this simpler one-shot path.
    """

    @asynccontextmanager
    async def _session(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
    ):
        async with open_mcp_session(connection, auth) as session:
            yield session

    async def list_tools(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
    ) -> list[DiscoveredTool]:
        async with self._session(connection, auth) as session:
            result: ListToolsResult = await session.list_tools()
            return [tool_to_discovered(tool) for tool in result.tools]

    async def list_resources(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
    ) -> list[DiscoveredResource]:
        async with self._session(connection, auth) as session:
            result: ListResourcesResult = await session.list_resources()
            return [resource_to_discovered(resource) for resource in result.resources]

    async def list_prompts(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
    ) -> list[DiscoveredPrompt]:
        async with self._session(connection, auth) as session:
            result: ListPromptsResult = await session.list_prompts()
            return [prompt_to_discovered(prompt) for prompt in result.prompts]

    async def get_connection_metadata(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
    ) -> dict[str, Any]:
        transport = connection.transport
        return {
            "server": connection.provider,
            "transport": transport.kind if transport is not None else None,
        }

    async def read_resource(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
        uri: str,
    ) -> dict[str, Any]:
        async with self._session(connection, auth) as session:
            result = await session.read_resource(AnyUrl(uri))
            return result.model_dump(by_alias=True, mode="json", exclude_none=True)

    async def get_prompt(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
        prompt_name: str,
        arguments: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        async with self._session(connection, auth) as session:
            result = await session.get_prompt(prompt_name, arguments)
            return result.model_dump(by_alias=True, mode="json", exclude_none=True)

    async def invoke_method(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        async with self._session(connection, auth) as session:
            result = await session.send_request(
                ClientRequest.model_validate({"method": method, "params": params}),
                ClientResult,
            )
            return result.model_dump(by_alias=True, mode="json", exclude_none=True)

    async def send_notification(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> None:
        async with self._session(connection, auth) as session:
            await session.send_notification(
                ClientNotification.model_validate({"method": method, "params": params})
            )

    async def call_tool(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
        tool_name: str,
        payload: dict[str, Any],
    ) -> ToolCallResult:
        async with self._session(connection, auth) as session:
            result = await session.call_tool(tool_name, payload)
            return tool_result_to_call_result(result)


__all__ = ["McpSdkAdapter"]
