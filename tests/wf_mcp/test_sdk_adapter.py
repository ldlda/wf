from __future__ import annotations

import asyncio

import pytest
from mcp import McpError
from mcp.types import ErrorData

from wf_mcp.broker import WfMcpService
from wf_mcp.capabilities import DiscoveredTool
from wf_mcp.models import ConnectionConfig
from wf_mcp.sdk import McpSdkAdapter
from wf_mcp.storage import FileStore

from .test_support import (
    everything_server_connection,
    fixture_server_path,
    local_temp_root,
    sys,
)


class _ToolsOnlyAdapter:
    async def list_tools(self, connection, auth):
        return [
            DiscoveredTool(
                name="echo_tool",
                title="Echo",
                description="Echo text.",
                input_schema={"type": "object", "properties": {}},
                output_schema={"type": "object", "properties": {}},
            )
        ]

    async def list_resources(self, connection, auth):
        raise McpError(ErrorData(code=-32601, message="Method not found"))

    async def list_prompts(self, connection, auth):
        raise McpError(ErrorData(code=-32601, message="Method not found"))

    async def get_connection_metadata(self, connection, auth):
        return {"server": connection.server}

    async def read_resource(self, connection, auth, uri):
        raise NotImplementedError

    async def get_prompt(self, connection, auth, prompt_name, arguments=None):
        raise NotImplementedError

    async def invoke_method(self, connection, auth, method, params=None):
        raise NotImplementedError

    async def send_notification(self, connection, auth, method, params=None):
        raise NotImplementedError

    async def call_tool(self, connection, auth, tool_name, payload):
        raise NotImplementedError


class _WrappedToolsOnlyAdapter(_ToolsOnlyAdapter):
    async def list_resources(self, connection, auth):
        raise ExceptionGroup(
            "unhandled errors in a TaskGroup",
            [McpError(ErrorData(code=-32601, message="Method not found"))],
        )


def test_mcp_sdk_adapter_lists_and_calls_stdio_tool() -> None:
    service = WfMcpService(store=FileStore(local_temp_root() / "sdk_adapter_store"))
    service.register_connection(
        ConnectionConfig(
            id="fixture.personal",
            server="fixture",
            account="personal",
            metadata={
                "transport": "stdio",
                "command": sys.executable,
                "args": [fixture_server_path()],
            },
        )
    )
    service.register_adapter("fixture", McpSdkAdapter())

    try:
        asyncio.run(service.refresh_connection_catalog("fixture.personal"))
    except PermissionError as exc:
        pytest.skip(f"stdio MCP transport is not permitted in this environment: {exc}")

    payload = service.get_catalog().as_payload()
    assert payload["nodes"][0]["qualified_name"] == "fixture.personal.echo_tool"
    assert payload["resources"] == [
        {
            "qualified_name": "fixture.personal.resource.welcome",
            "connection_id": "fixture.personal",
            "local_name": "resource.welcome",
            "uri": "fixture://docs/welcome",
            "title": "Resource Welcome",
            "description": "Welcome text resource for fixture tests.",
            "mime_type": "text/plain",
            "metadata": payload["resources"][0]["metadata"],
        }
    ]
    assert payload["prompts"] == [
        {
            "qualified_name": "fixture.personal.prompt.summarize",
            "connection_id": "fixture.personal",
            "local_name": "prompt.summarize",
            "title": "Prompt Summarize",
            "description": "Summarize an input text for fixture tests.",
            "arguments": payload["prompts"][0]["arguments"],
            "metadata": payload["prompts"][0]["metadata"],
        }
    ]

    resource_result = asyncio.run(
        service.read_resource("fixture.personal.resource.welcome")
    )
    prompt_result = asyncio.run(
        service.render_prompt(
            "fixture.personal.prompt.summarize",
            arguments={"text": "hello"},
        )
    )
    assert (
        resource_result["contents"][0]["text"] == "Welcome from the fixture MCP server."
    )
    assert (
        prompt_result["messages"][0]["content"]["text"]
        == "Summarize this text:\n\nhello"
    )
    ping_result = asyncio.run(service.invoke_method("fixture.personal", "ping"))
    assert ping_result == {}

    adapter = McpSdkAdapter()
    try:
        result = asyncio.run(
            adapter.call_tool(
                connection=service.connections.get("fixture.personal"),
                auth=None,
                tool_name="echo_tool",
                payload={"text": "hello"},
            )
        )
    except PermissionError as exc:
        pytest.skip(f"stdio MCP transport is not permitted in this environment: {exc}")
    assert result.outcome == "ok"
    assert result.output == {"echoed": "hello"}


def test_mcp_sdk_adapter_can_probe_everything_server() -> None:
    connection = everything_server_connection()
    if connection is None:
        pytest.skip(
            "set MCP_EVERYTHING_COMMAND to enable the live everything-server integration test"
        )

    service = WfMcpService(
        store=FileStore(local_temp_root() / "everything_server_store")
    )
    service.register_connection(connection)
    service.register_adapter("everything", McpSdkAdapter())

    try:
        asyncio.run(service.refresh_connection_catalog("everything.default"))
    except PermissionError as exc:
        pytest.skip(f"live MCP transport is not permitted in this environment: {exc}")

    payload = service.get_catalog().as_payload()
    assert payload["nodes"], "everything-server should expose at least one tool"
    assert all(
        node["qualified_name"].startswith("everything.default.")
        for node in payload["nodes"]
    )
    assert "resources" in payload
    assert "prompts" in payload


def test_refresh_catalog_keeps_tools_when_optional_lists_are_unsupported() -> None:
    service = WfMcpService(
        store=FileStore(local_temp_root() / "tools_only_server_store")
    )
    service.register_connection(
        ConnectionConfig(
            id="tools_only.personal",
            server="tools_only",
            account="personal",
        )
    )
    service.register_adapter("tools_only", _ToolsOnlyAdapter())

    asyncio.run(service.refresh_connection_catalog("tools_only.personal"))

    payload = service.get_catalog().as_payload()
    assert payload["nodes"][0]["qualified_name"] == "tools_only.personal.echo_tool"
    assert payload["resources"] == []
    assert payload["prompts"] == []


def test_refresh_catalog_unwraps_taskgroup_method_not_found() -> None:
    service = WfMcpService(
        store=FileStore(local_temp_root() / "wrapped_tools_only_server_store")
    )
    service.register_connection(
        ConnectionConfig(
            id="wrapped_tools_only.personal",
            server="wrapped_tools_only",
            account="personal",
        )
    )
    service.register_adapter("wrapped_tools_only", _WrappedToolsOnlyAdapter())

    asyncio.run(service.refresh_connection_catalog("wrapped_tools_only.personal"))

    payload = service.get_catalog().as_payload()
    assert payload["nodes"][0]["qualified_name"] == (
        "wrapped_tools_only.personal.echo_tool"
    )
