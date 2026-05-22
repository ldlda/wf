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
