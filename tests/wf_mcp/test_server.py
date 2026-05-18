from __future__ import annotations

import asyncio
import sys
from typing import Any

from mcp import types as mcp_types

from wf_mcp.models import BrokerConfig, ConnectionConfig
from wf_mcp.server import create_server_client

from .test_support import fixture_server_path, local_temp_root


def _structured(result: Any) -> dict[str, Any]:
    content = result.structured_content
    assert isinstance(content, dict)
    return content


def test_server_exposes_upstream_admin_and_workflow_tools() -> None:
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
        client = create_server_client(config)
        async with client:
            tools = await client.list_tools()
            names = [tool.name for tool in tools]
            assert "fixture.personal.echo_tool" in names
            assert "wf.admin.list_connections" in names
            assert "wf.admin.get_connection_statuses" in names
            assert "wf.admin.refresh_connection_catalog" in names
            assert "wf.admin.get_catalog" in names
            assert "wf.admin.get_planner_catalog" in names
            assert "wf.admin.list_sources" in names
            assert "wf.admin.inspect_source" in names
            assert "wf.admin.read_resource" in names
            assert "wf.admin.render_prompt" in names
            assert "wf.admin.invoke_method" in names
            assert "wf.admin.call_tool" in names
            assert "wf.admin.get_events" in names
            assert "wf.workflow.list_artifacts" in names
            assert "wf.workflow.list_capabilities" in names
            assert "wf.workflow.inspect_capability" in names
            assert "wf.workflow.call_capability" in names
            assert "wf.workflow.run_deployment" in names

            echo_result = await client.call_tool(
                "fixture.personal.echo_tool",
                {"text": "hello"},
            )
            artifacts_result = await client.call_tool("wf.workflow.list_artifacts")
            capability_result = await client.call_tool(
                "wf.workflow.call_capability",
                {
                    "qualified_name": "wf.std.constant",
                    "payload": {"value": "hello"},
                },
            )
            sources_result = await client.call_tool("wf.admin.list_sources")

            assert _structured(echo_result)["echoed"] == "hello"
            assert _structured(artifacts_result)["nodes"] == []
            assert _structured(capability_result)["outcome"] == "ok"
            assert _structured(capability_result)["output"] == {"value": "hello"}
            source_ids = {
                source["id"]
                for source in _structured(sources_result)["sources"]
            }
            assert "wf.admin" in source_ids
            assert "wf.docs" in source_ids
            assert "wf.mcp" in source_ids
            assert "wf.std" in source_ids

    asyncio.run(run_proxy())


def test_server_can_hide_admin_tools() -> None:
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
        client = create_server_client(config, admin_tools=False)
        async with client:
            tools = await client.list_tools()
            names = [tool.name for tool in tools]
            assert "fixture.personal.echo_tool" in names
            assert "wf.workflow.list_artifacts" in names
            assert "wf.admin.list_connections" not in names

    asyncio.run(run_proxy())


def test_server_search_mode_pins_stable_control_and_workflow_tools() -> None:
    config = BrokerConfig(
        store_root=local_temp_root() / "server_search_mode_store",
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
        client = create_server_client(config, search_tools=True)
        async with client:
            tools = await client.list_tools()
            names = [tool.name for tool in tools]

            assert "search_tools" in names
            assert "call_tool" in names
            assert "wf.admin.list_sources" in names
            assert "wf.admin.list_connections" in names
            assert "wf.admin.get_connection_statuses" in names
            assert "wf.admin.reload_config" in names
            assert "wf.admin.list_proxy_tools" in names
            assert "wf.admin.get_proxy_tool" in names
            assert "wf.workflow.list_artifacts" in names
            assert "wf.workflow.call_capability" in names
            assert "wf.workflow.inspect_artifact" in names
            assert "wf.workflow.list_deployments" in names
            assert "wf.workflow.validate_deployment" in names
            assert "wf.workflow.run_deployment" in names

            assert "wf.admin.call_tool" not in names
            assert "fixture.personal.echo_tool" not in names

    asyncio.run(run_proxy())


def test_workflow_tools_have_human_metadata() -> None:
    config = BrokerConfig(
        store_root=local_temp_root() / "unified_metadata_store",
        connections=[],
    )

    async def run_proxy() -> None:
        client = create_server_client(config, admin_tools=False)
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


def test_server_exposes_platform_documentation_resources() -> None:
    config = BrokerConfig(
        store_root=local_temp_root() / "unified_docs_resource_store",
        connections=[],
    )

    async def run_proxy() -> None:
        client = create_server_client(config, admin_tools=False)
        async with client:
            resources = await client.list_resources()
            uris = [str(resource.uri) for resource in resources]
            assert "wf://docs/operator-manual" in uris

            result = await client.read_resource("wf://docs/operator-manual")
            assert isinstance(result[0], mcp_types.TextResourceContents)
            assert "wf_mcp Operator Manual" in result[0].text

    asyncio.run(run_proxy())


def test_server_exposes_platform_documentation_prompts() -> None:
    config = BrokerConfig(
        store_root=local_temp_root() / "unified_docs_prompt_store",
        connections=[],
    )

    async def run_proxy() -> None:
        client = create_server_client(config, admin_tools=False)
        async with client:
            prompts = await client.list_prompts()
            names = [prompt.name for prompt in prompts]
            assert "wf.docs.operator_guide" in names

            result = await client.get_prompt("wf.docs.operator_guide")
            content = result.messages[0].content
            assert isinstance(content, mcp_types.TextContent)
            assert "wf://docs/operator-manual" in content.text

    asyncio.run(run_proxy())


def test_admin_tools_have_human_metadata() -> None:
    config = BrokerConfig(
        store_root=local_temp_root() / "unified_admin_metadata_store",
        connections=[],
    )

    async def run_proxy() -> None:
        client = create_server_client(config)
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
