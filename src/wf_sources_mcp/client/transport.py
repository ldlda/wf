"""Shared MCP session opener for one-shot and persistent runtimes."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.streamable_http import streamable_http_client

from wf_api.auth import StoredAuthRecord, auth_record_from_compat
from wf_sources_mcp.auth import AuthRecord, McpAuthBinder
from wf_sources_mcp.connections import McpSourceConnection
from wf_sources_mcp.transports import HttpSourceTransport, StdioSourceTransport


def _as_stored_auth(auth: AuthRecord | StoredAuthRecord | None) -> StoredAuthRecord | None:
    if auth is None or isinstance(auth, StoredAuthRecord):
        return auth
    return auth_record_from_compat(
        id=auth.connection_id,
        scheme=auth.scheme,
        payload=auth.payload,
        metadata={},
    )


@asynccontextmanager
async def open_mcp_session(
    connection: McpSourceConnection,
    auth: AuthRecord | StoredAuthRecord | None,
    *,
    auth_binder: McpAuthBinder | None = None,
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

    binder = auth_binder or McpAuthBinder()
    stored_auth = _as_stored_auth(auth)

    if isinstance(transport, StdioSourceTransport):
        bound = await binder.bind_stdio_auth(stored_auth)
        env = dict(transport.env)
        if bound.env:
            env = {**env, **bound.env}
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
        bound = await binder.bind_http_auth(stored_auth)
        http_client = httpx.AsyncClient(
            headers=bound.headers or None,
            auth=bound.auth,
        )
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
