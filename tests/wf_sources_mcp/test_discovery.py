from __future__ import annotations

from typing import Any

import pytest
from mcp import McpError
from mcp.types import ErrorData

from wf_authoring import build_async_registry
from wf_core import RuntimeContext
from wf_sources_mcp.auth import AuthRecord
from wf_sources_mcp.catalog import DiscoveredPrompt, DiscoveredResource, DiscoveredTool
from wf_sources_mcp.connections import McpSourceConnection
from wf_sources_mcp.discovery import (
    discover_connection_capabilities,
    specs_from_discovered_tools,
)
from wf_sources_mcp.sdk import BackendAdapter, ToolCallResult
from wf_sources_mcp.transports import StdioSourceTransport


def _connection() -> McpSourceConnection:
    return McpSourceConnection(
        id="demo.default",
        provider="demo",
        account="default",
        transport=StdioSourceTransport(command="demo-mcp"),
    )


class _Adapter:
    def __init__(self) -> None:
        self.seen_connections: list[McpSourceConnection] = []

    async def list_tools(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
    ) -> list[DiscoveredTool]:
        self.seen_connections.append(connection)
        return [
            DiscoveredTool(
                name="echo",
                title="Echo",
                description="Echo input",
                input_schema={"type": "object"},
                output_schema={"type": "object"},
            )
        ]

    async def list_resources(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
    ) -> list[DiscoveredResource]:
        return [
            DiscoveredResource(
                uri="demo://docs/guide",
                name="guide",
                title="Guide",
                description="Read me",
            )
        ]

    async def list_prompts(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
    ) -> list[DiscoveredPrompt]:
        return [
            DiscoveredPrompt(
                name="summarize",
                title="Summarize",
                description="Summarize text",
            )
        ]

    async def get_connection_metadata(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
    ) -> dict[str, Any]:
        return {"server": connection.provider}

    async def read_resource(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
        uri: str,
    ) -> dict[str, Any]:
        raise NotImplementedError

    async def get_prompt(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
        prompt_name: str,
        arguments: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError

    async def invoke_method(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError

    async def send_notification(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> None:
        raise NotImplementedError

    async def call_tool(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
        tool_name: str,
        payload: dict[str, Any],
    ) -> ToolCallResult:
        raise NotImplementedError


class _ToolsOnlyAdapter(_Adapter):
    async def list_resources(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
    ) -> list[DiscoveredResource]:
        raise McpError(ErrorData(code=-32601, message="Method not found"))

    async def list_prompts(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
    ) -> list[DiscoveredPrompt]:
        raise ExceptionGroup(
            "unhandled errors in a TaskGroup",
            [McpError(ErrorData(code=-32601, message="Method not found"))],
        )


class _BrokenResourceAdapter(_Adapter):
    async def list_resources(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
    ) -> list[DiscoveredResource]:
        raise RuntimeError("resource listing broke")


async def test_discover_connection_capabilities_collects_all_capability_families() -> (
    None
):
    adapter = _Adapter()
    connection = _connection()

    capabilities = await discover_connection_capabilities(
        connection=connection,
        auth=None,
        adapter=adapter,
    )

    assert capabilities.tools[0].name == "echo"
    assert capabilities.resources[0].name == "guide"
    assert capabilities.prompts[0].name == "summarize"
    assert capabilities.metadata == {"server": "demo"}
    assert adapter.seen_connections == [connection]


async def test_discover_connection_capabilities_treats_missing_optional_families_as_empty() -> (
    None
):
    capabilities = await discover_connection_capabilities(
        connection=_connection(),
        auth=None,
        adapter=_ToolsOnlyAdapter(),
    )

    assert [tool.name for tool in capabilities.tools] == ["echo"]
    assert capabilities.resources == []
    assert capabilities.prompts == []


async def test_discover_connection_capabilities_reraises_non_method_not_found_errors() -> (
    None
):
    with pytest.raises(RuntimeError, match="resource listing broke"):
        await discover_connection_capabilities(
            connection=_connection(),
            auth=None,
            adapter=_BrokenResourceAdapter(),
        )


def test_backend_adapter_static_shape() -> None:
    adapter: BackendAdapter = _Adapter()

    assert adapter is not None


class _RecordingExecutor:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def call_tool(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
        tool_name: str,
        payload: dict[str, Any],
    ) -> ToolCallResult:
        self.calls.append(
            {
                "connection": connection,
                "auth": auth,
                "tool_name": tool_name,
                "payload": payload,
            }
        )
        return ToolCallResult(
            outcome="ok",
            output={"content": [{"type": "text", "text": "Echo: hello"}]},
            meta={"duration_ms": 3},
        )


async def test_specs_from_discovered_tools_wraps_tools_with_neutral_events() -> None:
    executor = _RecordingExecutor()
    events: list[Any] = []
    connection = _connection()
    specs = specs_from_discovered_tools(
        connection=connection,
        auth=None,
        executor=executor,
        tools=[
            DiscoveredTool(
                name="echo",
                title="Echo",
                description="Echo input",
                input_schema={
                    "type": "object",
                    "properties": {"message": {"type": "string"}},
                    "required": ["message"],
                },
                output_schema={
                    "type": "object",
                    "properties": {"content": {"type": "array"}},
                },
            )
        ],
        emit_event=events.append,
    )
    handler = build_async_registry(*specs)["echo"]

    result = await handler(
        {"message": "hello"},
        RuntimeContext(current_node_id="echo"),
    )

    assert result["outcome"] == "ok"
    assert result["output"]["content"][0]["text"] == "Echo: hello"
    assert executor.calls[0]["connection"] is connection
    assert executor.calls[0]["tool_name"] == "echo"
    assert executor.calls[0]["payload"] == {"message": "hello"}
    assert [event.kind for event in events] == [
        "tool_call_started",
        "tool_call_completed",
    ]
    assert events[0].capability_id == "demo.default.echo"
    assert events[1].payload == {"outcome": "ok", "meta": {"duration_ms": 3}}


def test_specs_from_discovered_tools_exports_from_package_root() -> None:
    from wf_sources_mcp import specs_from_discovered_tools as root_specs_from_tools
    from wf_sources_mcp.discovery import specs_from_discovered_tools

    assert root_specs_from_tools is specs_from_discovered_tools


def test_discovery_symbols_export_from_package_root() -> None:
    from wf_sources_mcp import (
        DiscoveredConnectionCapabilities as RootDiscoveredConnectionCapabilities,
    )
    from wf_sources_mcp import (
        discover_connection_capabilities as root_discover_connection_capabilities,
    )
    from wf_sources_mcp.discovery import (
        DiscoveredConnectionCapabilities,
        discover_connection_capabilities,
    )

    assert RootDiscoveredConnectionCapabilities is DiscoveredConnectionCapabilities
    assert root_discover_connection_capabilities is discover_connection_capabilities
