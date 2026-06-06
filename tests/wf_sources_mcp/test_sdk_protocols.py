from __future__ import annotations

from dataclasses import is_dataclass
from typing import cast

from wf_mcp.broker.models import ConnectionConfig
from wf_sources_mcp.auth import AuthRecord
from wf_sources_mcp.catalog import DiscoveredTool
from wf_sources_mcp.sdk import BackendAdapter, ToolCallResult, ToolExecutor


class EchoAdapter:
    async def list_tools(
        self,
        connection: ConnectionConfig,
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
        connection: ConnectionConfig,
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
        ConnectionConfig(id="demo.default", server="demo", account="default"),
        None,
    )

    assert tools[0].name == "echo"


async def test_tool_executor_protocol_can_describe_tool_calls() -> None:
    executor = cast(ToolExecutor, EchoAdapter())
    result = await executor.call_tool(
        ConnectionConfig(id="demo.default", server="demo", account="default"),
        None,
        "echo",
        {"message": "hello"},
    )

    assert result.outcome == "ok"
    assert result.output == {"echoed": {"message": "hello"}}
