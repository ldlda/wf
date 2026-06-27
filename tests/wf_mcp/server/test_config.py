from __future__ import annotations

import asyncio

from wf_mcp.broker.config import build_service_from_config
from wf_mcp.server import create_server_client

from .conftest import server_config, structured


def test_config_built_service_uses_persistent_tool_executor() -> None:
    config = server_config()

    service = build_service_from_config(config)

    assert service.adapters["fixture"].__class__.__name__ == "McpSdkAdapter"
    assert service.tool_executor is not None


def test_server_exposes_upstream_admin_and_workflow_tools() -> None:
    config = server_config()

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
            assert "wf.workflow.bind" in names
            assert "wf.workflow.add_step_from_capability" in names
            assert "wf.workflow.create_minimal_draft_workspace" in names
            assert "wf.workflow.create_draft_workspace_from_capability" in names
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
            list_sources_schema = tools_by_name["wf.admin.list_sources"].inputSchema
            assert (
                "inspect_source"
                in list_sources_schema["properties"]["limit"]["description"]
            )
            inspect_source_schema = tools_by_name["wf.admin.inspect_source"].inputSchema
            assert (
                "Exact source id"
                in inspect_source_schema["properties"]["source_id"]["description"]
            )
            minimal_workspace_input = tools_by_name[
                "wf.workflow.create_minimal_draft_workspace"
            ].inputSchema
            minimal_request = minimal_workspace_input["properties"]["request"]
            assert minimal_request["properties"]["workspace_id"]["pattern"]
            assert "error_message_source" in minimal_request["properties"]
            assert "input" in minimal_request["properties"]
            assert "output" in minimal_request["properties"]
            assert "input_map" in minimal_request["properties"]
            assert (
                minimal_request["properties"]["input_schema"]["description"]
                == "Public input JSON Schema for the workflow or wrapper being "
                "drafted."
            )
            from_capability_input = tools_by_name[
                "wf.workflow.create_draft_workspace_from_capability"
            ].inputSchema
            from_capability_request = from_capability_input["properties"]["request"]
            assert "capability_name" in from_capability_request["properties"]
            assert "input_schema" in from_capability_request["properties"]
            assert "input" in from_capability_request["properties"]
            assert "output" in from_capability_request["properties"]
            assert "output_map" in from_capability_request["properties"]
            set_input_schema = tools_by_name[
                "wf.workflow.set_step_input_map"
            ].inputSchema
            set_input_request = set_input_schema["properties"]["request"]
            assert "merge" in set_input_request["properties"]
            add_step_schema = tools_by_name[
                "wf.workflow.add_step_from_capability"
            ].inputSchema
            add_step_request = add_step_schema["properties"]["request"]
            assert "capability_name" in add_step_request["properties"]
            assert "bind_outputs" in add_step_request["properties"]
            from_capability_output = tools_by_name[
                "wf.workflow.create_draft_workspace_from_capability"
            ].outputSchema
            assert from_capability_output is not None
            assert "wrapper_hints" in from_capability_output["properties"]
            assert "next_actions" in from_capability_output["properties"]
            next_actions_schema = from_capability_output["properties"]["next_actions"]
            assert "recommended_next_tool" in next_actions_schema["properties"]
            assert "patch_examples" in next_actions_schema["properties"]
            assert "can_continue" in next_actions_schema["properties"]
            assert (
                "Advisory"
                in next_actions_schema["properties"]["can_continue"]["description"]
            )
            assert (
                "Advisory"
                in next_actions_schema["properties"]["can_save_now"]["description"]
            )
            validate_deployment = tools_by_name["wf.workflow.validate_deployment"]
            run_deployment = tools_by_name["wf.workflow.run_deployment"]

            validate_output = validate_deployment.outputSchema
            run_output = run_deployment.outputSchema

            assert validate_output is not None
            assert "next_actions" in validate_output["properties"]
            assert (
                "recommended_next_tool"
                in validate_output["properties"]["next_actions"]["properties"]
            )
            assert run_output is not None
            assert "next_actions" in run_output["properties"]
            assert (
                "recommended_next_tool"
                in run_output["properties"]["next_actions"]["properties"]
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

            assert structured(echo_result)["echoed"] == "hello"
            assert structured(artifacts_result)["nodes"] == []
            assert structured(artifacts_result)["total"] == 0
            assert structured(capability_result)["outcome"] == "ok"
            assert structured(capability_result)["output"] == {"value": "hello"}
            source_ids = {
                source["id"] for source in structured(sources_result)["sources"]
            }
            assert "wf.admin" in source_ids
            assert "wf.docs" in source_ids
            assert "wf.std" in source_ids

    asyncio.run(run_proxy())


def test_server_reuses_real_upstream_session_across_workflow_requests() -> None:
    """Workflow node calls may share one stateful MCP session across requests."""
    config = server_config()

    async def run_proxy() -> None:
        client = create_server_client(config)
        async with client:
            await client.call_tool(
                "wf.admin.refresh_connection_catalog",
                {"connection_id": "fixture.personal"},
            )
            first = await client.call_tool(
                "wf.workflow.call_capability",
                {
                    "qualified_name": "fixture.personal.echo_tool",
                    "payload": {"text": "one"},
                },
            )
            second = await client.call_tool(
                "wf.workflow.call_capability",
                {
                    "qualified_name": "fixture.personal.echo_tool",
                    "payload": {"text": "two"},
                },
            )

            assert structured(first)["output"]["echoed"] == "one"
            assert structured(second)["output"]["echoed"] == "two"

    asyncio.run(run_proxy())


def test_server_can_hide_admin_tools() -> None:
    config = server_config()

    async def run_proxy() -> None:
        client = create_server_client(config, admin_tools=False)
        async with client:
            tools = await client.list_tools()
            names = [tool.name for tool in tools]
            assert "fixture.personal.echo_tool" in names
            assert "wf.workflow.list_artifacts" in names
            assert "wf.admin.list_connections" not in names

    asyncio.run(run_proxy())
