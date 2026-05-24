from __future__ import annotations

import pytest

from wf_core import (
    END,
    Edge,
    SchemaRef,
    StateField,
    StateSchema,
    SubgraphNode,
    Workflow,
    WorkflowExecutionError,
    execute_workflow,
)
from wf_core.validation.issues import ValidationIssueCode


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


def test_subgraph_step_runtime_fails_explicitly_until_native_execution_exists() -> None:
    workflow = _workflow()

    with pytest.raises(WorkflowExecutionError, match="native subgraph execution"):
        execute_workflow(workflow, {"text": "hello"}, {})


def _workflow(*, node: SubgraphNode | None = None) -> Workflow:
    subgraph = node or SubgraphNode.model_validate(
        {
            "id": "child",
            "type": "subgraph",
            "workflow": "child.workflow",
            "input_schema": _schema({"text": {"type": "string"}}),
            "output_schema": _schema({"answer": {"type": "string"}}),
            "input": [{"target": "text", "path": "input.text"}],
            "output": [{"source": "answer", "target": "state.answer"}],
        }
    )
    return Workflow(
        name="subgraph_parent",
        input_schema=_schema({"text": {"type": "string"}}),
        state_schema=StateSchema.from_field_map({"answer": StateField(type="string")}),
        output_schema=_schema({}),
        start="child",
        nodes=[subgraph],
        edges=[Edge.model_validate({"from": "child", "outcome": "ok", "to": END})],
    )


def _schema(properties: dict[str, object]) -> SchemaRef:
    return SchemaRef.model_validate({"type": "object", "properties": properties})
