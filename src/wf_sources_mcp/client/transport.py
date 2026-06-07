"""Shared MCP session opener for one-shot and persistent runtimes."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.streamable_http import streamable_http_client

from wf_sources_mcp.auth import AuthRecord, mcp_auth_env, mcp_auth_headers
from wf_sources_mcp.connections import McpSourceConnection
from wf_sources_mcp.transports import HttpSourceTransport, StdioSourceTransport


@asynccontextmanager
async def open_mcp_session(
    connection: McpSourceConnection,
    auth: AuthRecord | None,
) -> AsyncIterator[ClientSession]:
    """Open and initialize an MCP client session for the given connection.

    For stdio transports, merges transport env with auth env (auth wins on
    duplicate keys) and passes command, args, env, and cwd to
    StdioServerParameters.

    For HTTP transports, creates an httpx.AsyncClient with auth headers and
    enters streamable_http_client.

    Yields an initialized ClientSession. Caller owns the session lifetime.
    """
    transport = connection.transport
    if transport is None:
        raise ValueError(f"connection {connection.id!r} requires metadata.transport")

    if isinstance(transport, StdioSourceTransport):
        auth_env = mcp_auth_env(auth)
        env = dict(transport.env)
        if auth_env:
            env = {**env, **auth_env}
        params = StdioServerParameters(
            command=transport.command,
            args=list(transport.args),
            env=env,
            cwd=transport.cwd,
        )
        async with stdio_client(params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                yield session
        return

    if isinstance(transport, HttpSourceTransport):
        headers = mcp_auth_headers(auth)
        http_client = httpx.AsyncClient(headers=headers or None)
        async with http_client:
            async with streamable_http_client(
                str(transport.url),
                http_client=http_client,
            ) as (read_stream, write_stream, _get_session_id):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    yield session
        return

    raise ValueError(f"unsupported MCP transport {transport.kind!r}")
