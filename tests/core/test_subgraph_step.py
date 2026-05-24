from __future__ import annotations

import asyncio

import pytest

from wf_core import (
    END,
    Edge,
    EndNode,
    InterruptNode,
    NodeDef,
    NodeUse,
    PreparedSubgraph,
    RunState,
    SchemaRef,
    StateField,
    StateSchema,
    SubgraphNode,
    Workflow,
    WorkflowExecutionError,
    execute_workflow_async,
    execute_workflow,
)
from wf_core.validation.issues import ValidationIssueCode
from wf_core.models.steps import Step


def test_subgraph_step_validates_boundary_bindings_and_outcomes() -> None:
    workflow = _workflow()

    report = workflow.validate_structure()

    assert report.errors == []


def test_subgraph_step_rejects_undeclared_input_target() -> None:
    workflow = _workflow(
        node=SubgraphNode.model_validate(
            {
                "id": "child",
                "type": "subgraph",
                "workflow": "child.workflow",
                "input_schema": _schema({"text": {"type": "string"}}),
                "output_schema": _schema({"answer": {"type": "string"}}),
                "input": [{"target": "missing", "path": "input.text"}],
                "output": [{"source": "answer", "target": "state.answer"}],
            }
        )
    )

    report = workflow.validate_structure()

    assert any(
        issue.code == ValidationIssueCode.INVALID_NODE_INPUT_FIELD
        and issue.path == "nodes[0].input[0].target"
        for issue in report.errors
    )


def test_subgraph_step_rejects_unwired_declared_outcome() -> None:
    workflow = _workflow(
        node=SubgraphNode.model_validate(
            {
                "id": "child",
                "type": "subgraph",
                "workflow": "child.workflow",
                "input_schema": _schema({"text": {"type": "string"}}),
                "output_schema": _schema({"answer": {"type": "string"}}),
                "outcomes": ["ok", "failed"],
                "input": [{"target": "text", "path": "input.text"}],
                "output": [{"source": "answer", "target": "state.answer"}],
            }
        )
    )

    report = workflow.validate_structure()

    assert any(
        issue.code == ValidationIssueCode.MISSING_OUTCOME_EDGE
        and "failed" in issue.message
        for issue in report.errors
    )


def test_subgraph_step_requires_prepared_child_dependency() -> None:
    workflow = _workflow()

    with pytest.raises(WorkflowExecutionError, match="prepared child workflow"):
        execute_workflow(workflow, {"text": "hello"}, {})


def test_subgraph_step_executes_prepared_child_in_isolated_scope() -> None:
    workflow = _workflow(
        node=_subgraph_node(input_bindings=[{"target": "text", "value": "child-only"}]),
        output_schema=_schema({"answer": {"type": "string"}}),
    )
    child = _child_workflow()

    run = execute_workflow(
        workflow,
        {"text": "hello"},
        {},
        subgraphs={
            "child.workflow": PreparedSubgraph(
                workflow=child,
                registry={
                    "answer": lambda payload, _ctx: {
                        "answer": f"child:{payload['text']}"
                    }
                },
            )
        },
    )

    assert run.output["answer"] == "child:child-only"
    assert run.state["answer"] == "child:child-only"
    assert run.scopes["root"].committed_state["answer"] == "child:child-only"
    child_scope = next(
        scope for scope in run.scopes.values() if scope.workflow_name == child.name
    )
    assert child_scope.workflow_input["text"] == "child-only"
    assert child_scope.committed_state["answer"] == "child:child-only"
    assert run.trace[0].node_id == "answer"
    assert run.trace[0].frame_id != "root"
    assert run.trace[-1].node_id == "child"
    assert run.trace[-1].step_type == "subgraph"


def test_subgraph_step_executes_prepared_async_child() -> None:
    async def answer(payload: dict[str, object], _ctx: object) -> dict[str, object]:
        return {"answer": f"async:{payload['text']}"}

    async def execute() -> RunState:
        return await execute_workflow_async(
            _workflow(output_schema=_schema({"answer": {"type": "string"}})),
            {"text": "hello"},
            {},
            subgraphs={
                "child.workflow": PreparedSubgraph(
                    workflow=_child_workflow(),
                    registry={"answer": answer},
                )
            },
        )

    run = asyncio.run(execute())

    assert run.output["answer"] == "async:hello"
    assert run.trace[-1].step_type == "subgraph"


def test_subgraph_step_routes_through_child_terminal_outcome() -> None:
    child = _child_workflow(
        outcomes=["error"],
        terminal=EndNode(id="child_error", type="end", outcome="error"),
        edges=[
            Edge.model_validate(
                {"from": "answer", "outcome": "ok", "to": "child_error"}
            )
        ],
    )
    subgraph = _subgraph_node(outcomes=["error"])
    workflow = _workflow(
        node=subgraph,
        outcomes=["ok", "error"],
        nodes=[subgraph, EndNode(id="parent_error", type="end", outcome="error")],
        edges=[
            Edge.model_validate(
                {"from": "child", "outcome": "error", "to": "parent_error"}
            )
        ],
    )

    run = execute_workflow(
        workflow,
        {"text": "hello"},
        {},
        subgraphs={
            "child.workflow": PreparedSubgraph(
                workflow=child,
                registry={"answer": lambda payload, _ctx: {"answer": payload["text"]}},
            )
        },
    )

    assert run.outcome == "error"
    assert any(
        entry.node_id == "child_error" and entry.outcome == "error"
        for entry in run.trace
    )
    assert any(
        entry.node_id == "child" and entry.outcome == "error" for entry in run.trace
    )


def test_subgraph_step_rejects_child_interrupt_until_resume_route_exists() -> None:
    child = Workflow(
        name="child.workflow",
        input_schema=_schema({"text": {"type": "string"}}),
        state_schema=StateSchema.from_field_map({}),
        output_schema=_schema({}),
        start="ask",
        nodes=[
            InterruptNode.model_validate(
                {"id": "ask", "type": "interrupt", "kind": "input"}
            )
        ],
        edges=[Edge.model_validate({"from": "ask", "outcome": "submitted", "to": END})],
    )

    with pytest.raises(WorkflowExecutionError, match="child interrupts"):
        execute_workflow(
            _workflow(),
            {"text": "hello"},
            {},
            subgraphs={"child.workflow": PreparedSubgraph(workflow=child, registry={})},
        )


def _workflow(
    *,
    node: SubgraphNode | None = None,
    outcomes: list[str] | None = None,
    nodes: list[Step] | None = None,
    edges: list[Edge] | None = None,
    output_schema: SchemaRef | None = None,
) -> Workflow:
    subgraph = node or _subgraph_node()
    return Workflow(
        name="subgraph_parent",
        input_schema=_schema({"text": {"type": "string"}}),
        state_schema=StateSchema.from_field_map({"answer": StateField(type="string")}),
        output_schema=output_schema or _schema({}),
        outcomes=outcomes or ["ok"],
        start="child",
        nodes=[subgraph] if nodes is None else nodes,
        edges=edges
        or [Edge.model_validate({"from": "child", "outcome": "ok", "to": END})],
    )


def _subgraph_node(
    *,
    outcomes: list[str] | None = None,
    input_bindings: list[dict[str, object]] | None = None,
) -> SubgraphNode:
    return SubgraphNode.model_validate(
        {
            "id": "child",
            "type": "subgraph",
            "workflow": "child.workflow",
            "input_schema": _schema({"text": {"type": "string"}}),
            "output_schema": _schema({"answer": {"type": "string"}}),
            "input": (
                [{"target": "text", "path": "input.text"}]
                if input_bindings is None
                else input_bindings
            ),
            "output": [{"source": "answer", "target": "state.answer"}],
            "outcomes": outcomes or ["ok"],
        }
    )


def _child_workflow(
    *,
    outcomes: list[str] | None = None,
    terminal: EndNode | None = None,
    edges: list[Edge] | None = None,
) -> Workflow:
    node = NodeUse.model_validate(
        {
            "id": "answer",
            "type": "node",
            "node": "answer",
            "input": [{"target": "text", "path": "input.text"}],
            "output": [{"source": "answer", "target": "state.answer"}],
        }
    )
    return Workflow(
        name="child.workflow",
        input_schema=_schema({"text": {"type": "string"}}),
        state_schema=StateSchema.from_field_map({"answer": StateField(type="string")}),
        output_schema=_schema({"answer": {"type": "string"}}),
        node_defs=[
            NodeDef(
                name="answer",
                input_schema=_schema({"text": {"type": "string"}}),
                output_schema=_schema({"answer": {"type": "string"}}),
                outcomes=["ok"],
            )
        ],
        outcomes=outcomes or ["ok"],
        start="answer",
        nodes=[node] if terminal is None else [node, terminal],
        edges=edges
        or [Edge.model_validate({"from": "answer", "outcome": "ok", "to": END})],
    )


def _schema(properties: dict[str, object]) -> SchemaRef:
    return SchemaRef.model_validate({"type": "object", "properties": properties})
