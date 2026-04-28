from __future__ import annotations

from .run_state import ExecutionFrame, FrameStatus, RunState
from .tokens import END


def collapse_completed_frames(run: RunState) -> None:
    while run.current_frame_id is not None:
        frame = run.current_frame()
        if frame.node_id == END and frame.status != FrameStatus.COMPLETED:
            frame.status = FrameStatus.COMPLETED
            frame.finished_at_node_id = END
        if frame.status != FrameStatus.COMPLETED or frame.parent_frame_id is None:
            run.sync_from_current_frame()
            return
        run.current_frame_id = frame.parent_frame_id
        parent = run.current_frame()
        if parent.status == FrameStatus.PENDING:
            parent.status = FrameStatus.RUNNING
        run.sync_from_current_frame()


def frame_context_values(frame: ExecutionFrame) -> dict[str, object | None]:
    context: dict[str, object | None] = {
        "prior_outcome": frame.prior_outcome,
        "activated_incoming_edge": frame.activated_incoming_edge,
    }
    if frame.kind == "foreach_iteration":
        loop_item = frame.metadata.get("loop_item")
        loop_index = frame.metadata.get("loop_index")
        loop_alias = frame.metadata.get("loop_alias")
        context["loop_item"] = loop_item
        context["loop_index"] = loop_index
        if isinstance(loop_alias, str) and loop_alias:
            context[loop_alias] = loop_item
    return context
