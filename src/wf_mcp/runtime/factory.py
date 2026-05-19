from __future__ import annotations

from contextlib import AsyncExitStack
from dataclasses import dataclass

import httpx
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.streamable_http import streamable_http_client

from ..models import AuthRecord, ConnectionConfig
from .session import PersistentMcpSession


def _auth_headers(auth: AuthRecord | None) -> dict[str, str]:
    if auth is None:
        return {}
    headers = dict(auth.payload.get("headers", {}))
    token = auth.payload.get("token")
    if isinstance(token, str) and "Authorization" not in headers:
        headers["Authorization"] = f"Bearer {token}"
    return headers


@dataclass(slots=True)
class PersistentSessionFactory:
    """Create initialized persistent MCP sessions for configured connections.

    Input connection metadata must describe either stdio transport
    (`command`, optional `args`/`env`/`cwd`) or streamable HTTP transport
    (`url`). The returned session owns its transport stack and closes it through
    the `PersistentMcpSession.close_callback`.
    """

    async def create(
        self,
        connection: ConnectionConfig,
        auth: AuthRecord | None,
    ) -> PersistentMcpSession:
        stack = AsyncExitStack()
        try:
            session = await self._create_with_stack(stack, connection, auth)
        except BaseException:
            await stack.aclose()
            raise
        return PersistentMcpSession(
            connection=connection,
            auth=auth,
            client=session,
            close_callback=stack.aclose,
        )

    async def _create_with_stack(
        self,
        stack: AsyncExitStack,
        connection: ConnectionConfig,
        auth: AuthRecord | None,
    ) -> ClientSession:
        transport = connection.metadata.get("transport", "stdio")
        if transport == "stdio":
            env = connection.metadata.get("env")
            if auth is not None:
                auth_env = auth.payload.get("env")
                if isinstance(auth_env, dict):
                    env = {**(env or {}), **auth_env}
            params = StdioServerParameters(
                command=connection.metadata["command"],
                args=list(connection.metadata.get("args", [])),
                env=env,
                cwd=connection.metadata.get("cwd"),
            )
            read_stream, write_stream = await stack.enter_async_context(
                stdio_client(params)
            )
            session = await stack.enter_async_context(
                ClientSession(read_stream, write_stream)
            )
            await session.initialize()
            return session

        if transport == "streamable_http":
            http_client = await stack.enter_async_context(
                httpx.AsyncClient(headers=_auth_headers(auth) or None)
            )
            read_stream, write_stream, _get_session_id = (
                await stack.enter_async_context(
                    streamable_http_client(
                        connection.metadata["url"],
                        http_client=http_client,
                    )
                )
            )
            session = await stack.enter_async_context(
                ClientSession(read_stream, write_stream)
            )
            await session.initialize()
            return session

        raise ValueError(f"unsupported MCP transport {transport!r}")
