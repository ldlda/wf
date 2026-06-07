from __future__ import annotations

import asyncio
from typing import Any, cast

from wf_authoring import build_async_registry
from wf_core import RuntimeContext
from wf_mcp.capabilities import DiscoveredTool
from wf_mcp.models import AuthRecord, ConnectionConfig
from wf_mcp.runtime import ToolExecutor
from wf_mcp.sdk import ToolCallResult
from wf_mcp.workflow import wrap_discovered_tool
from wf_sources_mcp.connections import McpSourceConnection
from wf_sources_mcp.transports import StdioSourceTransport


class RecordingAdapter:
    """Tiny adapter fake that records exactly what MCP payload would be sent."""

    def __init__(self) -> None:
        self.payloads: list[dict[str, Any]] = []

    async def call_tool(
        self,
        connection: ConnectionConfig,
        auth: AuthRecord | None,
        tool_name: str,
        payload: dict[str, Any],
    ) -> ToolCallResult:
        self.payloads.append(payload)
        return ToolCallResult(outcome="ok", output={})


class TextContentAdapter:
    async def call_tool(
        self,
        connection: ConnectionConfig,
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


def test_discovered_tool_wrapper_omits_unset_optional_arguments() -> None:
    adapter = RecordingAdapter()
    spec = wrap_discovered_tool(
        connection=McpSourceConnection(
            id="playwright.default",
            provider="playwright",
            account="default",
            transport=StdioSourceTransport(command="placeholder"),
        ),
        auth=None,
        executor=cast(ToolExecutor, adapter),
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

    async def run_calls() -> None:
        await handler({}, RuntimeContext(current_node_id="snapshot"))
        await handler(
            {"target": "main"},
            RuntimeContext(current_node_id="snapshot"),
        )

    asyncio.run(run_calls())

    assert adapter.payloads[0] == {}
    assert adapter.payloads[1] == {"target": "main"}


def test_discovered_tool_wrapper_preserves_raw_mcp_content_output() -> None:
    spec = wrap_discovered_tool(
        connection=McpSourceConnection(
            id="everything.default",
            provider="everything",
            account="default",
            transport=StdioSourceTransport(command="placeholder"),
        ),
        auth=None,
        executor=cast(ToolExecutor, TextContentAdapter()),
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

    async def run_call() -> dict[str, Any]:
        return await handler(
            {"message": "hello"},
            RuntimeContext(current_node_id="echo"),
        )

    result = asyncio.run(run_call())

    assert result["outcome"] == "ok"
    assert "text" not in result["output"]
    assert result["output"]["content"][0]["type"] == "text"
    assert result["output"]["content"][0]["text"] == "Echo: hello"
