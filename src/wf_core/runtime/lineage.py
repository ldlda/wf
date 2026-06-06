from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from wf_core.errors import WorkflowExecutionError
from wf_core.run_state import ExecutionFrame, LineageState, RunState, StateWrite
from wf_core.runtime.foreach_state import ForeachBarrierState, item_frame_owner
from wf_core.runtime.ops.state import (
    StatePatch,
    commit_state_patch,
    safe_set_nested_value,
)


@dataclass(slots=True)
class LineageStateView:
    """Committed state plus writes visible inside one child lineage.

    Today concurrent foreach supplies the writes from barrier metadata. Future
    native subgraphs and fork/gather should use the same primitive instead of
    rebuilding foreach-specific overlay logic.
    """

    base_state: Mapping[str, Any]
    writes: Sequence[StateWrite]

    def to_state_dict(self) -> dict[str, Any]:
        """Materialize the lineage-visible state as an isolated mutable dict."""
        # Correctness first: this full copy isolates sibling reads. If state grows
        # large, replace this with a lazy/copy-on-write overlay.
        state_view = deepcopy(dict(self.base_state))
        for write in self.writes:
            safe_set_nested_value(
                state_view,
                list(write.path.parts),
                write.visible_value,
            )
        return state_view


def lineage_writes_for_frame(
    run: RunState, frame: ExecutionFrame
) -> Sequence[StateWrite]:
    """Return writes visible to this frame's current lineage.

    This is still backed by concurrent foreach barrier metadata. Keeping the
    lookup here gives future `RunState.lineages` or subgraph scopes one place to
    plug in without making node execution understand foreach internals.
    """
    lineage = run.lineages.get(frame.lineage_id)
    if lineage is not None and lineage.scope_id == frame.scope_id and lineage.writes:
        return tuple(
            lineage_state_writes(
                run, scope_id=frame.scope_id, lineage_id=frame.lineage_id
            )
        )

    # Compatibility fallback: concurrent foreach used barrier-local patches
    # before `RunState.lineages` became the primary write store. Keep reading
    # those patches so old serialized runs and direct barrier tests still work.
    owner = item_frame_owner(frame)
    if owner is None:
        return ()
    parent_frame_id, foreach_node_id, item_index = owner
    parent_frame = run.frames.get(parent_frame_id)
    if parent_frame is None:
        raise WorkflowExecutionError(
            "foreach lineage compatibility state references missing parent frame "
            f"{parent_frame_id!r} for child frame {frame.id!r}"
        )
    barrier = ForeachBarrierState.from_frame(parent_frame, foreach_node_id)
    if barrier is None or barrier.mode != "concurrent":
        return ()

    pending = barrier.pending_results.get(item_index)
    if pending is None:
        return ()
    return pending.patch.writes


def is_scope_root_lineage_frame(run: RunState, frame: ExecutionFrame) -> bool:
    """Return whether writes from this frame commit to its scope state root."""
    lineage = run.lineages.get(frame.lineage_id)
    return (
        lineage is not None
        and lineage.scope_id == frame.scope_id
        and lineage.parent_id is None
    )


def commit_patch_for_frame(
    run: RunState, frame: ExecutionFrame, patch: StatePatch
) -> dict[str, Any]:
    """Commit at a scope root or buffer writes in the frame lineage.

    Child workflow root frames own a committed child-state root just like the
    top-level root frame owns `RunState.state`. Descendant branch/item frames
    remain isolated until an explicit barrier or future gather commits them.
    """
    if is_scope_root_lineage_frame(run, frame):
        return commit_state_patch(scope_state_for_frame(run, frame), patch)
    append_lineage_writes(
        run,
        scope_id=frame.scope_id,
        lineage_id=frame.lineage_id,
        writes=patch.writes,
    )
    return {}


def scope_state_for_frame(run: RunState, frame: ExecutionFrame) -> dict[str, Any]:
    """Return the committed state root for the frame's runtime scope."""
    scope = run.scopes.get(frame.scope_id)
    if scope is None:
        raise ValueError(f"unknown scope {frame.scope_id!r}")
    return scope.committed_state


def scope_input_for_frame(run: RunState, frame: ExecutionFrame) -> dict[str, Any]:
    """Return the invocation input associated with the frame's workflow scope."""
    scope = run.scopes.get(frame.scope_id)
    if scope is None:
        raise ValueError(f"unknown scope {frame.scope_id!r}")
    return scope.workflow_input


def add_lineage(
    run: RunState,
    *,
    scope_id: str,
    lineage_id: str,
    parent_id: str | None,
) -> None:
    """Create one lineage record inside an existing runtime scope."""
    if scope_id not in run.scopes:
        raise ValueError(f"unknown scope {scope_id!r}")
    if lineage_id in run.lineages:
        raise ValueError(f"duplicate lineage {lineage_id!r}")
    if parent_id is not None and parent_id not in run.lineages:
        raise ValueError(f"unknown parent lineage {parent_id!r}")
    run.lineages[lineage_id] = LineageState(
        id=lineage_id,
        scope_id=scope_id,
        parent_id=parent_id,
    )


def append_lineage_writes(
    run: RunState,
    *,
    scope_id: str,
    lineage_id: str,
    writes: Sequence[StateWrite],
) -> None:
    """Append ordered writes to an existing lineage without committing state."""
    lineage = _lineage(run, scope_id=scope_id, lineage_id=lineage_id)
    lineage.writes.extend(writes)


def lineage_patch(
    run: RunState,
    *,
    scope_id: str,
    lineage_id: str,
) -> StatePatch:
    """Return a replayable patch for one lineage's pending writes.

    Barrier/gather code should consume this instead of reconstructing a patch
    from visible state. Incoming values are the replay source of truth.
    """
    lineage = _lineage(run, scope_id=scope_id, lineage_id=lineage_id)
    return StatePatch(writes=list(lineage.writes))


def lineage_state_view(
    run: RunState,
    *,
    scope_id: str,
    lineage_id: str,
) -> dict[str, Any]:
    """Materialize scope committed state plus ancestor/current lineage writes."""
    scope = run.scopes.get(scope_id)
    if scope is None:
        raise ValueError(f"unknown scope {scope_id!r}")
    writes: list[StateWrite] = []
    for lineage in _lineage_chain(run, scope_id=scope_id, lineage_id=lineage_id):
        writes.extend(lineage.writes)
    return LineageStateView(scope.committed_state, writes).to_state_dict()


def lineage_state_writes(
    run: RunState,
    *,
    scope_id: str,
    lineage_id: str,
) -> Iterator[StateWrite]:
    """Yield ancestor and current lineage writes in read-visibility order."""
    for lineage in _lineage_chain(run, scope_id=scope_id, lineage_id=lineage_id):
        yield from lineage.writes


def _lineage(run: RunState, *, scope_id: str, lineage_id: str) -> LineageState:
    lineage = run.lineages.get(lineage_id)
    if lineage is None:
        raise ValueError(f"unknown lineage {lineage_id!r}")
    if lineage.scope_id != scope_id:
        raise ValueError(
            f"lineage {lineage_id!r} belongs to scope {lineage.scope_id!r}, "
            f"not {scope_id!r}"
        )
    return lineage


def _lineage_chain(
    run: RunState, *, scope_id: str, lineage_id: str
) -> Iterator[LineageState]:
    lineage = _lineage(run, scope_id=scope_id, lineage_id=lineage_id)
    reverse_chain: list[LineageState] = []
    seen: set[str] = set()
    while True:
        if lineage.id in seen:
            raise WorkflowExecutionError(
                f"cycle detected in lineage chain at {lineage.id!r}"
            )
        seen.add(lineage.id)
        reverse_chain.append(lineage)
        if lineage.parent_id is None:
            break
        lineage = _lineage(run, scope_id=scope_id, lineage_id=lineage.parent_id)
    yield from reversed(reverse_chain)
