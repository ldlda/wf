from __future__ import annotations

import asyncio

from wf_artifacts import FileWorkflowArtifactStore, WorkflowDeployment
from wf_authoring import node, reducer
from wf_mcp.broker import WfMcpService
from wf_mcp.models import ConnectionConfig
from wf_mcp.storage import FileStore
from wf_mcp.workflow_surface import TraceRange, WorkflowSurfaceHandlers
from wf_platform import (
    CapabilityBuckets,
    CapabilitySource,
    SourcePermissions,
    SourceVisibility,
)

from ..test_support import echo_tool, input_binding, local_temp_root, output_binding
from .conftest import (
    AmountInput,
    AmountOutput,
    amount_tool,
    changed_echo_tool,
    custom_reducer_artifact,
    echo_artifact,
    echo_draft,
    failing_artifact,
    failing_tool,
    handlers,
    logical_echo_artifact,
    multiply,
)


def test_raw_workflow_plan_uses_core_step_and_edge_models() -> None:
    from wf_mcp.models import RawWorkflowPlan

    plan = RawWorkflowPlan.model_validate(echo_artifact().plan)

    assert plan.nodes[0].type == "node"
    assert plan.edges[0].outcome == "ok"


def test_workflow_surface_runs_non_interrupting_deployment() -> None:
    artifact_store = FileWorkflowArtifactStore(local_temp_root() / "surface_run")
    artifact_store.save_artifact(echo_artifact())
    artifact_store.save_deployment(
        WorkflowDeployment(
            id="echo.personal",
            artifact_id="echo",
            artifact_version=1,
            bindings=[{"logical_source": "demo", "concrete_source": "demo.personal"}],
        )
    )
    service = WfMcpService(
        store=FileStore(local_temp_root() / "surface_run_mcp"),
        artifact_store=artifact_store,
    )
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_specs("demo.personal", echo_tool)
    h = WorkflowSurfaceHandlers(service)

    payload = asyncio.run(
        h.run_deployment(
            deployment_id="echo.personal",
            workflow_input={"text": "hello"},
        )
    )

    assert payload["status"] == "completed"
    assert isinstance(payload["run_id"], str)
    assert payload["output"]["echoed"] == "hello"
    assert payload["diagnostics"] == []
    assert payload["trace_count"] == 1
    assert "trace" not in payload

    inspected = asyncio.run(h.inspect_run(run_id=payload["run_id"]))
    traced = asyncio.run(
        h.read_run_trace(
            run_id=payload["run_id"],
            trace_range=TraceRange(start=0, limit=1),
        )
    )

    assert inspected["run_id"] == payload["run_id"]
    assert inspected["status"] == "completed"
    assert inspected["trace_count"] == 1
    assert "trace" not in inspected
    assert traced["trace_count"] == 1
    assert traced["trace_start"] == 0
    assert traced["trace_limit"] == 1
    assert traced["trace"][0]["node_id"] == "echo"
    assert traced["trace_truncated"] is False


def test_workflow_surface_failed_deployment_exposes_error_on_run_and_inspect() -> None:
    artifact_store = FileWorkflowArtifactStore(
        local_temp_root() / "surface_failed_run_error"
    )
    artifact_store.save_artifact(failing_artifact())
    artifact_store.save_deployment(
        WorkflowDeployment(
            id="fail.personal",
            artifact_id="fail",
            artifact_version=1,
            bindings=[{"logical_source": "demo", "concrete_source": "demo.personal"}],
        )
    )
    service = WfMcpService(
        store=FileStore(local_temp_root() / "surface_failed_run_error_mcp"),
        artifact_store=artifact_store,
    )
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_specs("demo.personal", failing_tool)
    h = WorkflowSurfaceHandlers(service)

    payload = asyncio.run(
        h.run_deployment(
            deployment_id="fail.personal",
            workflow_input={"message": "hello"},
        )
    )
    inspected = asyncio.run(h.inspect_run(run_id=payload["run_id"]))

    assert payload["status"] == "failed"
    assert "upstream exploded" in payload["error"]
    assert payload["trace_count"] == 0
    assert inspected["status"] == "failed"
    assert inspected["error"] == payload["error"]


def test_workflow_surface_run_deployment_can_include_trace_detail() -> None:
    artifact_store = FileWorkflowArtifactStore(
        local_temp_root() / "surface_run_trace_detail"
    )
    artifact_store.save_artifact(echo_artifact())
    artifact_store.save_deployment(
        WorkflowDeployment(
            id="echo.personal",
            artifact_id="echo",
            artifact_version=1,
            bindings=[{"logical_source": "demo", "concrete_source": "demo.personal"}],
        )
    )
    service = WfMcpService(
        store=FileStore(local_temp_root() / "surface_run_trace_detail_mcp"),
        artifact_store=artifact_store,
    )
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_specs("demo.personal", echo_tool)
    h = WorkflowSurfaceHandlers(service)

    payload = asyncio.run(
        h.run_deployment(
            deployment_id="echo.personal",
            workflow_input={"text": "hello"},
            trace_range=TraceRange(start=0, limit=10),
        )
    )

    assert payload["status"] == "completed"
    assert payload["trace_count"] == 1
    assert payload["trace_start"] == 0
    assert payload["trace_limit"] == 10
    assert payload["trace_truncated"] is False
    assert len(payload["trace"]) == 1
    assert payload["trace"][0]["node_id"] == "echo"
    assert payload["trace"][0]["outcome"] == "ok"


def test_workflow_surface_run_deployment_can_read_empty_trace_range() -> None:
    artifact_store = FileWorkflowArtifactStore(
        local_temp_root() / "surface_run_trace_empty_range"
    )
    artifact_store.save_artifact(echo_artifact())
    artifact_store.save_deployment(
        WorkflowDeployment(
            id="echo.personal",
            artifact_id="echo",
            artifact_version=1,
            bindings=[{"logical_source": "demo", "concrete_source": "demo.personal"}],
        )
    )
    service = WfMcpService(
        store=FileStore(local_temp_root() / "surface_run_trace_empty_range_mcp"),
        artifact_store=artifact_store,
    )
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_specs("demo.personal", echo_tool)
    h = WorkflowSurfaceHandlers(service)

    payload = asyncio.run(
        h.run_deployment(
            deployment_id="echo.personal",
            workflow_input={"text": "hello"},
            trace_range=TraceRange(start=5, limit=10),
        )
    )

    assert payload["trace_count"] == 1
    assert payload["trace_start"] == 5
    assert payload["trace_limit"] == 10
    assert payload["trace"] == []
    assert payload["trace_truncated"] is False


def test_workflow_surface_runs_deployment_with_bound_node_spec_dependency() -> None:
    artifact_store = FileWorkflowArtifactStore(local_temp_root() / "surface_bound_node")
    artifact_store.save_artifact(logical_echo_artifact())
    artifact_store.save_deployment(
        WorkflowDeployment(
            id="echo.personal",
            artifact_id="logical_echo",
            artifact_version=1,
            bindings=[{"logical_source": "demo", "concrete_source": "demo.personal"}],
        )
    )
    service = WfMcpService(
        store=FileStore(local_temp_root() / "surface_bound_node_mcp"),
        artifact_store=artifact_store,
    )
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_specs("demo.personal", echo_tool)
    h = WorkflowSurfaceHandlers(service)

    payload = asyncio.run(
        h.run_deployment(
            deployment_id="echo.personal",
            workflow_input={"text": "hello"},
        )
    )

    assert payload["status"] == "completed"
    assert payload["output"]["echoed"] == "hello"
    assert payload["diagnostics"] == []


def test_workflow_surface_runs_artifact_created_from_concrete_node_ref() -> None:
    artifact_store = FileWorkflowArtifactStore(
        local_temp_root() / "surface_created_bound_node"
    )
    service = WfMcpService(
        store=FileStore(local_temp_root() / "surface_created_bound_node_mcp"),
        artifact_store=artifact_store,
    )
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_specs("demo.personal", echo_tool)
    h = WorkflowSurfaceHandlers(service)

    asyncio.run(
        h.create_artifact_from_plan(
            artifact_id="created_echo",
            version=1,
            title="Created Echo",
            plan=echo_artifact().plan,
            outcomes=("completed",),
            source_bindings={"demo": "demo.personal"},
        )
    )
    artifact_store.save_deployment(
        WorkflowDeployment(
            id="created_echo.personal",
            artifact_id="created_echo",
            artifact_version=1,
            bindings={
                "demo": "demo.personal",
                "wf.std": "wf.std",
            },
        )
    )

    payload = asyncio.run(
        h.run_deployment(
            deployment_id="created_echo.personal",
            workflow_input={"text": "hello"},
        )
    )
    artifact = artifact_store.get_artifact("created_echo", 1)

    assert artifact.plan["nodes"][0]["node"] == "demo.echo_tool"
    assert artifact.required_capability_map()["demo.echo_tool"].logical_source == "demo"
    assert payload["status"] == "completed"
    assert payload["output"]["echoed"] == "hello"
    assert payload["diagnostics"] == []


def test_workflow_surface_detects_drift_from_saved_node_spec_snapshot() -> None:
    artifact_store = FileWorkflowArtifactStore(
        local_temp_root() / "surface_created_drift"
    )
    service = WfMcpService(
        store=FileStore(local_temp_root() / "surface_created_drift_mcp"),
        artifact_store=artifact_store,
    )
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_specs("demo.personal", echo_tool)
    h = WorkflowSurfaceHandlers(service)

    asyncio.run(
        h.create_artifact_from_plan(
            artifact_id="created_echo_drift",
            version=1,
            title="Created Echo Drift",
            plan=echo_artifact().plan,
            outcomes=("completed",),
            source_bindings={"demo": "demo.personal"},
        )
    )
    artifact_store.save_deployment(
        WorkflowDeployment(
            id="created_echo_drift.personal",
            artifact_id="created_echo_drift",
            artifact_version=1,
            bindings={
                "demo": "demo.personal",
                "wf.std": "wf.std",
            },
        )
    )

    required = artifact_store.get_artifact(
        "created_echo_drift",
        1,
    ).required_capability_map()["demo.echo_tool"]
    assert required.input_schema_hash is not None

    service.register_connection(
        ConnectionConfig(id="demo.work", server="demo", account="work")
    )
    service.register_specs("demo.work", changed_echo_tool)
    artifact_store.save_deployment(
        WorkflowDeployment(
            id="created_echo_drift.work",
            artifact_id="created_echo_drift",
            artifact_version=1,
            bindings={
                "demo": "demo.work",
                "wf.std": "wf.std",
            },
        )
    )

    payload = asyncio.run(
        h.validate_deployment(deployment_id="created_echo_drift.work")
    )

    assert payload["status"] == "unrunnable"
    assert payload["diagnostics"][0]["code"] == "schema_changed"


def test_workflow_surface_runs_deployment_with_bound_reducer_dependency() -> None:
    artifact_store = FileWorkflowArtifactStore(local_temp_root() / "surface_reducer")
    artifact_store.save_artifact(custom_reducer_artifact())
    artifact_store.save_deployment(
        WorkflowDeployment(
            id="multiply.personal",
            artifact_id="multiply",
            artifact_version=1,
            bindings={
                "demo": "demo.personal",
                "custom": "custom.default",
            },
        )
    )
    service = WfMcpService(
        store=FileStore(local_temp_root() / "surface_reducer_mcp"),
        artifact_store=artifact_store,
    )
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_specs("demo.personal", amount_tool)
    service.register_capability_source(
        CapabilitySource(
            id="custom.default",
            kind="system",
            capabilities=CapabilityBuckets(
                reducers={multiply.definition.spec.name: multiply.definition.spec},
                reducer_definitions={
                    multiply.definition.spec.name: multiply.definition,
                },
            ),
            visibility=SourceVisibility(planner=True),
            permissions=SourcePermissions(safe_for_workflow=True),
        )
    )
    h = WorkflowSurfaceHandlers(service)

    payload = asyncio.run(
        h.run_deployment(
            deployment_id="multiply.personal",
            workflow_input={"total": 2, "amount": 3},
        )
    )

    assert payload["status"] == "completed"
    assert payload["output"]["total"] == 6
    assert payload["diagnostics"] == []
