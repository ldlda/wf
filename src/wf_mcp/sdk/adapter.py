from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

import httpx
from mcp import ClientResult
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.streamable_http import streamable_http_client
from mcp.types import (
    ClientNotification,
    ClientRequest,
    ListPromptsResult,
    ListResourcesResult,
    ListToolsResult,
)
from pydantic import AnyUrl

from ..capabilities import DiscoveredPrompt, DiscoveredResource, DiscoveredTool
from ..models import AuthRecord, ConnectionConfig
from .base import BackendAdapter, ToolCallResult
from .converters import (
    prompt_to_discovered,
    resource_to_discovered,
    tool_result_to_call_result,
    tool_to_discovered,
)


def _auth_headers(auth: AuthRecord | None) -> dict[str, str]:
    if auth is None:
        return {}
    headers = dict(auth.payload.get("headers", {}))
    token = auth.payload.get("token")
    if isinstance(token, str) and "Authorization" not in headers:
        headers["Authorization"] = f"Bearer {token}"
    return headers


class McpSdkAdapter(BackendAdapter):
    @asynccontextmanager
    async def _session(
        self,
        connection: ConnectionConfig,
        auth: AuthRecord | None,
    ):
        transport = connection.metadata.get("transport", "stdio")
        if transport == "stdio":
            command = connection.metadata["command"]
            args = list(connection.metadata.get("args", []))
            env = connection.metadata.get("env")
            cwd = connection.metadata.get("cwd")
            if auth is not None:
                auth_env = auth.payload.get("env")
                if isinstance(auth_env, dict):
                    env = {**(env or {}), **auth_env}
            params = StdioServerParameters(
                command=command,
                args=args,
                env=env,
                cwd=cwd,
            )
            async with stdio_client(params) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    yield session
            return

        if transport == "streamable_http":
            url = connection.metadata["url"]
            headers = _auth_headers(auth)
            http_client = httpx.AsyncClient(headers=headers or None)
            async with http_client:
                async with streamable_http_client(
                    url,
                    http_client=http_client,
                ) as (read_stream, write_stream, _get_session_id):
                    async with ClientSession(read_stream, write_stream) as session:
                        await session.initialize()
                        yield session
            return

        raise ValueError(f"unsupported MCP transport {transport!r}")

    async def list_tools(
        self,
        connection: ConnectionConfig,
        auth: AuthRecord | None,
    ) -> list[DiscoveredTool]:
        async with self._session(connection, auth) as session:
            result: ListToolsResult = await session.list_tools()
            return [tool_to_discovered(tool) for tool in result.tools]

    async def list_resources(
        self,
        connection: ConnectionConfig,
        auth: AuthRecord | None,
    ) -> list[DiscoveredResource]:
        async with self._session(connection, auth) as session:
            result: ListResourcesResult = await session.list_resources()
            return [resource_to_discovered(resource) for resource in result.resources]

    async def list_prompts(
        self,
        connection: ConnectionConfig,
        auth: AuthRecord | None,
    ) -> list[DiscoveredPrompt]:
        async with self._session(connection, auth) as session:
            result: ListPromptsResult = await session.list_prompts()
            return [prompt_to_discovered(prompt) for prompt in result.prompts]

    async def get_connection_metadata(
        self,
        connection: ConnectionConfig,
        auth: AuthRecord | None,
    ) -> dict[str, Any]:
        return {
            "server": connection.server,
            "transport": connection.metadata.get("transport", "stdio"),
        }

    async def read_resource(
        self,
        connection: ConnectionConfig,
        auth: AuthRecord | None,
        uri: str,
    ) -> dict[str, Any]:
        async with self._session(connection, auth) as session:
            result = await session.read_resource(AnyUrl(uri))
            return result.model_dump(by_alias=True, mode="json", exclude_none=True)

    async def get_prompt(
        self,
        connection: ConnectionConfig,
        auth: AuthRecord | None,
        prompt_name: str,
        arguments: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        async with self._session(connection, auth) as session:
            result = await session.get_prompt(prompt_name, arguments)
            return result.model_dump(by_alias=True, mode="json", exclude_none=True)

    async def invoke_method(
        self,
        connection: ConnectionConfig,
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
        connection: ConnectionConfig,
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
        connection: ConnectionConfig,
        auth: AuthRecord | None,
        tool_name: str,
        payload: dict[str, Any],
    ) -> ToolCallResult:
        async with self._session(connection, auth) as session:
            result = await session.call_tool(tool_name, payload)
            return tool_result_to_call_result(result)
