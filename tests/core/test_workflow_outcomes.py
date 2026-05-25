from __future__ import annotations

import pytest
from pydantic import ValidationError

from wf_core import END, EndNode, Workflow
from wf_core.runtime import execute_workflow
from wf_core.validation.issues import ValidationIssueCode


def test_legacy_end_token_completes_with_ok_workflow_outcome() -> None:
    workflow = _workflow(edges=[{"from": "finish", "outcome": "done", "to": END}])

    run = execute_workflow(workflow, {"text": "hello"}, {"finish": _finish})

    assert run.status == "completed"
    assert run.outcome == "ok"


def test_explicit_end_node_sets_workflow_outcome() -> None:
    workflow = _workflow(
        outcomes=["ok", "error"],
        nodes=[
            _finish_node_data(),
            {"id": "end_error", "type": "end", "outcome": "error"},
        ],
        edges=[{"from": "finish", "outcome": "done", "to": "end_error"}],
    )

    run = execute_workflow(workflow, {"text": "hello"}, {"finish": _finish})

    assert run.status == "completed"
    assert run.outcome == "error"


def test_root_workflow_output_bindings_project_final_output() -> None:
    workflow = Workflow.model_validate(
        {
            "name": "root_output_bindings",
            "input_schema": {
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
            "state_schema": {
                "type": "object",
                "properties": {
                    "result": {
                        "type": "object",
                        "properties": {"echoed": {"type": "string"}},
                    }
                },
            },
            "output_schema": {
                "type": "object",
                "properties": {"echoed": {"type": "string"}},
                "required": ["echoed"],
            },
            "output": [{"target": "echoed", "path": "state.result.echoed"}],
            "node_defs": [
                {
                    "name": "finish",
                    "input_schema": {
                        "type": "object",
                        "properties": {"text": {"type": "string"}},
                        "required": ["text"],
                    },
                    "output_schema": {
                        "type": "object",
                        "properties": {"echoed": {"type": "string"}},
                        "required": ["echoed"],
                    },
                    "outcomes": ["done"],
                }
            ],
            "start": "finish",
            "nodes": [
                {
                    "id": "finish",
                    "type": "node",
                    "node": "finish",
                    "input": [{"target": "text", "path": "input.text"}],
                    "output": [{"source": "echoed", "target": "state.result.echoed"}],
                }
            ],
            "edges": [{"from": "finish", "outcome": "done", "to": END}],
        }
    )

    run = execute_workflow(workflow, {"text": "hello"}, {"finish": _finish})

    assert run.output["echoed"] == "hello"
    assert run.state["result"]["echoed"] == "hello"


def test_validation_rejects_root_workflow_output_target_not_declared() -> None:
    workflow = _workflow(
        edges=[{"from": "finish", "outcome": "done", "to": END}],
        output=[{"target": "missing", "path": "state.echoed"}],
    )

    report = workflow.validate_structure()

    assert any(
        issue.code == ValidationIssueCode.INVALID_WORKFLOW_OUTPUT_FIELD
        and issue.path == "output[0].target"
        for issue in report.errors
    )


def test_validation_rejects_end_node_outcome_not_declared_by_workflow() -> None:
    workflow = _workflow(
        nodes=[
            _finish_node_data(),
            {"id": "end_error", "type": "end", "outcome": "error"},
        ],
        edges=[{"from": "finish", "outcome": "done", "to": "end_error"}],
    )

    report = workflow.validate_structure()

    assert any(
        issue.code == ValidationIssueCode.UNDECLARED_WORKFLOW_OUTCOME
        and issue.path == "nodes[1].outcome"
        for issue in report.errors
    )


def test_validation_rejects_legacy_end_without_ok_workflow_outcome() -> None:
    workflow = _workflow(
        outcomes=["error"],
        edges=[{"from": "finish", "outcome": "done", "to": END}],
    )

    report = workflow.validate_structure()

    assert any(
        issue.code == ValidationIssueCode.UNDECLARED_WORKFLOW_OUTCOME
        and issue.path == "edges[0].to"
        for issue in report.errors
    )


def test_end_node_rejects_empty_workflow_outcome() -> None:
    with pytest.raises(ValidationError):
        EndNode(id="end_empty", type="end", outcome="")


def _finish(payload: dict[str, object], _ctx: object) -> dict[str, object]:
    return {"outcome": "done", "output": {"echoed": payload["text"]}}


def _workflow(
    *,
    outcomes: list[str] | None = None,
    nodes: list[dict[str, object]] | None = None,
    edges: list[dict[str, object]],
    output: list[dict[str, object]] | None = None,
) -> Workflow:
    return Workflow.model_validate(
        {
            "name": "workflow_outcomes",
            "input_schema": {
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
            "state_schema": {
                "type": "object",
                "properties": {"echoed": {"type": "string"}},
            },
            "output_schema": {
                "type": "object",
                "properties": {"echoed": {"type": "string"}},
                "required": ["echoed"],
            },
            "node_defs": [
                {
                    "name": "finish",
                    "input_schema": {
                        "type": "object",
                        "properties": {"text": {"type": "string"}},
                        "required": ["text"],
                    },
                    "output_schema": {
                        "type": "object",
                        "properties": {"echoed": {"type": "string"}},
                        "required": ["echoed"],
                    },
                    "outcomes": ["done"],
                }
            ],
            "outcomes": outcomes or ["ok"],
            "output": [] if output is None else output,
            "start": "finish",
            "nodes": [_finish_node_data()] if nodes is None else nodes,
            "edges": edges,
        }
    )


def _finish_node_data() -> dict[str, object]:
    return {
        "id": "finish",
        "type": "node",
        "node": "finish",
        "input": [{"target": "text", "path": "input.text"}],
        "output": [{"source": "echoed", "target": "state.echoed"}],
    }
