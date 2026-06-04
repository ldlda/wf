from __future__ import annotations

import asyncio
import json
import sys

from mcp import types as mcp_types

from wf_mcp.broker.config import load_broker_config
from wf_mcp.models import BrokerConfig
from wf_mcp.server import create_server_client
from wf_mcp.source_registry import (
    FileSourceRegistryStore,
    McpSourceRegistryEntry,
    SourceRegistryFile,
    StdioSourceTransport,
)

from ..test_support import fixture_server_path, local_temp_root
from .conftest import structured


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
            assert "wf://docs/workflow-capabilities" in uris
            assert "wf://docs/workflow-drafts" in uris
            assert "wf://skills/wf-workflow/SKILL.md" in uris
            assert "wf://skills/wf-workflow/references/workflow-lifecycle.md" in uris

            result = await client.read_resource("wf://docs/operator-manual")
            assert isinstance(result[0], mcp_types.TextResourceContents)
            assert "wf_mcp Operator Manual" in result[0].text
            assert "Primary Workflow Lifecycle" in result[0].text
            assert "live_check" in result[0].text
            assert "delete_deployment" in result[0].text

            drafts_result = await client.read_resource("wf://docs/workflow-drafts")
            assert isinstance(drafts_result[0], mcp_types.TextResourceContents)
            assert "Two Outputs, Different Shapes" in drafts_result[0].text
            assert (
                "Do not use step output `source` here" in drafts_result[0].text
                or "Do not use `source` at top level" in drafts_result[0].text
            )

            skill_result = await client.read_resource(
                "wf://skills/wf-workflow/SKILL.md"
            )
            assert isinstance(skill_result[0], mcp_types.TextResourceContents)
            assert "name: wf-workflow" in skill_result[0].text
            assert "Workflow Lifecycle" in skill_result[0].text

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


def test_admin_tools_can_read_local_documentation_source() -> None:
    config = BrokerConfig(
        store_root=local_temp_root() / "unified_admin_docs_store",
        connections=[],
    )

    async def run_proxy() -> None:
        client = create_server_client(
            config,
            resources_as_tools=True,
            prompts_as_tools=True,
            safe_tool_names=True,
        )
        async with client:
            resource = await client.call_tool(
                "wf_admin_read_resource",
                {"qualified_name": "wf.docs.workflow_capabilities"},
            )
            prompt = await client.call_tool(
                "wf_admin_render_prompt",
                {"qualified_name": "wf.docs.workflow_authoring_guide"},
            )

            resource_payload = structured(resource)
            prompt_payload = structured(prompt)
            assert resource_payload["contents"][0]["uri"] == (
                "wf://docs/workflow-capabilities"
            )
            assert "# Workflow Capabilities" in resource_payload["contents"][0]["text"]
            assert (
                "wf://docs/workflow-capabilities"
                in (prompt_payload["messages"][0]["content"]["text"])
            )

    asyncio.run(run_proxy())


def test_server_reload_syncs_service_connection_source_enabled_state() -> None:
    tmp_path = local_temp_root() / "unified_reload_service_source_store"
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
                        "metadata": {
                            "transport": "stdio",
                            "command": sys.executable,
                            "args": [fixture_server_path()],
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    config = load_broker_config(config_path)

    async def run_proxy() -> None:
        client = create_server_client(config, config_path=config_path)
        async with client:
            await client.call_tool(
                "wf.admin.refresh_connection_catalog",
                {"connection_id": "fixture.personal"},
            )
            before = await client.call_tool(
                "wf.workflow.list_capabilities",
                {"source_id": "fixture.personal"},
            )
            assert structured(before)["capabilities"] == []

            await client.call_tool(
                "wf.admin.enable_connection",
                {"connection_id": "fixture.personal"},
            )
            await client.call_tool("wf.admin.reload_config")

            sources = await client.call_tool("wf.admin.list_sources", {"limit": 100})
            fixture_source = next(
                source
                for source in structured(sources)["sources"]
                if source["id"] == "fixture.personal"
            )
            assert fixture_source["enabled"] is True

            after = await client.call_tool(
                "wf.workflow.list_capabilities",
                {"source_id": "fixture.personal"},
            )
            names = [
                capability["name"] for capability in structured(after)["capabilities"]
            ]
            assert "fixture.personal.echo_tool" in names

    asyncio.run(run_proxy())


def test_server_reload_preserves_source_registry_connections() -> None:
    tmp_path = local_temp_root() / "unified_reload_registry_source_store"
    tmp_path.mkdir(parents=True, exist_ok=True)
    config_path = tmp_path / "wf_mcp.config.json"
    config_path.write_text(
        json.dumps({"store_root": ".wf_mcp_store", "connections": []}),
        encoding="utf-8",
    )
    config = load_broker_config(config_path)
    FileSourceRegistryStore(config.store_root).save_registry(
        SourceRegistryFile(
            sources=[
                McpSourceRegistryEntry(
                    id="fixture.registry",
                    kind="mcp",
                    enabled=True,
                    provider="fixture",
                    account="registry",
                    transport=StdioSourceTransport(command=sys.executable),
                )
            ]
        )
    )

    async def run_proxy() -> None:
        client = create_server_client(config, config_path=config_path)
        async with client:
            before = await client.call_tool("wf.admin.list_sources", {"limit": 100})
            before_ids = {source["id"] for source in structured(before)["sources"]}
            assert "fixture.registry" in before_ids

            await client.call_tool("wf.admin.reload_config")

            after = await client.call_tool("wf.admin.list_sources", {"limit": 100})
            after_ids = {source["id"] for source in structured(after)["sources"]}
            assert "fixture.registry" in after_ids

    asyncio.run(run_proxy())
