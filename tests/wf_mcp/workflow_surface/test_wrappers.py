from __future__ import annotations

import asyncio

from wf_artifacts import FileWorkflowArtifactStore, WorkflowDeployment
from wf_mcp.broker import WfMcpService
from wf_mcp.models import ConnectionConfig
from wf_mcp.storage import FileStore
from wf_mcp.workflow_surface import WorkflowSurfaceHandlers

from ..test_support import echo_tool, local_temp_root
from .conftest import echo_artifact, logical_echo_artifact


def test_workflow_surface_creates_wrapper_artifact_from_plan() -> None:
    artifact_store = FileWorkflowArtifactStore(
        local_temp_root() / "surface_wrapper_plan"
    )
    service = WfMcpService(
        store=FileStore(local_temp_root() / "surface_wrapper_plan_mcp"),
        artifact_store=artifact_store,
    )
    h = WorkflowSurfaceHandlers(service)

    payload = asyncio.run(
        h.create_artifact_from_plan(
            artifact_id="echo_wrapper",
            version=1,
            title="Echo Wrapper",
            kind="wrapper",
            plan=echo_artifact().plan,
            outcomes=("completed",),
        )
    )
    artifact = artifact_store.get_artifact("echo_wrapper", 1)

    assert payload["saved"] is True
    assert artifact.kind == "wrapper"


def test_workflow_surface_creates_artifact_with_logical_node_refs() -> None:
    artifact_store = FileWorkflowArtifactStore(
        local_temp_root() / "surface_logical_refs"
    )
    service = WfMcpService(
        store=FileStore(local_temp_root() / "surface_logical_refs_mcp"),
        artifact_store=artifact_store,
    )
    h = WorkflowSurfaceHandlers(service)
    plan = echo_artifact().plan
    plan["nodes"][0]["node"] = "demo.personal.echo_tool"

    asyncio.run(
        h.create_artifact_from_plan(
            artifact_id="echo_logical",
            version=1,
            title="Echo Logical",
            plan=plan,
            outcomes=("completed",),
            source_bindings={"demo": "demo.personal"},
        )
    )
    artifact = artifact_store.get_artifact("echo_logical", 1)

    assert artifact.plan["nodes"][0]["node"] == "demo.echo_tool"
    assert artifact.required_capability_map()["demo.echo_tool"].logical_source == "demo"


def test_workflow_surface_calls_saved_wrapper_artifact() -> None:
    artifact_store = FileWorkflowArtifactStore(
        local_temp_root() / "surface_wrapper_call"
    )
    wrapper = echo_artifact().model_copy(
        update={"id": "echo_wrapper", "kind": "wrapper"}
    )
    artifact_store.save_artifact(wrapper)
    service = WfMcpService(
        store=FileStore(local_temp_root() / "surface_wrapper_call_mcp"),
        artifact_store=artifact_store,
    )
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_specs("demo.personal", echo_tool)
    h = WorkflowSurfaceHandlers(service)

    payload = asyncio.run(
        h.call_capability(
            qualified_name="workflow.echo_wrapper.v1",
            payload={"text": "hello"},
        )
    )

    assert payload["qualified_name"] == "workflow.echo_wrapper.v1"
    assert payload["source_id"] == "workflow"
    assert payload["kind"] == "wrapper_artifact"
    assert payload["diagnostics"] == []
    assert payload["outcome"] == "completed"
    assert payload["output"]["echoed"] == "hello"


def test_workflow_surface_calls_live_node_spec_with_self_describing_response() -> None:
    service = WfMcpService(
        store=FileStore(local_temp_root() / "surface_live_capability_call"),
        artifact_store=FileWorkflowArtifactStore(
            local_temp_root() / "surface_live_capability_call_artifacts"
        ),
    )
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_specs("demo.personal", echo_tool)
    h = WorkflowSurfaceHandlers(service)

    payload = asyncio.run(
        h.call_capability(
            qualified_name="demo.personal.echo_tool",
            payload={"text": "hello"},
        )
    )

    assert payload["qualified_name"] == "demo.personal.echo_tool"
    assert payload["source_id"] == "demo.personal"
    assert payload["kind"] == "node_spec"
    assert payload["diagnostics"] == []
    assert payload["outcome"] == "ok"
    assert payload["output"]["echoed"] == "hello"


def test_workflow_surface_calls_saved_wrapper_artifact_with_deployment_bindings() -> (
    None
):
    artifact_store = FileWorkflowArtifactStore(
        local_temp_root() / "surface_wrapper_bound_call"
    )
    wrapper = logical_echo_artifact().model_copy(
        update={"id": "logical_echo_wrapper", "kind": "wrapper"}
    )
    artifact_store.save_artifact(wrapper)
    artifact_store.save_deployment(
        WorkflowDeployment(
            id="logical_echo_wrapper.personal",
            artifact_id="logical_echo_wrapper",
            artifact_version=1,
            bindings=[{"logical_source": "demo", "concrete_source": "demo.personal"}],
        )
    )
    service = WfMcpService(
        store=FileStore(local_temp_root() / "surface_wrapper_bound_call_mcp"),
        artifact_store=artifact_store,
    )
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_specs("demo.personal", echo_tool)
    h = WorkflowSurfaceHandlers(service)

    payload = asyncio.run(
        h.call_capability(
            qualified_name="workflow.logical_echo_wrapper.v1",
            payload={"text": "hello"},
            deployment_id="logical_echo_wrapper.personal",
        )
    )

    assert payload["qualified_name"] == "workflow.logical_echo_wrapper.v1"
    assert payload["source_id"] == "workflow"
    assert payload["kind"] == "wrapper_artifact"
    assert payload["deployment_id"] == "logical_echo_wrapper.personal"
    assert payload["diagnostics"] == []
    assert payload["outcome"] == "completed"
    assert payload["output"]["echoed"] == "hello"
