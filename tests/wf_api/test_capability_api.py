from __future__ import annotations

import asyncio

import pytest

from wf_artifacts import FileWorkflowArtifactStore
from wf_api.capabilities import WorkflowCapabilityApi
from wf_mcp.broker import WfMcpService
from wf_mcp.models import ConnectionConfig
from wf_mcp.storage import FileStore
from wf_mcp.workflow_surface import WorkflowSurfaceHandlers
from wf_mcp.broker.service.workflow_operation_context import context_from_service

from tests.wf_mcp.test_support import echo_tool, local_temp_root
from tests.wf_mcp.workflow_surface.conftest import echo_artifact, failing_tool


def _capability_api(
    artifact_store: FileWorkflowArtifactStore,
    *,
    register_echo: bool = False,
    register_failing: bool = False,
) -> tuple[WorkflowCapabilityApi, WfMcpService]:
    service = WfMcpService(
        store=FileStore(artifact_store.root / "caps_mcp" / str(id(artifact_store))),
        artifact_store=artifact_store,
    )
    if register_echo:
        service.register_connection(
            ConnectionConfig(id="demo.personal", server="demo", account="personal")
        )
        service.register_specs("demo.personal", echo_tool)
    if register_failing:
        service.register_connection(
            ConnectionConfig(id="demo.personal", server="demo", account="personal")
        )
        service.register_specs("demo.personal", failing_tool)
    context = context_from_service(service)
    return WorkflowCapabilityApi(context), service


def test_list_capabilities_returns_planner_visible_sources() -> None:
    artifact_store = FileWorkflowArtifactStore(local_temp_root() / "cap_api_list")
    api, _service = _capability_api(artifact_store, register_echo=True)

    result = asyncio.run(api.list_capabilities())

    assert result["total"] >= 1
    assert any(
        item["name"] == "demo.personal.echo_tool" for item in result["capabilities"]
    )
    first = next(
        item
        for item in result["capabilities"]
        if item["name"] == "demo.personal.echo_tool"
    )
    assert first["kind"] == "node_spec"
    assert "input_fields" in first
    assert "output_fields" in first


def test_list_capabilities_filters_by_source() -> None:
    artifact_store = FileWorkflowArtifactStore(
        local_temp_root() / "cap_api_list_filter"
    )
    api, _service = _capability_api(artifact_store, register_echo=True)

    result = asyncio.run(api.list_capabilities(source_id="wf.std", query="truthy"))

    assert [item["name"] for item in result["capabilities"]] == ["wf.std.truthy"]


def test_inspect_capability_returns_detail_with_wrapper_hints() -> None:
    artifact_store = FileWorkflowArtifactStore(local_temp_root() / "cap_api_inspect")
    api, _service = _capability_api(artifact_store, register_echo=True)

    detail = asyncio.run(
        api.inspect_capability(qualified_name="demo.personal.echo_tool")
    )

    assert detail["name"] == "demo.personal.echo_tool"
    assert "wrapper_hints" in detail
    hints = detail["wrapper_hints"]
    assert hints["capability_name"] == "demo.personal.echo_tool"
    assert hints["input_map"] == {"input.text": "text"}
    assert hints["output_map"] == {"echoed": "state.echoed"}


def test_inspect_capability_raises_on_unknown() -> None:
    artifact_store = FileWorkflowArtifactStore(
        local_temp_root() / "cap_api_inspect_unknown"
    )
    api, _service = _capability_api(artifact_store, register_echo=True)

    with pytest.raises(KeyError, match="no.such.capability"):
        asyncio.run(api.inspect_capability(qualified_name="no.such.capability"))


def test_call_capability_node_spec_success() -> None:
    artifact_store = FileWorkflowArtifactStore(local_temp_root() / "cap_api_call")
    api, _service = _capability_api(artifact_store, register_echo=True)

    result = asyncio.run(
        api.call_capability(
            qualified_name="demo.personal.echo_tool",
            payload={"text": "hello"},
        )
    )

    assert result["kind"] == "node_spec"
    assert result["outcome"] == "ok"
    assert result["output"] == {"echoed": "hello"}
    assert result["diagnostics"] == []
    assert result["deployment_id"] is None


def test_call_capability_node_spec_failure() -> None:
    artifact_store = FileWorkflowArtifactStore(local_temp_root() / "cap_api_call_fail")
    api, _service = _capability_api(artifact_store, register_failing=True)

    result = asyncio.run(
        api.call_capability(
            qualified_name="demo.personal.failing_tool",
            payload={"message": "boom"},
        )
    )

    assert result["kind"] == "node_spec"
    assert result["outcome"] == "runtime_error"
    assert result["output"] is None
    assert result["diagnostics"][0]["code"] == "capability_call_failed"


def test_list_capabilities_includes_saved_wrapper() -> None:
    artifact_store = FileWorkflowArtifactStore(
        local_temp_root() / "cap_api_wrapper_list"
    )
    artifact_store.save_artifact(
        echo_artifact().model_copy(
            update={
                "id": "echo_wrapper",
                "kind": "wrapper",
                "description": "Reusable echo wrapper.",
            }
        )
    )
    api, _service = _capability_api(artifact_store)

    result = asyncio.run(api.list_capabilities(source_id="workflow", query="echo"))

    names = [item["name"] for item in result["capabilities"]]
    assert names == ["workflow.echo_wrapper.v1"]
    row = result["capabilities"][0]
    assert row["source_id"] == "workflow"
    assert row["kind"] == "wrapper_artifact"
    assert row["artifact_id"] == "echo_wrapper"
    assert row["version"] == 1
    assert row["title"] == "Echo"
    assert row["description"] == "Reusable echo wrapper."
    assert row["outcomes"] == ["completed"]
    assert row["input_fields"] == ["text"]
    assert row["output_fields"] == ["echoed"]


def test_inspect_capability_saved_wrapper() -> None:
    artifact_store = FileWorkflowArtifactStore(
        local_temp_root() / "cap_api_wrapper_inspect"
    )
    artifact_store.save_artifact(
        echo_artifact().model_copy(update={"id": "echo_wrapper", "kind": "wrapper"})
    )
    api, _service = _capability_api(artifact_store)

    detail = asyncio.run(
        api.inspect_capability(qualified_name="workflow.echo_wrapper.v1")
    )

    assert detail["name"] == "workflow.echo_wrapper.v1"
    assert detail["source_id"] == "workflow"
    assert detail["kind"] == "wrapper_artifact"
    assert detail["artifact_id"] == "echo_wrapper"
    assert detail["outcomes"] == ["completed"]
    assert "input_schema" in detail
    assert detail["input_schema"]["properties"]["text"]["type"] == "string"
    assert detail["output_schema"]["properties"]["echoed"]["type"] == "string"
    hints = detail["wrapper_hints"]
    assert hints["capability_name"] == "workflow.echo_wrapper.v1"
    assert hints["declared_outcomes"] == ["completed"]
    assert hints["suggested_wrapper_outcomes"] == ["completed"]
    assert hints["input_map"] == {"input.text": "text"}
    assert hints["output_map"] == {"echoed": "state.echoed"}


def test_call_capability_saved_wrapper() -> None:
    artifact_store = FileWorkflowArtifactStore(
        local_temp_root() / "cap_api_wrapper_call"
    )
    artifact_store.save_artifact(
        echo_artifact().model_copy(update={"id": "echo_wrapper", "kind": "wrapper"})
    )
    api, service = _capability_api(artifact_store, register_echo=True)

    result = asyncio.run(
        api.call_capability(
            qualified_name="workflow.echo_wrapper.v1",
            payload={"text": "hi"},
        )
    )

    assert result["kind"] == "wrapper_artifact"
    assert result["outcome"] == "completed"
    assert result["diagnostics"] == []


def test_create_draft_workspace_from_capability() -> None:
    artifact_store = FileWorkflowArtifactStore(
        local_temp_root() / "cap_api_draft_bootstrap"
    )
    api, _service = _capability_api(artifact_store, register_echo=True)

    result = asyncio.run(
        api.create_draft_workspace_from_capability(
            workspace_id="echo_ws",
            capability_name="demo.personal.echo_tool",
        )
    )

    assert result["workspace_id"] == "echo_ws"
    assert result["revision"] == 1
    assert "wrapper_hints" in result
    assert "next_actions" in result
    assert result["wrapper_hints"]["capability_name"] == "demo.personal.echo_tool"

    fetched = asyncio.run(
        api.drafts.get_draft_workspace(workspace_id="echo_ws", include_draft=True)
    )
    assert fetched["draft"]["steps"]["call"]["use"] == "demo.personal.echo_tool"


def test_handler_delegates_to_capability_api() -> None:
    """WorkflowSurfaceHandlers methods produce the same result as direct API."""
    artifact_store = FileWorkflowArtifactStore(local_temp_root() / "cap_api_delegation")
    service = WfMcpService(
        store=FileStore(artifact_store.root / "delegation_mcp"),
        artifact_store=artifact_store,
    )
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_specs("demo.personal", echo_tool)

    h = WorkflowSurfaceHandlers(service)
    context = context_from_service(service)
    api = WorkflowCapabilityApi(context)

    handler_result = asyncio.run(
        h.inspect_capability(qualified_name="demo.personal.echo_tool")
    )
    api_result = asyncio.run(
        api.inspect_capability(qualified_name="demo.personal.echo_tool")
    )

    assert handler_result["name"] == api_result["name"]
    assert handler_result["wrapper_hints"] == api_result["wrapper_hints"]
