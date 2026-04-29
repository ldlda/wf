from __future__ import annotations

import asyncio
import sys

from wf_mcp import BrokerConfig, ConnectionConfig, create_transparent_proxy_client

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
