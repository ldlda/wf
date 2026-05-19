from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from wf_authoring import build_async_registry
from wf_core import RuntimeContext
from wf_mcp.capabilities import DiscoveredTool
from wf_mcp.models import AuthRecord, ConnectionConfig
from wf_mcp.runtime import McpRuntimePool, PersistentMcpSession
from wf_mcp.sdk import ToolCallResult
from wf_mcp.workflow import wrap_discovered_tool


@dataclass(slots=True)
class FakeStatefulExecutor:
    """Executor fake that exposes why workflow calls need shared MCP runtime."""

    page_open: bool = False
    calls: list[tuple[str, dict[str, Any]]] = field(default_factory=list)

    async def call_tool(
        self,
        connection: ConnectionConfig,
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

    async def call_tool(self, tool_name: str, payload: dict[str, Any]) -> ToolCallResult:
        self.calls.append((tool_name, payload))
        if tool_name == "browser_navigate":
            self.page_open = True
            return ToolCallResult(outcome="ok", output={"content": "opened"})
        if tool_name == "browser_snapshot" and self.page_open:
            return ToolCallResult(outcome="ok", output={"content": "snapshot"})
        return ToolCallResult(outcome="error", output={"message": "No open page"})

    async def close(self) -> None:
        self.closed = True


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

    connection = ConnectionConfig(
        id="playwright.default",
        server="playwright",
        account="default",
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
    connection = ConnectionConfig(
        id="playwright.default",
        server="playwright",
        account="default",
        metadata={
            "transport": "stdio",
            "command": "pnpx",
            "args": ["@playwright/mcp"],
        },
    )
    created_clients: list[FakeStatefulClient] = []

    async def factory(
        connection: ConnectionConfig,
        auth: AuthRecord | None,
    ) -> PersistentMcpSession:
        client = FakeStatefulClient()
        created_clients.append(client)
        return PersistentMcpSession(connection=connection, auth=auth, client=client)

    async def run_calls() -> ToolCallResult:
        pool = McpRuntimePool(factory)
        await pool.call_tool(connection, None, "browser_navigate", {})
        return await pool.call_tool(connection, None, "browser_snapshot", {})

    result = asyncio.run(run_calls())

    assert result.outcome == "ok"
    assert result.output["content"] == "snapshot"
    assert len(created_clients) == 1


def test_runtime_pool_replaces_session_when_fingerprint_changes() -> None:
    original = ConnectionConfig(
        id="playwright.default",
        server="playwright",
        account="default",
        metadata={"transport": "stdio", "command": "pnpx", "args": ["old"]},
    )
    changed = ConnectionConfig(
        id="playwright.default",
        server="playwright",
        account="default",
        metadata={"transport": "stdio", "command": "pnpx", "args": ["new"]},
    )
    created_clients: list[FakeStatefulClient] = []

    def factory(
        connection: ConnectionConfig,
        auth: AuthRecord | None,
    ) -> PersistentMcpSession:
        client = FakeStatefulClient()
        created_clients.append(client)
        return PersistentMcpSession(connection=connection, auth=auth, client=client)

    async def run_calls() -> None:
        pool = McpRuntimePool(factory)
        await pool.call_tool(original, None, "browser_navigate", {})
        await pool.call_tool(changed, None, "browser_snapshot", {})

    asyncio.run(run_calls())

    assert len(created_clients) == 2
    assert created_clients[0].closed is True
