from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastmcp import FastMCP
from fastmcp.client import Client
from fastmcp.client.transports.memory import FastMCPTransport

from wf_artifacts import FileDraftWorkspaceStore, FileWorkflowArtifactStore
from wf_core.models.steps import InputPathBinding, InputValueBinding, OutputBinding
from wf_mcp.broker import WfMcpService
from wf_mcp.models import BrokerConfig
from wf_mcp.server import create_server_client
from wf_mcp.storage import FileStore
from wf_mcp.workflow_surface.tools import register_workflow_tools

from .conftest import assert_safe_tool_maps, server_config, structured


@pytest.mark.asyncio
async def test_server_search_mode_pins_stable_control_and_workflow_tools() -> None:
    config = server_config()

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
        assert "wf.workflow.set_step_input_bindings" in names
        assert "wf.workflow.set_step_output_bindings" in names
        assert "wf.workflow.set_step_input_map" in names
        assert "wf.workflow.set_step_output_map" in names
        assert "wf.workflow.set_workflow_output_bindings" in names
        assert "wf.workflow.set_workflow_output_map" in names
        assert "wf.workflow.bind" in names
        assert "wf.workflow.remove_draft_route" in names
        assert "wf.workflow.remove_draft_step" in names
        assert "wf.workflow.remove_draft_binding" in names
        assert "wf.workflow.create_minimal_draft_workspace" in names
        assert "wf.workflow.create_artifact_from_workspace" in names
        assert "wf.workflow.create_wrapper_from_workspace" in names
        assert "wf.workflow.inspect_artifact" in names
        assert "wf.workflow.list_deployments" in names
        assert "wf.workflow.inspect_deployment" in names
        assert "wf.workflow.save_deployment" in names
        assert "wf.workflow.delete_deployment" in names
        assert "wf.workflow.validate_deployment" in names
        assert "wf.workflow.run_deployment" in names

        assert "wf.workflow.validate_draft" not in names
        assert "wf.workflow.compile_draft" not in names
        assert "wf.workflow.create_artifact_from_plan" not in names
        assert "wf.workflow.create_artifact_from_draft" not in names
        assert "wf.workflow.patch_draft" not in names
        assert "wf.admin.call_tool" not in names
        assert "fixture.personal.echo_tool" not in names


@pytest.mark.asyncio
async def test_registered_output_bindings_tool_delegates_typed_bindings_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class RecordingWorkflowHandler:
        def __init__(self) -> None:
            self.calls: list[dict[str, Any]] = []

        async def set_step_output_bindings(self, **kwargs: Any) -> dict[str, Any]:
            self.calls.append(kwargs)
            return {
                "workspace_id": kwargs["workspace_id"],
                "revision": kwargs["revision"] + 1,
                "status": "valid",
                "diagnostics": [],
                "summary": {},
            }

    recorder = RecordingWorkflowHandler()
    monkeypatch.setattr(
        "wf_mcp.workflow_surface.tools.WorkflowApi",
        lambda _context: recorder,
    )
    service = WfMcpService(
        store=FileStore(tmp_path / "tool_invocation_store"),
        artifact_store=FileWorkflowArtifactStore(
            tmp_path / "tool_invocation_artifacts"
        ),
        draft_workspace_store=FileDraftWorkspaceStore(
            tmp_path / "tool_invocation_drafts"
        ),
    )
    server = FastMCP("task-3-tool-test")
    register_workflow_tools(server, service)

    async with Client(FastMCPTransport(server)) as client:
        result = await client.call_tool(
            "wf.workflow.set_step_output_bindings",
            {
                "request": {
                    "workspace_id": "draft-output",
                    "revision": 4,
                    "step_id": "analyze",
                    "bindings": [
                        {"source": "report.title", "target": "state.report.title"},
                        {"source": "report.title", "target": "state.audit.title"},
                    ],
                }
            },
        )

    assert structured(result)["revision"] == 5
    assert len(recorder.calls) == 1
    call = recorder.calls[0]
    assert call["workspace_id"] == "draft-output"
    assert call["revision"] == 4
    assert call["step_id"] == "analyze"
    bindings = call["bindings"]
    assert all(isinstance(binding, OutputBinding) for binding in bindings)
    assert [(str(binding.source), str(binding.target)) for binding in bindings] == [
        ("report.title", "state.report.title"),
        ("report.title", "state.audit.title"),
    ]


@pytest.mark.asyncio
async def test_registered_workflow_output_bindings_tool_preserves_union_order(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class RecordingWorkflowHandler:
        def __init__(self) -> None:
            self.calls: list[dict[str, Any]] = []

        async def set_workflow_output_bindings(self, **kwargs: Any) -> dict[str, Any]:
            self.calls.append(kwargs)
            return {
                "workspace_id": kwargs["workspace_id"],
                "revision": kwargs["revision"] + 1,
                "status": "valid",
                "diagnostics": [],
                "summary": {},
            }

    recorder = RecordingWorkflowHandler()
    monkeypatch.setattr(
        "wf_mcp.workflow_surface.tools.WorkflowApi",
        lambda _context: recorder,
    )
    service = WfMcpService(
        store=FileStore(tmp_path / "workflow_output_tool_store"),
        artifact_store=FileWorkflowArtifactStore(
            tmp_path / "workflow_output_tool_artifacts"
        ),
        draft_workspace_store=FileDraftWorkspaceStore(
            tmp_path / "workflow_output_tool_drafts"
        ),
    )
    server = FastMCP("workflow-output-bindings-test")
    register_workflow_tools(server, service)

    async with Client(FastMCPTransport(server)) as client:
        result = await client.call_tool(
            "wf.workflow.set_workflow_output_bindings",
            {
                "request": {
                    "workspace_id": "draft-output",
                    "revision": 4,
                    "bindings": [
                        {
                            "path": "state.report.title",
                            "target": "report.title",
                        },
                        {"value": "markdown", "target": "format"},
                    ],
                }
            },
        )

    assert structured(result)["revision"] == 5
    call = recorder.calls[0]
    assert isinstance(call["bindings"][0], InputPathBinding)
    assert isinstance(call["bindings"][1], InputValueBinding)
    assert [binding.model_dump(mode="json") for binding in call["bindings"]] == [
        {"path": "state.report.title", "target": "report.title"},
        {"value": "markdown", "target": "format"},
    ]


@pytest.mark.asyncio
async def test_server_search_mode_can_use_safe_tool_names() -> None:
    config = server_config()

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

        result = await assert_safe_tool_maps(
            client,
            original_name="wf.admin.list_sources",
            safe_name="wf_admin_list_sources",
        )
        source_ids = {source["id"] for source in result["sources"]}
        assert "wf.std" in source_ids


@pytest.mark.asyncio
async def test_server_safe_tool_names_adapts_dotted_runtime_names() -> None:
    config = server_config()

    client = create_server_client(config, safe_tool_names=True)
    async with client:
        artifacts = await assert_safe_tool_maps(
            client,
            original_name="wf.workflow.list_artifacts",
            safe_name="wf_workflow_list_artifacts",
        )
        echo = await assert_safe_tool_maps(
            client,
            original_name="fixture.personal.echo_tool",
            safe_name="fixture_personal_echo_tool",
            arguments={"text": "hello"},
        )

        assert artifacts["nodes"] == []
        assert artifacts["total"] == 0
        assert echo["echoed"] == "hello"


@pytest.mark.asyncio
async def test_workflow_tools_have_human_metadata(tmp_path: Path) -> None:
    config = BrokerConfig(
        store_root=tmp_path / "unified_metadata_store",
        connections=[],
    )

    client = create_server_client(config, admin_tools=False)
    async with client:
        tools = await client.list_tools()
        by_name = {tool.name: tool for tool in tools}
        list_artifacts = by_name["wf.workflow.list_artifacts"]
        validate_deployment = by_name["wf.workflow.validate_deployment"]
        run_deployment = by_name["wf.workflow.run_deployment"]
        inspect_run = by_name["wf.workflow.inspect_run"]
        read_run_trace = by_name["wf.workflow.read_run_trace"]

        assert list_artifacts.title == "List Workflow Artifacts"
        assert "saved workflow artifacts" in (list_artifacts.description or "")
        assert "query" in list_artifacts.inputSchema["properties"]
        assert "kind" in list_artifacts.inputSchema["properties"]
        assert "cursor" in list_artifacts.inputSchema["properties"]
        assert "limit" in list_artifacts.inputSchema["properties"]
        live_check_schema = validate_deployment.inputSchema["properties"]["live_check"]
        assert "upstream" in live_check_schema.get("description", "")
        assert run_deployment.title == "Run Workflow Deployment"
        assert "deployment_id" in (run_deployment.description or "")
        assert "trace_range" in run_deployment.inputSchema["properties"]
        trace_range_schema = run_deployment.inputSchema["properties"]["trace_range"]
        assert "Debug traces" in trace_range_schema.get("description", "")
        assert "null" in [option.get("type") for option in trace_range_schema["anyOf"]]
        assert inspect_run.title == "Inspect Workflow Run"
        assert "trace" in (inspect_run.description or "").lower()
        read_trace_schema = read_run_trace.inputSchema["properties"]["trace_range"]
        assert "Debug traces" in read_trace_schema.get("description", "")


@pytest.mark.asyncio
async def test_create_artifact_from_plan_exposes_plan_as_plain_object(
    tmp_path: Path,
) -> None:
    config = BrokerConfig(
        store_root=tmp_path / "unified_create_artifact_schema_store",
        connections=[],
    )

    client = create_server_client(config, admin_tools=False)
    async with client:
        tools = await client.list_tools()
        by_name = {tool.name: tool for tool in tools}
        schema = by_name["wf.workflow.create_artifact_from_plan"].inputSchema
        plan_schema = schema["properties"]["plan"]

        assert plan_schema["type"] == "object"
        assert plan_schema.get("additionalProperties") is True


@pytest.mark.asyncio
async def test_draft_tools_expose_plain_object_and_patch_array_schemas(
    tmp_path: Path,
) -> None:
    config = BrokerConfig(
        store_root=tmp_path / "unified_draft_schema_store",
        connections=[],
    )

    client = create_server_client(config, admin_tools=False)
    async with client:
        tools = await client.list_tools()
        by_name = {tool.name: tool for tool in tools}

        validate_schema = by_name["wf.workflow.validate_draft"].inputSchema
        validate_draft_schema = validate_schema["properties"]["draft"]
        create_schema = by_name["wf.workflow.create_artifact_from_draft"].inputSchema
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


@pytest.mark.asyncio
async def test_admin_tools_have_human_metadata(tmp_path: Path) -> None:
    config = BrokerConfig(
        store_root=tmp_path / "unified_admin_metadata_store",
        connections=[],
    )

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
