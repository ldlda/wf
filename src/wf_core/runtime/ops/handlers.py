from __future__ import annotations

from wf_core.conditions import eval_condition
from wf_core.models.steps import ConditionNode, InterruptNode
from wf_core.run_state import FrameStatus, RunState, RunStatus, StepExecutionResult
from wf_core.runtime.ops.flow import append_trace
from wf_core.runtime.ops.frames import frame_context_values
from wf_core.runtime.ops.interrupts import build_interrupt_request


def handle_condition_step(
    run: RunState,
    step: ConditionNode,
) -> StepExecutionResult:
    frame = run.current_frame()
    predicate = eval_condition(
        step.check,
        run.state,
        run.workflow_input,
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
    interrupt_request = build_interrupt_request(
        step,
        frame_id=frame.id,
        state=run.state,
        workflow_input=run.workflow_input,
        context=frame_context_values(frame),
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
