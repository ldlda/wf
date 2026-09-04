from __future__ import annotations

from typing import Any

import pytest

from wf_core import (
    END,
    ConditionNode,
    Edge,
    ForeachNode,
    InterruptNode,
    NodeDef,
    NodeUse,
    ReducerRef,
    SchemaRef,
    StateField,
    StateSchema,
    SubgraphNode,
    Workflow,
    WorkflowExecutionError,
    execute_workflow,
    execute_workflow_async,
    resume_workflow_async,
)
from wf_core.run_state import ExecutionFrame, FrameStatus, RunState, RunStatus
from wf_core.runtime.foreach_state import item_frame_owner
from wf_core.runtime.scheduler import add_frame


def _node_use(node_id: str, *, node: str = "record") -> NodeUse:
    return NodeUse.model_validate(
        {
            "id": node_id,
            "type": "node",
            "node": node,
            "input": [{"target": "value", "path": "context.item"}],
            "output": [{"source": "seen", "target": "state.seen"}],
        }
    )


def _serial_workflow() -> Workflow:
    foreach = ForeachNode.model_validate(
        {
            "id": "each",
            "type": "foreach",
            "over": "state.items",
            "as": "item",
            "mode": "serial",
        }
    )
    return Workflow(
        name="foreach_back_edge",
        input_schema=SchemaRef(type="object", properties={"items": {"type": "array"}}),
        state_schema=StateSchema.from_field_map(
            {
                "items": StateField(type="array"),
                "seen": StateField(
                    type="array", reducer=ReducerRef(name="wf.std.append")
                ),
            }
        ),
        output_schema=SchemaRef(type="object", properties={"seen": {"type": "array"}}),
        node_defs=[
            NodeDef(
                name="record",
                input_schema=SchemaRef(
                    type="object", properties={"value": {}}, required=["value"]
                ),
                output_schema=SchemaRef(
                    type="object", properties={"seen": {}}, required=["seen"]
                ),
                outcomes=["ok"],
            )
        ],
        start="each",
        nodes=[
            foreach,
            NodeUse.model_validate(
                {
                    "id": "work",
                    "type": "node",
                    "node": "record",
                    "input": [{"target": "value", "path": "context.item"}],
                    "output": [{"source": "seen", "target": "state.seen"}],
                }
            ),
        ],
        edges=[
            Edge.model_validate({"from": "each", "outcome": "loop", "to": "work"}),
            Edge.model_validate({"from": "work", "outcome": "ok", "to": "each"}),
            Edge.model_validate({"from": "each", "outcome": "done", "to": END}),
        ],
    )


def test_serial_item_return_wakes_parent_and_admits_next_item() -> None:
    workflow = _serial_workflow()

    run = execute_workflow(
        workflow,
        {"items": ["a", "b"]},
        {
            "record": lambda payload, _ctx: {
                "outcome": "ok",
                "output": {"seen": payload["value"]},
            }
        },
    )

    assert run.status == RunStatus.COMPLETED
    assert run.state["seen"] == ["a", "b"]
    item_frames = [
        frame for frame in run.frames.values() if frame.kind == "foreach_iteration"
    ]
    assert len(item_frames) == 2
    assert all(frame.status == FrameStatus.COMPLETED for frame in item_frames)
    assert all(frame.finished_at_node_id == "each" for frame in item_frames)
    assert run.output["seen"] == ["a", "b"]


def test_foreach_body_cycle_can_repeat_then_return() -> None:
    foreach = ForeachNode.model_validate(
        {
            "id": "each",
            "type": "foreach",
            "over": "state.items",
            "as": "item",
            "mode": "serial",
        }
    )
    workflow = Workflow(
        name="foreach_body_cycle",
        input_schema=SchemaRef(type="object", properties={"items": {"type": "array"}}),
        state_schema=StateSchema.from_field_map(
            {
                "items": StateField(type="array"),
                "seen": StateField(
                    type="array", reducer=ReducerRef(name="wf.std.append")
                ),
            }
        ),
        output_schema=SchemaRef(type="object", properties={"seen": {"type": "array"}}),
        node_defs=[
            NodeDef(
                name="step_a",
                input_schema=SchemaRef(
                    type="object", properties={"value": {}}, required=["value"]
                ),
                output_schema=SchemaRef(
                    type="object", properties={"seen": {}}, required=["seen"]
                ),
                outcomes=["again", "done"],
            ),
            NodeDef(
                name="step_b",
                input_schema=SchemaRef(
                    type="object", properties={"seen": {}}, required=["seen"]
                ),
                output_schema=SchemaRef(
                    type="object", properties={"seen": {}}, required=["seen"]
                ),
                outcomes=["ok"],
            ),
        ],
        start="each",
        nodes=[
            foreach,
            NodeUse.model_validate(
                {
                    "id": "a",
                    "type": "node",
                    "node": "step_a",
                    "input": [{"target": "value", "path": "context.item"}],
                    "output": [{"source": "seen", "target": "state.seen"}],
                }
            ),
            NodeUse.model_validate(
                {
                    "id": "b",
                    "type": "node",
                    "node": "step_b",
                    "input": [{"target": "seen", "path": "context.item"}],
                    "output": [],
                }
            ),
        ],
        edges=[
            Edge.model_validate({"from": "each", "outcome": "loop", "to": "a"}),
            Edge.model_validate({"from": "a", "outcome": "again", "to": "b"}),
            Edge.model_validate({"from": "b", "outcome": "ok", "to": "a"}),
            Edge.model_validate({"from": "a", "outcome": "done", "to": "each"}),
            Edge.model_validate({"from": "each", "outcome": "done", "to": END}),
        ],
    )
    calls = {"count": 0}

    def step_a(payload: dict[str, Any], _ctx: object) -> dict[str, Any]:
        calls["count"] += 1
        outcome = "again" if calls["count"] == 1 else "done"
        return {"outcome": outcome, "output": {"seen": payload["value"]}}

    run = execute_workflow(
        workflow,
        {"items": ["x"]},
        {
            "step_a": step_a,
            "step_b": lambda payload, _ctx: {
                "outcome": "ok",
                "output": {"seen": payload["seen"]},
            },
        },
    )

    assert run.status == RunStatus.COMPLETED
    # `b` writes nothing; `a` writes once per visit (again + done).
    assert run.state["seen"] == ["x", "x"]


def test_conditional_body_can_return_on_either_outcome() -> None:
    foreach = ForeachNode.model_validate(
        {
            "id": "each",
            "type": "foreach",
            "over": "state.items",
            "as": "item",
            "mode": "serial",
        }
    )
    workflow = Workflow(
        name="foreach_conditional_return",
        input_schema=SchemaRef(type="object", properties={"items": {"type": "array"}}),
        state_schema=StateSchema.from_field_map(
            {
                "items": StateField(type="array"),
                "seen": StateField(
                    type="array", reducer=ReducerRef(name="wf.std.append")
                ),
            }
        ),
        output_schema=SchemaRef(type="object", properties={"seen": {"type": "array"}}),
        node_defs=[
            NodeDef(
                name="decide",
                input_schema=SchemaRef(
                    type="object", properties={"value": {}}, required=["value"]
                ),
                output_schema=SchemaRef(
                    type="object", properties={"seen": {}}, required=["seen"]
                ),
                outcomes=["true", "false"],
            ),
            NodeDef(
                name="work",
                input_schema=SchemaRef(
                    type="object", properties={"value": {}}, required=["value"]
                ),
                output_schema=SchemaRef(
                    type="object", properties={"seen": {}}, required=["seen"]
                ),
                outcomes=["ok"],
            ),
        ],
        start="each",
        nodes=[
            foreach,
            NodeUse.model_validate(
                {
                    "id": "condition",
                    "type": "node",
                    "node": "decide",
                    "input": [{"target": "value", "path": "context.item"}],
                    "output": [],
                }
            ),
            NodeUse.model_validate(
                {
                    "id": "work",
                    "type": "node",
                    "node": "work",
                    "input": [{"target": "value", "path": "context.item"}],
                    "output": [{"source": "seen", "target": "state.seen"}],
                }
            ),
            NodeUse.model_validate(
                {
                    "id": "work_false",
                    "type": "node",
                    "node": "work",
                    "input": [{"target": "value", "path": "context.item"}],
                    "output": [{"source": "seen", "target": "state.seen"}],
                }
            ),
        ],
        edges=[
            Edge.model_validate({"from": "each", "outcome": "loop", "to": "condition"}),
            Edge.model_validate({"from": "condition", "outcome": "true", "to": "work"}),
            Edge.model_validate(
                {"from": "condition", "outcome": "false", "to": "work_false"}
            ),
            Edge.model_validate({"from": "work", "outcome": "ok", "to": "each"}),
            Edge.model_validate({"from": "work_false", "outcome": "ok", "to": "each"}),
            Edge.model_validate({"from": "each", "outcome": "done", "to": END}),
        ],
    )

    def decide(payload: dict[str, Any], _ctx: object) -> dict[str, Any]:
        outcome = "true" if payload["value"] == "a" else "false"
        return {"outcome": outcome, "output": {"seen": payload["value"]}}

    def _work(payload: dict[str, Any], _ctx: object) -> dict[str, Any]:
        return {"outcome": "ok", "output": {"seen": payload["value"]}}

    run = execute_workflow(
        workflow,
        {"items": ["a", "b"]},
        {"decide": decide, "work": _work},
    )

    assert run.status == RunStatus.COMPLETED
    assert sorted(run.state["seen"]) == ["a", "b"]


def test_nested_foreach_returns_inner_then_outer() -> None:
    outer = ForeachNode.model_validate(
        {
            "id": "outer",
            "type": "foreach",
            "over": "state.items",
            "as": "outer_item",
            "mode": "concurrent",
            "concurrent": {"max_active": 2, "max_outstanding": 2},
        }
    )
    inner = ForeachNode.model_validate(
        {
            "id": "inner",
            "type": "foreach",
            "over": "state.inner_items",
            "as": "inner_item",
            "mode": "concurrent",
            "concurrent": {"max_active": 2, "max_outstanding": 2},
        }
    )
    workflow = Workflow(
        name="nested_foreach_return",
        input_schema=SchemaRef(type="object", properties={}),
        state_schema=StateSchema.from_field_map(
            {
                "items": StateField(type="array"),
                "inner_items": StateField(type="array"),
                "seen": StateField(
                    type="array", reducer=ReducerRef(name="wf.std.append")
                ),
            }
        ),
        output_schema=SchemaRef(type="object", properties={"seen": {"type": "array"}}),
        node_defs=[
            NodeDef(
                name="work",
                input_schema=SchemaRef(
                    type="object", properties={"value": {}}, required=["value"]
                ),
                output_schema=SchemaRef(
                    type="object", properties={"seen": {}}, required=["seen"]
                ),
                outcomes=["ok"],
            )
        ],
        start="outer",
        nodes=[
            outer,
            inner,
            NodeUse.model_validate(
                {
                    "id": "work",
                    "type": "node",
                    "node": "work",
                    "input": [{"target": "value", "path": "context.inner_item"}],
                    "output": [{"source": "seen", "target": "state.seen"}],
                }
            ),
            NodeUse.model_validate(
                {
                    "id": "tail",
                    "type": "node",
                    "node": "work",
                    "input": [{"target": "value", "path": "context.outer_item"}],
                    "output": [{"source": "seen", "target": "state.seen"}],
                }
            ),
            NodeUse.model_validate(
                {
                    "id": "after",
                    "type": "node",
                    "node": "work",
                    "input": [{"target": "value", "path": "state.seen"}],
                    "output": [],
                }
            ),
        ],
        edges=[
            Edge.model_validate({"from": "outer", "outcome": "loop", "to": "inner"}),
            Edge.model_validate({"from": "inner", "outcome": "loop", "to": "work"}),
            Edge.model_validate({"from": "work", "outcome": "ok", "to": "inner"}),
            Edge.model_validate({"from": "inner", "outcome": "done", "to": "tail"}),
            Edge.model_validate({"from": "tail", "outcome": "ok", "to": "outer"}),
            Edge.model_validate({"from": "outer", "outcome": "done", "to": "after"}),
            Edge.model_validate({"from": "after", "outcome": "ok", "to": END}),
        ],
    )

    run = execute_workflow(
        workflow,
        {"items": ["a"], "inner_items": [1, 2]},
        {
            "work": lambda payload, _ctx: {
                "outcome": "ok",
                "output": {"seen": payload["value"]},
            }
        },
    )

    assert run.status == RunStatus.COMPLETED
    # Inner items 1, 2 plus outer tail "a" plus after echo.
    assert run.state["seen"][:3] == [1, 2, "a"]


def _nested_mode_workflow(*, outer_mode: str, inner_mode: str) -> Workflow:
    def _foreach(node_id: str, *, over: str, alias: str, mode: str) -> ForeachNode:
        payload: dict[str, Any] = {
            "id": node_id,
            "type": "foreach",
            "over": over,
            "as": alias,
            "mode": mode,
        }
        if mode == "concurrent":
            payload["concurrent"] = {"max_active": 2, "max_outstanding": 2}
        return ForeachNode.model_validate(payload)

    return Workflow(
        name="nested_foreach_modes",
        input_schema=SchemaRef(type="object", properties={}),
        state_schema=StateSchema.from_field_map(
            {
                "items": StateField(type="array"),
                "inner_items": StateField(type="array"),
                "seen": StateField(
                    type="array", reducer=ReducerRef(name="wf.std.append")
                ),
            }
        ),
        output_schema=SchemaRef(type="object", properties={"seen": {"type": "array"}}),
        node_defs=[
            NodeDef(
                name="work",
                input_schema=SchemaRef(
                    type="object", properties={"value": {}}, required=["value"]
                ),
                output_schema=SchemaRef(
                    type="object", properties={"seen": {}}, required=["seen"]
                ),
                outcomes=["ok"],
            )
        ],
        start="outer",
        nodes=[
            _foreach("outer", over="state.items", alias="outer_item", mode=outer_mode),
            _foreach(
                "inner",
                over="state.inner_items",
                alias="inner_item",
                mode=inner_mode,
            ),
            NodeUse.model_validate(
                {
                    "id": "work",
                    "type": "node",
                    "node": "work",
                    "input": [{"target": "value", "path": "context.inner_item"}],
                    "output": [{"source": "seen", "target": "state.seen"}],
                }
            ),
        ],
        edges=[
            Edge.model_validate({"from": "outer", "outcome": "loop", "to": "inner"}),
            Edge.model_validate({"from": "inner", "outcome": "loop", "to": "work"}),
            Edge.model_validate({"from": "work", "outcome": "ok", "to": "inner"}),
            # No intermediate writer: the inner barrier (or serial return)
            # must route inner writes to the scope root on its own.
            Edge.model_validate({"from": "inner", "outcome": "done", "to": "outer"}),
            Edge.model_validate({"from": "outer", "outcome": "done", "to": END}),
        ],
    )


@pytest.mark.parametrize(
    ("outer_mode", "inner_mode", "exact_order"),
    [
        ("serial", "serial", True),
        ("serial", "concurrent", True),
        ("concurrent", "serial", False),
        ("concurrent", "concurrent", False),
    ],
)
def test_nested_foreach_preserves_inner_writes_in_all_modes(
    outer_mode: str, inner_mode: str, exact_order: bool
) -> None:
    """Inner writes must reach root state whatever the nesting modes are.

    Serial owners commit through the scope root; concurrent owners buffer
    for their barrier. Every inner write (1, 2 per outer item) must survive
    even with no intermediate writer to replay-rescue stranded lineages.

    Serial outer admission is strictly ordered, so the sequence is exactly
    [1, 2, 1, 2]. Concurrent outer completion order depends on scheduling,
    so only the multiset is contractual there.
    """
    workflow = _nested_mode_workflow(outer_mode=outer_mode, inner_mode=inner_mode)

    run = execute_workflow(
        workflow,
        {"items": ["a", "b"], "inner_items": [1, 2]},
        {
            "work": lambda payload, _ctx: {
                "outcome": "ok",
                "output": {"seen": payload["value"]},
            }
        },
    )

    assert run.status == RunStatus.COMPLETED
    seen = run.state.get("seen") or []
    if exact_order:
        assert seen == [1, 2, 1, 2]
    else:
        assert sorted(seen, key=repr) == sorted([1, 2, 1, 2], key=repr)


@pytest.mark.parametrize("inner_mode", ["serial", "concurrent"])
def test_nested_item_reads_buffered_ancestor_state(inner_mode: str) -> None:
    """An inner item inherits the enclosing concurrent item's state view."""
    inner_payload: dict[str, Any] = {
        "id": "inner",
        "type": "foreach",
        "over": "state.inner_items",
        "as": "inner_item",
        "mode": inner_mode,
    }
    if inner_mode == "concurrent":
        inner_payload["concurrent"] = {"max_active": 1, "max_outstanding": 1}
    workflow = Workflow(
        name="nested_foreach_reads_ancestor_state",
        input_schema=SchemaRef(type="object", properties={}),
        state_schema=StateSchema.from_field_map(
            {
                "items": StateField(type="array"),
                "inner_items": StateField(type="array"),
                "marker": StateField(type="string", default="root"),
                "seen": StateField(
                    type="array", reducer=ReducerRef(name="wf.std.append")
                ),
            }
        ),
        output_schema=SchemaRef(type="object", properties={"seen": {"type": "array"}}),
        node_defs=[
            NodeDef(
                name="write_marker",
                input_schema=SchemaRef(
                    type="object", properties={"marker": {}}, required=["marker"]
                ),
                output_schema=SchemaRef(
                    type="object", properties={"marker": {}}, required=["marker"]
                ),
                outcomes=["ok"],
            ),
            NodeDef(
                name="observe_marker",
                input_schema=SchemaRef(
                    type="object", properties={"marker": {}}, required=["marker"]
                ),
                output_schema=SchemaRef(
                    type="object", properties={"seen": {}}, required=["seen"]
                ),
                outcomes=["ok"],
            ),
        ],
        start="outer",
        nodes=[
            ForeachNode.model_validate(
                {
                    "id": "outer",
                    "type": "foreach",
                    "over": "state.items",
                    "as": "outer_item",
                    "mode": "concurrent",
                    "concurrent": {"max_active": 1, "max_outstanding": 1},
                }
            ),
            NodeUse.model_validate(
                {
                    "id": "write_outer",
                    "type": "node",
                    "node": "write_marker",
                    "input": [{"target": "marker", "path": "context.outer_item"}],
                    "output": [{"source": "marker", "target": "state.marker"}],
                }
            ),
            ForeachNode.model_validate(inner_payload),
            NodeUse.model_validate(
                {
                    "id": "read_inner",
                    "type": "node",
                    "node": "observe_marker",
                    "input": [{"target": "marker", "path": "state.marker"}],
                    "output": [{"source": "seen", "target": "state.seen"}],
                }
            ),
        ],
        edges=[
            Edge.model_validate(
                {"from": "outer", "outcome": "loop", "to": "write_outer"}
            ),
            Edge.model_validate(
                {"from": "write_outer", "outcome": "ok", "to": "inner"}
            ),
            Edge.model_validate(
                {"from": "inner", "outcome": "loop", "to": "read_inner"}
            ),
            Edge.model_validate({"from": "read_inner", "outcome": "ok", "to": "inner"}),
            Edge.model_validate({"from": "inner", "outcome": "done", "to": "outer"}),
            Edge.model_validate({"from": "outer", "outcome": "done", "to": END}),
        ],
    )

    run = execute_workflow(
        workflow,
        {"items": ["outer"], "inner_items": [1]},
        {
            "write_marker": lambda payload, _ctx: {
                "outcome": "ok",
                "output": {"marker": payload["marker"]},
            },
            "observe_marker": lambda payload, _ctx: {
                "outcome": "ok",
                "output": {"seen": payload["marker"]},
            },
        },
    )

    assert run.status == RunStatus.COMPLETED
    assert run.state["seen"] == ["outer"]


def _three_level_workflow(
    *, outer_mode: str, middle_mode: str, inner_mode: str
) -> Workflow:
    def _foreach(node_id: str, *, over: str, alias: str, mode: str) -> ForeachNode:
        payload: dict[str, Any] = {
            "id": node_id,
            "type": "foreach",
            "over": over,
            "as": alias,
            "mode": mode,
        }
        if mode == "concurrent":
            payload["concurrent"] = {"max_active": 2, "max_outstanding": 2}
        return ForeachNode.model_validate(payload)

    return Workflow(
        name="three_level_nested_foreach",
        input_schema=SchemaRef(type="object", properties={}),
        state_schema=StateSchema.from_field_map(
            {
                "items": StateField(type="array"),
                "mid_items": StateField(type="array"),
                "inner_items": StateField(type="array"),
                "seen": StateField(
                    type="array", reducer=ReducerRef(name="wf.std.append")
                ),
            }
        ),
        output_schema=SchemaRef(type="object", properties={"seen": {"type": "array"}}),
        node_defs=[
            NodeDef(
                name="work",
                input_schema=SchemaRef(
                    type="object", properties={"value": {}}, required=["value"]
                ),
                output_schema=SchemaRef(
                    type="object", properties={"seen": {}}, required=["seen"]
                ),
                outcomes=["ok"],
            )
        ],
        start="outer",
        nodes=[
            _foreach("outer", over="state.items", alias="outer_item", mode=outer_mode),
            _foreach(
                "middle",
                over="state.mid_items",
                alias="mid_item",
                mode=middle_mode,
            ),
            _foreach(
                "inner",
                over="state.inner_items",
                alias="inner_item",
                mode=inner_mode,
            ),
            NodeUse.model_validate(
                {
                    "id": "work",
                    "type": "node",
                    "node": "work",
                    "input": [{"target": "value", "path": "context.inner_item"}],
                    "output": [{"source": "seen", "target": "state.seen"}],
                }
            ),
        ],
        edges=[
            Edge.model_validate({"from": "outer", "outcome": "loop", "to": "middle"}),
            Edge.model_validate({"from": "middle", "outcome": "loop", "to": "inner"}),
            Edge.model_validate({"from": "inner", "outcome": "loop", "to": "work"}),
            Edge.model_validate({"from": "work", "outcome": "ok", "to": "inner"}),
            Edge.model_validate({"from": "inner", "outcome": "done", "to": "middle"}),
            Edge.model_validate({"from": "middle", "outcome": "done", "to": "outer"}),
            Edge.model_validate({"from": "outer", "outcome": "done", "to": END}),
        ],
    )


@pytest.mark.parametrize(
    ("outer_mode", "middle_mode", "inner_mode"),
    [
        ("serial", "serial", "serial"),
        ("serial", "serial", "concurrent"),
        ("serial", "concurrent", "serial"),
        ("serial", "concurrent", "concurrent"),
        ("concurrent", "serial", "serial"),
        ("concurrent", "serial", "concurrent"),
        ("concurrent", "concurrent", "serial"),
        ("concurrent", "concurrent", "concurrent"),
    ],
)
def test_three_level_nested_foreach_preserves_writes(
    outer_mode: str, middle_mode: str, inner_mode: str
) -> None:
    """Write routing holds through three nesting levels in every mode mix.

    Barriers merge items in index order, so each middle visit yields exactly
    [1, 2]; only the outer completion order varies. A serial outer admits
    in order, making [1, 2, 1, 2] exact, while a concurrent outer leaves
    only the multiset contractual.
    """
    workflow = _three_level_workflow(
        outer_mode=outer_mode, middle_mode=middle_mode, inner_mode=inner_mode
    )

    run = execute_workflow(
        workflow,
        {"items": ["a", "b"], "mid_items": ["m"], "inner_items": [1, 2]},
        {
            "work": lambda payload, _ctx: {
                "outcome": "ok",
                "output": {"seen": payload["value"]},
            }
        },
    )

    assert run.status == RunStatus.COMPLETED
    seen = run.state.get("seen") or []
    if outer_mode == "serial":
        assert seen == [1, 2, 1, 2]
    else:
        assert sorted(seen, key=repr) == sorted([1, 2, 1, 2], key=repr)


def test_item_frame_owner_rejects_missing_parent_frame() -> None:
    """A foreach_iteration frame without a parent is malformed, not ordinary."""
    frame = ExecutionFrame(
        id="orphan",
        kind="foreach_iteration",
        node_id="work",
        parent_frame_id=None,
        metadata={
            "foreach_node_id": "each",
            "activation_id": "root:each#0",
            "loop_index": 0,
            "loop_item": "a",
            "loop_alias": "item",
        },
    )

    with pytest.raises(WorkflowExecutionError, match="parent"):
        item_frame_owner(frame)


def test_foreach_aware_patch_rejects_parent_cycle() -> None:
    """A cyclic item-parent chain fails closed instead of looping forever."""
    from wf_core.runtime.foreach_state import load_or_begin_foreach_activation
    from wf_core.runtime.lineage import commit_foreach_aware_patch
    from wf_core.runtime.ops.state import StatePatch

    frame_a = ExecutionFrame(id="frame-a", kind="foreach_iteration", node_id="work")
    frame_b = ExecutionFrame(id="frame-b", kind="foreach_iteration", node_id="work")
    activation_on_b = load_or_begin_foreach_activation(frame_b, "each", mode="serial")
    activation_on_a = load_or_begin_foreach_activation(frame_a, "each", mode="serial")
    frame_a.parent_frame_id = "frame-b"
    frame_a.metadata.update(
        {
            "foreach_node_id": "each",
            "activation_id": activation_on_b.id,
            "loop_index": 0,
            "loop_item": "a",
            "loop_alias": "item",
        }
    )
    frame_b.parent_frame_id = "frame-a"
    frame_b.metadata.update(
        {
            "foreach_node_id": "each",
            "activation_id": activation_on_a.id,
            "loop_index": 0,
            "loop_item": "a",
            "loop_alias": "item",
        }
    )
    run = RunState(
        workflow_name="parent_cycle",
        status=RunStatus.RUNNING,
        workflow_input={},
        state={},
        frames={"frame-a": frame_a, "frame-b": frame_b},
    )

    with pytest.raises(WorkflowExecutionError, match="cycle"):
        commit_foreach_aware_patch(run, frame_a, StatePatch(changes={}))


def test_foreach_aware_patch_rejects_concurrent_self_cycle() -> None:
    """A self-parented item with a concurrent owner must fail, not buffer."""
    from wf_core.run_state import LineageState
    from wf_core.runtime.foreach_state import load_or_begin_foreach_activation
    from wf_core.runtime.lineage import commit_foreach_aware_patch
    from wf_core.runtime.ops.state import StatePatch

    frame = ExecutionFrame(
        id="self",
        kind="foreach_iteration",
        node_id="work",
        scope_id="root",
        lineage_id="root",
    )
    activation = load_or_begin_foreach_activation(frame, "each", mode="concurrent")
    frame.parent_frame_id = "self"
    frame.metadata.update(
        {
            "foreach_node_id": "each",
            "activation_id": activation.id,
            "loop_index": 0,
            "loop_item": "a",
            "loop_alias": "item",
        }
    )
    run = RunState(
        workflow_name="concurrent_self_cycle",
        status=RunStatus.RUNNING,
        workflow_input={},
        state={},
        frames={"self": frame},
        lineages={"root": LineageState(id="root", scope_id="root")},
    )

    with pytest.raises(WorkflowExecutionError, match="cycle"):
        commit_foreach_aware_patch(run, frame, StatePatch(changes={}))
    assert run.lineages["root"].writes == []


def test_foreach_aware_patch_rejects_cycle_through_concurrent_boundary() -> None:
    """A parent cycle spanning a concurrent boundary must fail, not buffer."""
    from wf_core.run_state import LineageState
    from wf_core.runtime.foreach_state import load_or_begin_foreach_activation
    from wf_core.runtime.lineage import commit_foreach_aware_patch
    from wf_core.runtime.ops.state import StatePatch

    frame_a = ExecutionFrame(
        id="frame-a",
        kind="foreach_iteration",
        node_id="work",
        scope_id="root",
        lineage_id="root",
    )
    frame_b = ExecutionFrame(id="frame-b", kind="foreach_iteration", node_id="work")
    activation_on_b = load_or_begin_foreach_activation(
        frame_b, "each", mode="concurrent"
    )
    activation_on_a = load_or_begin_foreach_activation(frame_a, "each", mode="serial")
    frame_a.parent_frame_id = "frame-b"
    frame_a.metadata.update(
        {
            "foreach_node_id": "each",
            "activation_id": activation_on_b.id,
            "loop_index": 0,
            "loop_item": "a",
            "loop_alias": "item",
        }
    )
    frame_b.parent_frame_id = "frame-a"
    frame_b.metadata.update(
        {
            "foreach_node_id": "each",
            "activation_id": activation_on_a.id,
            "loop_index": 0,
            "loop_item": "a",
            "loop_alias": "item",
        }
    )
    run = RunState(
        workflow_name="mixed_mode_cycle",
        status=RunStatus.RUNNING,
        workflow_input={},
        state={},
        frames={"frame-a": frame_a, "frame-b": frame_b},
        lineages={"root": LineageState(id="root", scope_id="root")},
    )

    with pytest.raises(WorkflowExecutionError, match="cycle"):
        commit_foreach_aware_patch(run, frame_a, StatePatch(changes={}))
    assert run.lineages["root"].writes == []


def test_reentering_foreach_uses_fresh_activation_and_item_frames() -> None:
    workflow = Workflow(
        name="foreach_reentry",
        input_schema=SchemaRef(type="object", properties={}),
        state_schema=StateSchema.from_field_map(
            {
                "items": StateField(type="array"),
                "count": StateField(type="integer", default=0),
                "seen": StateField(
                    type="array", reducer=ReducerRef(name="wf.std.append")
                ),
            }
        ),
        output_schema=SchemaRef(type="object", properties={"seen": {"type": "array"}}),
        node_defs=[
            NodeDef(
                name="record",
                input_schema=SchemaRef(
                    type="object", properties={"value": {}}, required=["value"]
                ),
                output_schema=SchemaRef(
                    type="object", properties={"seen": {}}, required=["seen"]
                ),
                outcomes=["ok"],
            ),
            NodeDef(
                name="bump",
                input_schema=SchemaRef(
                    type="object", properties={"count": {"type": "integer"}}
                ),
                output_schema=SchemaRef(
                    type="object", properties={"count": {"type": "integer"}}
                ),
                outcomes=["ok"],
            ),
        ],
        start="again",
        nodes=[
            ConditionNode.model_validate(
                {
                    "id": "again",
                    "type": "condition",
                    "check": {
                        "op": "lt",
                        "left": {"path": "state.count"},
                        "right": {"value": 2},
                    },
                }
            ),
            ForeachNode.model_validate(
                {
                    "id": "each",
                    "type": "foreach",
                    "over": "state.items",
                    "as": "item",
                    "mode": "serial",
                }
            ),
            NodeUse.model_validate(
                {
                    "id": "work",
                    "type": "node",
                    "node": "record",
                    "input": [{"target": "value", "path": "context.item"}],
                    "output": [{"source": "seen", "target": "state.seen"}],
                }
            ),
            NodeUse.model_validate(
                {
                    "id": "bump",
                    "type": "node",
                    "node": "bump",
                    "input": [{"target": "count", "path": "state.count"}],
                    "output": [{"source": "count", "target": "state.count"}],
                }
            ),
        ],
        edges=[
            Edge.model_validate({"from": "again", "outcome": "true", "to": "each"}),
            Edge.model_validate({"from": "each", "outcome": "loop", "to": "work"}),
            Edge.model_validate({"from": "work", "outcome": "ok", "to": "each"}),
            Edge.model_validate({"from": "each", "outcome": "done", "to": "bump"}),
            Edge.model_validate({"from": "bump", "outcome": "ok", "to": "again"}),
            Edge.model_validate({"from": "again", "outcome": "false", "to": END}),
        ],
    )

    def bump(payload: dict[str, Any], _ctx: object) -> dict[str, Any]:
        count = payload.get("count", 0)
        assert isinstance(count, int)
        return {"outcome": "ok", "output": {"count": count + 1}}

    run = execute_workflow(
        workflow,
        {"items": ["a"]},
        {
            "record": lambda payload, _ctx: {
                "outcome": "ok",
                "output": {"seen": payload["value"]},
            },
            "bump": bump,
        },
    )

    assert run.status == RunStatus.COMPLETED
    assert run.state["seen"] == ["a", "a"]
    item_frames = [
        frame for frame in run.frames.values() if frame.kind == "foreach_iteration"
    ]
    assert len(item_frames) == 2
    owners = [item_frame_owner(frame) for frame in item_frames]
    assert all(owner is not None for owner in owners)
    assert owners[0] is not None and owners[1] is not None
    assert owners[0].activation_id != owners[1].activation_id
    assert item_frames[0].id != item_frames[1].id
    # Both visits run item zero, but activation-qualified frame ids differ.
    assert all(frame.id.endswith(":0") for frame in item_frames)


def test_subgraph_end_returns_to_subgraph_node_then_foreach_owner() -> None:
    from wf_core import PreparedSubgraph

    child = Workflow(
        name="child",
        input_schema=SchemaRef(type="object", properties={"value": {}}),
        state_schema=StateSchema.from_field_map({"seen": StateField(type="string")}),
        output_schema=SchemaRef(type="object", properties={"seen": {}}),
        node_defs=[
            NodeDef(
                name="inner_record",
                input_schema=SchemaRef(
                    type="object", properties={"value": {}}, required=["value"]
                ),
                output_schema=SchemaRef(
                    type="object", properties={"seen": {}}, required=["seen"]
                ),
                outcomes=["ok"],
            )
        ],
        start="inner_record",
        nodes=[
            NodeUse.model_validate(
                {
                    "id": "inner_record",
                    "type": "node",
                    "node": "inner_record",
                    "input": [{"target": "value", "path": "input.value"}],
                    "output": [{"source": "seen", "target": "state.seen"}],
                }
            )
        ],
        edges=[
            Edge.model_validate({"from": "inner_record", "outcome": "ok", "to": END})
        ],
    )
    foreach = ForeachNode.model_validate(
        {
            "id": "each",
            "type": "foreach",
            "over": "state.items",
            "as": "item",
            "mode": "serial",
        }
    )
    workflow = Workflow(
        name="foreach_subgraph",
        input_schema=SchemaRef(type="object", properties={"items": {"type": "array"}}),
        state_schema=StateSchema.from_field_map(
            {
                "items": StateField(type="array"),
                "seen": StateField(
                    type="array", reducer=ReducerRef(name="wf.std.append")
                ),
            }
        ),
        output_schema=SchemaRef(type="object", properties={"seen": {"type": "array"}}),
        node_defs=[],
        start="each",
        nodes=[
            foreach,
            SubgraphNode.model_validate(
                {
                    "id": "child",
                    "type": "subgraph",
                    "workflow": "child.workflow",
                    "input_schema": {"type": "object", "properties": {"value": {}}},
                    "output_schema": {"type": "object", "properties": {"seen": {}}},
                    "input": [{"target": "value", "path": "context.item"}],
                    "output": [{"source": "seen", "target": "state.seen"}],
                    "outcomes": ["ok"],
                }
            ),
        ],
        edges=[
            Edge.model_validate({"from": "each", "outcome": "loop", "to": "child"}),
            Edge.model_validate({"from": "child", "outcome": "ok", "to": "each"}),
            Edge.model_validate({"from": "each", "outcome": "done", "to": END}),
        ],
    )

    run = execute_workflow(
        workflow,
        {"items": ["a", "b"]},
        {},
        subgraphs={
            "child.workflow": PreparedSubgraph(
                workflow=child,
                registry={
                    "inner_record": lambda payload, _ctx: {"seen": payload["value"]}
                },
            )
        },
    )

    assert run.status == RunStatus.COMPLETED
    assert run.state["seen"] == ["a", "b"]


def test_concurrent_subgraph_item_returns_through_owner() -> None:
    from wf_core import PreparedSubgraph

    child = Workflow(
        name="child",
        input_schema=SchemaRef(type="object", properties={"value": {}}),
        state_schema=StateSchema.from_field_map({"seen": StateField(type="string")}),
        output_schema=SchemaRef(type="object", properties={"seen": {}}),
        node_defs=[
            NodeDef(
                name="inner_record",
                input_schema=SchemaRef(
                    type="object", properties={"value": {}}, required=["value"]
                ),
                output_schema=SchemaRef(
                    type="object", properties={"seen": {}}, required=["seen"]
                ),
                outcomes=["ok"],
            )
        ],
        start="inner_record",
        nodes=[
            NodeUse.model_validate(
                {
                    "id": "inner_record",
                    "type": "node",
                    "node": "inner_record",
                    "input": [{"target": "value", "path": "input.value"}],
                    "output": [{"source": "seen", "target": "state.seen"}],
                }
            )
        ],
        edges=[
            Edge.model_validate({"from": "inner_record", "outcome": "ok", "to": END})
        ],
    )
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
    workflow = Workflow(
        name="foreach_concurrent_subgraph",
        input_schema=SchemaRef(type="object", properties={"items": {"type": "array"}}),
        state_schema=StateSchema.from_field_map(
            {
                "items": StateField(type="array"),
                "seen": StateField(
                    type="array", reducer=ReducerRef(name="wf.std.append")
                ),
            }
        ),
        output_schema=SchemaRef(type="object", properties={"seen": {"type": "array"}}),
        node_defs=[],
        start="each",
        nodes=[
            foreach,
            SubgraphNode.model_validate(
                {
                    "id": "child",
                    "type": "subgraph",
                    "workflow": "child.workflow",
                    "input_schema": {"type": "object", "properties": {"value": {}}},
                    "output_schema": {"type": "object", "properties": {"seen": {}}},
                    "input": [{"target": "value", "path": "context.item"}],
                    "output": [{"source": "seen", "target": "state.seen"}],
                    "outcomes": ["ok"],
                }
            ),
        ],
        edges=[
            Edge.model_validate({"from": "each", "outcome": "loop", "to": "child"}),
            Edge.model_validate({"from": "child", "outcome": "ok", "to": "each"}),
            Edge.model_validate({"from": "each", "outcome": "done", "to": END}),
        ],
    )

    run = execute_workflow(
        workflow,
        {"items": ["a", "b"]},
        {},
        subgraphs={
            "child.workflow": PreparedSubgraph(
                workflow=child,
                registry={
                    "inner_record": lambda payload, _ctx: {"seen": payload["value"]}
                },
            )
        },
    )

    assert run.status == RunStatus.COMPLETED
    assert sorted(run.state["seen"]) == ["a", "b"]


async def test_serial_interrupt_resume_commits_answer_to_parent_state() -> None:
    """A serial item resume must land in parent state, not the child lineage."""
    foreach = ForeachNode.model_validate(
        {
            "id": "each",
            "type": "foreach",
            "over": "state.items",
            "as": "item",
            "mode": "serial",
        }
    )
    workflow = Workflow(
        name="foreach_serial_interrupt",
        input_schema=SchemaRef(type="object", properties={"items": {"type": "array"}}),
        state_schema=StateSchema.from_field_map(
            {
                "items": StateField(type="array"),
                "answers": StateField(
                    type="array", reducer=ReducerRef(name="wf.std.append")
                ),
            }
        ),
        output_schema=SchemaRef(
            type="object", properties={"answers": {"type": "array"}}
        ),
        node_defs=[],
        start="each",
        nodes=[
            foreach,
            InterruptNode.model_validate(
                {
                    "id": "ask",
                    "type": "interrupt",
                    "kind": "approval",
                    "request": [{"target": "item", "path": "context.item"}],
                    "resume": [{"source": "answer", "target": "state.answers"}],
                }
            ),
        ],
        edges=[
            Edge.model_validate({"from": "each", "outcome": "loop", "to": "ask"}),
            Edge.model_validate({"from": "ask", "outcome": "submitted", "to": "each"}),
            Edge.model_validate({"from": "each", "outcome": "done", "to": END}),
        ],
    )

    run = await execute_workflow_async(workflow, {"items": ["a", "b"]}, {})
    assert run.status == RunStatus.INTERRUPTED

    resumed = await resume_workflow_async(
        workflow, run, {}, resume_payload={"answer": "a"}
    )
    assert resumed.status == RunStatus.INTERRUPTED

    finished = await resume_workflow_async(
        workflow, resumed, {}, resume_payload={"answer": "b"}
    )
    assert finished.status == RunStatus.COMPLETED
    assert finished.state["answers"] == ["a", "b"]


def test_nonlocal_runtime_return_fails_closed_when_validation_is_bypassed() -> None:
    run = RunState(
        workflow_name="nonlocal",
        status=RunStatus.RUNNING,
        workflow_input={},
        state={},
        frames={},
    )
    add_frame(
        run,
        ExecutionFrame(id="root", kind="workflow", node_id="outer"),
    )
    add_frame(
        run,
        ExecutionFrame(
            id="outer-item",
            kind="foreach_iteration",
            node_id="inner",
            parent_frame_id="root",
            metadata={
                "foreach_node_id": "outer",
                "activation_id": "root:outer#0",
                "loop_index": 0,
                "loop_item": "a",
                "loop_alias": "outer_item",
            },
        ),
    )
    add_frame(
        run,
        ExecutionFrame(
            id="inner-item",
            kind="foreach_iteration",
            node_id="work",
            parent_frame_id="outer-item",
            metadata={
                "foreach_node_id": "inner",
                "activation_id": "outer-item:inner#0",
                "loop_index": 0,
                "loop_item": 1,
                "loop_alias": "inner_item",
            },
        ),
    )
    run.current_frame_id = "inner-item"
    run.sync_from_current_frame()

    from wf_core.runtime.ops.flow import advance_frame

    with pytest.raises(WorkflowExecutionError, match="non-local|ancestor|immediate"):
        advance_frame(run, run.frames["inner-item"], outcome="ok", next_node_id="outer")


def test_root_frame_targeting_foreach_enters_normally() -> None:
    """A root frame naming a foreach enters it; only an item frame returns."""
    from wf_core.runtime.ops.flow import advance_frame

    run = RunState(
        workflow_name="root_entry",
        status=RunStatus.RUNNING,
        workflow_input={},
        state={},
        frames={},
    )
    add_frame(
        run,
        ExecutionFrame(id="root", kind="workflow", node_id="start"),
    )
    run.current_frame_id = "root"
    run.sync_from_current_frame()

    advance_frame(run, run.frames["root"], outcome="ok", next_node_id="each")

    entered = run.frames["root"]
    assert entered.node_id == "each"
    assert entered.status == FrameStatus.PENDING
    assert entered.finished_at_node_id is None


def test_completed_activation_cannot_consume_later_activation_result_or_wake() -> None:
    """A closed visit rejects buffered results and wake-ups from other visits."""
    from wf_core.runtime.foreach_state import (
        close_foreach_activation,
        load_or_begin_foreach_activation,
        require_foreach_activation,
    )
    from wf_core.runtime.scheduler import (
        block_frame_on_children,
        wake_parent_for_child_progress,
    )

    parent = ExecutionFrame(id="root", kind="workflow", node_id="each")
    first = load_or_begin_foreach_activation(parent, "each", mode="concurrent")
    first.barrier.next_index = 1
    first.barrier.start_child(f"{first.id}:0")
    from wf_core.runtime.foreach_state import save_foreach_activation

    save_foreach_activation(parent, first)
    close_foreach_activation(parent, first)
    second = load_or_begin_foreach_activation(parent, "each", mode="concurrent")
    save_foreach_activation(parent, second)

    assert second.id != first.id

    with pytest.raises(WorkflowExecutionError, match="closed|superseded"):
        require_foreach_activation(parent, "each", first.id)

    run = RunState(
        workflow_name="activation_isolation",
        status=RunStatus.RUNNING,
        workflow_input={},
        state={},
        frames={parent.id: parent},
    )
    stale_child = ExecutionFrame(
        id=f"{first.id}:0",
        kind="foreach_iteration",
        node_id="work",
        parent_frame_id="root",
        metadata={
            "foreach_node_id": "each",
            "activation_id": first.id,
            "loop_index": 0,
            "loop_item": "a",
            "loop_alias": "item",
        },
    )
    run.frames[stale_child.id] = stale_child
    block_frame_on_children(run, "root", (stale_child.id,))
    stale_child.status = FrameStatus.COMPLETED
    with pytest.raises(WorkflowExecutionError, match="closed activation"):
        wake_parent_for_child_progress(run, stale_child.id)
