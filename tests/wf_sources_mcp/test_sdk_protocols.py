from __future__ import annotations

from dataclasses import is_dataclass
from typing import cast

from wf_sources_mcp.auth import AuthRecord
from wf_sources_mcp.catalog import DiscoveredTool
from wf_sources_mcp.connections import McpSourceConnection
from wf_sources_mcp.sdk import BackendAdapter, ToolCallResult, ToolExecutor
from wf_sources_mcp.transports import StdioSourceTransport


class EchoAdapter:
    async def list_tools(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
    ) -> list[DiscoveredTool]:
        return [
            DiscoveredTool(
                name="echo",
                title=None,
                description="Echo",
                input_schema={"type": "object"},
                output_schema={"type": "object"},
            )
        ]

    async def call_tool(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
        tool_name: str,
        payload: dict[str, object],
    ) -> ToolCallResult:
        return ToolCallResult(outcome="ok", output={"echoed": payload})


def test_tool_call_result_is_slots_dataclass_with_empty_defaults() -> None:
    result = ToolCallResult(outcome="ok")

    assert is_dataclass(result)
    assert result.output == {}
    assert result.meta == {}


async def test_backend_adapter_protocol_can_describe_tool_listing() -> None:
    adapter = cast(BackendAdapter, EchoAdapter())
    tools = await adapter.list_tools(
        McpSourceConnection(
            id="demo.default",
            provider="demo",
            account="default",
            transport=StdioSourceTransport(command="echo"),
        ),
        None,
    )

    assert tools[0].name == "echo"


async def test_tool_executor_protocol_can_describe_tool_calls() -> None:
    executor = cast(ToolExecutor, EchoAdapter())
    result = await executor.call_tool(
        McpSourceConnection(
            id="demo.default",
            provider="demo",
            account="default",
            transport=StdioSourceTransport(command="echo"),
        ),
        None,
        "echo",
        {"message": "hello"},
    )

    assert result.outcome == "ok"
    assert result.output == {"echoed": {"message": "hello"}}


def test_stateful_mcp_runtime_protocol_shape() -> None:
    from wf_sources_mcp.sdk import StatefulMcpRuntime, ToolExecutor

    assert StatefulMcpRuntime.__name__ == "StatefulMcpRuntime"
    assert ToolExecutor.__name__ == "ToolExecutor"


def test_stateful_runtime_protocol_slices_export() -> None:
    from wf_sources_mcp.sdk import (
        PromptRuntime,
        ResourceRuntime,
        StatefulMcpRuntime,
        ToolExecutor,
        ToolRuntime,
    )

    assert ToolRuntime.__name__ == "ToolRuntime"
    assert ResourceRuntime.__name__ == "ResourceRuntime"
    assert PromptRuntime.__name__ == "PromptRuntime"
    assert ToolExecutor.__name__ == "ToolExecutor"
    assert StatefulMcpRuntime.__name__ == "StatefulMcpRuntime"
