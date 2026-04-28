from __future__ import annotations

from typing import Any

from .model import Workflow
from .run_state import ExecutionFrame, FrameStatus, RunState, RunStatus, TraceEntry
from .schema_tools import validate_payload_against_schema
from .state_ops import project_output
from .tokens import END


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


def advance_frame(
    run: RunState,
    frame: ExecutionFrame,
    *,
    outcome: str,
    next_node_id: str,
) -> None:
    frame.prior_outcome = outcome
    frame.activated_incoming_edge = frame.node_id
    frame.node_id = next_node_id
    if next_node_id == END:
        frame.status = FrameStatus.COMPLETED
        frame.finished_at_node_id = END
    else:
        frame.finished_at_node_id = None
    run.sync_from_current_frame()


def finalize_run(workflow: Workflow, run: RunState) -> RunState:
    run.output = project_output(workflow, run.state)
    validate_payload_against_schema(
        workflow.output_schema, run.output, "workflow output"
    )
    run.status = RunStatus.COMPLETED
    run.current_node_id = END
    return run
