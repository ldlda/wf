from __future__ import annotations

import asyncio
import sys
from typing import Any

from wf_mcp.models import BrokerConfig, ConnectionConfig
from wf_mcp.server import create_unified_proxy_client

from .test_support import fixture_server_path, local_temp_root


def _structured(result: Any) -> dict[str, Any]:
    content = result.structured_content
    assert isinstance(content, dict)
    return content


def test_unified_server_exposes_upstream_admin_and_workflow_tools() -> None:
    config = BrokerConfig(
        store_root=local_temp_root() / "unified_server_store",
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
        client = create_unified_proxy_client(config)
        async with client:
            tools = await client.list_tools()
            names = [tool.name for tool in tools]
            assert "fixture.personal_echo_tool" in names
            assert "wf.admin.list_connections" in names
            assert "wf.workflow.list_artifacts" in names
            assert "wf.workflow.run_deployment" in names

            echo_result = await client.call_tool(
                "fixture.personal_echo_tool",
                {"text": "hello"},
            )
            artifacts_result = await client.call_tool("wf.workflow.list_artifacts")

            assert _structured(echo_result)["echoed"] == "hello"
            assert _structured(artifacts_result)["nodes"] == []

    asyncio.run(run_proxy())


def test_unified_server_can_hide_admin_tools() -> None:
    config = BrokerConfig(
        store_root=local_temp_root() / "unified_no_admin_store",
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
        client = create_unified_proxy_client(config, admin_tools=False)
        async with client:
            tools = await client.list_tools()
            names = [tool.name for tool in tools]
            assert "fixture.personal_echo_tool" in names
            assert "wf.workflow.list_artifacts" in names
            assert "wf.admin.list_connections" not in names

    asyncio.run(run_proxy())
