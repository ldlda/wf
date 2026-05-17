from __future__ import annotations

import asyncio
from typing import Any

from pydantic import BaseModel

from wf_artifacts import (
    FileWorkflowArtifactStore,
    RequiredCapability,
    WorkflowArtifact,
    WorkflowDeployment,
)
from wf_authoring import node, reducer
from wf_mcp.broker import WfMcpService
from wf_mcp.broker.service.capability_sources import (
    CapabilityBuckets,
    CapabilitySource,
    SourcePermissions,
    SourceVisibility,
)
from wf_mcp.models import ConnectionConfig
from wf_mcp.models import RawWorkflowPlan
from wf_mcp.storage import FileStore
from wf_mcp.workflow_surface import WorkflowSurfaceHandlers

from .test_support import echo_tool, local_temp_root


class AmountInput(BaseModel):
    amount: int


class AmountOutput(BaseModel):
    amount: int


@node()
async def amount_tool(payload: AmountInput) -> AmountOutput:
    return AmountOutput(amount=payload.amount)


@reducer(name="custom.default.multiply")
def multiply(current: int | None, incoming: int) -> int:
    return (current or 1) * incoming


def test_workflow_surface_lists_artifact_catalog_entries() -> None:
    artifact_store = FileWorkflowArtifactStore(local_temp_root() / "surface_artifacts")
    artifact_store.save_artifact(_artifact())
    handlers = _handlers(artifact_store)

    payload = asyncio.run(handlers.list_artifacts())

    nodes = payload["nodes"]
    assert len(nodes) == 1
    assert nodes[0]["name"] == "workflow.summarize_docs.v1"
    assert nodes[0]["artifact_id"] == "summarize_docs"
    assert nodes[0]["version"] == 1
    assert nodes[0]["kind"] == "workflow"
    assert nodes[0]["required_sources"] == ["context7"]
    assert "plan" not in nodes[0]


def test_workflow_surface_validates_deployment_dependencies() -> None:
    artifact_store = FileWorkflowArtifactStore(local_temp_root() / "surface_validate")
    artifact_store.save_artifact(_artifact())
    artifact_store.save_deployment(
        WorkflowDeployment(
            id="summarize_docs.personal",
            artifact_id="summarize_docs",
            artifact_version=1,
            bindings={"context7": "context7.personal"},
        )
    )
    handlers = _handlers(artifact_store)

    payload = asyncio.run(
        handlers.validate_deployment(deployment_id="summarize_docs.personal")
    )

    assert payload["status"] == "unrunnable"
    assert payload["diagnostics"][0]["code"] == "source_missing"


def test_workflow_surface_records_artifact_and_deployment_save_events() -> None:
    artifact_store = FileWorkflowArtifactStore(local_temp_root() / "surface_events")
    handlers = _handlers(artifact_store)

    artifact_payload = asyncio.run(
        handlers.save_artifact(_echo_artifact().model_dump(mode="json"))
    )
    deployment_payload = asyncio.run(
        handlers.save_deployment(
            WorkflowDeployment(
                id="echo.personal",
                artifact_id="echo",
                artifact_version=1,
                bindings={"demo": "demo.personal"},
            ).model_dump(mode="json")
        )
    )

    events = handlers.service.list_events()
    assert artifact_payload["saved"] is True
    assert deployment_payload["saved"] is True
    assert [event.kind for event in events] == [
        "workflow_artifact_saved",
        "workflow_deployment_saved",
    ]
    assert events[0].capability_id == "workflow.echo.v1"
    assert events[1].capability_id == "deployment.echo.personal"


def test_workflow_surface_creates_wrapper_artifact_from_plan() -> None:
    artifact_store = FileWorkflowArtifactStore(
        local_temp_root() / "surface_wrapper_plan"
    )
    handlers = _handlers(artifact_store)

    payload = asyncio.run(
        handlers.create_artifact_from_plan(
            artifact_id="echo_wrapper",
            version=1,
            title="Echo Wrapper",
            kind="wrapper",
            plan=_echo_artifact().plan,
            outcomes=("completed",),
        )
    )
    artifact = artifact_store.get_artifact("echo_wrapper", 1)

    assert payload["saved"] is True
    assert artifact.kind == "wrapper"


def test_raw_workflow_plan_uses_core_step_and_edge_models() -> None:
    plan = RawWorkflowPlan.model_validate(_echo_artifact().plan)

    assert plan.nodes[0].type == "node"
    assert plan.edges[0].outcome == "ok"


def test_workflow_surface_runs_non_interrupting_deployment() -> None:
    artifact_store = FileWorkflowArtifactStore(local_temp_root() / "surface_run")
    artifact_store.save_artifact(_echo_artifact())
    artifact_store.save_deployment(
        WorkflowDeployment(
            id="echo.personal",
            artifact_id="echo",
            artifact_version=1,
            bindings={"demo": "demo.personal"},
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
    handlers = WorkflowSurfaceHandlers(service)

    payload = asyncio.run(
        handlers.run_deployment(
            deployment_id="echo.personal",
            workflow_input={"text": "hello"},
        )
    )

    assert payload["status"] == "completed"
    assert payload["output"]["echoed"] == "hello"
    assert payload["diagnostics"] == []


def test_workflow_surface_runs_deployment_with_bound_reducer_dependency() -> None:
    artifact_store = FileWorkflowArtifactStore(local_temp_root() / "surface_reducer")
    artifact_store.save_artifact(_custom_reducer_artifact())
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
    handlers = WorkflowSurfaceHandlers(service)

    payload = asyncio.run(
        handlers.run_deployment(
            deployment_id="multiply.personal",
            workflow_input={"total": 2, "amount": 3},
        )
    )

    assert payload["status"] == "completed"
    assert payload["output"]["total"] == 6
    assert payload["diagnostics"] == []


def test_workflow_surface_calls_saved_wrapper_artifact() -> None:
    artifact_store = FileWorkflowArtifactStore(
        local_temp_root() / "surface_wrapper_call"
    )
    wrapper = _echo_artifact().model_copy(
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
    handlers = WorkflowSurfaceHandlers(service)

    payload = asyncio.run(
        handlers.call_capability(
            qualified_name="workflow.echo_wrapper.v1",
            payload={"text": "hello"},
        )
    )

    assert payload["qualified_name"] == "workflow.echo_wrapper.v1"
    assert payload["outcome"] == "completed"
    assert payload["output"]["echoed"] == "hello"


def _handlers(artifact_store: FileWorkflowArtifactStore) -> WorkflowSurfaceHandlers:
    service = WfMcpService(
        store=FileStore(local_temp_root() / "surface_mcp"),
        artifact_store=artifact_store,
    )
    return WorkflowSurfaceHandlers(service)


def _artifact() -> WorkflowArtifact:
    return WorkflowArtifact(
        id="summarize_docs",
        version=1,
        title="Summarize Docs",
        description="Summarize retrieved documentation.",
        input_schema={"type": "object", "properties": {}},
        output_schema={"type": "object", "properties": {}},
        outcomes=("done",),
        plan={"name": "summarize_docs", "nodes": [], "edges": []},
        required_capabilities={
            "context7.query-docs": RequiredCapability(
                logical_source="context7",
                capability_name="query-docs",
                kind="tool",
                input_schema_hash="sha256:input",
                output_schema_hash="sha256:output",
            )
        },
    )


def _echo_artifact() -> WorkflowArtifact:
    plan: dict[str, Any] = {
        "name": "echo",
        "input_schema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
        "state_schema": {"fields": {"echoed": {"type": "string"}}},
        "output_schema": {
            "type": "object",
            "properties": {"echoed": {"type": "string"}},
            "required": ["echoed"],
        },
        "start": "echo",
        "nodes": [
            {
                "id": "echo",
                "type": "node",
                "node": "demo.personal.echo_tool",
                "in_map": {"input.text": "text"},
                "out_map": {"echoed": "state.echoed"},
            }
        ],
        "edges": [{"from": "echo", "outcome": "ok", "to": "__end__"}],
    }
    return WorkflowArtifact(
        id="echo",
        version=1,
        title="Echo",
        input_schema=plan["input_schema"],
        output_schema=plan["output_schema"],
        outcomes=("completed",),
        plan=plan,
        required_capabilities={
            "demo.echo_tool": RequiredCapability(
                logical_source="demo",
                capability_name="echo_tool",
                kind="node_spec",
            )
        },
    )


def _custom_reducer_artifact() -> WorkflowArtifact:
    plan: dict[str, Any] = {
        "name": "multiply",
        "input_schema": {
            "type": "object",
            "properties": {
                "total": {"type": "integer"},
                "amount": {"type": "integer"},
            },
            "required": ["total", "amount"],
        },
        "state_schema": {
            "fields": {
                "total": {
                    "type": "integer",
                    "reducer": "custom.multiply",
                }
            }
        },
        "output_schema": {
            "type": "object",
            "properties": {"total": {"type": "integer"}},
            "required": ["total"],
        },
        "start": "amount",
        "nodes": [
            {
                "id": "amount",
                "type": "node",
                "node": "demo.personal.amount_tool",
                "in_map": {"input.amount": "amount"},
                "out_map": {"amount": "state.total"},
            }
        ],
        "edges": [{"from": "amount", "outcome": "ok", "to": "__end__"}],
    }
    return WorkflowArtifact(
        id="multiply",
        version=1,
        title="Multiply",
        input_schema=plan["input_schema"],
        output_schema=plan["output_schema"],
        outcomes=("completed",),
        plan=plan,
        required_capabilities={
            "demo.amount_tool": RequiredCapability(
                logical_source="demo",
                capability_name="amount_tool",
                kind="node_spec",
            ),
            "custom.multiply": RequiredCapability(
                logical_source="custom",
                capability_name="multiply",
                kind="reducer",
            ),
        },
    )
