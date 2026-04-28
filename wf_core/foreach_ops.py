from __future__ import annotations

from typing import Any

from .conditions import safe_resolve_path
from .errors import WorkflowExecutionError
from .flow_ops import advance_frame, append_trace
from .frame_ops import frame_context_values
from .model import ForeachNode, Workflow
from .run_state import ExecutionFrame, FrameStatus, RunState


def step_foreach(
    workflow: Workflow,
    run: RunState,
    step: ForeachNode,
    edge_map: dict[tuple[str, str], str],
) -> RunState:
    if step.mode != "serial":
        raise WorkflowExecutionError("parallel foreach execution is not implemented yet")

    frame = run.current_frame()
    progress_map = frame.metadata.setdefault("foreach_progress", {})
    progress = progress_map.setdefault(step.id, {"index": 0})

    iterable = safe_resolve_path(
        step.over,
        state=run.state,
        workflow_input=run.workflow_input,
        context=frame_context_values(frame),
    )
    if not isinstance(iterable, list):
        raise WorkflowExecutionError(
            f"foreach source {step.over!r} must resolve to a list"
        )

    index = progress["index"]
    if index >= len(iterable):
        outcome = "done"
        next_node_id = edge_map.get((frame.node_id, outcome))
        if next_node_id is None:
            raise WorkflowExecutionError(
                f"no edge found for node {frame.node_id!r} and outcome {outcome!r}"
            )
        append_trace(
            run,
            frame_id=frame.id,
            node_id=frame.node_id,
            step_type=step.type,
            resolved_input={"count": len(iterable), "index": index},
            outcome=outcome,
            next_node_id=next_node_id,
            output={},
            state_changes={},
        )
        advance_frame(run, frame, outcome=outcome, next_node_id=next_node_id)
        return run

    loop_start = edge_map.get((frame.node_id, "loop"))
    if loop_start is None:
        raise WorkflowExecutionError(
            f"no edge found for foreach node {frame.node_id!r} and outcome 'loop'"
        )

    item = iterable[index]
    progress["index"] = index + 1
    child_id = f"{frame.id}:{step.id}:{index}"
    child_metadata = {
        "foreach_node_id": step.id,
        "loop_index": index,
        "loop_item": item,
        "loop_alias": step.as_,
    }
    run.frames[child_id] = ExecutionFrame(
        id=child_id,
        kind="foreach_iteration",
        node_id=loop_start,
        status=FrameStatus.PENDING,
        parent_frame_id=frame.id,
        metadata=child_metadata,
    )
    append_trace(
        run,
        frame_id=frame.id,
        node_id=frame.node_id,
        step_type=step.type,
        resolved_input={"item": item, "index": index},
        outcome="loop",
        next_node_id=loop_start,
        output={},
        state_changes={},
    )
    run.current_frame_id = child_id
    run.sync_from_current_frame()
    return run
