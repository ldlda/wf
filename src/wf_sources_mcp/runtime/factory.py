from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from itertools import count
from typing import Any, Generic, TypeVar

from mcp.client.session import ClientSession

from wf_sources_mcp.auth import AuthRecord
from wf_sources_mcp.client import McpSourceClient, open_mcp_session
from wf_sources_mcp.connections import McpSourceConnection
from wf_sources_mcp.sdk import ToolCallResult

from .session import PersistentMcpSession

T = TypeVar("T")
ClientOperation = Callable[[McpSourceClient], Awaitable[T]]


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
        connection: McpSourceConnection,
        auth: AuthRecord | None,
    ) -> PersistentMcpSession:
        owner = _SessionOwner(factory=self, connection=connection, auth=auth)
        await owner.start()
        return PersistentMcpSession(
            connection=connection,
            auth=auth,
            call_callback=owner.call_tool,
            read_resource_callback=owner.read_resource,
            close_callback=owner.close,
        )

    async def _create_with_stack(
        self,
        stack: AsyncExitStack,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
    ) -> ClientSession:
        session = await stack.enter_async_context(open_mcp_session(connection, auth))
        return session


@dataclass(slots=True)
class _ClientOperationRequest(Generic[T]):
    """One explicit operation submitted to the MCP transport owner task.

    `operation` is metadata for diagnostics/tracing only. Execution uses `run`;
    do not dispatch with `getattr(client, operation)`.
    """

    operation: str
    connection_id: str
    sequence: int
    submitted_at: float
    run: ClientOperation[T]
    result: asyncio.Future[T]


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
    connection: McpSourceConnection
    auth: AuthRecord | None
    _requests: asyncio.Queue[_ClientOperationRequest[Any] | None] = field(
        default_factory=asyncio.Queue
    )
    _sequence: count = field(default_factory=lambda: count(1))
    _task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Start the owner task and wait until its MCP session is initialized."""
        ready = asyncio.get_running_loop().create_future()
        self._task = asyncio.create_task(
            self._run(ready),
            name=f"wf-mcp-session:{self.connection.id}",
        )
        await ready

    async def submit(
        self,
        operation: str,
        run: ClientOperation[T],
    ) -> T:
        """Submit an explicit client operation to the MCP owner task."""
        task = self._task
        if task is None:
            raise RuntimeError("persistent MCP session is not started")
        if task.done():
            await task
            raise RuntimeError("persistent MCP session stopped unexpectedly")

        result: asyncio.Future[T] = asyncio.get_running_loop().create_future()
        await self._requests.put(
            _ClientOperationRequest(
                operation=operation,
                connection_id=self.connection.id,
                sequence=next(self._sequence),
                submitted_at=time.monotonic(),
                run=run,
                result=result,
            )
        )
        done, _pending = await asyncio.wait(
            {result, task}, return_when=asyncio.FIRST_COMPLETED
        )
        if result in done:
            return result.result()
        await task
        raise RuntimeError("persistent MCP session stopped unexpectedly")

    async def call_tool(
        self,
        tool_name: str,
        payload: dict[str, object],
    ) -> ToolCallResult:
        """Submit a tool call through the generic owner-task operation queue."""
        return await self.submit(
            operation="call_tool",
            run=lambda client: client.call_tool(tool_name, payload),
        )

    async def read_resource(self, uri: str) -> dict[str, Any]:
        """Submit a resource read through the generic owner-task operation queue."""
        return await self.submit(
            operation="read_resource",
            run=lambda client: client.read_resource(uri),
        )

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
                client = McpSourceClient(session=session, connection=self.connection)
                ready.set_result(None)
                while True:
                    request = await self._requests.get()
                    if request is None:
                        return
                    try:
                        response = await request.run(client)
                    except Exception as exc:
                        request.result.set_exception(exc)
                    else:
                        request.result.set_result(response)
        except BaseException as exc:
            if not ready.done():
                ready.set_exception(exc)
                return
            while not self._requests.empty():
                pending = self._requests.get_nowait()
                if pending is not None and not pending.result.done():
                    pending.result.set_exception(exc)
            raise
