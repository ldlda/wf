from __future__ import annotations

from typing import Any, cast

import pytest

from wf_authoring import build_async_registry
from wf_core import RuntimeContext
from wf_sources_mcp.auth import AuthRecord
from wf_sources_mcp.catalog import DiscoveredTool
from wf_sources_mcp.connections import McpSourceConnection
from wf_sources_mcp.sdk import ToolCallResult, ToolExecutor
from wf_sources_mcp.tool_wrappers import wrap_discovered_tool
from wf_sources_mcp.transports import StdioSourceTransport


def _connection() -> McpSourceConnection:
    return McpSourceConnection(
        id="everything.default",
        provider="everything",
        account="default",
        transport=StdioSourceTransport(command="placeholder"),
    )


class RecordingExecutor:
    def __init__(self) -> None:
        self.payloads: list[dict[str, Any]] = []

    async def call_tool(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
        tool_name: str,
        payload: dict[str, Any],
    ) -> ToolCallResult:
        self.payloads.append(payload)
        return ToolCallResult(outcome="ok", output={})


class TextContentExecutor:
    async def call_tool(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
        tool_name: str,
        payload: dict[str, Any],
    ) -> ToolCallResult:
        message = payload.get("message", "")
        return ToolCallResult(
            outcome="ok",
            output={
                "content": [
                    {
                        "type": "text",
                        "text": f"Echo: {message}",
                    }
                ],
            },
        )


@pytest.mark.asyncio
async def test_wrap_discovered_tool_omits_unset_optional_arguments() -> None:
    executor = RecordingExecutor()
    spec = wrap_discovered_tool(
        connection=_connection(),
        auth=None,
        executor=cast(ToolExecutor, executor),
        tool=DiscoveredTool(
            name="browser_snapshot",
            title=None,
            description=None,
            input_schema={
                "type": "object",
                "properties": {
                    "target": {"type": "string"},
                    "depth": {"type": "integer"},
                },
            },
            output_schema={"type": "object", "properties": {}},
        ),
    )
    handler = build_async_registry(spec)[spec.name]

    await handler({}, RuntimeContext(current_node_id="snapshot"))
    await handler({"target": "main"}, RuntimeContext(current_node_id="snapshot"))

    assert executor.payloads == [{}, {"target": "main"}]


@pytest.mark.asyncio
async def test_wrap_discovered_tool_preserves_raw_mcp_content_output() -> None:
    spec = wrap_discovered_tool(
        connection=_connection(),
        auth=None,
        executor=cast(ToolExecutor, TextContentExecutor()),
        tool=DiscoveredTool(
            name="echo",
            title="Echo",
            description=None,
            input_schema={
                "type": "object",
                "properties": {"message": {"type": "string"}},
                "required": ["message"],
            },
            output_schema={
                "type": "object",
                "properties": {"content": {"type": "array"}},
            },
        ),
    )
    handler = build_async_registry(spec)[spec.name]

    result = await handler(
        {"message": "hello"},
        RuntimeContext(current_node_id="echo"),
    )

    assert result["outcome"] == "ok"
    assert "text" not in result["output"]
    assert result["output"]["content"][0]["type"] == "text"
    assert result["output"]["content"][0]["text"] == "Echo: hello"


@pytest.mark.asyncio
async def test_wrap_discovered_tool_emits_neutral_tool_events() -> None:
    events = []
    spec = wrap_discovered_tool(
        connection=_connection(),
        auth=None,
        executor=cast(ToolExecutor, TextContentExecutor()),
        tool=DiscoveredTool(
            name="echo",
            title="Echo",
            description=None,
            input_schema={
                "type": "object",
                "properties": {"message": {"type": "string"}},
                "required": ["message"],
            },
            output_schema={
                "type": "object",
                "properties": {"content": {"type": "array"}},
            },
        ),
        emit_event=events.append,
    )
    handler = build_async_registry(spec)[spec.name]

    await handler({"message": "hello"}, RuntimeContext(current_node_id="echo"))

    assert [event.kind for event in events] == [
        "tool_call_started",
        "tool_call_completed",
    ]
    assert events[0].connection_id == "everything.default"
    assert events[0].capability_id == "everything.default.echo"
    assert events[0].payload == {"input": {"message": "hello"}}
    assert events[1].payload["outcome"] == "ok"


def test_wrap_discovered_tool_exports_from_package_root() -> None:
    from wf_sources_mcp import wrap_discovered_tool as root_wrap_discovered_tool
    from wf_sources_mcp.tool_wrappers import wrap_discovered_tool

    assert root_wrap_discovered_tool is wrap_discovered_tool
