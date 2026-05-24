from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from wf_core.run_state import ExecutionFrame, RunState, StateWrite
from wf_core.runtime.foreach_state import ForeachBarrierState, item_frame_owner
from wf_core.runtime.ops.state import safe_set_nested_value


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
    owner = item_frame_owner(frame)
    if owner is None:
        return ()
    parent_frame_id, foreach_node_id, item_index = owner
    parent_frame = run.frames[parent_frame_id]
    barrier = ForeachBarrierState.from_frame(parent_frame, foreach_node_id)
    if barrier is None or barrier.mode != "concurrent":
        return ()

    pending = barrier.pending_results.get(item_index)
    if pending is None:
        return ()
    return pending.patch.writes
