from __future__ import annotations

import pytest

from wf_core.errors import WorkflowExecutionError
from wf_core.run_state import ExecutionFrame, ForeachContext, RunState, RunStatus
from wf_core.runtime.ops.frames import frame_context_view


def _run_with_frames(frames: list[ExecutionFrame]) -> RunState:
    run = RunState(
        workflow_name="demo",
        status=RunStatus.RUNNING,
        workflow_input={},
        state={},
    )
    for frame in frames:
        run.frames[frame.id] = frame
    return run


def _item_frame(
    *,
    frame_id: str,
    parent_id: str | None,
    node_id: str,
    activation_id: str,
    index: int,
    item: object,
    alias: str,
    scope_id: str = "root",
    lineage_id: str = "lineage",
) -> ExecutionFrame:
    return ExecutionFrame(
        id=frame_id,
        kind="foreach_iteration",
        node_id=node_id,
        parent_frame_id=parent_id,
        scope_id=scope_id,
        lineage_id=lineage_id,
        metadata={
            "foreach_node_id": node_id,
            "activation_id": activation_id,
            "loop_index": index,
            "loop_item": item,
            "loop_alias": alias,
        },
    )


def test_root_frame_has_empty_structured_foreach_context() -> None:
    run = _run_with_frames(
        [ExecutionFrame(id="root", kind="root", node_id="start", scope_id="root")]
    )
    view = frame_context_view(run, run.frames["root"])
    assert dict(view.foreach) == {}
    assert view.graph["foreach"] == {}
    assert "loop_item" not in view.graph
    assert "loop_index" not in view.graph


def test_nested_same_scope_frames_expose_outermost_to_innermost_context() -> None:
    run = _run_with_frames(
        [
            ExecutionFrame(id="root", kind="root", node_id="customers", scope_id="root"),
            _item_frame(
                frame_id="outer-item",
                parent_id="root",
                node_id="customers",
                activation_id="customers:activation:1",
                index=0,
                item={"name": "Ada"},
                alias="customer",
                lineage_id="customers:lineage:0",
            ),
            ExecutionFrame(
                id="inner-controller",
                kind="foreach",
                node_id="orders",
                parent_frame_id="outer-item",
                scope_id="root",
                lineage_id="customers:lineage:0",
            ),
            _item_frame(
                frame_id="inner-item",
                parent_id="inner-controller",
                node_id="orders",
                activation_id="orders:activation:1",
                index=2,
                item={"sku": "A-17"},
                alias="order",
                lineage_id="orders:lineage:2",
            ),
        ]
    )
    view = frame_context_view(run, run.frames["inner-item"])
    contexts = view.foreach

    assert tuple(contexts) == ("customers", "orders")
    assert contexts["customers"] == ForeachContext(
        node_id="customers",
        activation_id="customers:activation:1",
        frame_id="outer-item",
        scope_id="root",
        lineage_id="customers:lineage:0",
        index=0,
        item={"name": "Ada"},
    )
    assert contexts["orders"].index == 2
    assert contexts["orders"].item == {"sku": "A-17"}


def test_graph_context_values_keep_all_aliases_and_innermost_loop_keys() -> None:
    run = _run_with_frames(
        [
            ExecutionFrame(id="root", kind="root", node_id="customers", scope_id="root"),
            _item_frame(
                frame_id="outer-item",
                parent_id="root",
                node_id="customers",
                activation_id="customers:activation:1",
                index=0,
                item={"name": "Ada"},
                alias="customer",
                lineage_id="customers:lineage:0",
            ),
            _item_frame(
                frame_id="inner-item",
                parent_id="outer-item",
                node_id="orders",
                activation_id="orders:activation:1",
                index=2,
                item={"sku": "A-17"},
                alias="order",
                lineage_id="orders:lineage:2",
            ),
        ]
    )
    view = frame_context_view(run, run.frames["inner-item"])
    graph = dict(view.graph)
    assert graph["customer"] == {"name": "Ada"}
    assert graph["order"] == {"sku": "A-17"}
    assert graph["loop_item"] == {"sku": "A-17"}
    assert graph["loop_index"] == 2
    foreach_map = graph["foreach"]
    assert isinstance(foreach_map, dict)
    assert set(foreach_map) == {"customers", "orders"}
    assert foreach_map["orders"]["index"] == 2
    assert foreach_map["orders"]["item"] == {"sku": "A-17"}


def test_context_ancestry_stops_at_runtime_scope_boundary() -> None:
    run = _run_with_frames(
        [
            ExecutionFrame(id="root", kind="root", node_id="customers", scope_id="root"),
            _item_frame(
                frame_id="outer-item",
                parent_id="root",
                node_id="customers",
                activation_id="customers:activation:1",
                index=0,
                item={"name": "Ada"},
                alias="customer",
                lineage_id="customers:lineage:0",
            ),
            ExecutionFrame(
                id="child-root",
                kind="subgraph_root",
                node_id="start",
                parent_frame_id="outer-item",
                scope_id="child",
                lineage_id="child:root",
            ),
        ]
    )
    view = frame_context_view(run, run.frames["child-root"])
    assert dict(view.foreach) == {}
    assert view.graph["foreach"] == {}


def test_structured_context_rejects_malformed_foreach_metadata() -> None:
    run = _run_with_frames(
        [
            ExecutionFrame(
                id="bad",
                kind="foreach_iteration",
                node_id="body",
                scope_id="root",
                metadata={"foreach_node_id": "", "activation_id": "a"},
            )
        ]
    )
    with pytest.raises(WorkflowExecutionError, match="malformed|missing"):
        frame_context_view(run, run.frames["bad"])


def test_structured_context_rejects_missing_parent_frame() -> None:
    run = _run_with_frames(
        [
            ExecutionFrame(
                id="child",
                kind="node",
                node_id="body",
                parent_frame_id="missing",
                scope_id="root",
            )
        ]
    )
    with pytest.raises(WorkflowExecutionError, match="missing parent frame"):
        frame_context_view(run, run.frames["child"])


def test_structured_context_rejects_parent_cycle() -> None:
    run = _run_with_frames(
        [
            ExecutionFrame(
                id="a", kind="node", node_id="x", parent_frame_id="b", scope_id="root"
            ),
            ExecutionFrame(
                id="b", kind="node", node_id="y", parent_frame_id="a", scope_id="root"
            ),
        ]
    )
    with pytest.raises(WorkflowExecutionError, match="cyclic"):
        frame_context_view(run, run.frames["a"])


def test_structured_context_rejects_duplicate_active_foreach_id() -> None:
    run = _run_with_frames(
        [
            ExecutionFrame(id="root", kind="root", node_id="each", scope_id="root"),
            _item_frame(
                frame_id="outer-item",
                parent_id="root",
                node_id="each",
                activation_id="act-1",
                index=0,
                item="a",
                alias="first",
            ),
            _item_frame(
                frame_id="inner-item",
                parent_id="outer-item",
                node_id="each",
                activation_id="act-2",
                index=1,
                item="b",
                alias="second",
            ),
        ]
    )
    with pytest.raises(WorkflowExecutionError, match="duplicate active foreach id"):
        frame_context_view(run, run.frames["inner-item"])


def test_structured_context_rejects_duplicate_active_alias() -> None:
    run = _run_with_frames(
        [
            ExecutionFrame(id="root", kind="root", node_id="a", scope_id="root"),
            _item_frame(
                frame_id="outer-item",
                parent_id="root",
                node_id="customers",
                activation_id="act-1",
                index=0,
                item="a",
                alias="same",
            ),
            _item_frame(
                frame_id="inner-item",
                parent_id="outer-item",
                node_id="orders",
                activation_id="act-2",
                index=0,
                item="b",
                alias="same",
            ),
        ]
    )
    with pytest.raises(WorkflowExecutionError, match="duplicate active foreach alias"):
        frame_context_view(run, run.frames["inner-item"])


def test_context_read_does_not_mutate_run_state() -> None:
    run = _run_with_frames(
        [
            ExecutionFrame(id="root", kind="root", node_id="customers", scope_id="root"),
            _item_frame(
                frame_id="outer-item",
                parent_id="root",
                node_id="customers",
                activation_id="act-1",
                index=0,
                item={"name": "Ada"},
                alias="customer",
            ),
        ]
    )
    before = run.to_dict()
    frame_context_view(run, run.frames["outer-item"])
    assert run.to_dict() == before
