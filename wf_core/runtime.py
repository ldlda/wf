from __future__ import annotations

from collections.abc import Mapping
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
from .node_exec import (
    AsyncNodeHandler,
    NodeHandler,
    coerce_node_result,
    execute_node_use,
    execute_node_use_async,
)
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
    "AsyncNodeHandler",
    "NodeHandler",
    "coerce_node_result",
    "execute_workflow_async",
    "execute_workflow",
    "resume_workflow_async",
    "resume_workflow",
    "step_workflow_async",
    "step_workflow",
]


def _prepare_new_run(workflow: Workflow, workflow_input: dict[str, Any]) -> RunState:
    run = create_run_state(workflow, workflow_input)
    workflow.validate_structure().raise_for_errors()
    validate_payload_against_schema(
        workflow.input_schema, workflow_input, "workflow input"
    )
    return run


def _prepare_resume(
    workflow: Workflow,
    run: RunState,
    *,
    resume_payload: dict[str, Any] | None,
    resume_outcome: str,
) -> WorkflowIndex | None:
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
        return None

    index = build_workflow_index(workflow)

    if run.status == RunStatus.INTERRUPTED:
        if resume_payload is None:
            return None
        resume_interrupt(
            workflow,
            run,
            index=index,
            resume_payload=resume_payload,
            resume_outcome=resume_outcome,
        )
        collapse_completed_frames(run)
        if run.current_node_id == END:
            return None

    run.status = RunStatus.RUNNING
    run.error = None
    run.current_frame().status = FrameStatus.RUNNING
    return index


def _prepare_step(
    workflow: Workflow,
    run: RunState,
    index: WorkflowIndex | None,
) -> tuple[WorkflowIndex, object] | None:
    if run.current_frame_id is None:
        raise WorkflowExecutionError("run has no current frame")

    collapse_completed_frames(run)
    if run.current_node_id is None or run.current_node_id == END:
        return None
    if run.status == RunStatus.INTERRUPTED:
        return None

    if run.status == RunStatus.PENDING:
        run.status = RunStatus.RUNNING
    run.error = None

    resolved_index = index or build_workflow_index(workflow)
    frame = run.current_frame()
    if frame.status == FrameStatus.PENDING:
        frame.status = FrameStatus.RUNNING
    step = resolved_index.nodes_by_id[frame.node_id]
    return resolved_index, step


def _complete_step(
    *,
    run: RunState,
    index: WorkflowIndex,
    outcome: str,
    frame_id: str,
    node_id: str,
    step_type: str,
    step_result: Any,
) -> RunState:
    next_node_id = index.next_node_id(node_id, outcome)

    append_step_result_trace(
        run,
        frame_id=frame_id,
        node_id=node_id,
        step_type=step_type,
        next_node_id=next_node_id,
        result=step_result,
    )
    advance_frame(
        run,
        run.frames[frame_id],
        outcome=outcome,
        next_node_id=next_node_id,
    )
    return run


def execute_workflow(
    workflow: Workflow,
    workflow_input: dict[str, Any],
    registry: Mapping[str, NodeHandler],
) -> RunState:
    run = create_run_state(workflow, workflow_input)

    try:
        run = _prepare_new_run(workflow, workflow_input)
        return resume_workflow(workflow, run, registry)
    except Exception as exc:
        run.status = RunStatus.FAILED
        run.error = str(exc)
        raise


async def execute_workflow_async(
    workflow: Workflow,
    workflow_input: dict[str, Any],
    registry: Mapping[str, AsyncNodeHandler],
) -> RunState:
    run = create_run_state(workflow, workflow_input)

    try:
        run = _prepare_new_run(workflow, workflow_input)
        return await resume_workflow_async(workflow, run, registry)
    except Exception as exc:
        run.status = RunStatus.FAILED
        run.error = str(exc)
        raise


def resume_workflow(
    workflow: Workflow,
    run: RunState,
    registry: Mapping[str, NodeHandler],
    *,
    resume_payload: dict[str, Any] | None = None,
    resume_outcome: str = "submitted",
) -> RunState:
    index = _prepare_resume(
        workflow,
        run,
        resume_payload=resume_payload,
        resume_outcome=resume_outcome,
    )
    if index is None:
        if run.current_node_id == END:
            return finalize_run(workflow, run)
        return run

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


async def resume_workflow_async(
    workflow: Workflow,
    run: RunState,
    registry: Mapping[str, AsyncNodeHandler],
    *,
    resume_payload: dict[str, Any] | None = None,
    resume_outcome: str = "submitted",
) -> RunState:
    index = _prepare_resume(
        workflow,
        run,
        resume_payload=resume_payload,
        resume_outcome=resume_outcome,
    )
    if index is None:
        if run.current_node_id == END:
            return finalize_run(workflow, run)
        return run

    while True:
        collapse_completed_frames(run)
        if run.current_node_id == END:
            break
        await step_workflow_async(
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
    registry: Mapping[str, NodeHandler],
    *,
    index: WorkflowIndex | None = None,
) -> RunState:
    prepared = _prepare_step(workflow, run, index)
    if prepared is None:
        return run
    index, step = prepared
    frame = run.current_frame()

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
        raise WorkflowExecutionError(
            f"unsupported step type {getattr(step, 'type', type(step).__name__)!r}"
        )

    return _complete_step(
        run=run,
        index=index,
        outcome=step_result.outcome,
        frame_id=frame.id,
        node_id=frame.node_id,
        step_type=step.type,
        step_result=step_result,
    )


async def step_workflow_async(
    workflow: Workflow,
    run: RunState,
    registry: Mapping[str, AsyncNodeHandler],
    *,
    index: WorkflowIndex | None = None,
) -> RunState:
    prepared = _prepare_step(workflow, run, index)
    if prepared is None:
        return run
    index, step = prepared
    frame = run.current_frame()

    if isinstance(step, NodeUse):
        node_def = index.node_defs[step.node]
        step_result = await execute_node_use_async(
            workflow, run, step, node_def, registry
        )
    elif isinstance(step, ConditionNode):
        step_result = handle_condition_step(run, step)
    elif isinstance(step, JoinNode):
        step_result = handle_join_step()
    elif isinstance(step, InterruptNode):
        return handle_interrupt_step(run, step)
    elif isinstance(step, ForeachNode):
        return step_foreach(workflow, run, step, index)
    else:
        raise WorkflowExecutionError(
            f"unsupported step type {getattr(step, 'type', type(step).__name__)!r}"
        )

    return _complete_step(
        run=run,
        index=index,
        outcome=step_result.outcome,
        frame_id=frame.id,
        node_id=frame.node_id,
        step_type=step.type,
        step_result=step_result,
    )
