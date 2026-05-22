from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from wf_core.errors import WorkflowExecutionError
from wf_core.run_state import ExecutionFrame, FrameStatus, RunState, RunStatus


@dataclass(slots=True, frozen=True)
class BlockedOnChildren:
    """Typed block reason for frames waiting on child frame completion."""

    child_frame_ids: tuple[str, ...]

    @classmethod
    def from_frame(cls, frame: ExecutionFrame) -> "BlockedOnChildren | None":
        raw = frame.metadata.get("blocked_on")
        if raw is None:
            return None
        if not isinstance(raw, dict) or raw.get("type") != "child_frames":
            raise WorkflowExecutionError(
                f"malformed block reason for frame {frame.id!r}"
            )
        raw_ids = raw.get("frame_ids")
        if not isinstance(raw_ids, list) or not all(
            isinstance(item, str) for item in raw_ids
        ):
            raise WorkflowExecutionError(
                f"malformed child frame ids for frame {frame.id!r}"
            )
        return cls(tuple(raw_ids))

    def to_metadata(self) -> dict[str, object]:
        return {"type": "child_frames", "frame_ids": list(self.child_frame_ids)}


@dataclass(slots=True, frozen=True)
class ForeachIterationMetadata:
    """Typed metadata for a foreach iteration frame."""

    foreach_node_id: str
    loop_index: int
    loop_item: Any
    loop_alias: str

    @classmethod
    def from_frame(cls, frame: ExecutionFrame) -> "ForeachIterationMetadata | None":
        if frame.kind != "foreach_iteration":
            return None
        metadata = frame.metadata
        foreach_node_id = metadata.get("foreach_node_id")
        loop_index = metadata.get("loop_index")
        loop_alias = metadata.get("loop_alias")
        if not isinstance(foreach_node_id, str) or not foreach_node_id:
            raise WorkflowExecutionError(
                f"malformed foreach node id for frame {frame.id!r}"
            )
        if not isinstance(loop_index, int):
            raise WorkflowExecutionError(
                f"malformed foreach loop index for frame {frame.id!r}"
            )
        if not isinstance(loop_alias, str) or not loop_alias:
            raise WorkflowExecutionError(
                f"malformed foreach loop alias for frame {frame.id!r}"
            )
        if "loop_item" not in metadata:
            raise WorkflowExecutionError(
                f"missing foreach loop item for frame {frame.id!r}"
            )
        return cls(
            foreach_node_id=foreach_node_id,
            loop_index=loop_index,
            loop_item=metadata["loop_item"],
            loop_alias=loop_alias,
        )

    def to_metadata(self) -> dict[str, object]:
        return {
            "foreach_node_id": self.foreach_node_id,
            "loop_index": self.loop_index,
            "loop_item": self.loop_item,
            "loop_alias": self.loop_alias,
        }


def add_frame(run: RunState, frame: ExecutionFrame, *, ready: bool = False) -> None:
    """Add a frame once; frame id reuse is always a runtime invariant error."""
    if frame.id in run.frames:
        raise WorkflowExecutionError(f"duplicate frame id {frame.id!r}")
    run.frames[frame.id] = frame
    if ready:
        enqueue_frame(run, frame.id)


def enqueue_frame(run: RunState, frame_id: str, *, front: bool = False) -> None:
    """Put a pending frame in the ready queue without creating duplicates."""
    frame = _frame(run, frame_id)
    if frame.status != FrameStatus.PENDING:
        raise WorkflowExecutionError(
            f"cannot enqueue frame {frame_id!r} with status {frame.status!s}"
        )
    if frame_id in run.ready_frame_ids:
        run.ready_frame_ids.remove(frame_id)
    if front:
        run.ready_frame_ids.insert(0, frame_id)
    else:
        run.ready_frame_ids.append(frame_id)


def select_next_frame(run: RunState) -> ExecutionFrame | None:
    """Select the next ready frame and update compatibility cursor fields."""
    while run.ready_frame_ids:
        frame_id = run.ready_frame_ids.pop(0)
        frame = _frame(run, frame_id)
        if frame.status != FrameStatus.PENDING:
            raise WorkflowExecutionError(
                f"ready frame {frame_id!r} has status {frame.status!s}"
            )
        frame.status = FrameStatus.RUNNING
        run.current_frame_id = frame.id
        run.sync_from_current_frame()
        return frame
    return None


def mark_frame_pending(run: RunState, frame_id: str, *, front: bool = False) -> None:
    """Mark a live frame pending and enqueue it for future execution."""
    frame = _frame(run, frame_id)
    frame.status = FrameStatus.PENDING
    enqueue_frame(run, frame_id, front=front)


def block_frame_on_children(
    run: RunState, frame_id: str, child_frame_ids: Sequence[str]
) -> None:
    """Mark a frame blocked on child completion and remove it from readiness."""
    if not child_frame_ids:
        raise WorkflowExecutionError(
            f"cannot block frame {frame_id!r} on an empty child set"
        )
    frame = _frame(run, frame_id)
    run.ready_frame_ids = [item for item in run.ready_frame_ids if item != frame_id]
    frame.status = FrameStatus.BLOCKED
    frame.metadata["blocked_on"] = BlockedOnChildren(
        tuple(child_frame_ids)
    ).to_metadata()


def wake_frame(run: RunState, frame_id: str, *, front: bool = False) -> None:
    """Wake a blocked or interrupted frame and enqueue it as pending."""
    frame = _frame(run, frame_id)
    if frame.status not in {FrameStatus.BLOCKED, FrameStatus.INTERRUPTED}:
        raise WorkflowExecutionError(
            f"cannot wake frame {frame_id!r} with status {frame.status!s}"
        )
    frame.status = FrameStatus.PENDING
    frame.metadata.pop("blocked_on", None)
    enqueue_frame(run, frame_id, front=front)


def wake_parent_if_children_complete(run: RunState, child_frame_id: str) -> None:
    """Wake a blocked parent once all child frames it waits on are completed."""
    child = _frame(run, child_frame_id)
    parent_id = child.parent_frame_id
    if parent_id is None:
        return
    parent = _frame(run, parent_id)
    block = BlockedOnChildren.from_frame(parent)
    if block is None:
        return
    if all(
        _frame(run, item).status == FrameStatus.COMPLETED
        for item in block.child_frame_ids
    ):
        wake_frame(run, parent_id)


def wake_parent_for_child_progress(run: RunState, child_frame_id: str) -> None:
    """Wake a blocked parent after one child finishes so it can refill slots."""
    child = _frame(run, child_frame_id)
    parent_id = child.parent_frame_id
    if parent_id is None:
        return
    parent = _frame(run, parent_id)
    if parent.status != FrameStatus.BLOCKED:
        return
    block = BlockedOnChildren.from_frame(parent)
    if block is None or child_frame_id not in block.child_frame_ids:
        return
    wake_frame(run, parent_id)


def resolve_no_ready_frames(run: RunState) -> RunStatus:
    """Classify an empty ready queue into terminal, paused, or deadlocked state."""
    if run.status == RunStatus.INTERRUPTED:
        return RunStatus.INTERRUPTED
    if any(
        frame.parent_frame_id is None and frame.status == FrameStatus.COMPLETED
        for frame in run.frames.values()
    ):
        return RunStatus.COMPLETED
    if any(frame.status == FrameStatus.FAILED for frame in run.frames.values()):
        return RunStatus.FAILED
    if run.frames and all(
        frame.status == FrameStatus.COMPLETED for frame in run.frames.values()
    ):
        return RunStatus.COMPLETED
    if any(frame.status == FrameStatus.BLOCKED for frame in run.frames.values()):
        raise WorkflowExecutionError(
            "run has no ready frames and is deadlocked; "
            f"{_scheduler_state_summary(run)}"
        )
    raise WorkflowExecutionError(
        f"run has no ready frames; {_scheduler_state_summary(run)}"
    )


def _scheduler_state_summary(run: RunState) -> str:
    """Return compact scheduler state for no-ready-frame diagnostics."""
    frame_summary = ", ".join(
        f"{frame.id}:{frame.status.value}@{frame.node_id}"
        for frame in run.frames.values()
    )
    return (
        f"ready_frame_ids={run.ready_frame_ids!r}; "
        f"current_frame_id={run.current_frame_id!r}; "
        f"frames=[{frame_summary}]"
    )


def _frame(run: RunState, frame_id: str) -> ExecutionFrame:
    frame = run.frames.get(frame_id)
    if frame is None:
        raise WorkflowExecutionError(f"unknown frame id {frame_id!r}")
    return frame
