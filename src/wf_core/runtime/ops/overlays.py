from __future__ import annotations

from typing import Any

from wf_core.run_state import ExecutionFrame, RunState


def state_view_for_frame(run: RunState, frame: ExecutionFrame) -> dict[str, Any]:
    """Return the state view visible to one execution frame.

    This is intentionally a no-op seam for concurrent foreach V1. The first
    sync-concurrent slice only supports single-node item bodies, so item frames
    do not need to read their own prior buffered writes yet. The overlay slice
    should replace this with parent-state plus item-local staged writes.
    """
    return run.state
