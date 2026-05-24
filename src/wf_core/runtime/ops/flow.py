from __future__ import annotations

from typing import Any

from wf_core.models.workflow import Workflow
from wf_core.run_state import (
    ExecutionFrame,
    FrameStatus,
    RunState,
    RunStatus,
    StepExecutionResult,
    TraceEntry,
)
from wf_core.runtime.ops.schemas import validate_payload_against_schema
from wf_core.runtime.ops.state import project_output
from wf_core.runtime.scheduler import (
    mark_frame_pending,
    wake_parent_for_child_progress,
)
from wf_core.tokens import END


def append_trace(
    run: RunState,
    *,
    frame_id: str,
    node_id: str,
    step_type: str,
    resolved_input: dict[str, Any],
    outcome: str,
    next_node_id: str,
    output: dict[str, Any],
    state_changes: dict[str, Any],
) -> None:
    run.trace.append(
        TraceEntry(
            frame_id=frame_id,
            node_id=node_id,
            step_type=step_type,
            resolved_input=resolved_input,
            outcome=outcome,
            next_node_id=next_node_id,
            output=output,
            state_changes=state_changes,
        )
    )


def append_step_result_trace(
    run: RunState,
    *,
    frame_id: str,
    node_id: str,
    step_type: str,
    next_node_id: str,
    result: StepExecutionResult,
) -> None:
    append_trace(
        run,
        frame_id=frame_id,
        node_id=node_id,
        step_type=step_type,
        resolved_input=result.resolved_input,
        outcome=result.outcome,
        next_node_id=next_node_id,
        output=result.output,
        state_changes=result.state_changes,
    )


def advance_frame(
    run: RunState,
    frame: ExecutionFrame,
    *,
    outcome: str,
    next_node_id: str,
    front: bool = False,
) -> None:
    frame.prior_outcome = outcome
    frame.activated_incoming_edge = frame.node_id
    frame.node_id = next_node_id
    if next_node_id == END:
        if frame.kind in {"workflow", "subgraph_root"}:
            # Legacy terminal routing emits the workflow-level `ok` outcome.
            # Explicit EndNode execution stores its declared outcome first.
            frame.metadata.setdefault("workflow_outcome", "ok")
        frame.status = FrameStatus.COMPLETED
        frame.finished_at_node_id = END
        wake_parent_for_child_progress(run, frame.id)
    else:
        frame.finished_at_node_id = None
        mark_frame_pending(run, frame.id, front=front)
    run.sync_from_current_frame()


def finalize_run(workflow: Workflow, run: RunState) -> RunState:
    if run.outcome is None:
        run.outcome = "ok"
    run.output = project_output(workflow, run.state)
    validate_payload_against_schema(
        workflow.output_schema, run.output, "workflow output"
    )
    run.status = RunStatus.COMPLETED
    run.current_node_id = END
    return run
