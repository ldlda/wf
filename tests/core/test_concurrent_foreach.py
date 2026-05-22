from __future__ import annotations

from typing import Any

import pytest

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
    WorkflowExecutionError,
    execute_workflow,
)


def test_sync_concurrent_foreach_interleaves_items_and_commits_at_barrier() -> None:
    workflow = _workflow(
        state_schema=StateSchema.from_field_map(
            {
                "items": StateField(type="array"),
                "seen": StateField(
                    type="array",
                    reducer=ReducerRef(name="wf.std.append"),
                ),
            }
        ),
        foreach=ForeachNode.model_validate(
            {
                "id": "each",
                "type": "foreach",
                "over": "state.items",
                "as": "item",
                "mode": "concurrent",
                "concurrent": {"max_active": 2, "max_outstanding": 2},
            }
        ),
    )

    run = execute_workflow(
        workflow,
        {"items": ["a", "b", "c"]},
        {"record": lambda payload, _ctx: {"outcome": "ok", "output": payload}},
    )

    assert run.output["seen"] == ["a", "b", "c"]
    assert run.state["seen"] == ["a", "b", "c"]
    foreach_entries = [entry for entry in run.trace if entry.step_type == "foreach"]
    assert foreach_entries[-1].outcome == "done"
    assert foreach_entries[-1].state_changes["state.seen"] == ["a", "b", "c"]


def test_sync_concurrent_foreach_respects_max_active_by_refill_trace() -> None:
    workflow = _workflow(
        state_schema=StateSchema.from_field_map(
            {
                "items": StateField(type="array"),
                "seen": StateField(
                    type="array",
                    reducer=ReducerRef(name="wf.std.append"),
                ),
            }
        ),
        foreach=ForeachNode.model_validate(
            {
                "id": "each",
                "type": "foreach",
                "over": "state.items",
                "as": "item",
                "mode": "concurrent",
                "concurrent": {"max_active": 2, "max_outstanding": 2},
            }
        ),
    )

    run = execute_workflow(
        workflow,
        {"items": ["a", "b", "c", "d"]},
        {"record": lambda payload, _ctx: {"outcome": "ok", "output": payload}},
    )

    loop_entries = [
        entry
        for entry in run.trace
        if entry.step_type == "foreach" and entry.outcome == "loop"
    ]
    assert loop_entries[0].resolved_input["active_count"] == 0
    assert loop_entries[1].resolved_input["active_count"] == 1
    assert any(entry.resolved_input["active_count"] > 0 for entry in loop_entries)
    assert all(entry.resolved_input["active_count"] < 2 for entry in loop_entries)


def test_sync_concurrent_foreach_rejects_non_fail_item_policy_for_now() -> None:
    workflow = _workflow(
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
        foreach=ForeachNode.model_validate(
            {
                "id": "each",
                "type": "foreach",
                "over": "state.items",
                "as": "item",
                "mode": "concurrent",
                "concurrent": {"max_active": 2, "max_outstanding": 2},
                "item_error": {"action": "collect", "collect_to": "state.errors"},
            }
        ),
        include_completed_with_errors=True,
    )

    with pytest.raises(
        WorkflowExecutionError,
        match="only supports item_error.action='fail'",
    ):
        execute_workflow(
            workflow,
            {"items": ["a"]},
            {"record": lambda payload, _ctx: {"outcome": "ok", "output": payload}},
        )


def test_sync_concurrent_foreach_fails_run_on_item_runtime_error() -> None:
    workflow = _workflow(
        state_schema=StateSchema.from_field_map(
            {
                "items": StateField(type="array"),
                "seen": StateField(
                    type="array",
                    reducer=ReducerRef(name="wf.std.append"),
                ),
            }
        ),
        foreach=ForeachNode.model_validate(
            {
                "id": "each",
                "type": "foreach",
                "over": "state.items",
                "as": "item",
                "mode": "concurrent",
                "concurrent": {"max_active": 2, "max_outstanding": 2},
            }
        ),
    )

    def fail_on_b(payload: dict[str, Any], _ctx: object) -> dict[str, Any]:
        if payload["value"] == "b":
            raise ValueError("bad item")
        return {"outcome": "ok", "output": payload}

    with pytest.raises(ValueError, match="bad item"):
        execute_workflow(workflow, {"items": ["a", "b", "c"]}, {"record": fail_on_b})


def test_sync_concurrent_foreach_item_reads_own_buffered_write() -> None:
    workflow = _multi_step_overlay_workflow()

    run = execute_workflow(
        workflow,
        {"items": ["a", "b", "c"]},
        {
            "stage_scratch": lambda payload, _ctx: {
                "outcome": "ok",
                "output": {"scratch": f"scratch:{payload['value']}"},
            },
            "read_scratch": lambda payload, _ctx: {
                "outcome": "ok",
                "output": {"seen": payload["scratch"]},
            },
        },
    )

    assert run.state["seen"] == ["scratch:a", "scratch:b", "scratch:c"]


def test_sync_concurrent_foreach_sibling_overlays_do_not_leak() -> None:
    workflow = _multi_step_overlay_workflow()

    run = execute_workflow(
        workflow,
        {"items": ["a", "b"]},
        {
            "stage_scratch": lambda payload, _ctx: {
                "outcome": "ok",
                "output": {"scratch": payload["value"]},
            },
            "read_scratch": lambda payload, _ctx: {
                "outcome": "ok",
                "output": {"seen": payload["scratch"]},
            },
        },
    )

    assert run.state["seen"] == ["a", "b"]


def test_sync_concurrent_foreach_rejects_sibling_replace_writes() -> None:
    workflow = _same_path_replace_workflow()

    with pytest.raises(WorkflowExecutionError, match="explicit reducer"):
        execute_workflow(
            workflow,
            {"items": ["a", "b"]},
            {
                "write_winner": lambda payload, _ctx: {
                    "outcome": "ok",
                    "output": {"winner": payload["value"]},
                }
            },
        )


def _workflow(
    *,
    state_schema: StateSchema,
    foreach: ForeachNode,
    include_completed_with_errors: bool = False,
) -> Workflow:
    edges = [
        Edge.model_validate({"from": "each", "outcome": "loop", "to": "record"}),
        Edge.model_validate({"from": "record", "outcome": "ok", "to": END}),
        Edge.model_validate({"from": "each", "outcome": "done", "to": END}),
    ]
    if include_completed_with_errors:
        edges.append(
            Edge.model_validate(
                {"from": "each", "outcome": "completed_with_errors", "to": END}
            )
        )
    return Workflow(
        name="concurrent_foreach_v1",
        input_schema=SchemaRef(
            type="object",
            properties={"items": {"type": "array"}},
        ),
        state_schema=state_schema,
        output_schema=SchemaRef(
            type="object",
            properties={"seen": {"type": "array"}},
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
            foreach,
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
        edges=edges,
    )


def _multi_step_overlay_workflow() -> Workflow:
    foreach = ForeachNode.model_validate(
        {
            "id": "each",
            "type": "foreach",
            "over": "state.items",
            "as": "item",
            "mode": "concurrent",
            "concurrent": {"max_active": 2, "max_outstanding": 2},
        }
    )
    return Workflow(
        name="concurrent_foreach_overlay",
        input_schema=SchemaRef(
            type="object",
            properties={"items": {"type": "array"}},
        ),
        state_schema=StateSchema.from_field_map(
            {
                "items": StateField(type="array"),
                "scratch": StateField(
                    type="array",
                    reducer=ReducerRef(name="wf.std.append"),
                ),
                "seen": StateField(
                    type="array",
                    reducer=ReducerRef(name="wf.std.append"),
                ),
            }
        ),
        output_schema=SchemaRef(
            type="object",
            properties={"seen": {"type": "array"}},
        ),
        node_defs=[
            NodeDef(
                name="stage_scratch",
                input_schema=SchemaRef(
                    type="object",
                    properties={"value": {}},
                    required=["value"],
                ),
                output_schema=SchemaRef(
                    type="object",
                    properties={"scratch": {}},
                    required=["scratch"],
                ),
                outcomes=["ok"],
            ),
            NodeDef(
                name="read_scratch",
                input_schema=SchemaRef(
                    type="object",
                    properties={"scratch": {}},
                    required=["scratch"],
                ),
                output_schema=SchemaRef(
                    type="object",
                    properties={"seen": {}},
                    required=["seen"],
                ),
                outcomes=["ok"],
            ),
        ],
        start="each",
        nodes=[
            foreach,
            NodeUse.model_validate(
                {
                    "id": "stage_scratch",
                    "type": "node",
                    "node": "stage_scratch",
                    "input": [{"target": "value", "path": "context.item"}],
                    "output": [{"source": "scratch", "target": "state.scratch"}],
                }
            ),
            NodeUse.model_validate(
                {
                    "id": "read_scratch",
                    "type": "node",
                    "node": "read_scratch",
                    "input": [{"target": "scratch", "path": "state.scratch"}],
                    "output": [{"source": "seen", "target": "state.seen"}],
                }
            ),
        ],
        edges=[
            Edge.model_validate(
                {"from": "each", "outcome": "loop", "to": "stage_scratch"}
            ),
            Edge.model_validate(
                {"from": "stage_scratch", "outcome": "ok", "to": "read_scratch"}
            ),
            Edge.model_validate({"from": "read_scratch", "outcome": "ok", "to": END}),
            Edge.model_validate({"from": "each", "outcome": "done", "to": END}),
        ],
    )


def _same_path_replace_workflow() -> Workflow:
    foreach = ForeachNode.model_validate(
        {
            "id": "each",
            "type": "foreach",
            "over": "state.items",
            "as": "item",
            "mode": "concurrent",
            "concurrent": {"max_active": 2, "max_outstanding": 2},
        }
    )
    return Workflow(
        name="concurrent_foreach_replace_conflict",
        input_schema=SchemaRef(
            type="object",
            properties={"items": {"type": "array"}},
        ),
        state_schema=StateSchema.from_field_map(
            {
                "items": StateField(type="array"),
                "winner": StateField(type="string"),
            }
        ),
        output_schema=SchemaRef(type="object", properties={}),
        node_defs=[
            NodeDef(
                name="write_winner",
                input_schema=SchemaRef(
                    type="object",
                    properties={"value": {}},
                    required=["value"],
                ),
                output_schema=SchemaRef(
                    type="object",
                    properties={"winner": {}},
                    required=["winner"],
                ),
                outcomes=["ok"],
            )
        ],
        start="each",
        nodes=[
            foreach,
            NodeUse.model_validate(
                {
                    "id": "write_winner",
                    "type": "node",
                    "node": "write_winner",
                    "input": [{"target": "value", "path": "context.item"}],
                    "output": [{"source": "winner", "target": "state.winner"}],
                }
            ),
        ],
        edges=[
            Edge.model_validate(
                {"from": "each", "outcome": "loop", "to": "write_winner"}
            ),
            Edge.model_validate({"from": "write_winner", "outcome": "ok", "to": END}),
            Edge.model_validate({"from": "each", "outcome": "done", "to": END}),
        ],
    )
