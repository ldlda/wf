from __future__ import annotations

import asyncio

from pydantic import BaseModel

from examples.authoring_workflow_as_node import (
    build_parent_workflow,
    run_parent_workflow,
    wrapped_demo_workflow,
)
from examples.demo_workflow import build_demo_registry, build_demo_workflow
from wf_authoring import (
    WorkflowBuilder,
    async_subgraph_node,
    build_async_registry,
    build_registry,
    input_from,
    input_path,
    node,
    output_to,
    state_path,
    subgraph_node,
    subgraph_ref,
)
from wf_core import (
    END,
    Edge,
    RunStatus,
    RuntimeContext,
    Workflow,
    execute_workflow_async,
)


def test_subgraph_node_wraps_compiled_workflow() -> None:
    class ChildInput(BaseModel):
        folder_id: str
        should_email: bool

    class ChildOutput(BaseModel):
        summary: str
        email_status: str

    child_workflow = build_demo_workflow()
    child_registry = build_demo_registry()
    wrapped = subgraph_node(
        name="wrapped_demo",
        workflow=child_workflow,
        registry=child_registry,
        input_model=ChildInput,
        output_model=ChildOutput,
    )

    registry = build_registry(wrapped)
    result = registry["wrapped_demo"](
        {"folder_id": "demo-folder", "should_email": False},
        RuntimeContext(current_node_id="parent"),
    )

    assert result["outcome"] == "ok"
    assert result["output"]["email_status"] == "skipped"
    assert "summary" in result["output"]


def test_async_subgraph_node_wraps_async_compiled_workflow() -> None:
    class ChildInput(BaseModel):
        text: str

    class ChildState(BaseModel):
        text: str

    class ChildOutput(BaseModel):
        text: str

    @node(name="child.async_upper", input_model=ChildInput, output_model=ChildOutput)
    async def async_upper(payload: ChildInput) -> ChildOutput:
        return ChildOutput(text=payload.text.upper())

    child = WorkflowBuilder(
        name="async_child",
        input_schema=ChildInput,
        state_schema=ChildState,
        output_schema=ChildOutput,
    )
    upper = child.use(
        async_upper,
        id="upper",
        input=[input_from(input_path("text"), "text")],
        output=[output_to("text", state_path("text"))],
    )
    child.set_entry_point(upper)
    child.connect(upper, "ok", END)

    wrapped = async_subgraph_node(
        name="wrapped_async_child",
        workflow=child.compile(),
        registry=build_async_registry(async_upper),
        input_model=ChildInput,
        output_model=ChildOutput,
    )
    parent = WorkflowBuilder(
        name="async_parent",
        input_schema=ChildInput,
        state_schema=ChildState,
        output_schema=ChildOutput,
    )
    step = parent.use(
        wrapped,
        id="run_async_child",
        input=[input_from(input_path("text"), "text")],
        output=[output_to("text", state_path("text"))],
    )
    parent.set_entry_point(step)
    parent.connect(step, "ok", END)

    run = asyncio.run(
        execute_workflow_async(
            parent.compile(),
            {"text": "hello"},
            build_async_registry(wrapped),
        )
    )

    assert run.status == RunStatus.COMPLETED
    assert run.output["text"] == "HELLO"


def test_workflow_as_node_example_runs_child_inside_parent_workflow() -> None:
    run = run_parent_workflow()

    assert run.status == RunStatus.COMPLETED
    assert run.output["email_status"] == "skipped"
    assert "Summary of demo-folder/meeting-notes.md" in run.output["summary"]


def test_workflow_as_node_example_parent_trace_is_one_node_call() -> None:
    run = run_parent_workflow()

    assert len(run.trace) == 1
    assert run.trace[0].node_id == "run_child"
    assert run.trace[0].step_type == "node"
    assert run.trace[0].outcome == "ok"


def test_workflow_as_node_example_compiles_to_normal_node_use() -> None:
    workflow = build_parent_workflow().compile()
    node = workflow.nodes[0]

    assert node.type == "node"
    assert node.node == wrapped_demo_workflow.name
    assert workflow.node_defs[0].name == wrapped_demo_workflow.name


def test_subgraph_ref_copies_child_workflow_contract() -> None:
    child = build_demo_workflow()

    step = subgraph_ref(
        id="run_child",
        workflow=child,
        input=[input_from(input_path("folder_id"), "folder_id")],
        output=[output_to("summary", state_path("summary"))],
    )

    assert step.type == "subgraph"
    assert step.workflow.name == child.name
    assert step.input_schema == child.input_schema
    assert step.output_schema == child.output_schema
    assert step.outcomes == child.outcomes


def test_subgraph_ref_contract_validates_in_parent_workflow() -> None:
    child = build_demo_workflow()
    step = subgraph_ref(
        id="run_child",
        workflow=child,
        input=[input_from(input_path("folder_id"), "folder_id")],
        output=[output_to("summary", state_path("summary"))],
    )

    parent = Workflow.model_validate(
        {
            "name": "native_subgraph_parent",
            "input_schema": child.input_schema.model_dump(mode="json"),
            "state_schema": {
                "type": "object",
                "properties": {"summary": {"type": "string"}},
            },
            "output_schema": {
                "type": "object",
                "properties": {"summary": {"type": "string"}},
            },
            "outcomes": ["ok"],
            "start": "run_child",
            "nodes": [step.model_dump(mode="json", by_alias=True)],
            "edges": [
                Edge.model_validate({"from": "run_child", "outcome": "ok", "to": END})
            ],
        }
    )

    assert parent.validate_structure().errors == []


def test_subgraph_ref_accepts_structural_saved_workflow_reference() -> None:
    child = build_demo_workflow()

    step = subgraph_ref(
        id="run_child",
        workflow=child,
        workflow_ref={"artifact_id": "demo_child", "version": 2},
    )

    dumped = step.model_dump(mode="json")
    assert dumped["workflow"]["artifact_id"] == "demo_child"
    assert dumped["workflow"]["version"] == 2
    assert "name" not in dumped["workflow"]


def test_workflow_builder_subgraph_adds_native_subgraph_node() -> None:
    class ParentInput(BaseModel):
        folder_id: str
        should_email: bool

    class ParentState(BaseModel):
        summary: str

    class ParentOutput(BaseModel):
        summary: str

    child = build_demo_workflow()
    parent = WorkflowBuilder(
        name="native_parent",
        input_schema=ParentInput,
        state_schema=ParentState,
        output_schema=ParentOutput,
    )

    step = parent.subgraph(
        workflow=child,
        id="run_child",
        input=[
            input_from(input_path("folder_id"), "folder_id"),
            input_from(input_path("should_email"), "should_email"),
        ],
        output=[output_to("summary", state_path("summary"))],
    )
    parent.set_entry_point(step)
    parent.connect(step, "ok", END)

    workflow = parent.compile()

    assert workflow.nodes[0].type == "subgraph"
    assert workflow.nodes[0].id == "run_child"
    assert workflow.nodes[0].outcomes == child.outcomes
    assert workflow.validate_structure().errors == []
