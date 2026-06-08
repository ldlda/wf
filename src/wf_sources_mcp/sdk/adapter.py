from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from wf_sources_mcp.auth import AuthRecord
from wf_sources_mcp.catalog import DiscoveredPrompt, DiscoveredResource, DiscoveredTool
from wf_sources_mcp.client import McpSourceClient, open_mcp_session
from wf_sources_mcp.connections import McpSourceConnection

from .protocols import BackendAdapter, ToolCallResult


class McpSdkAdapter(BackendAdapter):
    """One-shot MCP client adapter for upstream MCP source operations.

    This adapter intentionally opens a fresh SDK session per operation. It
    delegates all MCP operation/conversion details to `McpSourceClient` so the
    same operation facade can later be used inside persistent runtime owners.
    """

    @asynccontextmanager
    async def _client(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
    ) -> AsyncIterator[McpSourceClient]:
        async with open_mcp_session(connection, auth) as session:
            yield McpSourceClient(session=session, connection=connection)

    async def list_tools(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
    ) -> list[DiscoveredTool]:
        async with self._client(connection, auth) as client:
            return await client.list_tools()

    async def list_resources(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
    ) -> list[DiscoveredResource]:
        async with self._client(connection, auth) as client:
            return await client.list_resources()

    async def list_prompts(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
    ) -> list[DiscoveredPrompt]:
        async with self._client(connection, auth) as client:
            return await client.list_prompts()

    async def get_connection_metadata(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
    ) -> dict[str, Any]:
        # Metadata is derived from local connection config. Opening an MCP
        # transport here would create an unnecessary session during discovery.
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
        async with self._client(connection, auth) as client:
            return await client.read_resource(uri)

    async def get_prompt(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
        prompt_name: str,
        arguments: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        async with self._client(connection, auth) as client:
            return await client.get_prompt(prompt_name, arguments)

    async def invoke_method(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        async with self._client(connection, auth) as client:
            return await client.invoke_method(method, params)

    async def send_notification(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> None:
        async with self._client(connection, auth) as client:
            await client.send_notification(method, params)

    async def call_tool(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
        tool_name: str,
        payload: dict[str, Any],
    ) -> ToolCallResult:
        async with self._client(connection, auth) as client:
            return await client.call_tool(tool_name, payload)


__all__ = ["McpSdkAdapter"]
