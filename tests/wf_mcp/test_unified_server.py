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


def test_unified_workflow_tools_have_human_metadata() -> None:
    config = BrokerConfig(
        store_root=local_temp_root() / "unified_metadata_store",
        connections=[],
    )

    async def run_proxy() -> None:
        client = create_unified_proxy_client(config, admin_tools=False)
        async with client:
            tools = await client.list_tools()
            by_name = {tool.name: tool for tool in tools}
            list_artifacts = by_name["wf.workflow.list_artifacts"]
            run_deployment = by_name["wf.workflow.run_deployment"]

            assert list_artifacts.title == "List Workflow Artifacts"
            assert "saved workflow artifacts" in (list_artifacts.description or "")
            assert run_deployment.title == "Run Workflow Deployment"
            assert "deployment_id" in (run_deployment.description or "")

    asyncio.run(run_proxy())


def test_unified_admin_tools_have_human_metadata() -> None:
    config = BrokerConfig(
        store_root=local_temp_root() / "unified_admin_metadata_store",
        connections=[],
    )

    async def run_proxy() -> None:
        client = create_unified_proxy_client(config)
        async with client:
            tools = await client.list_tools()
            by_name = {tool.name: tool for tool in tools}
            list_connections = by_name["wf.admin.list_connections"]
            reload_config = by_name["wf.admin.reload_config"]

            assert list_connections.title == "List Connections"
            assert "configured MCP connections" in (list_connections.description or "")
            assert reload_config.title == "Reload Config"
            assert "remount" in (reload_config.description or "")

    asyncio.run(run_proxy())
