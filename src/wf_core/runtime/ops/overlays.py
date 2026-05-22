from __future__ import annotations

from copy import deepcopy
from typing import Any

from wf_core.paths import StatePath
from wf_core.run_state import ExecutionFrame, RunState
from wf_core.runtime.foreach_state import ForeachBarrierState, item_frame_owner
from wf_core.runtime.ops.state import safe_set_nested_value


def state_view_for_frame(run: RunState, frame: ExecutionFrame) -> dict[str, Any]:
    """Return committed parent state plus this frame's item-local overlay.

    Concurrent foreach item frames buffer writes in the parent barrier until the
    foreach barrier commits. Later nodes in the same item must read those
    earlier writes, while sibling item frames must not see them.
    """
    owner = item_frame_owner(frame)
    if owner is None:
        return run.state

    parent_frame_id, foreach_node_id, item_index = owner
    parent_frame = run.frames[parent_frame_id]
    barrier = ForeachBarrierState.from_frame(parent_frame, foreach_node_id)
    if barrier is None or barrier.mode != "concurrent":
        return run.state

    pending = barrier.pending_results.get(item_index)
    if pending is None:
        return run.state

    state_view = deepcopy(run.state)
    for destination, value in pending.patch.changes.items():
        path = StatePath.parse(destination)
        safe_set_nested_value(state_view, list(path.parts), value)
    return state_view
