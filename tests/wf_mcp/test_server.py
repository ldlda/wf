from __future__ import annotations

import asyncio
import json
import re
import sys
from typing import Any

from mcp import types as mcp_types

from wf_mcp.broker.config import load_broker_config
from wf_mcp.models import BrokerConfig, ConnectionConfig
from wf_mcp.server import create_server_client

from .test_support import fixture_server_path, local_temp_root


def _structured(result: Any) -> dict[str, Any]:
    content = result.structured_content
    assert isinstance(content, dict)
    return content


async def _assert_safe_tool_maps(
    client: Any,
    *,
    original_name: str,
    safe_name: str,
    arguments: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assert one safe public tool name maps back to its original tool."""
    tools = await client.list_tools()
    names = [tool.name for tool in tools]
    assert safe_name in names
    assert original_name not in names
    assert all(re.fullmatch(r"^[a-zA-Z0-9_-]{1,64}$", name) for name in names)
    assert len(names) == len(set(names))
    return _structured(await client.call_tool(safe_name, arguments or {}))


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
            tools_by_name = {tool.name: tool for tool in tools}
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
            assert "wf.workflow.validate_draft" in names
            assert "wf.workflow.compile_draft" in names
            assert "wf.workflow.create_artifact_from_draft" in names
            assert "wf.workflow.patch_draft" in names
            assert "wf.workflow.list_draft_workspaces" in names
            assert "wf.workflow.create_draft_workspace" in names
            assert "wf.workflow.get_draft_workspace" in names
            assert "wf.workflow.delete_draft_workspace" in names
            assert "wf.workflow.patch_draft_workspace" in names
            assert "wf.workflow.validate_draft_workspace" in names
            assert "wf.workflow.set_draft_name" in names
            assert "wf.workflow.set_draft_route" in names
            assert "wf.workflow.set_step_input_map" in names
            assert "wf.workflow.set_step_output_map" in names
            assert "wf.workflow.create_minimal_draft_workspace" in names
            assert "wf.workflow.create_artifact_from_workspace" in names
            assert "wf.workflow.create_wrapper_from_workspace" in names
            assert "wf.workflow.run_deployment" in names
            call_capability_schema = tools_by_name[
                "wf.workflow.call_capability"
            ].outputSchema
            assert call_capability_schema is not None
            assert "source_id" in call_capability_schema["properties"]
            assert "kind" in call_capability_schema["properties"]
            assert "diagnostics" in call_capability_schema["properties"]
            create_workspace_schema = tools_by_name[
                "wf.workflow.create_draft_workspace"
            ].outputSchema
            assert create_workspace_schema is not None
            assert "workspace_id" in create_workspace_schema["properties"]
            assert "revision" in create_workspace_schema["properties"]
            minimal_workspace_input = tools_by_name[
                "wf.workflow.create_minimal_draft_workspace"
            ].inputSchema
            minimal_request = minimal_workspace_input["properties"]["request"]
            assert minimal_request["properties"]["workspace_id"]["pattern"]
            assert "error_message_source" in minimal_request["properties"]
            assert (
                minimal_request["properties"]["input_schema"]["description"]
                == "Public input JSON Schema for the workflow or wrapper being "
                "drafted."
            )
            wrapper_workspace_input = tools_by_name[
                "wf.workflow.create_wrapper_from_workspace"
            ].inputSchema
            wrapper_request = wrapper_workspace_input["properties"]["request"]
            assert "kind" not in wrapper_request["properties"]
            assert "artifact_id" in wrapper_request["properties"]

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
                source["id"] for source in _structured(sources_result)["sources"]
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
            assert "wf.workflow.list_capabilities" in names
            assert "wf.workflow.inspect_capability" in names
            assert "wf.workflow.call_capability" in names
            assert "wf.workflow.list_draft_workspaces" in names
            assert "wf.workflow.create_draft_workspace" in names
            assert "wf.workflow.get_draft_workspace" in names
            assert "wf.workflow.delete_draft_workspace" in names
            assert "wf.workflow.patch_draft_workspace" in names
            assert "wf.workflow.validate_draft_workspace" in names
            assert "wf.workflow.set_draft_name" in names
            assert "wf.workflow.set_draft_route" in names
            assert "wf.workflow.set_step_input_map" in names
            assert "wf.workflow.set_step_output_map" in names
            assert "wf.workflow.create_minimal_draft_workspace" in names
            assert "wf.workflow.create_artifact_from_workspace" in names
            assert "wf.workflow.create_wrapper_from_workspace" in names
            assert "wf.workflow.inspect_artifact" in names
            assert "wf.workflow.list_deployments" in names
            assert "wf.workflow.save_deployment" in names
            assert "wf.workflow.validate_deployment" in names
            assert "wf.workflow.run_deployment" in names

            assert "wf.workflow.validate_draft" not in names
            assert "wf.workflow.compile_draft" not in names
            assert "wf.workflow.create_artifact_from_plan" not in names
            assert "wf.workflow.create_artifact_from_draft" not in names
            assert "wf.workflow.patch_draft" not in names
            assert "wf.admin.call_tool" not in names
            assert "fixture.personal.echo_tool" not in names

    asyncio.run(run_proxy())


def test_server_search_mode_can_use_safe_tool_names() -> None:
    config = BrokerConfig(
        store_root=local_temp_root() / "server_search_safe_names_store",
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
        client = create_server_client(
            config,
            search_tools=True,
            safe_tool_names=True,
        )
        async with client:
            tools = await client.list_tools()
            names = [tool.name for tool in tools]

            assert "search_tools" in names
            assert "call_tool" in names
            assert "wf_admin_list_sources" in names
            assert "wf_workflow_call_capability" in names
            assert "wf.admin.list_sources" not in names

            result = await _assert_safe_tool_maps(
                client,
                original_name="wf.admin.list_sources",
                safe_name="wf_admin_list_sources",
            )
            source_ids = {source["id"] for source in result["sources"]}
            assert "wf.std" in source_ids

    asyncio.run(run_proxy())


def test_server_safe_tool_names_adapts_dotted_runtime_names() -> None:
    config = BrokerConfig(
        store_root=local_temp_root() / "server_safe_tool_names_store",
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
        client = create_server_client(config, safe_tool_names=True)
        async with client:
            artifacts = await _assert_safe_tool_maps(
                client,
                original_name="wf.workflow.list_artifacts",
                safe_name="wf_workflow_list_artifacts",
            )
            echo = await _assert_safe_tool_maps(
                client,
                original_name="fixture.personal.echo_tool",
                safe_name="fixture_personal_echo_tool",
                arguments={"text": "hello"},
            )

            assert artifacts["nodes"] == []
            assert echo["echoed"] == "hello"

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


def test_create_artifact_from_plan_exposes_plan_as_plain_object() -> None:
    config = BrokerConfig(
        store_root=local_temp_root() / "unified_create_artifact_schema_store",
        connections=[],
    )

    async def run_proxy() -> None:
        client = create_server_client(config, admin_tools=False)
        async with client:
            tools = await client.list_tools()
            by_name = {tool.name: tool for tool in tools}
            schema = by_name["wf.workflow.create_artifact_from_plan"].inputSchema
            plan_schema = schema["properties"]["plan"]

            assert plan_schema["type"] == "object"
            assert plan_schema.get("additionalProperties") is True

    asyncio.run(run_proxy())


def test_draft_tools_expose_plain_object_and_patch_array_schemas() -> None:
    config = BrokerConfig(
        store_root=local_temp_root() / "unified_draft_schema_store",
        connections=[],
    )

    async def run_proxy() -> None:
        client = create_server_client(config, admin_tools=False)
        async with client:
            tools = await client.list_tools()
            by_name = {tool.name: tool for tool in tools}

            validate_schema = by_name["wf.workflow.validate_draft"].inputSchema
            validate_draft_schema = validate_schema["properties"]["draft"]
            create_schema = by_name[
                "wf.workflow.create_artifact_from_draft"
            ].inputSchema
            create_draft_schema = create_schema["properties"]["draft"]
            patch_schema = by_name["wf.workflow.patch_draft"].inputSchema
            patch_draft_schema = patch_schema["properties"]["draft"]
            patch_patch_schema = patch_schema["properties"]["patch"]

            assert validate_draft_schema["type"] == "object"
            assert validate_draft_schema.get("additionalProperties") is True
            assert create_draft_schema["type"] == "object"
            assert create_draft_schema.get("additionalProperties") is True
            assert patch_draft_schema["type"] == "object"
            assert patch_patch_schema["type"] == "array"
            assert "$defs" not in patch_patch_schema

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
            assert "wf://docs/workflow-capabilities" in uris
            assert "wf://docs/workflow-drafts" in uris

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

            resource_payload = _structured(resource)
            prompt_payload = _structured(prompt)
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
            assert _structured(before)["capabilities"] == []

            await client.call_tool(
                "wf.admin.enable_connection",
                {"connection_id": "fixture.personal"},
            )
            await client.call_tool("wf.admin.reload_config")

            sources = await client.call_tool("wf.admin.list_sources", {"limit": 100})
            fixture_source = next(
                source
                for source in _structured(sources)["sources"]
                if source["id"] == "fixture.personal"
            )
            assert fixture_source["enabled"] is True

            after = await client.call_tool(
                "wf.workflow.list_capabilities",
                {"source_id": "fixture.personal"},
            )
            names = [
                capability["name"] for capability in _structured(after)["capabilities"]
            ]
            assert "fixture.personal.echo_tool" in names

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
