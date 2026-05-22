from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from wf_core.errors import WorkflowExecutionError
from wf_core.models.steps import (
    ConditionNode,
    ForeachNode,
    InterruptNode,
    JoinNode,
    NodeUse,
)
from wf_core.models.workflow import Workflow
from wf_core.runtime.ops.flow import advance_frame, append_step_result_trace
from wf_core.runtime.ops.foreach import step_foreach
from wf_core.runtime.ops.handlers import (
    handle_condition_step,
    handle_interrupt_step,
    handle_join_step,
)
from wf_core.runtime.ops.index import WorkflowIndex
from wf_core.runtime.ops.merges import ReducerDefinition
from wf_core.runtime.ops.nodes import (
    AsyncNodeHandler,
    NodeHandler,
    execute_node_use,
    execute_node_use_async,
)
from wf_core.runtime.scheduler import (
    ForeachIterationMetadata,
    select_next_frame,
    wake_parent_for_child_progress,
)
from wf_core.run_state import ExecutionFrame, FrameStatus, RunState

from .preparation import prepare_step


def complete_step(
    *,
    run: RunState,
    index: WorkflowIndex,
    outcome: str,
    frame_id: str,
    node_id: str,
    step_type: str,
    step_result: Any,
) -> RunState:
    """Record a completed step and advance the active frame."""
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


def step_workflow(
    workflow: Workflow,
    run: RunState,
    registry: Mapping[str, NodeHandler],
    *,
    index: WorkflowIndex | None = None,
    reducers: Mapping[str, ReducerDefinition] | None = None,
) -> RunState:
    """Execute at most one synchronous workflow step."""
    frame = run.current_frame() if run.current_frame_id is not None else None
    if frame is None or frame.status != FrameStatus.RUNNING:
        if select_next_frame(run) is None:
            return run
    prepared = prepare_step(workflow, run, index)
    if prepared is None:
        return run
    index, step = prepared
    frame = run.current_frame()

    if isinstance(step, NodeUse):
        node_def = index.node_defs[step.node]
        try:
            step_result = execute_node_use(
                workflow,
                run,
                step,
                node_def,
                registry,
                reducers=reducers,
            )
        except Exception as exc:
            if _mark_handled_item_failure(run, index, frame, exc):
                return run
            raise
    elif isinstance(step, ConditionNode):
        step_result = handle_condition_step(run, step)
    elif isinstance(step, JoinNode):
        step_result = handle_join_step()
    elif isinstance(step, InterruptNode):
        return handle_interrupt_step(run, step)
    elif isinstance(step, ForeachNode):
        return step_foreach(workflow, run, step, index, reducers=reducers)
    else:
        raise WorkflowExecutionError(
            f"unsupported step type {getattr(step, 'type', type(step).__name__)!r}"
        )

    return complete_step(
        run=run,
        index=index,
        outcome=step_result.outcome,
        frame_id=frame.id,
        node_id=frame.node_id,
        step_type=step.type,
        step_result=step_result,
    )


def _mark_handled_item_failure(
    run: RunState,
    index: WorkflowIndex,
    frame: ExecutionFrame,
    exc: Exception,
) -> bool:
    """Record skip/collect item failures without failing the whole run here."""
    metadata = ForeachIterationMetadata.from_frame(frame)
    if metadata is None or frame.parent_frame_id is None:
        return False
    owner_step = index.nodes_by_id.get(metadata.foreach_node_id)
    if not isinstance(owner_step, ForeachNode):
        return False
    if owner_step.item_error.action == "fail":
        return False

    frame.status = FrameStatus.FAILED
    frame.metadata["error"] = str(exc)
    frame.metadata["error_type"] = type(exc).__name__
    frame.metadata["failed_at_node_id"] = frame.node_id
    wake_parent_for_child_progress(run, frame.id)
    run.sync_from_current_frame()
    return True


async def step_workflow_async(
    workflow: Workflow,
    run: RunState,
    registry: Mapping[str, AsyncNodeHandler],
    *,
    index: WorkflowIndex | None = None,
    reducers: Mapping[str, ReducerDefinition] | None = None,
) -> RunState:
    """Execute at most one async workflow step."""
    frame = run.current_frame() if run.current_frame_id is not None else None
    if frame is None or frame.status != FrameStatus.RUNNING:
        if select_next_frame(run) is None:
            return run
    prepared = prepare_step(workflow, run, index)
    if prepared is None:
        return run
    index, step = prepared
    frame = run.current_frame()

    if isinstance(step, NodeUse):
        node_def = index.node_defs[step.node]
        try:
            step_result = await execute_node_use_async(
                workflow,
                run,
                step,
                node_def,
                registry,
                reducers=reducers,
            )
        except Exception as exc:
            if _mark_handled_item_failure(run, index, frame, exc):
                return run
            raise
    elif isinstance(step, ConditionNode):
        step_result = handle_condition_step(run, step)
    elif isinstance(step, JoinNode):
        step_result = handle_join_step()
    elif isinstance(step, InterruptNode):
        return handle_interrupt_step(run, step)
    elif isinstance(step, ForeachNode):
        return step_foreach(workflow, run, step, index, reducers=reducers)
    else:
        raise WorkflowExecutionError(
            f"unsupported step type {getattr(step, 'type', type(step).__name__)!r}"
        )

    return complete_step(
        run=run,
        index=index,
        outcome=step_result.outcome,
        frame_id=frame.id,
        node_id=frame.node_id,
        step_type=step.type,
        step_result=step_result,
    )
