from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from wf_core.errors import WorkflowExecutionError
from wf_core.run_state import ExecutionFrame, RunState
from wf_core.runtime.scheduler import ForeachIterationMetadata

_ACTIVATION_METADATA_KEY = "foreach_activations"


@dataclass(slots=True)
class ForeachActivationState:
    """Persisted state for one dynamic visit to a foreach controller.

    A parent frame creates a fresh activation on first entry, reuses it while
    admitting items, and closes it before emitting ``done``. The id is opaque:
    callers compare it by name and never parse it.
    """

    id: str
    foreach_node_id: str
    barrier: ForeachBarrierState


@dataclass(frozen=True, slots=True)
class ForeachItemOwner:
    """Named ownership record for one foreach item frame."""

    parent_frame_id: str
    foreach_node_id: str
    activation_id: str
    item_index: int


@dataclass(slots=True)
class ItemErrorRecord:
    """Structured runtime failure record for one foreach item."""

    index: int
    frame_id: str
    node_id: str
    error_type: str
    message: str
    item: Any = None

    @classmethod
    def from_metadata(cls, raw: object) -> ItemErrorRecord:
        if not isinstance(raw, dict):
            raise WorkflowExecutionError("malformed foreach item error record")
        try:
            index = raw["index"]
            frame_id = raw["frame_id"]
            node_id = raw["node_id"]
            error_type = raw["error_type"]
            message = raw["message"]
        except KeyError as exc:
            raise WorkflowExecutionError(
                f"malformed foreach item error record missing {exc.args[0]!r}"
            ) from exc
        if not isinstance(index, int) or index < 0:
            raise WorkflowExecutionError("malformed foreach item error index")
        if not all(
            isinstance(value, str) for value in (frame_id, node_id, error_type, message)
        ):
            raise WorkflowExecutionError("malformed foreach item error text fields")
        return cls(
            index=index,
            frame_id=frame_id,
            node_id=node_id,
            error_type=error_type,
            message=message,
            item=raw.get("item"),
        )

    def to_metadata(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "frame_id": self.frame_id,
            "node_id": self.node_id,
            "error_type": self.error_type,
            "message": self.message,
            "item": self.item,
        }


@dataclass(slots=True)
class PendingItemResult:
    """Buffered item result waiting for a future foreach barrier commit.

    Concurrent item writes live in `RunState.lineages`; the barrier keeps
    only the lineage identity per item index.
    """

    index: int
    frame_id: str
    status: Literal["succeeded", "failed"]
    lineage_id: str | None = None
    error: ItemErrorRecord | None = None

    @classmethod
    def from_metadata(cls, raw: object) -> PendingItemResult:
        if not isinstance(raw, dict):
            raise WorkflowExecutionError("malformed pending foreach result")
        try:
            index = raw["index"]
            frame_id = raw["frame_id"]
            status = raw["status"]
        except KeyError as exc:
            raise WorkflowExecutionError(
                f"malformed pending foreach result missing {exc.args[0]!r}"
            ) from exc
        lineage_id = raw.get("lineage_id")
        if not isinstance(index, int) or index < 0:
            raise WorkflowExecutionError("malformed pending foreach result index")
        if not isinstance(frame_id, str):
            raise WorkflowExecutionError("malformed pending foreach result frame id")
        if status == "succeeded" and not isinstance(lineage_id, str):
            raise WorkflowExecutionError("malformed pending foreach result lineage id")
        if lineage_id is not None and not isinstance(lineage_id, str):
            raise WorkflowExecutionError("malformed pending foreach result lineage id")
        if status not in {"succeeded", "failed"}:
            raise WorkflowExecutionError("malformed pending foreach result status")
        raw_error = raw.get("error")
        return cls(
            index=index,
            frame_id=frame_id,
            status=status,
            lineage_id=lineage_id,
            error=(
                ItemErrorRecord.from_metadata(raw_error)
                if raw_error is not None
                else None
            ),
        )

    def to_metadata(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "frame_id": self.frame_id,
            "status": self.status,
            "lineage_id": self.lineage_id,
            "error": self.error.to_metadata() if self.error is not None else None,
        }


@dataclass(slots=True)
class ForeachBarrierState:
    """Resumable state owned by one foreach parent frame."""

    next_index: int = 0
    mode: Literal["serial", "concurrent"] = "serial"
    active_frame_ids: tuple[str, ...] = ()
    outstanding_frame_ids: tuple[str, ...] = ()
    pending_results: dict[int, PendingItemResult] = field(default_factory=dict)

    @classmethod
    def from_metadata(cls, raw: object) -> ForeachBarrierState:
        if not isinstance(raw, dict):
            raise WorkflowExecutionError("malformed foreach barrier state")
        next_index = raw.get("next_index")
        mode = raw.get("mode", "serial")
        active_frame_ids = _string_tuple(raw.get("active_frame_ids", ()))
        outstanding_frame_ids = _string_tuple(raw.get("outstanding_frame_ids", ()))
        pending_results = raw.get("pending_results", {})
        if not isinstance(next_index, int):
            raise WorkflowExecutionError("malformed foreach barrier next_index")
        if mode not in {"serial", "concurrent"}:
            raise WorkflowExecutionError("malformed foreach barrier mode")
        if not isinstance(pending_results, dict):
            raise WorkflowExecutionError("malformed foreach barrier pending results")
        parsed_results: dict[int, PendingItemResult] = {}
        for raw_index, raw_result in pending_results.items():
            try:
                index = int(raw_index)
            except (TypeError, ValueError) as exc:
                raise WorkflowExecutionError(
                    "malformed foreach barrier pending result index"
                ) from exc
            parsed_results[index] = PendingItemResult.from_metadata(raw_result)
        return cls(
            next_index=next_index,
            mode=mode,
            active_frame_ids=active_frame_ids,
            outstanding_frame_ids=outstanding_frame_ids,
            pending_results=parsed_results,
        )

    def to_metadata(self) -> dict[str, Any]:
        return {
            "next_index": self.next_index,
            "mode": self.mode,
            "active_frame_ids": list(self.active_frame_ids),
            "outstanding_frame_ids": list(self.outstanding_frame_ids),
            "pending_results": {
                str(index): result.to_metadata()
                for index, result in self.pending_results.items()
            },
        }

    def start_child(self, frame_id: str) -> None:
        """Record one admitted child frame as active and outstanding."""
        if frame_id in self.active_frame_ids or frame_id in self.outstanding_frame_ids:
            raise WorkflowExecutionError(
                f"foreach child frame {frame_id!r} already active"
            )
        self.active_frame_ids = (*self.active_frame_ids, frame_id)
        self.outstanding_frame_ids = (*self.outstanding_frame_ids, frame_id)

    def finish_child(self, frame_id: str) -> None:
        """Record one child frame as no longer active or outstanding."""
        if (
            frame_id not in self.active_frame_ids
            or frame_id not in self.outstanding_frame_ids
        ):
            raise WorkflowExecutionError(
                f"foreach child frame {frame_id!r} is not active"
            )
        self.active_frame_ids = tuple(
            item for item in self.active_frame_ids if item != frame_id
        )
        self.outstanding_frame_ids = tuple(
            item for item in self.outstanding_frame_ids if item != frame_id
        )

    def add_success_patch(
        self,
        *,
        index: int,
        frame_id: str,
        lineage_id: str,
    ) -> None:
        """Record one completed concurrent item by lineage identity.

        Registration is idempotent for the same frame and lineage so the
        owner back-edge can own it regardless of which operation ran last.
        Any conflicting identity fails closed.
        """
        existing = self.pending_results.get(index)
        if existing is None:
            self.pending_results[index] = PendingItemResult(
                index=index,
                frame_id=frame_id,
                status="succeeded",
                lineage_id=lineage_id,
            )
            return
        if existing.frame_id != frame_id:
            raise WorkflowExecutionError(
                f"foreach item result for index {index!r} belongs to frame "
                f"{existing.frame_id!r}, got {frame_id!r}"
            )
        if existing.lineage_id != lineage_id:
            raise WorkflowExecutionError(
                f"foreach item result for index {index!r} belongs to lineage "
                f"{existing.lineage_id!r}, got {lineage_id!r}"
            )

    def add_failure(self, *, error: ItemErrorRecord) -> None:
        """Buffer one handled item failure for the foreach barrier.

        The child frame stays `FAILED` for observability. The parent barrier
        owns whether that failed child is skipped, collected, or treated as a
        whole-run failure.
        """
        existing = self.pending_results.get(error.index)
        if existing is not None:
            raise WorkflowExecutionError(
                f"foreach item result for index {error.index!r} already exists"
            )
        self.pending_results[error.index] = PendingItemResult(
            index=error.index,
            frame_id=error.frame_id,
            status="failed",
            error=error,
        )


def _activation_entry(
    frame: ExecutionFrame, table: dict[str, Any], foreach_node_id: str
) -> dict[str, Any] | None:
    """Return the mutable activation entry or fail fast on corrupt state."""
    entry = table.get(foreach_node_id)
    if entry is None:
        return None
    if not isinstance(entry, dict):
        raise WorkflowExecutionError(
            f"malformed foreach activation entry for frame {frame.id!r}"
        )
    return entry


def load_or_begin_foreach_activation(
    frame: ExecutionFrame,
    foreach_node_id: str,
    *,
    mode: Literal["serial", "concurrent"],
) -> ForeachActivationState:
    """Load the active activation or begin a fresh visit.

    The first entry for one visit allocates an opaque id from the parent frame
    id, foreach node id, and a persisted per-frame sequence. Later calls reuse
    the active activation; closing it makes the next visit allocate a new id
    with fresh barrier state. Mode mismatches and malformed tables fail fast.
    """
    table = _activation_table(frame)
    entry = _activation_entry(frame, table, foreach_node_id)
    if entry is None:
        entry = {"next_sequence": 0, "active": None}
        table[foreach_node_id] = entry
    next_sequence = entry.get("next_sequence", 0)
    if not isinstance(next_sequence, int) or next_sequence < 0:
        raise WorkflowExecutionError(
            f"malformed foreach activation sequence for frame {frame.id!r}"
        )
    active = entry.get("active")
    if active is not None:
        activation = _activation_from_metadata(
            active, frame_id=frame.id, foreach_node_id=foreach_node_id
        )
        if activation.barrier.mode != mode:
            raise WorkflowExecutionError(
                f"foreach {foreach_node_id!r} activation {activation.id!r} "
                f"has mode {activation.barrier.mode!r}, got {mode!r}"
            )
        return activation
    activation_id = f"{frame.id}:{foreach_node_id}#{next_sequence}"
    activation = ForeachActivationState(
        id=activation_id,
        foreach_node_id=foreach_node_id,
        barrier=ForeachBarrierState(mode=mode),
    )
    entry["next_sequence"] = next_sequence + 1
    entry["active"] = {
        "id": activation.id,
        "barrier": activation.barrier.to_metadata(),
    }
    return activation


def save_foreach_activation(
    frame: ExecutionFrame, activation: ForeachActivationState
) -> None:
    """Persist barrier progress for the named active activation."""
    table = _activation_table(frame)
    entry = _activation_entry(frame, table, activation.foreach_node_id)
    if entry is None:
        raise WorkflowExecutionError(
            f"malformed foreach activation entry for frame {frame.id!r}"
        )
    active = entry.get("active")
    if not isinstance(active, dict) or active.get("id") != activation.id:
        raise WorkflowExecutionError(
            f"cannot save stale foreach activation {activation.id!r} "
            f"for frame {frame.id!r}"
        )
    active["barrier"] = activation.barrier.to_metadata()


def close_foreach_activation(
    frame: ExecutionFrame, activation: ForeachActivationState
) -> None:
    """Close the named active activation, preserving the visit sequence.

    The barrier is removed so a later visit starts fresh; the sequence keeps
    increasing so child and lineage ids cannot collide across visits.
    """
    table = _activation_table(frame)
    entry = _activation_entry(frame, table, activation.foreach_node_id)
    if entry is None:
        raise WorkflowExecutionError(
            f"malformed foreach activation entry for frame {frame.id!r}"
        )
    active = entry.get("active")
    if not isinstance(active, dict) or active.get("id") != activation.id:
        raise WorkflowExecutionError(
            f"cannot close stale foreach activation {activation.id!r} "
            f"for frame {frame.id!r}"
        )
    entry["active"] = None


def load_foreach_activation(
    frame: ExecutionFrame, foreach_node_id: str, activation_id: str
) -> ForeachActivationState | None:
    """Return the active activation only when its id matches the child.

    A child result naming a closed or different activation must fail closed in
    the caller rather than buffering into the wrong barrier.
    """
    table = _activation_table(frame)
    entry = _activation_entry(frame, table, foreach_node_id)
    if entry is None:
        raise WorkflowExecutionError(
            f"malformed foreach activation entry for frame {frame.id!r}"
        )
    active = entry.get("active")
    if active is None:
        return None
    activation = _activation_from_metadata(
        active, frame_id=frame.id, foreach_node_id=foreach_node_id
    )
    if activation.id != activation_id:
        return None
    return activation


def require_foreach_activation(
    frame: ExecutionFrame, foreach_node_id: str, activation_id: str
) -> ForeachActivationState:
    """Load the named activation or raise when it is closed or superseded."""
    activation = load_foreach_activation(frame, foreach_node_id, activation_id)
    if activation is None:
        raise WorkflowExecutionError(
            f"foreach item activation {activation_id!r} for node "
            f"{foreach_node_id!r} is closed or superseded"
        )
    return activation


def item_frame_owner(frame: ExecutionFrame) -> ForeachItemOwner | None:
    """Return the named foreach ownership record for item frames.

    Malformed item metadata fails closed via ``ForeachIterationMetadata``;
    only non-item frames return ``None``.
    """
    if frame.kind != "foreach_iteration" or frame.parent_frame_id is None:
        return None
    metadata = ForeachIterationMetadata.from_frame(frame)
    if metadata is None:
        return None
    return ForeachItemOwner(
        parent_frame_id=frame.parent_frame_id,
        foreach_node_id=metadata.foreach_node_id,
        activation_id=metadata.activation_id,
        item_index=metadata.loop_index,
    )


def _activation_table(frame: ExecutionFrame) -> dict[str, Any]:
    raw = frame.metadata.get(_ACTIVATION_METADATA_KEY)
    if raw is None:
        table: dict[str, Any] = {}
        frame.metadata[_ACTIVATION_METADATA_KEY] = table
        return table
    if not isinstance(raw, dict):
        raise WorkflowExecutionError(
            f"malformed foreach activation table for frame {frame.id!r}"
        )
    return raw


def _activation_from_metadata(
    raw: object, *, frame_id: str, foreach_node_id: str
) -> ForeachActivationState:
    if not isinstance(raw, dict):
        raise WorkflowExecutionError(
            f"malformed foreach activation for frame {frame_id!r}"
        )
    activation_id = raw.get("id")
    barrier_raw = raw.get("barrier")
    if not isinstance(activation_id, str) or not activation_id:
        raise WorkflowExecutionError(
            f"malformed foreach activation id for frame {frame_id!r}"
        )
    return ForeachActivationState(
        id=activation_id,
        foreach_node_id=foreach_node_id,
        barrier=ForeachBarrierState.from_metadata(barrier_raw),
    )


def _string_tuple(raw: object) -> tuple[str, ...]:
    if isinstance(raw, tuple) and all(isinstance(item, str) for item in raw):
        return raw
    if isinstance(raw, list) and all(isinstance(item, str) for item in raw):
        return tuple(raw)
    raise WorkflowExecutionError("malformed foreach barrier frame id list")


def register_foreach_item_success(
    run: RunState, frame: ExecutionFrame, owner: ForeachItemOwner
) -> None:
    """Record one completed concurrent item at its owner back-edge.

    Registration keys off the returning frame, so it works regardless of
    which operation ran last in the item (node, subgraph, or nested
    control). Serial items commit through the parent at operation time and
    need no barrier entry. A closed or superseded activation fails closed.
    """
    parent_frame = run.frames.get(owner.parent_frame_id)
    if parent_frame is None:
        raise WorkflowExecutionError(
            "foreach lineage state references missing parent frame "
            f"{owner.parent_frame_id!r} for child frame {frame.id!r}"
        )
    activation = require_foreach_activation(
        parent_frame, owner.foreach_node_id, owner.activation_id
    )
    if activation.barrier.mode != "concurrent":
        return
    activation.barrier.add_success_patch(
        index=owner.item_index,
        frame_id=frame.id,
        lineage_id=frame.lineage_id,
    )
    save_foreach_activation(parent_frame, activation)
