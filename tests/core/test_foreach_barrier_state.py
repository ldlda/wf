from __future__ import annotations

import pytest

from wf_core.errors import WorkflowExecutionError
from wf_core.run_state import ExecutionFrame
from wf_core.runtime.foreach_state import (
    ForeachBarrierState,
    ItemErrorRecord,
    PendingItemResult,
)
from wf_core.runtime.ops.state import StatePatch


def test_foreach_barrier_state_round_trips_through_frame_metadata() -> None:
    frame = ExecutionFrame(id="root", kind="root", node_id="each")
    barrier = ForeachBarrierState(
        next_index=2,
        active_frame_ids=("child-1",),
        outstanding_frame_ids=("child-1", "child-2"),
        pending_results={
            1: PendingItemResult(
                index=1,
                frame_id="child-1",
                status="failed",
                patch=StatePatch(changes={"state.count": 1}),
                error=ItemErrorRecord(
                    index=1,
                    frame_id="child-1",
                    node_id="work",
                    error_type="ValueError",
                    message="bad item",
                    item={"id": "a"},
                ),
            )
        },
    )

    barrier.save_to_frame(frame, "each")
    loaded = ForeachBarrierState.from_frame(frame, "each")

    assert loaded is not None
    assert loaded.next_index == 2
    assert loaded.active_frame_ids == ("child-1",)
    assert loaded.outstanding_frame_ids == ("child-1", "child-2")
    assert loaded.pending_results[1].patch.changes["state.count"] == 1
    assert loaded.pending_results[1].error is not None
    assert loaded.pending_results[1].error.message == "bad item"


def test_foreach_barrier_state_returns_none_when_missing() -> None:
    frame = ExecutionFrame(id="root", kind="root", node_id="each")

    assert ForeachBarrierState.from_frame(frame, "each") is None


def test_foreach_barrier_state_rejects_malformed_metadata() -> None:
    frame = ExecutionFrame(
        id="root",
        kind="root",
        node_id="each",
        metadata={"foreach_barriers": {"each": {"next_index": "bad"}}},
    )

    with pytest.raises(WorkflowExecutionError, match="next_index"):
        ForeachBarrierState.from_frame(frame, "each")


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


def test_foreach_barrier_rejects_duplicate_item_result() -> None:
    barrier = ForeachBarrierState()
    patch = StatePatch(changes={"state.count": 1})

    barrier.add_success_patch(index=0, frame_id="child-0", patch=patch)

    with pytest.raises(WorkflowExecutionError, match="already recorded"):
        barrier.add_success_patch(index=0, frame_id="child-0", patch=patch)


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
            {"index": -1, "frame_id": "child", "status": "succeeded"}
        )


def test_save_to_frame_rejects_corrupt_table_without_mutating() -> None:
    frame = ExecutionFrame(
        id="root",
        kind="root",
        node_id="each",
        metadata={"foreach_barriers": "corrupt"},
    )
    barrier = ForeachBarrierState(next_index=1)

    with pytest.raises(WorkflowExecutionError, match="barrier table"):
        barrier.save_to_frame(frame, "each")

    assert frame.metadata["foreach_barriers"] == "corrupt"
