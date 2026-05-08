from __future__ import annotations

from wf_core.conditions import safe_resolve_path
from wf_core.errors import WorkflowExecutionError
from wf_core.model import ForeachNode, Workflow
from wf_core.run_state import ExecutionFrame, FrameStatus, RunState, StepExecutionResult
from wf_core.runtime.ops.flow import advance_frame, append_step_result_trace
from wf_core.runtime.ops.frames import frame_context_values
from wf_core.runtime.ops.index import WorkflowIndex


def step_foreach(
    workflow: Workflow,
    run: RunState,
    step: ForeachNode,
    index: WorkflowIndex,
) -> RunState:
    if step.mode != "serial":
        raise WorkflowExecutionError(
            "parallel foreach execution is not implemented yet"
        )

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

    loop_index = progress["index"]
    if loop_index >= len(iterable):
        outcome = "done"
        next_node_id = index.next_node_id(frame.node_id, outcome)
        append_step_result_trace(
            run,
            frame_id=frame.id,
            node_id=frame.node_id,
            step_type=step.type,
            next_node_id=next_node_id,
            result=StepExecutionResult(
                outcome=outcome,
                resolved_input={"count": len(iterable), "index": loop_index},
                output={},
                state_changes={},
            ),
        )
        advance_frame(run, frame, outcome=outcome, next_node_id=next_node_id)
        return run

    loop_start = index.next_node_id(frame.node_id, "loop")

    item = iterable[loop_index]
    progress["index"] = loop_index + 1
    child_id = f"{frame.id}:{step.id}:{loop_index}"
    child_metadata = {
        "foreach_node_id": step.id,
        "loop_index": loop_index,
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
    append_step_result_trace(
        run,
        frame_id=frame.id,
        node_id=frame.node_id,
        step_type=step.type,
        next_node_id=loop_start,
        result=StepExecutionResult(
            outcome="loop",
            resolved_input={"item": item, "index": loop_index},
            output={},
            state_changes={},
        ),
    )
    run.current_frame_id = child_id
    run.sync_from_current_frame()
    return run
