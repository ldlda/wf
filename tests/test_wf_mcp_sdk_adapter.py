from __future__ import annotations

import asyncio

import pytest

from wf_mcp import ConnectionConfig, FileStore, McpSdkAdapter, WfMcpService

from test_wf_mcp_support import (
    everything_server_connection,
    fixture_server_path,
    local_temp_root,
    sys,
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
            "description": "Summarize an input text for fixture tests.",
            "arguments": payload["prompts"][0]["arguments"],
            "metadata": payload["prompts"][0]["metadata"],
        }
    ]

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
