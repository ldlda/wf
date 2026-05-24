from __future__ import annotations

from wf_core.conditions import eval_condition
from wf_core.errors import WorkflowExecutionError
from wf_core.models.steps import ConditionNode, InterruptNode
from wf_core.run_state import (
    ROOT_SCOPE_ID,
    ExecutionFrame,
    FrameStatus,
    InterruptRoute,
    RunState,
    RunStatus,
    StepExecutionResult,
)
from wf_core.runtime.lineage import scope_input_for_frame
from wf_core.runtime.ops.flow import append_trace
from wf_core.runtime.ops.frames import frame_context_values
from wf_core.runtime.ops.interrupts import build_interrupt_request
from wf_core.runtime.ops.overlays import state_view_for_frame


def handle_condition_step(
    run: RunState,
    step: ConditionNode,
) -> StepExecutionResult:
    frame = run.current_frame()
    predicate = eval_condition(
        step.check,
        state_view_for_frame(run, frame),
        scope_input_for_frame(run, frame),
        frame.prior_outcome,
    )
    outcome = "true" if predicate else "false"
    return StepExecutionResult(
        outcome=outcome,
        resolved_input={},
        output={"predicate": predicate},
        state_changes={},
    )


def handle_join_step() -> StepExecutionResult:
    return StepExecutionResult(
        outcome="done",
        resolved_input={},
        output={},
        state_changes={},
    )


def handle_interrupt_step(
    run: RunState,
    step: InterruptNode,
) -> RunState:
    frame = run.current_frame()
    public_frame = frame
    route = None
    if frame.scope_id != ROOT_SCOPE_ID:
        public_frame = _owning_subgraph_frame(run, frame)
        scope = run.scopes.get(frame.scope_id)
        if scope is None or scope.workflow_ref is None:
            raise WorkflowExecutionError(
                f"child interrupt frame {frame.id!r} has no workflow scope"
            )
        route = InterruptRoute(
            frame_id=frame.id,
            node_id=frame.node_id,
            scope_id=frame.scope_id,
            lineage_id=frame.lineage_id,
            parent_frame_id=public_frame.id,
            workflow_ref=scope.workflow_ref,
        )
    interrupt_request = build_interrupt_request(
        step,
        frame_id=frame.id,
        state=state_view_for_frame(run, frame),
        workflow_input=scope_input_for_frame(run, frame),
        context=frame_context_values(frame),
        public_frame_id=public_frame.id,
        public_node_id=public_frame.node_id,
        route=route,
    )
    run.interrupt = interrupt_request
    run.status = RunStatus.INTERRUPTED
    frame.status = FrameStatus.INTERRUPTED
    append_trace(
        run,
        frame_id=frame.id,
        node_id=frame.node_id,
        step_type=step.type,
        resolved_input=interrupt_request.payload,
        outcome="interrupt",
        next_node_id=frame.node_id,
        output=interrupt_request.payload,
        state_changes={},
    )
    return run


def _owning_subgraph_frame(run: RunState, frame: ExecutionFrame) -> ExecutionFrame:
    """Return the graph-boundary frame that owns one child-scope interrupt."""
    cursor = frame
    while cursor.parent_frame_id is not None:
        parent = run.frames.get(cursor.parent_frame_id)
        if parent is None:
            raise WorkflowExecutionError(
                f"child interrupt frame {frame.id!r} references missing parent "
                f"{cursor.parent_frame_id!r}"
            )
        if parent.scope_id != frame.scope_id:
            return parent
        cursor = parent
    raise WorkflowExecutionError(
        f"child interrupt frame {frame.id!r} has no parent subgraph"
    )
