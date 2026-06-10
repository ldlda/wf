from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from wf_api.saved_subgraphs import resolve_saved_subgraph_tree
from wf_artifacts import (
    FileRunStore,
    FileWorkflowArtifactStore,
    RequiredCapability,
    ResumeReadiness,
    WorkflowArtifact,
    WorkflowDeployment,
)
from wf_mcp.broker import WfMcpService
from wf_mcp.models import ConnectionConfig
from wf_mcp.storage import FileStore
from wf_mcp.workflow_surface import WorkflowSurfaceHandlers

from .test_support import echo_tool, input_binding, output_binding


def test_saved_subgraph_tree_loads_exact_child_artifact_version(tmp_path: Path) -> None:
    store = FileWorkflowArtifactStore(tmp_path / "saved_subgraph_tree")
    parent = _parent_artifact()
    store.save_artifact(_leaf_artifact())

    resolution = resolve_saved_subgraph_tree(
        root_artifact=parent,
        artifact_store=store,
    )

    assert resolution.diagnostics == []
    assert resolution.artifacts_by_ref["workflow.child.v1"].id == "child"
    assert resolution.artifacts_by_ref["workflow.child.v1"].version == 1


def test_saved_subgraph_tree_reports_missing_child_artifact(tmp_path: Path) -> None:
    store = FileWorkflowArtifactStore(tmp_path / "saved_subgraph_missing")

    resolution = resolve_saved_subgraph_tree(
        root_artifact=_parent_artifact(),
        artifact_store=store,
    )

    assert len(resolution.diagnostics) == 1
    assert resolution.diagnostics[0].code == "workflow_dependency_missing"
    assert resolution.diagnostics[0].logical_ref == "workflow.child.v1"


def test_saved_subgraph_tree_reports_recursive_child_cycle(tmp_path: Path) -> None:
    store = FileWorkflowArtifactStore(tmp_path / "saved_subgraph_cycle")
    parent = _parent_artifact()
    child = _parent_artifact(
        artifact_id="child",
        title="Child",
        child_artifact_id="parent",
    )
    store.save_artifact(parent)
    store.save_artifact(child)

    resolution = resolve_saved_subgraph_tree(
        root_artifact=parent,
        artifact_store=store,
    )

    assert len(resolution.diagnostics) == 1
    assert resolution.diagnostics[0].code == "workflow_dependency_cycle"
    assert resolution.diagnostics[0].logical_ref == "workflow.parent.v1"


def test_saved_child_uses_parent_deployment_binding_for_validation(
    tmp_path: Path,
) -> None:
    store = FileWorkflowArtifactStore(tmp_path / "saved_subgraph_validate")
    store.save_artifact(_parent_artifact())
    store.save_artifact(_leaf_artifact())
    store.save_deployment(_deployment())
    handlers = _handlers(store, tmp_path)

    result = asyncio.run(handlers.validate_deployment(deployment_id="parent.personal"))

    assert result["status"] == "runnable"
    assert result["diagnostics"] == []


def test_saved_child_missing_parent_binding_is_unrunnable(tmp_path: Path) -> None:
    store = FileWorkflowArtifactStore(tmp_path / "saved_subgraph_unbound")
    store.save_artifact(_parent_artifact())
    store.save_artifact(_leaf_artifact())
    store.save_deployment(_deployment(bindings={}))
    handlers = _handlers(store, tmp_path)

    result = asyncio.run(handlers.validate_deployment(deployment_id="parent.personal"))

    assert result["status"] == "unrunnable"
    assert result["diagnostics"][0]["code"] == "binding_missing"
    assert result["diagnostics"][0]["logical_ref"] == "demo.echo_tool"


def test_interrupting_saved_child_pauses_and_resumes_through_deployment_surface(
    tmp_path: Path,
) -> None:
    store = FileWorkflowArtifactStore(tmp_path / "saved_subgraph_interrupt")
    store.save_artifact(_parent_artifact())
    store.save_artifact(_interrupting_child_artifact())
    store.save_deployment(_deployment())
    handlers = _handlers(store, tmp_path)

    validation = asyncio.run(
        handlers.validate_deployment(deployment_id="parent.personal")
    )

    assert validation["status"] == "runnable"
    assert validation["diagnostics"] == []

    paused = asyncio.run(
        handlers.run_deployment(
            deployment_id="parent.personal",
            workflow_input={"text": "hello"},
        )
    )

    assert paused["status"] == "interrupted"
    assert isinstance(paused["run_id"], str)
    assert paused["interrupt"]["node_id"] == "child_step"
    assert paused["interrupt"]["payload"]["question"] == "hello"

    # Durable resume must not rely on the process-local handler instance.
    handlers = _handlers(store, tmp_path)
    resumed = asyncio.run(
        handlers.resume_run(
            run_id=paused["run_id"],
            resume_payload={"answer": "world"},
        )
    )

    assert resumed["status"] == "completed"
    assert resumed["outcome"] == "ok"
    assert resumed["output"]["echoed"] == "world"


def test_interrupted_saved_child_blocks_resume_until_pinned_source_returns(
    tmp_path: Path,
) -> None:
    store = FileWorkflowArtifactStore(tmp_path / "saved_subgraph_blocked")
    store.save_artifact(_parent_artifact())
    store.save_artifact(_interrupting_child_artifact(requires_demo=True))
    store.save_deployment(_deployment())
    handlers = _handlers(store, tmp_path)

    paused = asyncio.run(
        handlers.run_deployment(
            deployment_id="parent.personal",
            workflow_input={"text": "hello"},
        )
    )
    run_store = handlers.service.run_store
    assert run_store is not None

    handlers.service.capability_sources["demo.personal"].enabled = False
    blocked = asyncio.run(
        handlers.resume_run(
            run_id=paused["run_id"],
            resume_payload={"answer": "world"},
        )
    )

    assert blocked["status"] == "interrupted"
    assert blocked["resume_readiness"] == "blocked"
    assert blocked["diagnostics"][0]["code"] == "source_disabled"
    assert (
        run_store.get_run(paused["run_id"]).resume_readiness is ResumeReadiness.BLOCKED
    )
    assert run_store.get_latest_checkpoint(paused["run_id"]).sequence == 1

    handlers.service.capability_sources["demo.personal"].enabled = True
    resumed = asyncio.run(
        handlers.resume_run(
            run_id=paused["run_id"],
            resume_payload={"answer": "world"},
        )
    )

    assert resumed["status"] == "completed"
    assert resumed["resume_readiness"] == "not_applicable"
    assert resumed["output"]["echoed"] == "world"
    assert run_store.get_latest_checkpoint(paused["run_id"]).sequence == 2


def test_missing_saved_child_is_unrunnable_on_deployment_surface(
    tmp_path: Path,
) -> None:
    store = FileWorkflowArtifactStore(tmp_path / "saved_subgraph_missing_run")
    store.save_artifact(_parent_artifact())
    store.save_deployment(_deployment())
    handlers = _handlers(store, tmp_path)

    result = asyncio.run(handlers.validate_deployment(deployment_id="parent.personal"))

    assert result["status"] == "unrunnable"
    assert result["diagnostics"][0]["code"] == "workflow_dependency_missing"
    assert result["diagnostics"][0]["logical_ref"] == "workflow.child.v1"


def test_cyclic_saved_child_is_unrunnable_on_deployment_surface(tmp_path: Path) -> None:
    store = FileWorkflowArtifactStore(tmp_path / "saved_subgraph_cycle_run")
    store.save_artifact(_parent_artifact())
    store.save_artifact(
        _parent_artifact(
            artifact_id="child",
            title="Child",
            child_artifact_id="parent",
        )
    )
    store.save_deployment(_deployment())
    handlers = _handlers(store, tmp_path)

    result = asyncio.run(handlers.validate_deployment(deployment_id="parent.personal"))

    assert result["status"] == "unrunnable"
    assert result["diagnostics"][0]["code"] == "workflow_dependency_cycle"
    assert result["diagnostics"][0]["logical_ref"] == "workflow.parent.v1"


def test_saved_child_runs_natively_with_parent_deployment_binding(
    tmp_path: Path,
) -> None:
    store = FileWorkflowArtifactStore(tmp_path / "saved_subgraph_run")
    store.save_artifact(_parent_artifact())
    store.save_artifact(_leaf_artifact())
    store.save_deployment(_deployment())
    handlers = _handlers(store, tmp_path)

    result = asyncio.run(
        handlers.run_deployment(
            deployment_id="parent.personal",
            workflow_input={"text": "hello"},
        )
    )

    assert result["status"] == "completed"
    assert result["output"]["echoed"] == "hello"
    assert result["diagnostics"] == []


def test_nested_saved_child_inherits_root_deployment_binding(tmp_path: Path) -> None:
    store = FileWorkflowArtifactStore(tmp_path / "saved_subgraph_nested_run")
    store.save_artifact(_parent_artifact(child_artifact_id="middle"))
    store.save_artifact(
        _parent_artifact(
            artifact_id="middle",
            title="Middle",
            child_artifact_id="child",
        )
    )
    store.save_artifact(_leaf_artifact())
    store.save_deployment(_deployment())
    handlers = _handlers(store, tmp_path)

    result = asyncio.run(
        handlers.run_deployment(
            deployment_id="parent.personal",
            workflow_input={"text": "hello"},
        )
    )

    assert result["status"] == "completed"
    assert result["output"]["echoed"] == "hello"
    assert result["diagnostics"] == []


def _leaf_artifact() -> WorkflowArtifact:
    plan: dict[str, Any] = {
        "name": "child",
        "input_schema": _io_schema("text"),
        "state_schema": {"fields": {"echoed": {"type": "string"}}},
        "output_schema": _io_schema("echoed"),
        "start": "echo",
        "nodes": [
            {
                "id": "echo",
                "type": "node",
                "node": "demo.echo_tool",
                "input": [input_binding("input.text", "text")],
                "output": [output_binding("echoed", "state.echoed")],
            }
        ],
        "edges": [{"from": "echo", "outcome": "ok", "to": "__end__"}],
    }
    return WorkflowArtifact(
        id="child",
        version=1,
        title="Child",
        input_schema=plan["input_schema"],
        output_schema=plan["output_schema"],
        outcomes=("completed",),
        plan=plan,
        required_capabilities=[
            RequiredCapability(ref="demo.echo_tool", kind="node_spec")
        ],
    )


def _parent_artifact(
    *,
    artifact_id: str = "parent",
    title: str = "Parent",
    child_artifact_id: str = "child",
) -> WorkflowArtifact:
    plan: dict[str, Any] = {
        "name": artifact_id,
        "input_schema": _io_schema("text"),
        "state_schema": {"fields": {"echoed": {"type": "string"}}},
        "output_schema": _io_schema("echoed"),
        "start": "child_step",
        "nodes": [
            {
                "id": "child_step",
                "type": "subgraph",
                "workflow": {"artifact_id": child_artifact_id, "version": 1},
                "input_schema": _io_schema("text"),
                "output_schema": _io_schema("echoed"),
                "input": [input_binding("input.text", "text")],
                "output": [output_binding("echoed", "state.echoed")],
            }
        ],
        "edges": [{"from": "child_step", "outcome": "ok", "to": "__end__"}],
    }
    return WorkflowArtifact(
        id=artifact_id,
        version=1,
        title=title,
        input_schema=plan["input_schema"],
        output_schema=plan["output_schema"],
        outcomes=("completed",),
        plan=plan,
    )


def _io_schema(field: str) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {field: {"type": "string"}},
        "required": [field],
    }


def _interrupting_child_artifact(*, requires_demo: bool = False) -> WorkflowArtifact:
    plan: dict[str, Any] = {
        "name": "child",
        "input_schema": _io_schema("text"),
        "state_schema": {"fields": {"echoed": {"type": "string"}}},
        "output_schema": _io_schema("echoed"),
        "start": "ask",
        "nodes": [
            {
                "id": "ask",
                "type": "interrupt",
                "kind": "input",
                "request": [input_binding("input.text", "question")],
                "resume": [output_binding("answer", "state.echoed")],
            }
        ],
        "edges": [{"from": "ask", "outcome": "submitted", "to": "__end__"}],
    }
    return WorkflowArtifact(
        id="child",
        version=1,
        title="Interrupting Child",
        input_schema=plan["input_schema"],
        output_schema=plan["output_schema"],
        outcomes=("completed",),
        plan=plan,
        required_capabilities=(
            [RequiredCapability(ref="demo.echo_tool", kind="node_spec")]
            if requires_demo
            else []
        ),
    )


def _deployment(*, bindings: dict[str, str] | None = None) -> WorkflowDeployment:
    return WorkflowDeployment(
        id="parent.personal",
        artifact_id="parent",
        artifact_version=1,
        bindings={"demo": "demo.personal"} if bindings is None else bindings,
    )


def _handlers(
    artifact_store: FileWorkflowArtifactStore, tmp_path: Path
) -> WorkflowSurfaceHandlers:
    mcp_root = tmp_path / f"{artifact_store.root.name}_mcp"
    service = WfMcpService(
        store=FileStore(mcp_root),
        artifact_store=artifact_store,
        run_store=FileRunStore(mcp_root),
    )
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_specs("demo.personal", echo_tool)
    return WorkflowSurfaceHandlers(service)
