from __future__ import annotations

import asyncio
import sys
from typing import Any

import anyio
import httpx
import mcp.types as mcp_types
import pytest
from mcp.shared.exceptions import McpError

from wf_mcp.models import BrokerConfig, ConnectionConfig
from wf_mcp.proxy import create_proxy_client
from wf_mcp.proxy.mounts import _bounded_proxy_list

from ..test_support import fixture_server_path, local_temp_root
from .conftest import proxy_config, structured


def test_proxy_lists_and_calls_upstream_tools() -> None:
    config = proxy_config()

    async def run_proxy() -> None:
        client = create_proxy_client(config)
        async with client:
            tools = await client.list_tools()
            names = [tool.name for tool in tools]
            assert "wf.admin.list_connections" in names
            assert "wf.admin.get_connection_statuses" in names
            assert "wf.admin.list_proxy_tools" in names
            assert "wf.admin.get_proxy_tool" in names
            assert "fixture.personal.echo_tool" in names

            connections_result = await client.call_tool("wf.admin.list_connections")
            assert structured(connections_result) == {
                "result": [
                    {
                        "id": "fixture.personal",
                        "server": "fixture",
                        "account": "personal",
                        "enabled": True,
                        "metadata": {
                            "transport": "stdio",
                            "command": sys.executable,
                            "args": [fixture_server_path()],
                        },
                    }
                ]
            }

            result = await client.call_tool(
                "fixture.personal.echo_tool",
                {"text": "hello"},
            )
            assert structured(result) == {"echoed": "hello"}

            proxy_tools_result = await client.call_tool("wf.admin.list_proxy_tools")
            proxy_tools_payload = structured(proxy_tools_result)
            proxy_tools = proxy_tools_payload["tools"]
            assert proxy_tools_payload["nextCursor"] is None
            assert proxy_tools_payload["total"] == 5
            assert len(proxy_tools) == 5
            assert proxy_tools[0]["proxy_name"] == "fixture.personal.echo_tool"
            assert proxy_tools[0]["connection_id"] == "fixture.personal"
            assert proxy_tools[0]["local_name"] == "echo_tool"
            assert proxy_tools[0]["enabled"] is True
            proxy_names = [tool["proxy_name"] for tool in proxy_tools]
            assert "fixture.personal.emit_notifications_tool" in proxy_names
            assert "fixture.personal.remember_value_tool" in proxy_names
            assert "fixture.personal.recall_value_tool" in proxy_names
            assert "fixture.personal.resource_link_tool" in proxy_names

            proxy_tool_result = await client.call_tool(
                "wf.admin.get_proxy_tool",
                {"proxy_name": "fixture.personal.echo_tool"},
            )
            proxy_tool = structured(proxy_tool_result)
            assert proxy_tool["proxy_name"] == "fixture.personal.echo_tool"
            assert proxy_tool["connection_id"] == "fixture.personal"
            assert proxy_tool["local_name"] == "echo_tool"
            assert proxy_tool["input_schema"]["properties"]["text"]["type"] == "string"

    asyncio.run(run_proxy())


def test_proxy_listing_degrades_when_one_source_hangs() -> None:
    async def stuck_listing() -> list[Any]:
        await asyncio.sleep(1)
        return [{"name": "unreachable"}]

    async def run_timeout() -> None:
        result = await _bounded_proxy_list(
            stuck_listing(),
            connection_id="serena.default",
            operation="tools/list",
            timeout_seconds=0.01,
        )
        assert result == []

    asyncio.run(run_timeout())


def test_proxy_listing_degrades_when_one_source_has_transport_error() -> None:
    async def broken_listing() -> list[Any]:
        raise OSError("stdio process exited")

    async def run_failure() -> None:
        result = await _bounded_proxy_list(
            broken_listing(),
            connection_id="serena.default",
            operation="tools/list",
            timeout_seconds=1,
        )
        assert result == []

    asyncio.run(run_failure())


def test_proxy_listing_degrades_when_one_source_has_connection_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def connection_failed_listing() -> list[Any]:
        raise ConnectionError("connection refused")

    async def run_failure() -> None:
        result = await _bounded_proxy_list(
            connection_failed_listing(),
            connection_id="serena.default",
            operation="tools/list",
            timeout_seconds=1,
        )
        assert result == []

    import logging

    with caplog.at_level(logging.WARNING, logger="wf_mcp.proxy.mounts"):
        asyncio.run(run_failure())

    assert "ConnectionError" in caplog.text
    assert "serena.default" in caplog.text
    assert "tools/list" in caplog.text


@pytest.mark.parametrize(
    ("exc", "expected_log_name"),
    [
        (
            McpError(
                mcp_types.ErrorData(
                    code=mcp_types.INTERNAL_ERROR,
                    message="connection closed",
                )
            ),
            "McpError",
        ),
        (anyio.ClosedResourceError(), "ClosedResourceError"),
        (anyio.EndOfStream(), "EndOfStream"),
        (httpx.ConnectError("connection refused"), "ConnectError"),
    ],
)
def test_proxy_listing_degrades_when_session_transport_closes(
    exc: Exception,
    expected_log_name: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def failed_listing() -> list[Any]:
        raise exc

    async def run_failure() -> None:
        result = await _bounded_proxy_list(
            failed_listing(),
            connection_id="remote.default",
            operation="tools/list",
            timeout_seconds=1,
        )
        assert result == []

    import logging

    with caplog.at_level(logging.WARNING, logger="wf_mcp.proxy.mounts"):
        asyncio.run(run_failure())

    assert expected_log_name in caplog.text
    assert "remote.default" in caplog.text


def test_proxy_registers_admin_tools_on_local_provider() -> None:
    config = proxy_config()

    async def run_proxy() -> None:
        client = create_proxy_client(config)
        async with client:
            tools = await client.list_tools()
            admin_names = [
                tool.name for tool in tools if tool.name.startswith("wf.admin.")
            ]
            assert "wf.admin.list_connections" in admin_names
            assert "wf.admin.get_connection_statuses" in admin_names
            assert "wf.admin.list_proxy_tools" in admin_names
            assert "wf.admin.get_proxy_tool" in admin_names

    asyncio.run(run_proxy())


def test_proxy_rewrites_resource_links_returned_by_tools() -> None:
    config = proxy_config()

    async def run_proxy() -> None:
        client = create_proxy_client(config)
        async with client:
            result = await client.call_tool("fixture.personal.resource_link_tool")
            link = result.content[0]
            assert link.type == "resource_link"
            assert str(link.uri) == "fixture://fixture/personal/docs/welcome"

    asyncio.run(run_proxy())


def test_proxy_reuses_one_upstream_session_for_stateful_tools() -> None:
    """Visible proxy tools must share server-local state for one MCP client."""
    config = proxy_config()

    async def run_proxy() -> None:
        client = create_proxy_client(config)
        async with client:
            written = await client.call_tool(
                "fixture.personal.remember_value_tool",
                {"value": "held"},
            )
            recalled = await client.call_tool("fixture.personal.recall_value_tool")

            assert structured(written)["remembered"] == "held"
            assert structured(recalled)["remembered"] == "held"

    asyncio.run(run_proxy())


def test_proxy_rejects_invalid_connection_config() -> None:
    config = BrokerConfig(
        store_root=local_temp_root() / "proxy_invalid_store",
        connections=[
            ConnectionConfig(
                id="fixture.personal",
                server="fixture",
                account="personal",
                metadata={"transport": "stdio"},
            ),
            ConnectionConfig(
                id="fixture.personal",
                server="fixture",
                account="work",
                metadata={"transport": "websocket"},
            ),
            ConnectionConfig(
                id="bad_scope.personal",
                server="bad_scope",
                account="personal",
                metadata={"transport": "stdio", "command": sys.executable},
            ),
            ConnectionConfig(
                id="fixture.http",
                server="fixture",
                account="http",
                metadata={"transport": "http"},
            ),
            ConnectionConfig(
                id="wf.mcp",
                server="wf",
                account="mcp",
                metadata={"transport": "stdio", "command": sys.executable},
            ),
            ConnectionConfig(
                id="wf.admin",
                server="wf",
                account="admin",
                metadata={"transport": "stdio", "command": sys.executable},
            ),
        ],
    )

    from wf_mcp.proxy_validation import ProxyConfigError, validate_proxy_config

    with pytest.raises(ProxyConfigError) as exc_info:
        validate_proxy_config(config)

    message = str(exc_info.value)
    assert "duplicate connection id 'fixture.personal'" in message
    assert "fixture.personal: stdio transport requires metadata.command" in message
    assert "fixture.personal: unsupported MCP transport 'websocket'" in message
    assert "fixture.http: http transport requires metadata.url" in message
    assert "connection id 'wf.mcp' is reserved by wf-mcp" in message
    assert "connection id 'wf.admin' is reserved by wf-mcp" in message


def test_proxy_can_expose_resources_and_prompts_as_tools() -> None:
    config = proxy_config()

    async def run_proxy() -> None:
        client = create_proxy_client(
            config,
            resources_as_tools=True,
            prompts_as_tools=True,
        )
        async with client:
            tools = await client.list_tools()
            names = [tool.name for tool in tools]
            assert "list_resources" in names
            assert "read_resource" in names
            assert "list_prompts" in names
            assert "get_prompt" in names

    asyncio.run(run_proxy())


def test_proxy_can_collapse_upstream_tools_behind_search() -> None:
    config = BrokerConfig(
        store_root=local_temp_root() / "search_proxy_store",
        connections=[
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
        ],
    )

    async def run_proxy() -> None:
        client = create_proxy_client(config, search_tools=True)
        async with client:
            tools = await client.list_tools()
            names = [tool.name for tool in tools]
            assert "search_tools" in names
            assert "wf.admin.list_connections" in names
            assert "wf.admin.get_connection_statuses" in names
            assert "wf.admin.list_proxy_tools" in names
            assert "fixture.personal.echo_tool" not in names

    asyncio.run(run_proxy())


def test_proxy_admin_inventory_ignores_search_visibility() -> None:
    config = BrokerConfig(
        store_root=local_temp_root() / "search_admin_store",
        connections=[
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
        ],
    )

    async def run_proxy() -> None:
        client = create_proxy_client(config, search_tools=True)
        async with client:
            result = await client.call_tool("wf.admin.list_proxy_tools")
            payload = structured(result)
            assert payload["total"] > 0

    asyncio.run(run_proxy())


def test_proxy_proxy_tool_listing_supports_filters_and_cursor() -> None:
    config = proxy_config()

    async def run_proxy() -> None:
        client = create_proxy_client(config)
        async with client:
            result = await client.call_tool(
                "wf.admin.list_proxy_tools",
                {"limit": 2},
            )
            payload = structured(result)
            assert len(payload["tools"]) == 2
            assert payload["nextCursor"] is not None

            result2 = await client.call_tool(
                "wf.admin.list_proxy_tools",
                {"limit": 2, "cursor": payload["nextCursor"]},
            )
            payload2 = structured(result2)
            assert len(payload2["tools"]) > 0

    asyncio.run(run_proxy())
