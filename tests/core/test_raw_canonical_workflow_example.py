from __future__ import annotations

from wf_core import RunStatus

from examples.raw_canonical_workflow import (
    build_raw_canonical_workflow,
    run_raw_canonical_example,
)


def test_raw_canonical_workflow_runs() -> None:
    run = run_raw_canonical_example("hello")

    assert run.status == RunStatus.COMPLETED
    assert run.output["message"] == "raw:HELLO"
    assert run.state["message"] == "raw:HELLO"
    assert run.trace[0].resolved_input["text"] == "hello"
    assert run.trace[0].resolved_input["prefix"] == "raw:"


def test_raw_canonical_workflow_serializes_new_shape() -> None:
    workflow = build_raw_canonical_workflow()
    dumped = workflow.model_dump(mode="json")
    node = dumped["nodes"][0]
    state_field = dumped["state_schema"]["fields"][0]

    assert "input" in node
    assert "output" in node
    assert "in_map" not in node
    assert "input_values" not in node
    assert "out_map" not in node
    assert node["input"][0]["path"] == "input.text"
    assert node["input"][0]["target"] == "text"
    assert node["input"][1]["value"] == "raw:"
    assert node["output"][0]["source"] == "message"
    assert node["output"][0]["target"] == "state.message"
    assert state_field["path"] == "state.message"
    assert state_field["schema"]["type"] == "string"
