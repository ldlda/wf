from __future__ import annotations

from examples.raw_canonical_workflow import (
    build_raw_canonical_workflow,
    run_raw_canonical_example,
)
from examples.raw_concurrent_foreach import (
    build_raw_concurrent_foreach_workflow,
    run_raw_concurrent_foreach_example,
)
from wf_core import RunStatus


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
    message_schema = dumped["state_schema"]["properties"]["message"]

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
    assert message_schema["type"] == "string"
    assert message_schema["reducer"] == "wf.std.replace"


def test_raw_concurrent_foreach_workflow_runs() -> None:
    run = run_raw_concurrent_foreach_example()

    assert run.status == RunStatus.COMPLETED
    assert run.output["seen"] == ["a", "c"]
    assert len(run.output["errors"]) == 1
    error = run.output["errors"][0]
    assert error["index"] == 1
    assert error["node_id"] == "record"
    assert error["error_type"] == "ValueError"
    assert error["message"] == "bad item"


def test_raw_concurrent_foreach_serializes_canonical_policy_shape() -> None:
    workflow = build_raw_concurrent_foreach_workflow()
    dumped = workflow.model_dump(mode="json")
    foreach = dumped["nodes"][0]

    assert foreach["mode"] == "concurrent"
    assert foreach["concurrent"]["max_active"] == 2
    assert foreach["item_error"]["action"] == "collect"
    assert foreach["item_error"]["collect_to"] == "state.errors"
    assert "on_item_error" not in foreach
