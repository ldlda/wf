from __future__ import annotations

import asyncio
import json
import sys

import pytest

from wf_mcp import (
    BrokerConfig,
    ConnectionConfig,
    ProxyConfigError,
    create_transparent_proxy_client,
    validate_transparent_proxy_config,
)
from wf_mcp.broker_server import load_broker_config

from tests.test_wf_mcp_support import fixture_server_path, local_temp_root


def test_transparent_proxy_lists_and_calls_upstream_tools() -> None:
    config = BrokerConfig(
        store_root=local_temp_root() / "transparent_proxy_store",
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
        client = create_transparent_proxy_client(config)
        async with client:
            tools = await client.list_tools()
            names = [tool.name for tool in tools]
            assert "wf.mcp_list_connections" in names
            assert "wf.mcp_get_connection_statuses" in names
            assert "fixture.personal_echo_tool" in names

            connections_result = await client.call_tool("wf.mcp_list_connections")
            assert connections_result.structured_content == {
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
                "fixture.personal_echo_tool",
                {"text": "hello"},
            )
            assert result.structured_content == {"echoed": "hello"}

    asyncio.run(run_proxy())


def test_transparent_proxy_rejects_invalid_connection_config() -> None:
    config = BrokerConfig(
        store_root=local_temp_root() / "transparent_proxy_invalid_store",
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
        ],
    )

    with pytest.raises(ProxyConfigError) as exc_info:
        validate_transparent_proxy_config(config)

    message = str(exc_info.value)
    assert "duplicate connection id 'fixture.personal'" in message
    assert "fixture.personal: stdio transport requires metadata.command" in message
    assert "fixture.personal: unsupported MCP transport 'websocket'" in message
    assert "connection id 'bad_scope.personal' must not contain '_'" in message
    assert "fixture.http: http transport requires metadata.url" in message
    assert "connection id 'wf.mcp' is reserved by wf-mcp" in message


def test_transparent_proxy_can_expose_resources_and_prompts_as_tools() -> None:
    config = BrokerConfig(
        store_root=local_temp_root() / "transparent_proxy_helper_store",
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
        client = create_transparent_proxy_client(
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


def test_transparent_proxy_can_collapse_upstream_tools_behind_search() -> None:
    config = BrokerConfig(
        store_root=local_temp_root() / "transparent_proxy_search_store",
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
        client = create_transparent_proxy_client(config, search_tools=True)
        async with client:
            tools = await client.list_tools()
            names = [tool.name for tool in tools]
            assert "search_tools" in names
            assert "wf.mcp_list_connections" in names
            assert "wf.mcp_get_connection_statuses" in names
            assert "fixture.personal_echo_tool" not in names

            search_result = await client.call_tool(
                "search_tools",
                {"query": "echo text back"},
            )
            assert "fixture.personal_echo_tool" in str(search_result)

    asyncio.run(run_proxy())


def test_transparent_proxy_admin_tools_mutate_config_file() -> None:
    tmp_path = local_temp_root() / "transparent_proxy_admin_store"
    tmp_path.mkdir(parents=True, exist_ok=True)
    config_path = tmp_path / "wf_mcp.config.json"
    config_path.write_text(
        json.dumps(
            {
                "store_root": ".wf_mcp_store",
                "connections": [
                    {
                        "id": "fixture.personal",
                        "server": "fixture",
                        "account": "personal",
                        "enabled": False,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    config = load_broker_config(config_path)

    async def run_proxy() -> None:
        client = create_transparent_proxy_client(config, config_path=config_path)
        async with client:
            add_result = await client.call_tool(
                "wf.mcp_add_connection",
                {
                    "connection_id": "fixture.work",
                    "server": "fixture",
                    "account": "work",
                    "enabled": False,
                    "metadata": {
                        "transport": "stdio",
                        "command": sys.executable,
                        "args": [fixture_server_path()],
                    },
                },
            )
            assert add_result.structured_content == {
                "action": "add_connection",
                "connection_id": "fixture.work",
                "ok": True,
                "requires_reload": True,
            }

            disable_result = await client.call_tool(
                "wf.mcp_disable_connection",
                {"connection_id": "fixture.work"},
            )
            assert disable_result.structured_content == {
                "action": "update_connection",
                "connection_id": "fixture.work",
                "ok": True,
                "requires_reload": True,
            }

            update_result = await client.call_tool(
                "wf.mcp_update_connection",
                {
                    "connection_id": "fixture.work",
                    "metadata": {
                        "transport": "stdio",
                        "command": sys.executable,
                        "args": ["updated.py"],
                    },
                },
            )
            assert update_result.structured_content == {
                "action": "update_connection",
                "connection_id": "fixture.work",
                "ok": True,
                "requires_reload": True,
            }

            config_result = await client.call_tool("wf.mcp_get_config")
            assert "fixture.work" in str(config_result.structured_content)

            remove_result = await client.call_tool(
                "wf.mcp_remove_connection",
                {"connection_id": "fixture.work"},
            )
            assert remove_result.structured_content == {
                "action": "remove_connection",
                "connection_id": "fixture.work",
                "ok": True,
                "requires_reload": True,
            }

    asyncio.run(run_proxy())

    config_after = load_broker_config(config_path)
    assert [connection.id for connection in config_after.connections] == [
        "fixture.personal"
    ]


def test_transparent_proxy_admin_reload_remounts_connections() -> None:
    tmp_path = local_temp_root() / "transparent_proxy_reload_store"
    tmp_path.mkdir(parents=True, exist_ok=True)
    config_path = tmp_path / "wf_mcp.config.json"
    config_path.write_text(
        json.dumps(
            {
                "store_root": ".wf_mcp_store",
                "connections": [],
            }
        ),
        encoding="utf-8",
    )
    config = load_broker_config(config_path)

    async def run_proxy() -> None:
        client = create_transparent_proxy_client(config, config_path=config_path)
        async with client:
            initial_tools = await client.list_tools()
            initial_names = [tool.name for tool in initial_tools]
            assert "fixture.personal_echo_tool" not in initial_names

            await client.call_tool(
                "wf.mcp_add_connection",
                {
                    "connection_id": "fixture.personal",
                    "server": "fixture",
                    "account": "personal",
                    "metadata": {
                        "transport": "stdio",
                        "command": sys.executable,
                        "args": [fixture_server_path()],
                    },
                },
            )

            before_reload_tools = await client.list_tools()
            before_reload_names = [tool.name for tool in before_reload_tools]
            assert "fixture.personal_echo_tool" not in before_reload_names

            reload_result = await client.call_tool("wf.mcp_reload_config")
            assert reload_result.structured_content == {
                "ok": True,
                "reloaded": True,
                "mounted_connections": ["fixture.personal"],
                "connection_count": 1,
                "enabled_connection_count": 1,
            }

            after_reload_tools = await client.list_tools()
            after_reload_names = [tool.name for tool in after_reload_tools]
            assert "fixture.personal_echo_tool" in after_reload_names

            result = await client.call_tool(
                "fixture.personal_echo_tool",
                {"text": "reloaded"},
            )
            assert result.structured_content == {"echoed": "reloaded"}

    asyncio.run(run_proxy())
