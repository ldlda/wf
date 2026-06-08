from __future__ import annotations

from dataclasses import is_dataclass
from typing import cast

from wf_sources_mcp.auth import AuthRecord
from wf_sources_mcp.catalog import DiscoveredPrompt, DiscoveredResource, DiscoveredTool
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


class _FullSurfaceAdapter:
    """Implements every MCP operation for protocol conformance tests."""

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

    async def list_resources(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
    ) -> list[DiscoveredResource]:
        return []

    async def list_prompts(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
    ) -> list[DiscoveredPrompt]:
        return []

    async def get_connection_metadata(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
    ) -> dict[str, object]:
        return {"server": "demo"}

    async def read_resource(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
        uri: str,
    ) -> dict[str, object]:
        return {"contents": []}

    async def get_prompt(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
        prompt_name: str,
        arguments: dict[str, str] | None = None,
    ) -> dict[str, object]:
        return {"messages": []}

    async def invoke_method(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
        method: str,
        params: dict[str, object] | None = None,
    ) -> dict[str, object]:
        return {}

    async def send_notification(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
        method: str,
        params: dict[str, object] | None = None,
    ) -> None:
        return None

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


async def test_backend_adapter_protocol_full_operation_surface() -> None:
    adapter = cast(BackendAdapter, _FullSurfaceAdapter())
    conn = McpSourceConnection(
        id="demo.default",
        provider="demo",
        account="default",
        transport=StdioSourceTransport(command="echo"),
    )

    tools = await adapter.list_tools(conn, None)
    resources = await adapter.list_resources(conn, None)
    prompts = await adapter.list_prompts(conn, None)
    metadata = await adapter.get_connection_metadata(conn, None)
    read_result = await adapter.read_resource(conn, None, "test://x")
    prompt_result = await adapter.get_prompt(conn, None, "prompt.summarize")
    invoke_result = await adapter.invoke_method(conn, None, "ping")
    await adapter.send_notification(conn, None, "test.notify")
    call_result = await adapter.call_tool(conn, None, "echo", {"text": "hi"})

    assert tools[0].name == "echo"
    assert resources == []
    assert prompts == []
    assert metadata["server"] == "demo"
    assert read_result == {"contents": []}
    assert prompt_result == {"messages": []}
    assert invoke_result == {}
    assert call_result.outcome == "ok"


async def test_stateful_mcp_runtime_protocol_full_operation_surface() -> None:
    from wf_sources_mcp.sdk import StatefulMcpRuntime

    runtime = cast(StatefulMcpRuntime, _FullSurfaceAdapter())
    conn = McpSourceConnection(
        id="demo.default",
        provider="demo",
        account="default",
        transport=StdioSourceTransport(command="echo"),
    )

    tools = await runtime.list_tools(conn, None)
    resources = await runtime.list_resources(conn, None)
    prompts = await runtime.list_prompts(conn, None)
    metadata = await runtime.get_connection_metadata(conn, None)
    read_result = await runtime.read_resource(conn, None, "test://x")
    prompt_result = await runtime.get_prompt(conn, None, "prompt.summarize")
    invoke_result = await runtime.invoke_method(conn, None, "ping")
    await runtime.send_notification(conn, None, "test.notify")
    call_result = await runtime.call_tool(conn, None, "echo", {"text": "hi"})

    assert tools[0].name == "echo"
    assert resources == []
    assert prompts == []
    assert metadata["server"] == "demo"
    assert read_result == {"contents": []}
    assert prompt_result == {"messages": []}
    assert invoke_result == {}
    assert call_result.outcome == "ok"


def test_mcp_source_operations_protocol_shape() -> None:
    from wf_sources_mcp.sdk import McpSourceOperations

    assert McpSourceOperations.__name__ == "McpSourceOperations"


def test_stateful_mcp_runtime_protocol_shape() -> None:
    from wf_sources_mcp.sdk import StatefulMcpRuntime, ToolExecutor

    assert StatefulMcpRuntime.__name__ == "StatefulMcpRuntime"
    assert ToolExecutor.__name__ == "ToolExecutor"


def test_stateful_runtime_protocol_slices_export() -> None:
    from wf_sources_mcp.sdk import (
        McpSourceOperations,
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
    assert McpSourceOperations.__name__ == "McpSourceOperations"
    assert StatefulMcpRuntime.__name__ == "StatefulMcpRuntime"
