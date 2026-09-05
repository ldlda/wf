from __future__ import annotations

from typing import Any

import pytest

from wf_client.codec import (
    decode_dependency_diagnostics,
    decode_deployment,
    decode_run_result,
    decode_trace_result,
    decode_workflow_artifact,
)
from wf_client.errors import InvalidResponse


def _constant_plan_payload() -> dict[str, Any]:
    return {
        "name": "report",
        "input_schema": {"type": "object", "properties": {}},
        "state_schema": {
            "type": "object",
            "properties": {"result": {"type": "string", "reducer": "wf.std.replace"}},
        },
        "output_schema": {
            "type": "object",
            "properties": {"result": {"type": "string"}},
            "required": ["result"],
        },
        "outcomes": ["ok"],
        "start": "constant",
        "nodes": [
            {
                "id": "constant",
                "type": "node",
                "node": "wf.std.constant",
                "input": [{"value": "hello", "target": "local.value"}],
                "output": [{"source": "local.value", "target": "state.result"}],
            }
        ],
        "edges": [{"from": "constant", "outcome": "ok", "to": "__end__"}],
        "output": [{"path": "state.result", "target": "result"}],
    }


def _workflow_artifact_payload(*, plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": "report",
        "version": 1,
        "title": "Report",
        "kind": "workflow",
        "description": None,
        "input_schema": {"type": "object", "properties": {}},
        "output_schema": {
            "type": "object",
            "properties": {"result": {"type": "string"}},
        },
        "outcomes": ["ok"],
        "plan": plan,
        "required_capabilities": [],
        "workflow_dependencies": {},
        "created_from_catalog_version": None,
    }


def test_decode_workflow_artifact_validates_plan() -> None:
    artifact, workflow = decode_workflow_artifact(
        _workflow_artifact_payload(plan=_constant_plan_payload())
    )

    assert artifact.id == "report"
    assert workflow.name == "report"
    assert workflow.start == "constant"


def test_decode_workflow_artifact_rejects_invalid_nested_plan() -> None:
    with pytest.raises(InvalidResponse, match="workflow.artifacts.inspect"):
        decode_workflow_artifact(_workflow_artifact_payload(plan={"name": "broken"}))


def test_decode_deployment_returns_domain_model() -> None:
    deployment = decode_deployment(
        {
            "id": "production",
            "artifact_id": "report",
            "artifact_version": 1,
            "bindings": [],
            "drift_policy": "block",
        }
    )

    assert deployment.id == "production"
    assert deployment.artifact_id == "report"


def test_decode_dependency_diagnostics_returns_domain_models() -> None:
    diagnostics = decode_dependency_diagnostics(
        [
            {
                "severity": "error",
                "code": "missing_source",
                "logical_ref": "demo",
                "bound_source": None,
                "message": "missing",
                "repair_hint": "bind it",
            }
        ]
    )

    assert diagnostics[0].code == "missing_source"
    assert diagnostics[0].severity.value == "error"


def _run_payload(*, trace: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "artifact_id": "report",
        "artifact_version": 1,
        "deployment_id": "production",
        "status": "completed",
        "run_id": "run-1",
        "resume_readiness": None,
        "interrupt": None,
        "outcome": "ok",
        "error": None,
        "output": {"result": "hello"},
        "trace_count": 0 if trace is None else len(trace),
        "max_steps": 10_000,
        "steps_executed": 1,
        "steps_remaining": 9_999,
        "diagnostics": [],
        "next_actions": {
            "can_continue": False,
            "can_save_now": None,
            "recommended_next_tool": None,
            "reason": "done",
            "patch_examples": [],
            "warnings": [],
        },
    }
    if trace is not None:
        payload.update(
            trace=trace,
            trace_start=0,
            trace_limit=25,
            trace_truncated=False,
        )
    return payload


def test_decode_run_result_returns_typed_domain_boundary() -> None:
    result = decode_run_result(_run_payload())

    assert result.run_id == "run-1"
    assert result.output == {"result": "hello"}
    assert result.diagnostics == ()


def test_decode_trace_result_decodes_bounded_trace() -> None:
    result = decode_trace_result(
        _run_payload(
            trace=[
                {
                    "frame_id": "root",
                    "node_id": "constant",
                    "step_type": "node",
                    "resolved_input": {},
                    "outcome": "ok",
                    "next_node_id": "__end__",
                    "output": {},
                    "state_changes": {},
                }
            ]
        )
    )

    assert result.trace_start == 0
    assert result.trace is not None
    assert result.trace[0]["node_id"] == "constant"
