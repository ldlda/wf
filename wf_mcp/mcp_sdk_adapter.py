from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

import httpx
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.streamable_http import streamable_http_client
from mcp.types import CallToolResult as McpCallToolResult
from mcp.types import ListPromptsResult, ListResourcesResult
from mcp.types import ListToolsResult, Tool as McpTool
from mcp.types import Prompt as McpPrompt
from mcp.types import Resource as McpResource

from .adapters import (
    BackendAdapter,
    DiscoveredPrompt,
    DiscoveredResource,
    DiscoveredTool,
    ToolCallResult,
)
from .models import AuthRecord, ConnectionConfig


def _auth_headers(auth: AuthRecord | None) -> dict[str, str]:
    if auth is None:
        return {}
    headers = dict(auth.payload.get("headers", {}))
    token = auth.payload.get("token")
    if isinstance(token, str) and "Authorization" not in headers:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _tool_to_discovered(tool: McpTool) -> DiscoveredTool:
    output_schema = tool.outputSchema or {
        "type": "object",
        "properties": {"content": {"type": "array"}},
    }
    return DiscoveredTool(
        name=tool.name,
        description=tool.description,
        input_schema=tool.inputSchema,
        output_schema=output_schema,
        outcomes=("ok", "error"),
        metadata=tool.model_dump(by_alias=True),
    )


def _resource_to_discovered(resource: McpResource) -> DiscoveredResource:
    return DiscoveredResource(
        uri=str(resource.uri),
        name=str(resource.uri),
        description=resource.description,
        mime_type=resource.mimeType,
        metadata=resource.model_dump(by_alias=True),
    )


def _prompt_to_discovered(prompt: McpPrompt) -> DiscoveredPrompt:
    arguments = [
        argument.model_dump(by_alias=True) for argument in prompt.arguments or []
    ]
    return DiscoveredPrompt(
        name=prompt.name,
        description=prompt.description,
        arguments=arguments,
        metadata=prompt.model_dump(by_alias=True),
    )


def _tool_result_to_call_result(result: McpCallToolResult) -> ToolCallResult:
    if result.structuredContent is not None:
        output = result.structuredContent
    else:
        output = {
            "content": [item.model_dump(by_alias=True) for item in result.content]
        }
    return ToolCallResult(
        outcome="error" if result.isError else "ok",
        output=output,
        meta=result.meta or {},
    )


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
            return [_tool_to_discovered(tool) for tool in result.tools]

    async def list_resources(
        self,
        connection: ConnectionConfig,
        auth: AuthRecord | None,
    ) -> list[DiscoveredResource]:
        async with self._session(connection, auth) as session:
            result: ListResourcesResult = await session.list_resources()
            return [_resource_to_discovered(resource) for resource in result.resources]

    async def list_prompts(
        self,
        connection: ConnectionConfig,
        auth: AuthRecord | None,
    ) -> list[DiscoveredPrompt]:
        async with self._session(connection, auth) as session:
            result: ListPromptsResult = await session.list_prompts()
            return [_prompt_to_discovered(prompt) for prompt in result.prompts]

    async def get_connection_metadata(
        self,
        connection: ConnectionConfig,
        auth: AuthRecord | None,
    ) -> dict[str, Any]:
        return {
            "server": connection.server,
            "transport": connection.metadata.get("transport", "stdio"),
        }

    async def call_tool(
        self,
        connection: ConnectionConfig,
        auth: AuthRecord | None,
        tool_name: str,
        payload: dict[str, Any],
    ) -> ToolCallResult:
        async with self._session(connection, auth) as session:
            result = await session.call_tool(tool_name, payload)
            return _tool_result_to_call_result(result)
