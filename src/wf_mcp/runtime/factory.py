from __future__ import annotations

import asyncio
from contextlib import AsyncExitStack
from dataclasses import dataclass, field

import httpx
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.streamable_http import streamable_http_client
from mcp.types import CallToolResult

from wf_sources_mcp.auth import AuthRecord, mcp_auth_env, mcp_auth_headers

from ..models import ConnectionConfig
from .session import PersistentMcpSession


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
        owner = _SessionOwner(factory=self, connection=connection, auth=auth)
        await owner.start()
        return PersistentMcpSession(
            connection=connection,
            auth=auth,
            call_callback=owner.call_tool,
            close_callback=owner.close,
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
            auth_env = mcp_auth_env(auth)
            if auth_env:
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
                httpx.AsyncClient(headers=mcp_auth_headers(auth) or None)
            )
            (
                read_stream,
                write_stream,
                _get_session_id,
            ) = await stack.enter_async_context(
                streamable_http_client(
                    connection.metadata["url"],
                    http_client=http_client,
                )
            )
            session = await stack.enter_async_context(
                ClientSession(read_stream, write_stream)
            )
            await session.initialize()
            return session

        raise ValueError(f"unsupported MCP transport {transport!r}")


@dataclass(slots=True)
class _ToolCallRequest:
    """One request submitted to the task that owns the MCP transport."""

    tool_name: str
    payload: dict[str, object]
    result: asyncio.Future[CallToolResult]


@dataclass(slots=True)
class _SessionOwner:
    """Run one MCP client session entirely inside its owning asyncio task.

    MCP SDK transports open AnyIO cancel scopes. Entering a transport in one
    inbound MCP request and reusing it from another causes
    `ClosedResourceError`/cancel-scope ownership failures. This actor keeps
    transport creation, calls, and cleanup in one stable task while the public
    workflow surface submits requests through a queue.
    """

    factory: PersistentSessionFactory
    connection: ConnectionConfig
    auth: AuthRecord | None
    _requests: asyncio.Queue[_ToolCallRequest | None] = field(
        default_factory=asyncio.Queue
    )
    _task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Start the owner task and wait until its MCP session is initialized."""
        ready = asyncio.get_running_loop().create_future()
        self._task = asyncio.create_task(
            self._run(ready),
            name=f"wf-mcp-session:{self.connection.id}",
        )
        await ready

    async def call_tool(
        self,
        tool_name: str,
        payload: dict[str, object],
    ) -> CallToolResult:
        """Submit a call and fail promptly if its transport owner exits."""
        task = self._task
        if task is None:
            raise RuntimeError("persistent MCP session is not started")
        if task.done():
            await task
            raise RuntimeError("persistent MCP session stopped unexpectedly")
        result = asyncio.get_running_loop().create_future()
        await self._requests.put(
            _ToolCallRequest(tool_name=tool_name, payload=payload, result=result)
        )
        done, _pending = await asyncio.wait(
            {result, task}, return_when=asyncio.FIRST_COMPLETED
        )
        if result in done:
            return result.result()
        await task
        raise RuntimeError("persistent MCP session stopped unexpectedly")

    async def close(self) -> None:
        """Ask the owner task to close the MCP transport in its own scope."""
        task = self._task
        if task is None:
            return
        if not task.done():
            await self._requests.put(None)
        await task
        self._task = None

    async def _run(self, ready: asyncio.Future[None]) -> None:
        """Own the complete MCP transport lifecycle and serialized call loop."""
        try:
            async with AsyncExitStack() as stack:
                session = await self.factory._create_with_stack(
                    stack, self.connection, self.auth
                )
                ready.set_result(None)
                while True:
                    request = await self._requests.get()
                    if request is None:
                        return
                    try:
                        response = await session.call_tool(
                            request.tool_name, request.payload
                        )
                    except Exception as exc:
                        request.result.set_exception(exc)
                    else:
                        request.result.set_result(response)
        except BaseException as exc:
            if not ready.done():
                ready.set_exception(exc)
                return
            # Calls already queued behind the failing request cannot otherwise
            # observe that their sole transport owner has exited.
            while not self._requests.empty():
                pending = self._requests.get_nowait()
                if pending is not None and not pending.result.done():
                    pending.result.set_exception(exc)
            raise
