from __future__ import annotations

from copy import deepcopy

import pytest

from wf_core.errors import WorkflowExecutionError
from wf_core.models.reducers import ReducerRef
from wf_core.paths import StatePath
from wf_core.run_state import (
    ExecutionFrame,
    LineageState,
    RunState,
    RunStatus,
    RuntimeScope,
    StateWrite,
)
from wf_core.runtime.foreach_state import (
    ForeachBarrierState,
    ForeachItemOwner,
    ItemErrorRecord,
    PendingItemResult,
    item_frame_owner,
    load_foreach_activation,
    load_or_begin_foreach_activation,
    save_foreach_activation,
)
from wf_core.runtime.lineage import (
    LineageStateView,
    add_lineage,
    append_lineage_writes,
    lineage_writes_for_frame,
)


def test_foreach_barrier_state_round_trips_through_activation_metadata() -> None:
    frame = ExecutionFrame(id="root", kind="root", node_id="each")
    activation = load_or_begin_foreach_activation(frame, "each", mode="serial")
    activation.barrier.next_index = 2
    activation.barrier.start_child("child-1")
    activation.barrier.start_child("child-2")
    activation.barrier.finish_child("child-2")
    activation.barrier.add_failure(
        error=ItemErrorRecord(
            index=1,
            frame_id="child-1",
            node_id="work",
            error_type="ValueError",
            message="bad item",
            item={"id": "a"},
        )
    )
    save_foreach_activation(frame, activation)

    loaded = load_foreach_activation(frame, "each", activation.id)

    assert loaded is not None
    assert loaded.barrier.next_index == 2
    assert loaded.barrier.active_frame_ids == ("child-1",)
    assert loaded.barrier.outstanding_frame_ids == ("child-1",)
    assert loaded.barrier.pending_results[1].status == "failed"
    assert loaded.barrier.pending_results[1].error is not None
    assert loaded.barrier.pending_results[1].error.message == "bad item"


def test_concurrent_success_round_trips_lineage_identity() -> None:
    frame = ExecutionFrame(id="root", kind="root", node_id="each")
    activation = load_or_begin_foreach_activation(frame, "each", mode="concurrent")
    activation.barrier.add_success_patch(
        index=0,
        frame_id="child-0",
        lineage_id="root:each#0[0]",
    )
    save_foreach_activation(frame, activation)

    loaded = load_foreach_activation(frame, "each", activation.id)

    assert loaded is not None
    assert loaded.barrier.pending_results[0].lineage_id == "root:each#0[0]"
    assert loaded.barrier.pending_results[0].status == "succeeded"


def test_lineage_state_view_materializes_visible_values_without_mutating_base() -> None:
    base_state = {"count": 2, "nested": {"value": "old"}}
    view = LineageStateView(
        base_state,
        [
            StateWrite(
                path=StatePath(("count",)),
                incoming_value=3,
                visible_value=5,
                reducer=ReducerRef(name="wf.std.add"),
            ),
            StateWrite(
                path=StatePath(("nested", "value")),
                incoming_value="new",
                visible_value="new",
                reducer=ReducerRef(name="wf.std.replace"),
            ),
        ],
    )

    state_view = view.to_state_dict()

    assert state_view["count"] == 5
    assert state_view["nested"]["value"] == "new"
    assert base_state["count"] == 2
    assert base_state["nested"]["value"] == "old"


def test_lineage_writes_for_frame_reads_item_lineage_store() -> None:
    parent = ExecutionFrame(id="root", kind="workflow", node_id="each")
    activation = load_or_begin_foreach_activation(parent, "each", mode="concurrent")
    child_lineage_id = f"{activation.id}[0]"
    child = ExecutionFrame(
        id=f"{activation.id}:0",
        kind="foreach_iteration",
        node_id="work",
        parent_frame_id="root",
        lineage_id=child_lineage_id,
        parent_lineage_id="root",
        metadata={
            "foreach_node_id": "each",
            "activation_id": activation.id,
            "loop_index": 0,
            "loop_item": "a",
            "loop_alias": "item",
        },
    )
    # Ownership is named, not positional.
    owner = item_frame_owner(child)
    assert isinstance(owner, ForeachItemOwner)
    assert owner.activation_id == activation.id
    assert owner.item_index == 0
    save_foreach_activation(parent, activation)
    run = RunState(
        workflow_name="lineage",
        status=RunStatus.PENDING,
        workflow_input={},
        state={"count": 2},
        frames={parent.id: parent, child.id: child},
    )
    run.scopes["root"] = RuntimeScope(
        id="root",
        workflow_name="lineage",
        workflow_input={},
        committed_state=run.state,
    )
    run.lineages["root"] = LineageState(id="root", scope_id="root")
    add_lineage(run, scope_id="root", lineage_id=child_lineage_id, parent_id="root")
    append_lineage_writes(
        run,
        scope_id="root",
        lineage_id=child_lineage_id,
        writes=[
            StateWrite(
                path=StatePath(("count",)),
                incoming_value=3,
                visible_value=5,
                reducer=ReducerRef(name="wf.std.add"),
            )
        ],
    )

    writes = lineage_writes_for_frame(run, child)

    assert len(writes) == 1
    assert writes[0].incoming_value == 3
    assert writes[0].visible_value == 5


def test_load_activation_returns_none_when_missing() -> None:
    from wf_core.runtime.foreach_state import close_foreach_activation

    frame = ExecutionFrame(id="root", kind="root", node_id="each")
    activation = load_or_begin_foreach_activation(frame, "each", mode="serial")
    save_foreach_activation(frame, activation)
    close_foreach_activation(frame, activation)

    assert load_foreach_activation(frame, "each", activation.id) is None
    assert load_foreach_activation(frame, "each", "root:each#99") is None


def test_foreach_barrier_tracks_active_and_outstanding_children() -> None:
    barrier = ForeachBarrierState()

    barrier.start_child("child-0")
    assert barrier.active_frame_ids == ("child-0",)
    assert barrier.outstanding_frame_ids == ("child-0",)

    barrier.start_child("child-1")
    assert barrier.active_frame_ids == ("child-0", "child-1")
    assert barrier.outstanding_frame_ids == ("child-0", "child-1")

    barrier.finish_child("child-0")

    assert barrier.active_frame_ids == ("child-1",)
    assert barrier.outstanding_frame_ids == ("child-1",)


def test_foreach_barrier_rejects_duplicate_child_start() -> None:
    barrier = ForeachBarrierState()
    barrier.start_child("child-0")

    with pytest.raises(WorkflowExecutionError, match="already active"):
        barrier.start_child("child-0")


def test_foreach_barrier_rejects_finishing_unknown_child() -> None:
    barrier = ForeachBarrierState()

    with pytest.raises(WorkflowExecutionError, match="not active"):
        barrier.finish_child("child-0")


def test_foreach_barrier_success_registration_is_idempotent_for_same_lineage() -> None:
    barrier = ForeachBarrierState(mode="concurrent")

    barrier.add_success_patch(
        index=0,
        frame_id="child-0",
        lineage_id="root:each#0[0]",
    )
    barrier.add_success_patch(
        index=0,
        frame_id="child-0",
        lineage_id="root:each#0[0]",
    )

    result = barrier.pending_results[0]
    assert result.status == "succeeded"
    assert result.lineage_id == "root:each#0[0]"


def test_foreach_barrier_rejects_success_lineage_mismatch() -> None:
    barrier = ForeachBarrierState(mode="concurrent")
    barrier.add_success_patch(index=0, frame_id="child-0", lineage_id="root:each#0[0]")

    with pytest.raises(WorkflowExecutionError, match="belongs to lineage"):
        barrier.add_success_patch(
            index=0, frame_id="child-0", lineage_id="root:each#0[1]"
        )


def test_foreach_barrier_rejects_item_result_frame_mismatch() -> None:
    barrier = ForeachBarrierState(mode="concurrent")

    barrier.add_success_patch(index=0, frame_id="child-0", lineage_id="root:each#0[0]")

    with pytest.raises(WorkflowExecutionError, match="belongs to frame"):
        barrier.add_success_patch(
            index=0, frame_id="child-1", lineage_id="root:each#0[0]"
        )


def test_item_error_record_rejects_negative_index() -> None:
    with pytest.raises(WorkflowExecutionError, match="index"):
        ItemErrorRecord.from_metadata(
            {
                "index": -1,
                "frame_id": "child",
                "node_id": "work",
                "error_type": "ValueError",
                "message": "bad",
            }
        )


def test_pending_item_result_reports_missing_required_field() -> None:
    with pytest.raises(WorkflowExecutionError, match="missing 'frame_id'"):
        PendingItemResult.from_metadata({"index": 0, "status": "succeeded"})


def test_pending_item_result_rejects_negative_index() -> None:
    with pytest.raises(WorkflowExecutionError, match="index"):
        PendingItemResult.from_metadata(
            {
                "index": -1,
                "frame_id": "child",
                "status": "succeeded",
            }
        )


def test_pending_item_result_requires_lineage_for_success() -> None:
    with pytest.raises(WorkflowExecutionError, match="lineage"):
        PendingItemResult.from_metadata(
            {
                "index": 0,
                "frame_id": "child",
                "status": "succeeded",
                "lineage_id": None,
            }
        )


def test_pending_item_result_rejects_error_on_success() -> None:
    with pytest.raises(WorkflowExecutionError, match="must not carry an error"):
        PendingItemResult.from_metadata(
            {
                "index": 0,
                "frame_id": "child",
                "status": "succeeded",
                "lineage_id": "root:each#0[0]",
                "error": {
                    "index": 0,
                    "frame_id": "child",
                    "node_id": "work",
                    "error_type": "ValueError",
                    "message": "bad",
                },
            }
        )


def test_pending_item_result_requires_error_for_failure() -> None:
    with pytest.raises(WorkflowExecutionError, match="requires an error"):
        PendingItemResult.from_metadata(
            {
                "index": 0,
                "frame_id": "child",
                "status": "failed",
                "lineage_id": None,
                "error": None,
            }
        )


def test_pending_item_result_rejects_index_key_mismatch() -> None:
    frame = ExecutionFrame(id="root", kind="root", node_id="each")
    activation = load_or_begin_foreach_activation(frame, "each", mode="concurrent")
    activation.barrier.add_success_patch(
        index=0, frame_id="child-0", lineage_id="root:each#0[0]"
    )
    save_foreach_activation(frame, activation)
    raw = deepcopy(frame.metadata["foreach_activations"])
    raw["each"]["active"]["barrier"]["pending_results"] = {
        "7": raw["each"]["active"]["barrier"]["pending_results"]["0"]
    }

    with pytest.raises(WorkflowExecutionError, match="index mismatch"):
        ForeachBarrierState.from_metadata(raw["each"]["active"]["barrier"])
