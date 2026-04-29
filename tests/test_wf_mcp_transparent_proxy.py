from __future__ import annotations

import asyncio
import sys

import pytest

from wf_mcp import (
    BrokerConfig,
    ConnectionConfig,
    ProxyConfigError,
    create_transparent_proxy_client,
    validate_transparent_proxy_config,
)

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
            assert "fixture.personal_echo_tool" in names

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
