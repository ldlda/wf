from __future__ import annotations

import asyncio
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from typing import Any, cast

from mcp.client.session import ClientSession
from mcp.types import CallToolResult

from wf_authoring import build_async_registry
from wf_core import RuntimeContext
from wf_mcp.capabilities import DiscoveredTool
from wf_mcp.models import AuthRecord
from wf_mcp.runtime import McpRuntimePool, PersistentMcpSession
from wf_mcp.runtime.factory import PersistentSessionFactory
from wf_mcp.sdk import ToolCallResult
from wf_mcp.workflow import wrap_discovered_tool
from wf_sources_mcp.connections import McpSourceConnection
from wf_sources_mcp.transports import StdioSourceTransport


@dataclass(slots=True)
class FakeStatefulExecutor:
    """Executor fake that exposes why workflow calls need shared MCP runtime."""

    page_open: bool = False
    calls: list[tuple[str, dict[str, Any]]] = field(default_factory=list)

    async def call_tool(
        self,
        connection,
        auth: AuthRecord | None,
        tool_name: str,
        payload: dict[str, Any],
    ) -> ToolCallResult:
        self.calls.append((tool_name, payload))
        if tool_name == "browser_navigate":
            self.page_open = True
            return ToolCallResult(outcome="ok", output={"content": "opened"})
        if tool_name == "browser_snapshot":
            if not self.page_open:
                return ToolCallResult(outcome="error", output={"content": "no page"})
            return ToolCallResult(outcome="ok", output={"content": "snapshot"})
        raise KeyError(tool_name)


@dataclass(slots=True)
class FakeStatefulClient:
    """Session-client fake with the same call shape as MCP SDK ClientSession."""

    page_open: bool = False
    closed: bool = False
    calls: list[tuple[str, dict[str, Any]]] = field(default_factory=list)

    async def call_tool(
        self, tool_name: str, payload: dict[str, Any]
    ) -> CallToolResult:
        self.calls.append((tool_name, payload))
        if tool_name == "browser_navigate":
            self.page_open = True
            return CallToolResult(
                content=[],
                structuredContent={"content": "opened"},
            )
        if tool_name == "browser_snapshot" and self.page_open:
            return CallToolResult(
                content=[],
                structuredContent={"content": "snapshot"},
            )
        return CallToolResult(
            content=[],
            structuredContent={"message": "No open page"},
            isError=True,
        )

    async def close(self) -> None:
        self.closed = True


class OwnerCrash(BaseException):
    """Simulate transport-owner death outside normal per-request exceptions."""


@dataclass(slots=True)
class CrashingClient:
    started: asyncio.Event
    crash: asyncio.Event

    async def call_tool(
        self, tool_name: str, payload: dict[str, object]
    ) -> CallToolResult:
        self.started.set()
        await self.crash.wait()
        raise OwnerCrash("transport owner died")


class CrashingSessionFactory(PersistentSessionFactory):
    def __init__(self, client: CrashingClient) -> None:
        self.client = client

    async def _create_with_stack(
        self,
        stack: AsyncExitStack,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
    ) -> ClientSession:
        return cast(ClientSession, self.client)


def _tool(name: str) -> DiscoveredTool:
    return DiscoveredTool(
        name=name,
        title=None,
        description=None,
        input_schema={"type": "object", "properties": {}},
        output_schema={"type": "object", "properties": {}},
        outcomes=("ok", "error"),
    )


def test_generated_workflow_specs_share_injected_tool_executor() -> None:
    """Generated NodeSpecs use the injected executor, not a baked-in adapter."""

    connection = McpSourceConnection(
        id="playwright.default",
        provider="playwright",
        account="default",
        transport=StdioSourceTransport(command="placeholder"),
    )
    executor = FakeStatefulExecutor()
    navigate = wrap_discovered_tool(
        connection=connection,
        auth=None,
        executor=executor,
        tool=_tool("browser_navigate"),
    )
    snapshot = wrap_discovered_tool(
        connection=connection,
        auth=None,
        executor=executor,
        tool=_tool("browser_snapshot"),
    )
    handlers = build_async_registry(navigate, snapshot)

    async def run_workflow_calls() -> dict[str, Any]:
        await handlers["browser_navigate"](
            {},
            RuntimeContext(current_node_id="navigate"),
        )
        return await handlers["browser_snapshot"](
            {},
            RuntimeContext(current_node_id="snapshot"),
        )

    result = asyncio.run(run_workflow_calls())

    assert result["outcome"] == "ok"
    assert result["output"]["content"] == "snapshot"
    assert executor.calls == [("browser_navigate", {}), ("browser_snapshot", {})]


def test_runtime_pool_reuses_stateful_session_for_same_connection() -> None:
    connection = McpSourceConnection(
        id="playwright.default",
        provider="playwright",
        account="default",
        transport=StdioSourceTransport(command="pnpx"),
    )
    created_clients: list[FakeStatefulClient] = []

    async def factory(
        connection: McpSourceConnection,
        auth: AuthRecord | None,
    ) -> PersistentMcpSession:
        client = FakeStatefulClient()
        created_clients.append(client)
        return PersistentMcpSession(
            connection=connection,
            auth=auth,
            client=cast(ClientSession, client),
            close_callback=client.close,
        )

    async def run_calls() -> ToolCallResult:
        pool = McpRuntimePool(factory)
        await pool.call_tool(connection, None, "browser_navigate", {})
        return await pool.call_tool(connection, None, "browser_snapshot", {})

    result = asyncio.run(run_calls())

    assert result.outcome == "ok"
    assert result.output["content"] == "snapshot"
    assert len(created_clients) == 1


def test_runtime_pool_replaces_session_when_fingerprint_changes() -> None:
    original = McpSourceConnection(
        id="playwright.default",
        provider="playwright",
        account="default",
        transport=StdioSourceTransport(command="pnpx"),
    )
    changed = McpSourceConnection(
        id="playwright.default",
        provider="playwright",
        account="default",
        transport=StdioSourceTransport(command="pnpx-new"),
    )
    created_clients: list[FakeStatefulClient] = []

    def factory(
        connection: McpSourceConnection,
        auth: AuthRecord | None,
    ) -> PersistentMcpSession:
        client = FakeStatefulClient()
        created_clients.append(client)
        return PersistentMcpSession(
            connection=connection,
            auth=auth,
            client=cast(ClientSession, client),
            close_callback=client.close,
        )

    async def run_calls() -> None:
        pool = McpRuntimePool(factory)
        await pool.call_tool(original, None, "browser_navigate", {})
        await pool.call_tool(changed, None, "browser_snapshot", {})

    asyncio.run(run_calls())

    assert len(created_clients) == 2
    assert created_clients[0].closed is True


def test_persistent_session_fails_inflight_and_queued_calls_if_owner_dies() -> None:
    connection = McpSourceConnection(
        id="failing.default",
        provider="failing",
        account="default",
    )

    async def exercise() -> tuple[
        BaseException | ToolCallResult, BaseException | ToolCallResult
    ]:
        started = asyncio.Event()
        crash = asyncio.Event()
        session = await CrashingSessionFactory(
            CrashingClient(started=started, crash=crash)
        ).create(connection, None)
        first = asyncio.create_task(session.call_tool("first", {}))
        await started.wait()
        second = asyncio.create_task(session.call_tool("second", {}))
        await asyncio.sleep(0)
        crash.set()
        return await asyncio.wait_for(
            asyncio.gather(first, second, return_exceptions=True),
            timeout=0.2,
        )

    results = asyncio.run(exercise())

    assert isinstance(results[0], OwnerCrash)
    assert isinstance(results[1], OwnerCrash)
