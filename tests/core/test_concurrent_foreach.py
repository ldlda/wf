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
from wf_core.run_state import ExecutionFrame, RunState, RuntimeContext
from wf_core.runtime.scheduler import ForeachIterationMetadata


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


def test_concurrent_foreach_item_frames_use_distinct_lineages() -> None:
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

    context_lineage_ids: list[str] = []

    def record(payload: dict[str, Any], ctx: RuntimeContext) -> dict[str, Any]:
        context_lineage_ids.append(ctx.lineage_id)
        return {"outcome": "ok", "output": payload}

    run = execute_workflow(
        workflow,
        {"items": ["a", "b"]},
        {"record": record},
    )

    item_frames = [
        frame for frame in run.frames.values() if frame.kind == "foreach_iteration"
    ]
    item_lineage_ids = {frame.lineage_id for frame in item_frames}

    assert run.frames["root"].scope_id == "root"
    assert run.frames["root"].lineage_id == "root"
    assert run.frames["root"].parent_lineage_id is None
    assert len(item_frames) == 2
    assert item_lineage_ids == {"root/each[0]", "root/each[1]"}
    assert set(context_lineage_ids) == item_lineage_ids
    assert all(frame.scope_id == "root" for frame in item_frames)
    assert all(frame.parent_lineage_id == "root" for frame in item_frames)


def test_nested_concurrent_foreach_records_parent_child_lineages() -> None:
    workflow = _nested_foreach_lineage_workflow()

    run = execute_workflow(
        workflow,
        {"outer_items": ["a", "b"], "inner_items": [1, 2]},
        {"record": lambda payload, _ctx: {"outcome": "ok", "output": payload}},
    )

    outer_frames = _foreach_frames(run, "outer_each")
    inner_frames = _foreach_frames(run, "inner_each")

    assert {frame.lineage_id for frame in outer_frames} == {
        "root/outer_each[0]",
        "root/outer_each[1]",
    }
    assert all(frame.parent_lineage_id == "root" for frame in outer_frames)
    assert {(frame.parent_lineage_id, frame.lineage_id) for frame in inner_frames} == {
        ("root/outer_each[0]", "root/outer_each[0]/inner_each[0]"),
        ("root/outer_each[0]", "root/outer_each[0]/inner_each[1]"),
        ("root/outer_each[1]", "root/outer_each[1]/inner_each[0]"),
        ("root/outer_each[1]", "root/outer_each[1]/inner_each[1]"),
    }


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


def test_sync_concurrent_foreach_barrier_replays_add_reducer_inputs() -> None:
    workflow = _sum_items_workflow()

    run = execute_workflow(
        workflow,
        {"items": [3, 1]},
        {
            "add_item": lambda payload, _ctx: {
                "outcome": "ok",
                "output": {"number": payload["value"]},
            }
        },
    )

    assert run.state["number"] == 6
    assert run.output["number"] == 6
    foreach_entries = [entry for entry in run.trace if entry.step_type == "foreach"]
    assert foreach_entries[-1].state_changes["state.number"] == 6


def test_sync_concurrent_foreach_same_item_reads_add_reducer_visible_value() -> None:
    workflow = _same_item_reducer_visibility_workflow()

    run = execute_workflow(
        workflow,
        {"items": [3]},
        {
            "add_item": lambda payload, _ctx: {
                "outcome": "ok",
                "output": {"number": payload["value"]},
            },
            "read_number": lambda payload, _ctx: {
                "outcome": "ok",
                "output": {"seen_number": payload["number"]},
            },
        },
    )

    stage_entry = next(entry for entry in run.trace if entry.node_id == "add_item")
    assert stage_entry.resolved_input["value"] == 3
    assert stage_entry.resolved_input["current_number"] == 2
    assert stage_entry.state_changes == {}
    read_entry = next(entry for entry in run.trace if entry.node_id == "read_number")
    assert read_entry.resolved_input["number"] == 5
    assert run.state["seen_number"] == [5]


def test_sync_concurrent_foreach_rejects_sibling_replace_writes() -> None:
    workflow = _same_path_replace_workflow()

    with pytest.raises(WorkflowExecutionError, match="mergeable reducer"):
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


def _sum_items_workflow() -> Workflow:
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
        name="concurrent_foreach_sum",
        input_schema=SchemaRef(
            type="object",
            properties={"items": {"type": "array"}},
        ),
        state_schema=StateSchema.from_field_map(
            {
                "items": StateField(type="array"),
                "number": StateField(
                    type="integer",
                    default=2,
                    reducer=ReducerRef(name="wf.std.add"),
                ),
            }
        ),
        output_schema=SchemaRef(
            type="object",
            properties={"number": {"type": "integer"}},
        ),
        node_defs=[
            NodeDef(
                name="add_item",
                input_schema=SchemaRef(
                    type="object",
                    properties={
                        "value": {"type": "integer"},
                        "current_number": {"type": "integer"},
                    },
                    required=["value", "current_number"],
                ),
                output_schema=SchemaRef(
                    type="object",
                    properties={"number": {"type": "integer"}},
                    required=["number"],
                ),
                outcomes=["ok"],
            )
        ],
        start="each",
        nodes=[
            foreach,
            NodeUse.model_validate(
                {
                    "id": "add_item",
                    "type": "node",
                    "node": "add_item",
                    "input": [
                        {"target": "value", "path": "context.item"},
                        {"target": "current_number", "path": "state.number"},
                    ],
                    "output": [{"source": "number", "target": "state.number"}],
                }
            ),
        ],
        edges=[
            Edge.model_validate({"from": "each", "outcome": "loop", "to": "add_item"}),
            Edge.model_validate({"from": "add_item", "outcome": "ok", "to": END}),
            Edge.model_validate({"from": "each", "outcome": "done", "to": END}),
        ],
    )


def _same_item_reducer_visibility_workflow() -> Workflow:
    foreach = ForeachNode.model_validate(
        {
            "id": "each",
            "type": "foreach",
            "over": "state.items",
            "as": "item",
            "mode": "concurrent",
            "concurrent": {"max_active": 1, "max_outstanding": 1},
        }
    )
    return Workflow(
        name="concurrent_foreach_same_item_reducer_visibility",
        input_schema=SchemaRef(
            type="object",
            properties={"items": {"type": "array"}},
        ),
        state_schema=StateSchema.from_field_map(
            {
                "items": StateField(type="array"),
                "number": StateField(
                    type="integer",
                    default=2,
                    reducer=ReducerRef(name="wf.std.add"),
                ),
                "seen_number": StateField(
                    type="array",
                    reducer=ReducerRef(name="wf.std.append"),
                ),
            }
        ),
        output_schema=SchemaRef(
            type="object",
            properties={"seen_number": {"type": "array"}},
        ),
        node_defs=[
            NodeDef(
                name="add_item",
                input_schema=SchemaRef(
                    type="object",
                    properties={
                        "value": {"type": "integer"},
                        "current_number": {"type": "integer"},
                    },
                    required=["value", "current_number"],
                ),
                output_schema=SchemaRef(
                    type="object",
                    properties={"number": {"type": "integer"}},
                    required=["number"],
                ),
                outcomes=["ok"],
            ),
            NodeDef(
                name="read_number",
                input_schema=SchemaRef(
                    type="object",
                    properties={"number": {"type": "integer"}},
                    required=["number"],
                ),
                output_schema=SchemaRef(
                    type="object",
                    properties={"seen_number": {"type": "integer"}},
                    required=["seen_number"],
                ),
                outcomes=["ok"],
            ),
        ],
        start="each",
        nodes=[
            foreach,
            NodeUse.model_validate(
                {
                    "id": "add_item",
                    "type": "node",
                    "node": "add_item",
                    "input": [
                        {"target": "value", "path": "context.item"},
                        {"target": "current_number", "path": "state.number"},
                    ],
                    "output": [{"source": "number", "target": "state.number"}],
                }
            ),
            NodeUse.model_validate(
                {
                    "id": "read_number",
                    "type": "node",
                    "node": "read_number",
                    "input": [{"target": "number", "path": "state.number"}],
                    "output": [
                        {"source": "seen_number", "target": "state.seen_number"}
                    ],
                }
            ),
        ],
        edges=[
            Edge.model_validate({"from": "each", "outcome": "loop", "to": "add_item"}),
            Edge.model_validate(
                {
                    "from": "add_item",
                    "outcome": "ok",
                    "to": "read_number",
                }
            ),
            Edge.model_validate({"from": "read_number", "outcome": "ok", "to": END}),
            Edge.model_validate({"from": "each", "outcome": "done", "to": END}),
        ],
    )


def _nested_foreach_lineage_workflow() -> Workflow:
    outer = ForeachNode.model_validate(
        {
            "id": "outer_each",
            "type": "foreach",
            "over": "state.outer_items",
            "as": "outer",
            "mode": "concurrent",
            "concurrent": {"max_active": 2, "max_outstanding": 2},
        }
    )
    inner = ForeachNode.model_validate(
        {
            "id": "inner_each",
            "type": "foreach",
            "over": "state.inner_items",
            "as": "inner",
            "mode": "concurrent",
            "concurrent": {"max_active": 2, "max_outstanding": 2},
        }
    )
    return Workflow(
        name="nested_foreach_lineages",
        input_schema=SchemaRef(
            type="object",
            properties={
                "outer_items": {"type": "array"},
                "inner_items": {"type": "array"},
            },
        ),
        state_schema=StateSchema.from_field_map(
            {
                "outer_items": StateField(type="array"),
                "inner_items": StateField(type="array"),
                "seen": StateField(
                    type="array",
                    reducer=ReducerRef(name="wf.std.append"),
                ),
            }
        ),
        output_schema=SchemaRef(type="object", properties={"seen": {"type": "array"}}),
        node_defs=[
            NodeDef(
                name="record",
                input_schema=SchemaRef(
                    type="object",
                    properties={"seen": {}},
                    required=["seen"],
                ),
                output_schema=SchemaRef(
                    type="object",
                    properties={"seen": {}},
                    required=["seen"],
                ),
                outcomes=["ok"],
            )
        ],
        start="outer_each",
        nodes=[
            outer,
            inner,
            NodeUse.model_validate(
                {
                    "id": "record",
                    "type": "node",
                    "node": "record",
                    "input": [{"target": "seen", "path": "context.inner"}],
                    "output": [{"source": "seen", "target": "state.seen"}],
                }
            ),
        ],
        edges=[
            Edge.model_validate(
                {
                    "from": "outer_each",
                    "outcome": "loop",
                    "to": "inner_each",
                }
            ),
            Edge.model_validate(
                {
                    "from": "inner_each",
                    "outcome": "loop",
                    "to": "record",
                }
            ),
            Edge.model_validate({"from": "record", "outcome": "ok", "to": END}),
            Edge.model_validate({"from": "inner_each", "outcome": "done", "to": END}),
            Edge.model_validate({"from": "outer_each", "outcome": "done", "to": END}),
        ],
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
                {
                    "from": "each",
                    "outcome": "completed_with_errors",
                    "to": END,
                }
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


def _foreach_frames(run: RunState, foreach_node_id: str) -> list[ExecutionFrame]:
    frames = []
    for frame in run.frames.values():
        metadata = ForeachIterationMetadata.from_frame(frame)
        if metadata is not None and metadata.foreach_node_id == foreach_node_id:
            frames.append(frame)
    return frames


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
                {
                    "from": "each",
                    "outcome": "loop",
                    "to": "stage_scratch",
                }
            ),
            Edge.model_validate(
                {
                    "from": "stage_scratch",
                    "outcome": "ok",
                    "to": "read_scratch",
                }
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
                {
                    "from": "each",
                    "outcome": "loop",
                    "to": "write_winner",
                }
            ),
            Edge.model_validate({"from": "write_winner", "outcome": "ok", "to": END}),
            Edge.model_validate({"from": "each", "outcome": "done", "to": END}),
        ],
    )
