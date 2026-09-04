from __future__ import annotations

import pytest

from wf_core.errors import WorkflowExecutionError
from wf_core.run_state import ExecutionFrame
from wf_core.runtime.foreach_state import (
    close_foreach_activation,
    item_frame_owner,
    load_or_begin_foreach_activation,
    save_foreach_activation,
)
from wf_core.runtime.scheduler import ForeachIterationMetadata


def _frame() -> ExecutionFrame:
    return ExecutionFrame(id="root", kind="workflow", node_id="each")


def test_activation_lifecycle_reuses_active_then_fresh_after_close() -> None:
    frame = _frame()

    first = load_or_begin_foreach_activation(frame, "each", mode="serial")
    save_foreach_activation(frame, first)
    restored = load_or_begin_foreach_activation(frame, "each", mode="serial")

    assert restored.id == first.id

    close_foreach_activation(frame, restored)
    second = load_or_begin_foreach_activation(frame, "each", mode="serial")

    assert second.id != first.id
    assert second.barrier.next_index == 0


def test_activation_rejects_malformed_metadata() -> None:
    frame = ExecutionFrame(
        id="root",
        kind="workflow",
        node_id="each",
        metadata={"foreach_activations": "corrupt"},
    )

    with pytest.raises(WorkflowExecutionError, match="activation"):
        load_or_begin_foreach_activation(frame, "each", mode="serial")


def test_activation_rejects_mode_mismatch() -> None:
    frame = _frame()
    activation = load_or_begin_foreach_activation(frame, "each", mode="serial")
    save_foreach_activation(frame, activation)

    with pytest.raises(WorkflowExecutionError, match="mode"):
        load_or_begin_foreach_activation(frame, "each", mode="concurrent")


def test_closing_stale_activation_fails_closed() -> None:
    frame = _frame()
    first = load_or_begin_foreach_activation(frame, "each", mode="serial")
    save_foreach_activation(frame, first)
    close_foreach_activation(frame, first)
    second = load_or_begin_foreach_activation(frame, "each", mode="serial")
    save_foreach_activation(frame, second)

    with pytest.raises(WorkflowExecutionError, match="stale|closed|active"):
        close_foreach_activation(frame, first)


def test_activation_json_round_trip_through_frame_metadata() -> None:
    frame = _frame()
    activation = load_or_begin_foreach_activation(frame, "each", mode="serial")
    activation.barrier.next_index = 2
    save_foreach_activation(frame, activation)

    dumped = dict(frame.metadata)
    restored_frame = ExecutionFrame(
        id="root", kind="workflow", node_id="each", metadata=dumped
    )
    restored = load_or_begin_foreach_activation(restored_frame, "each", mode="serial")

    assert restored.id == activation.id
    assert restored.barrier.next_index == 2


def test_item_metadata_requires_activation_identity() -> None:
    frame = ExecutionFrame(
        id="root:each#0:0",
        kind="foreach_iteration",
        node_id="work",
        parent_frame_id="root",
        metadata={
            "foreach_node_id": "each",
            "loop_index": 0,
            "loop_item": "a",
            "loop_alias": "item",
        },
    )

    with pytest.raises(WorkflowExecutionError, match="activation"):
        ForeachIterationMetadata.from_frame(frame)
    with pytest.raises(WorkflowExecutionError, match="activation"):
        item_frame_owner(frame)
