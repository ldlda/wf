from __future__ import annotations

from typing import Any

from .conditions import safe_resolve_path
from .errors import WorkflowExecutionError
from .model import InterruptNode, Workflow
from .run_state import FrameStatus, InterruptRequest, RunState, TraceEntry
from .state_ops import apply_mapped_state
from .tokens import END


def build_interrupt_request(
    node: InterruptNode,
    *,
    frame_id: str,
    state: dict[str, Any],
    workflow_input: dict[str, Any],
    context: dict[str, Any],
) -> InterruptRequest:
    payload = {
        payload_field: safe_resolve_path(
            source_path,
            state=state,
            workflow_input=workflow_input,
            context=context,
        )
        for source_path, payload_field in node.request_map.items()
    }
    return InterruptRequest(
        id=f"interrupt:{node.id}",
        frame_id=frame_id,
        node_id=node.id,
        kind=node.kind,
        payload=payload,
    )


def resume_interrupt(
    workflow: Workflow,
    run: RunState,
    *,
    nodes_by_id: dict[str, Any],
    edge_map: dict[tuple[str, str], str],
    resume_payload: dict[str, Any],
    resume_outcome: str,
) -> None:
    if run.current_frame_id is None:
        raise WorkflowExecutionError("interrupted run has no current frame")
    if run.current_node_id is None:
        raise WorkflowExecutionError("interrupted run has no current node")
    if run.interrupt is None:
        raise WorkflowExecutionError("run is interrupted but has no interrupt request")

    frame = run.current_frame()
    step = nodes_by_id[frame.node_id]
    if not isinstance(step, InterruptNode):
        raise WorkflowExecutionError(
            f"interrupted run expected interrupt node, got {step.type!r}"
        )
    if resume_outcome not in step.outcomes:
        raise WorkflowExecutionError(
            f"interrupt node {step.id!r} does not declare resume outcome {resume_outcome!r}"
        )

    state_changes = apply_mapped_state(
        workflow,
        resume_payload,
        step.out_map,
        run.state,
        missing_field_message="interrupt resume payload is missing required field {field}",
    )
    next_node_id = edge_map.get((frame.node_id, resume_outcome))
    if next_node_id is None:
        raise WorkflowExecutionError(
            f"no edge found for interrupt node {frame.node_id!r} and outcome {resume_outcome!r}"
        )

    run.trace.append(
        TraceEntry(
            frame_id=frame.id,
            node_id=frame.node_id,
            step_type=step.type,
            resolved_input=resume_payload,
            outcome=resume_outcome,
            next_node_id=next_node_id,
            output=resume_payload,
            state_changes=state_changes,
        )
    )
    frame.prior_outcome = resume_outcome
    frame.activated_incoming_edge = frame.node_id
    frame.node_id = next_node_id
    frame.status = FrameStatus.RUNNING if next_node_id != END else FrameStatus.COMPLETED
    frame.finished_at_node_id = END if next_node_id == END else None
    run.interrupt = None
    run.sync_from_current_frame()
