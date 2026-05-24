from __future__ import annotations

from typing import Any

from wf_core.run_state import ExecutionFrame, RunState
from wf_core.runtime.lineage import (
    LineageStateView,
    lineage_writes_for_frame,
    scope_state_for_frame,
)


def state_view_for_frame(run: RunState, frame: ExecutionFrame) -> dict[str, Any]:
    """Return committed parent state plus this frame's item-local overlay.

    Concurrent foreach item frames buffer writes in the parent barrier until the
    foreach barrier commits. Later nodes in the same item must read those
    earlier writes, while sibling item frames must not see them.
    """
    scope_state = scope_state_for_frame(run, frame)
    writes = lineage_writes_for_frame(run, frame)
    if not writes:
        return scope_state

    return LineageStateView(scope_state, writes).to_state_dict()
