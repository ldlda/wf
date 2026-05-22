from __future__ import annotations

from typing import Any

from wf_core import (
    END,
    Edge,
    ForeachNode,
    NodeDef,
    NodeUse,
    ReducerRef,
    SchemaRef,
    StateField,
    StateSchema,
    Workflow,
    execute_workflow,
)


def test_concurrent_foreach_skip_emits_completed_with_errors() -> None:
    workflow = _workflow(item_error={"action": "skip"})

    run = execute_workflow(
        workflow,
        {"items": ["a", "b", "c"]},
        {"record": _fail_on_b},
    )

    assert run.state["seen"] == ["a", "c"]
    assert run.frames["root:each:1"].status == "failed"
    foreach_entries = [entry for entry in run.trace if entry.step_type == "foreach"]
    assert foreach_entries[-1].outcome == "completed_with_errors"
    assert foreach_entries[-1].resolved_input["failed_items"] == 1
    assert foreach_entries[-1].state_changes["state.seen"] == ["a", "c"]


def test_concurrent_foreach_collect_writes_ordered_error_records() -> None:
    workflow = _workflow(item_error={"action": "collect", "collect_to": "state.errors"})

    run = execute_workflow(
        workflow,
        {"items": ["a", "b", "c"]},
        {"record": _fail_on_b},
    )

    assert run.state["seen"] == ["a", "c"]
    assert len(run.state["errors"]) == 1
    error = run.state["errors"][0]
    assert error["index"] == 1
    assert error["frame_id"] == "root:each:1"
    assert error["node_id"] == "record"
    assert error["error_type"] == "ValueError"
    assert error["message"] == "bad item"
    assert error["item"] == "b"
    foreach_entries = [entry for entry in run.trace if entry.step_type == "foreach"]
    assert foreach_entries[-1].outcome == "completed_with_errors"
    assert foreach_entries[-1].state_changes["state.errors"] == run.state["errors"]


def test_concurrent_foreach_collect_writes_empty_list_on_clean_success() -> None:
    workflow = _workflow(item_error={"action": "collect", "collect_to": "state.errors"})

    run = execute_workflow(
        workflow,
        {"items": ["a", "b"]},
        {"record": lambda payload, _ctx: {"outcome": "ok", "output": payload}},
    )

    assert run.state["seen"] == ["a", "b"]
    assert run.state["errors"] == []
    foreach_entries = [entry for entry in run.trace if entry.step_type == "foreach"]
    assert foreach_entries[-1].outcome == "done"
    assert foreach_entries[-1].state_changes["state.errors"] == []


def _fail_on_b(payload: dict[str, Any], _ctx: object) -> dict[str, Any]:
    if payload["value"] == "b":
        raise ValueError("bad item")
    return {"outcome": "ok", "output": payload}


def _workflow(*, item_error: dict[str, object]) -> Workflow:
    return Workflow(
        name="concurrent_foreach_item_errors",
        input_schema=SchemaRef(
            type="object",
            properties={"items": {"type": "array"}},
        ),
        state_schema=StateSchema.from_field_map(
            {
                "items": StateField(type="array"),
                "seen": StateField(
                    type="array",
                    reducer=ReducerRef(name="wf.std.append"),
                ),
                "errors": StateField(type="array"),
            }
        ),
        output_schema=SchemaRef(
            type="object",
            properties={"seen": {"type": "array"}, "errors": {"type": "array"}},
        ),
        node_defs=[
            NodeDef(
                name="record",
                input_schema=SchemaRef(
                    type="object",
                    properties={"value": {}, "seen": {}},
                    required=["value", "seen"],
                ),
                output_schema=SchemaRef(
                    type="object",
                    properties={"value": {}, "seen": {}},
                    required=["seen"],
                ),
                outcomes=["ok"],
            )
        ],
        start="each",
        nodes=[
            ForeachNode.model_validate(
                {
                    "id": "each",
                    "type": "foreach",
                    "over": "state.items",
                    "as": "item",
                    "mode": "concurrent",
                    "concurrent": {"max_active": 2, "max_outstanding": 2},
                    "item_error": item_error,
                }
            ),
            NodeUse.model_validate(
                {
                    "id": "record",
                    "type": "node",
                    "node": "record",
                    "input": [
                        {"target": "value", "path": "context.item"},
                        {"target": "seen", "path": "context.item"},
                    ],
                    "output": [{"source": "seen", "target": "state.seen"}],
                }
            ),
        ],
        edges=[
            Edge.model_validate({"from": "each", "outcome": "loop", "to": "record"}),
            Edge.model_validate({"from": "record", "outcome": "ok", "to": END}),
            Edge.model_validate({"from": "each", "outcome": "done", "to": END}),
            Edge.model_validate(
                {"from": "each", "outcome": "completed_with_errors", "to": END}
            ),
        ],
    )
