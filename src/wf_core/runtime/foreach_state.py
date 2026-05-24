from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from wf_core.errors import WorkflowExecutionError
from wf_core.models.reducers import ReducerRef
from wf_core.paths import StatePath
from wf_core.run_state import ExecutionFrame, StateWrite
from wf_core.runtime.ops.state import StatePatch
from wf_core.runtime.scheduler import ForeachIterationMetadata

_BARRIER_METADATA_KEY = "foreach_barriers"


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
    """Buffered item result waiting for a future foreach barrier commit."""

    index: int
    frame_id: str
    status: Literal["succeeded", "failed"]
    lineage_id: str | None = None
    patch: StatePatch = field(default_factory=StatePatch)
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
        patch_changes = raw.get("patch_changes", {})
        patch_writes = raw.get("patch_writes")
        lineage_id = raw.get("lineage_id")
        if not isinstance(index, int) or index < 0:
            raise WorkflowExecutionError("malformed pending foreach result index")
        if not isinstance(frame_id, str):
            raise WorkflowExecutionError("malformed pending foreach result frame id")
        if lineage_id is not None and not isinstance(lineage_id, str):
            raise WorkflowExecutionError("malformed pending foreach result lineage id")
        if status not in {"succeeded", "failed"}:
            raise WorkflowExecutionError("malformed pending foreach result status")
        if not isinstance(patch_changes, dict):
            raise WorkflowExecutionError("malformed pending foreach result patch")
        if patch_writes is not None and not isinstance(patch_writes, list):
            raise WorkflowExecutionError("malformed pending foreach result writes")
        raw_error = raw.get("error")
        return cls(
            index=index,
            frame_id=frame_id,
            status=status,
            lineage_id=lineage_id,
            patch=(
                StatePatch(
                    writes=[_state_write_from_metadata(item) for item in patch_writes]
                )
                if patch_writes is not None
                else StatePatch(changes=patch_changes)
            ),
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
            "patch_changes": dict(self.patch.changes),
            "patch_writes": [
                _state_write_to_metadata(write) for write in self.patch.writes
            ],
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
    def from_frame(
        cls,
        frame: ExecutionFrame,
        foreach_node_id: str,
    ) -> ForeachBarrierState | None:
        """Load one foreach barrier state from frame metadata.

        Missing metadata means the foreach has not started on this frame yet.
        Malformed metadata means runtime state is corrupt and should fail fast.
        """
        all_barriers = frame.metadata.get(_BARRIER_METADATA_KEY)
        if all_barriers is None:
            return None
        if not isinstance(all_barriers, dict):
            raise WorkflowExecutionError(
                f"malformed foreach barrier table for frame {frame.id!r}"
            )
        raw = all_barriers.get(foreach_node_id)
        if raw is None:
            return None
        if not isinstance(raw, dict):
            raise WorkflowExecutionError(
                f"malformed foreach barrier state for frame {frame.id!r}"
            )
        return cls.from_metadata(raw)

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

    def save_to_frame(self, frame: ExecutionFrame, foreach_node_id: str) -> None:
        """Store this barrier state in frame metadata under its foreach node id."""
        existing = frame.metadata.get(_BARRIER_METADATA_KEY)
        if existing is None:
            frame.metadata[_BARRIER_METADATA_KEY] = {
                foreach_node_id: self.to_metadata()
            }
            return
        if not isinstance(existing, dict):
            raise WorkflowExecutionError(
                f"malformed foreach barrier table for frame {frame.id!r}"
            )
        existing[foreach_node_id] = self.to_metadata()

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
        patch: StatePatch,
        lineage_id: str | None = None,
    ) -> None:
        """Buffer or extend successful item patches by item index.

        A multi-step item body can produce multiple node patches. They are
        accumulated for the same item lineage and replayed by the barrier in
        item index order. Do not merge `_prepared_writes` here: the barrier
        intentionally replays public changes against one staged parent state.
        """
        existing = self.pending_results.get(index)
        if existing is None:
            self.pending_results[index] = PendingItemResult(
                index=index,
                frame_id=frame_id,
                status="succeeded",
                lineage_id=lineage_id,
                patch=patch,
            )
            return
        if existing.frame_id != frame_id:
            raise WorkflowExecutionError(
                f"foreach item result for index {index!r} belongs to frame "
                f"{existing.frame_id!r}, got {frame_id!r}"
            )
        if lineage_id is not None and existing.lineage_id not in {None, lineage_id}:
            raise WorkflowExecutionError(
                f"foreach item result for index {index!r} belongs to lineage "
                f"{existing.lineage_id!r}, got {lineage_id!r}"
            )
        if existing.lineage_id is None:
            existing.lineage_id = lineage_id
        existing.patch.extend(patch)

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


def item_frame_owner(frame: ExecutionFrame) -> tuple[str, str, int] | None:
    """Return parent frame id, foreach node id, and item index for item frames."""
    if frame.kind != "foreach_iteration" or frame.parent_frame_id is None:
        return None
    metadata = ForeachIterationMetadata.from_frame(frame)
    if metadata is None:
        return None
    return frame.parent_frame_id, metadata.foreach_node_id, metadata.loop_index


def _string_tuple(raw: object) -> tuple[str, ...]:
    if isinstance(raw, tuple) and all(isinstance(item, str) for item in raw):
        return raw
    if isinstance(raw, list) and all(isinstance(item, str) for item in raw):
        return tuple(raw)
    raise WorkflowExecutionError("malformed foreach barrier frame id list")


def _state_write_from_metadata(raw: object) -> StateWrite:
    """Parse one persisted item-lineage write record.

    Barrier metadata must keep reducer-visible values across interrupt/resume;
    reconstructing from `patch_changes` would downgrade reducer writes to
    replace-style incoming values.
    """
    if not isinstance(raw, dict):
        raise WorkflowExecutionError("malformed pending foreach write")
    try:
        path = raw["path"]
        incoming_value = raw["incoming_value"]
        visible_value = raw["visible_value"]
        reducer = raw["reducer"]
    except KeyError as exc:
        raise WorkflowExecutionError(
            f"malformed pending foreach write missing {exc.args[0]!r}"
        ) from exc
    try:
        return StateWrite(
            path=_state_path_from_metadata(path),
            incoming_value=incoming_value,
            visible_value=visible_value,
            reducer=ReducerRef.model_validate(reducer),
        )
    except Exception as exc:
        raise WorkflowExecutionError("malformed pending foreach write") from exc


def _state_write_to_metadata(write: StateWrite) -> dict[str, Any]:
    """Serialize one item-lineage write without relying on dotted display paths."""
    return {
        "path": {"root": "state", "parts": list(write.path.parts)},
        "incoming_value": write.incoming_value,
        "visible_value": write.visible_value,
        "reducer": write.reducer.model_dump(mode="json"),
    }


def _state_path_from_metadata(raw: object) -> StatePath:
    if isinstance(raw, str):
        return StatePath.parse(raw)
    if not isinstance(raw, dict) or raw.get("root") != "state":
        raise WorkflowExecutionError("malformed pending foreach write path")
    parts = raw.get("parts")
    if not isinstance(parts, list) or not all(isinstance(part, str) for part in parts):
        raise WorkflowExecutionError("malformed pending foreach write path")
    return StatePath(tuple(parts))
