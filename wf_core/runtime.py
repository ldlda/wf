from __future__ import annotations

from typing import Any

from .errors import WorkflowExecutionError
from .foreach_ops import step_foreach
from .flow_ops import advance_frame, append_step_result_trace, finalize_run
from .frame_ops import collapse_completed_frames
from .interrupt_ops import resume_interrupt
from .model import (
    ConditionNode,
    ForeachNode,
    InterruptNode,
    JoinNode,
    NodeUse,
    Workflow,
)
from .node_exec import NodeHandler, coerce_node_result, execute_node_use
from .run_factory import create_run_state
from .run_state import (
    FrameStatus,
    RunState,
    RunStatus,
)
from .schema_tools import validate_payload_against_schema
from .step_handlers import (
    handle_condition_step,
    handle_interrupt_step,
    handle_join_step,
)
from .tokens import END
from .workflow_index import WorkflowIndex, build_workflow_index

__all__ = [
    "NodeHandler",
    "coerce_node_result",
    "execute_workflow",
    "resume_workflow",
    "step_workflow",
]


def execute_workflow(
    workflow: Workflow,
    workflow_input: dict[str, Any],
    registry: dict[str, NodeHandler],
) -> RunState:
    run = create_run_state(workflow, workflow_input)

    try:
        workflow.validate_structure().raise_for_errors()
        validate_payload_against_schema(
            workflow.input_schema, workflow_input, "workflow input"
        )
        return resume_workflow(workflow, run, registry)
    except Exception as exc:
        run.status = RunStatus.FAILED
        run.error = str(exc)
        raise


def resume_workflow(
    workflow: Workflow,
    run: RunState,
    registry: dict[str, NodeHandler],
    *,
    resume_payload: dict[str, Any] | None = None,
    resume_outcome: str = "submitted",
) -> RunState:
    if run.workflow_name != workflow.name:
        raise WorkflowExecutionError(
            f"run state belongs to workflow {run.workflow_name!r}, not {workflow.name!r}"
        )

    if run.current_frame_id is None:
        raise WorkflowExecutionError("run has no current frame")
    collapse_completed_frames(run)

    if run.current_node_id is None:
        raise WorkflowExecutionError("run has no current node")

    if run.status == RunStatus.COMPLETED:
        return run

    index = build_workflow_index(workflow)

    if run.status == RunStatus.INTERRUPTED:
        if resume_payload is None:
            return run
        resume_interrupt(
            workflow,
            run,
            index=index,
            resume_payload=resume_payload,
            resume_outcome=resume_outcome,
        )
        collapse_completed_frames(run)
        if run.current_node_id == END:
            return finalize_run(workflow, run)

    run.status = RunStatus.RUNNING
    run.error = None
    run.current_frame().status = FrameStatus.RUNNING

    while True:
        collapse_completed_frames(run)
        if run.current_node_id == END:
            break
        step_workflow(
            workflow,
            run,
            registry,
            index=index,
        )
        if run.status == RunStatus.INTERRUPTED:
            return run

    return finalize_run(workflow, run)


def step_workflow(
    workflow: Workflow,
    run: RunState,
    registry: dict[str, NodeHandler],
    *,
    index: WorkflowIndex | None = None,
) -> RunState:
    if run.current_frame_id is None:
        raise WorkflowExecutionError("run has no current frame")

    collapse_completed_frames(run)
    if run.current_node_id is None or run.current_node_id == END:
        return run
    if run.status == RunStatus.INTERRUPTED:
        return run

    if run.status == RunStatus.PENDING:
        run.status = RunStatus.RUNNING
    run.error = None

    index = index or build_workflow_index(workflow)

    frame = run.current_frame()
    if frame.status == FrameStatus.PENDING:
        frame.status = FrameStatus.RUNNING
    step = index.nodes_by_id[frame.node_id]

    if isinstance(step, NodeUse):
        node_def = index.node_defs[step.node]
        step_result = execute_node_use(workflow, run, step, node_def, registry)
    elif isinstance(step, ConditionNode):
        step_result = handle_condition_step(run, step)
    elif isinstance(step, JoinNode):
        step_result = handle_join_step()
    elif isinstance(step, InterruptNode):
        return handle_interrupt_step(run, step)
    elif isinstance(step, ForeachNode):
        return step_foreach(workflow, run, step, index)
    else:
        raise WorkflowExecutionError(f"unsupported step type {step.type!r}")

    next_node_id = index.next_node_id(frame.node_id, step_result.outcome)

    append_step_result_trace(
        run,
        frame_id=frame.id,
        node_id=frame.node_id,
        step_type=step.type,
        next_node_id=next_node_id,
        result=step_result,
    )
    advance_frame(
        run,
        frame,
        outcome=step_result.outcome,
        next_node_id=next_node_id,
    )
    return run
