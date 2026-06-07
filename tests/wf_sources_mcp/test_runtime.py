from __future__ import annotations

from contextlib import AsyncExitStack
from typing import Any

import pytest
from mcp.client.session import ClientSession
from mcp.types import CallToolResult, TextContent

from wf_sources_mcp.auth import AuthRecord
from wf_sources_mcp.connections import McpSourceConnection
from wf_sources_mcp.runtime import (
    McpRuntimePool,
    PersistentMcpSession,
    connection_runtime_fingerprint,
)
from wf_sources_mcp.runtime.factory import PersistentSessionFactory
from wf_sources_mcp.transports import StdioSourceTransport


def _connection() -> McpSourceConnection:
    return McpSourceConnection(
        id="demo.personal",
        provider="demo",
        account="personal",
        transport=StdioSourceTransport(command="fake"),
    )


@pytest.mark.asyncio
async def test_persistent_session_call_callback_normalizes_tool_result() -> None:
    async def call_tool(tool_name: str, payload: dict[str, Any]) -> CallToolResult:
        assert tool_name == "echo"
        assert payload == {"text": "hi"}
        return CallToolResult(
            content=[TextContent(type="text", text="ok")],
            structuredContent={"echoed": "hi"},
        )

    session = PersistentMcpSession(
        connection=_connection(),
        auth=AuthRecord(connection_id="demo.personal", scheme="none"),
        call_callback=call_tool,
    )

    result = await session.call_tool("echo", {"text": "hi"})

    assert result.outcome == "ok"
    assert result.output == {"echoed": "hi"}


@pytest.mark.asyncio
async def test_persistent_session_raises_without_transport() -> None:
    session = PersistentMcpSession(connection=_connection(), auth=None)

    with pytest.raises(RuntimeError, match="no tool call transport"):
        await session.call_tool("echo", {})


class _FakeFactory(PersistentSessionFactory):
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.closed = False

    async def _call_tool(
        self, tool_name: str, payload: dict[str, object]
    ) -> CallToolResult:
        self.calls.append((tool_name, payload))
        return CallToolResult(
            content=[TextContent(type="text", text="ok")],
            structuredContent={"echoed": payload["text"]},
        )

    async def _close(self) -> None:
        self.closed = True

    async def _create_with_stack(
        self,
        stack: AsyncExitStack,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
    ) -> ClientSession:
        factory = self

        class _FakeClient:
            async def call_tool(
                self, tool_name: str, payload: dict[str, object]
            ) -> CallToolResult:
                return await factory._call_tool(tool_name, payload)

        return _FakeClient()  # type: ignore[return-value]


@pytest.mark.asyncio
async def test_persistent_session_factory_serializes_tool_calls() -> None:
    factory = _FakeFactory()
    session = await factory.create(_connection(), None)

    first = await session.call_tool("echo", {"text": "one"})
    second = await session.call_tool("echo", {"text": "two"})
    await session.close()

    assert first.output == {"echoed": "one"}
    assert second.output == {"echoed": "two"}
    assert factory.calls == [
        ("echo", {"text": "one"}),
        ("echo", {"text": "two"}),
    ]


@pytest.mark.asyncio
async def test_runtime_pool_reuses_unchanged_connection() -> None:
    created: list[McpSourceConnection] = []

    async def create_session(
        connection: McpSourceConnection, auth: AuthRecord | None
    ) -> PersistentMcpSession:
        created.append(connection)

        async def _call(tool_name: str, payload: dict[str, Any]) -> CallToolResult:
            return CallToolResult(
                content=[TextContent(type="text", text="ok")],
                structuredContent={"echoed": payload["text"]},
            )

        return PersistentMcpSession(
            connection=connection,
            auth=auth,
            call_callback=_call,
        )

    pool = McpRuntimePool(session_factory=create_session)
    connection = _connection()

    await pool.call_tool(connection, None, "echo", {"text": "one"})
    await pool.call_tool(connection, None, "echo", {"text": "two"})

    assert created == [connection]


def test_runtime_fingerprint_changes_when_transport_changes() -> None:
    original = _connection()
    changed = McpSourceConnection(
        id="demo.personal",
        provider="demo",
        account="personal",
        transport=StdioSourceTransport(command="changed"),
    )

    assert connection_runtime_fingerprint(original) != connection_runtime_fingerprint(
        changed
    )
