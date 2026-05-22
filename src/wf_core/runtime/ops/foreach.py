from __future__ import annotations

from collections.abc import Mapping

from wf_core.conditions import safe_resolve_path
from wf_core.errors import WorkflowExecutionError
from wf_core.models.steps import ForeachNode
from wf_core.models.workflow import Workflow
from wf_core.run_state import ExecutionFrame, FrameStatus, RunState, StepExecutionResult
from wf_core.runtime.foreach_state import ForeachBarrierState, ItemErrorRecord
from wf_core.runtime.ops.flow import advance_frame, append_step_result_trace
from wf_core.runtime.ops.frames import frame_context_values
from wf_core.runtime.ops.index import WorkflowIndex
from wf_core.runtime.ops.merges import ReducerDefinition
from wf_core.runtime.ops.state import (
    StatePatch,
    build_barrier_patch,
    commit_state_patch,
)
from wf_core.runtime.scheduler import (
    ForeachIterationMetadata,
    add_frame,
    block_frame_on_children,
)


def step_foreach(
    workflow: Workflow,
    run: RunState,
    step: ForeachNode,
    index: WorkflowIndex,
    *,
    reducers: Mapping[str, ReducerDefinition] | None = None,
) -> RunState:
    if step.mode == "serial":
        return _step_foreach_serial(workflow, run, step, index)
    return _step_foreach_concurrent(
        workflow,
        run,
        step,
        index,
        reducers=reducers,
    )


def _step_foreach_serial(
    workflow: Workflow,
    run: RunState,
    step: ForeachNode,
    index: WorkflowIndex,
) -> RunState:
    if step.mode != "serial":
        raise WorkflowExecutionError("serial foreach helper received non-serial mode")

    frame = run.current_frame()
    barrier = ForeachBarrierState.from_frame(frame, step.id) or ForeachBarrierState()
    iterable = _resolve_foreach_iterable(run, frame, step)

    loop_index = barrier.next_index
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
    barrier.next_index = loop_index + 1
    barrier.save_to_frame(frame, step.id)
    child_id = f"{frame.id}:{step.id}:{loop_index}"
    add_frame(
        run,
        ExecutionFrame(
            id=child_id,
            kind="foreach_iteration",
            node_id=loop_start,
            status=FrameStatus.PENDING,
            parent_frame_id=frame.id,
            metadata=ForeachIterationMetadata(
                foreach_node_id=step.id,
                loop_index=loop_index,
                loop_item=item,
                loop_alias=step.as_,
            ).to_metadata(),
        ),
        ready=True,
    )
    block_frame_on_children(run, frame.id, (child_id,))
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
    run.sync_from_current_frame()
    return run


def _step_foreach_concurrent(
    workflow: Workflow,
    run: RunState,
    step: ForeachNode,
    index: WorkflowIndex,
    *,
    reducers: Mapping[str, ReducerDefinition] | None = None,
) -> RunState:
    if step.concurrent is None:
        raise WorkflowExecutionError("concurrent foreach requires concurrent policy")
    frame = run.current_frame()
    barrier = ForeachBarrierState.from_frame(frame, step.id)
    if barrier is None:
        barrier = ForeachBarrierState(mode="concurrent")
    elif barrier.mode != "concurrent":
        raise WorkflowExecutionError("malformed concurrent foreach barrier mode")

    _finish_completed_children(run, step, barrier)
    iterable = _resolve_foreach_iterable(run, frame, step)
    _admit_concurrent_children(
        run=run,
        frame=frame,
        step=step,
        index=index,
        barrier=barrier,
        iterable=iterable,
    )

    if barrier.next_index >= len(iterable) and not barrier.outstanding_frame_ids:
        return _finish_concurrent_foreach(
            workflow=workflow,
            run=run,
            frame=frame,
            step=step,
            index=index,
            barrier=barrier,
            reducers=reducers,
        )

    barrier.save_to_frame(frame, step.id)
    block_frame_on_children(run, frame.id, barrier.outstanding_frame_ids)
    run.sync_from_current_frame()
    return run


def _resolve_foreach_iterable(
    run: RunState,
    frame: ExecutionFrame,
    step: ForeachNode,
) -> list[object]:
    iterable = safe_resolve_path(
        str(step.over),
        state=run.state,
        workflow_input=run.workflow_input,
        context=frame_context_values(frame),
    )
    if not isinstance(iterable, list):
        raise WorkflowExecutionError(
            f"foreach source {str(step.over)!r} must resolve to a list"
        )
    return iterable


def _finish_completed_children(
    run: RunState,
    step: ForeachNode,
    barrier: ForeachBarrierState,
) -> None:
    for child_id in tuple(barrier.outstanding_frame_ids):
        child = run.frames[child_id]
        if child.status == FrameStatus.COMPLETED:
            barrier.finish_child(child_id)
        elif child.status == FrameStatus.FAILED:
            if step.item_error.action in {"skip", "collect"}:
                barrier.finish_child(child_id)
                barrier.add_failure(error=_item_error_record(child))
                continue
            message = child.metadata.get("error", "unknown item failure")
            raise WorkflowExecutionError(
                f"concurrent foreach item frame {child_id!r} failed: {message}"
            )


def _item_error_record(child: ExecutionFrame) -> ItemErrorRecord:
    metadata = ForeachIterationMetadata.from_frame(child)
    if metadata is None:
        raise WorkflowExecutionError(
            f"failed foreach item frame {child.id!r} is missing item metadata"
        )
    error_type = child.metadata.get("error_type", "Exception")
    message = child.metadata.get("error", "unknown item failure")
    node_id = child.metadata.get("failed_at_node_id", child.node_id)
    if not all(isinstance(value, str) for value in (error_type, message, node_id)):
        raise WorkflowExecutionError(
            f"malformed failure metadata for foreach item frame {child.id!r}"
        )
    return ItemErrorRecord(
        index=metadata.loop_index,
        frame_id=child.id,
        node_id=node_id,
        error_type=error_type,
        message=message,
        item=metadata.loop_item,
    )


def _admit_concurrent_children(
    *,
    run: RunState,
    frame: ExecutionFrame,
    step: ForeachNode,
    index: WorkflowIndex,
    barrier: ForeachBarrierState,
    iterable: list[object],
) -> None:
    if step.concurrent is None:
        raise WorkflowExecutionError("concurrent foreach requires concurrent policy")

    loop_start = index.next_node_id(frame.node_id, "loop")
    while (
        barrier.next_index < len(iterable)
        and len(barrier.active_frame_ids) < step.concurrent.max_active
        and len(barrier.outstanding_frame_ids) < step.concurrent.max_outstanding
    ):
        loop_index = barrier.next_index
        item = iterable[loop_index]
        child_id = f"{frame.id}:{step.id}:{loop_index}"
        active_count = len(barrier.active_frame_ids)
        barrier.next_index = loop_index + 1
        barrier.start_child(child_id)
        add_frame(
            run,
            ExecutionFrame(
                id=child_id,
                kind="foreach_iteration",
                node_id=loop_start,
                status=FrameStatus.PENDING,
                parent_frame_id=frame.id,
                metadata=ForeachIterationMetadata(
                    foreach_node_id=step.id,
                    loop_index=loop_index,
                    loop_item=item,
                    loop_alias=step.as_,
                ).to_metadata(),
            ),
            ready=True,
        )
        append_step_result_trace(
            run,
            frame_id=frame.id,
            node_id=frame.node_id,
            step_type=step.type,
            next_node_id=loop_start,
            result=StepExecutionResult(
                outcome="loop",
                resolved_input={
                    "item": item,
                    "index": loop_index,
                    "active_count": active_count,
                },
                output={},
                state_changes={},
            ),
        )


def _finish_concurrent_foreach(
    *,
    workflow: Workflow,
    run: RunState,
    frame: ExecutionFrame,
    step: ForeachNode,
    index: WorkflowIndex,
    barrier: ForeachBarrierState,
    reducers: Mapping[str, ReducerDefinition] | None = None,
) -> RunState:
    error_records = [
        result.error.to_metadata()
        for result in sorted(
            barrier.pending_results.values(), key=lambda item: item.index
        )
        if result.status == "failed" and result.error is not None
    ]
    outcome = "completed_with_errors" if error_records else "done"
    next_node_id = index.next_node_id(frame.node_id, outcome)
    success_patches = [
        result.patch
        for result in (
            barrier.pending_results[item_index]
            for item_index in sorted(barrier.pending_results)
        )
        if result.status == "succeeded"
    ]
    item_patches = list(success_patches)
    if step.item_error.action == "collect":
        collect_to = step.item_error.collect_to
        if collect_to is None:
            raise WorkflowExecutionError(
                "collect item error policy requires collect_to"
            )
        item_patches.append(StatePatch(changes={str(collect_to): error_records}))
    combined = build_barrier_patch(
        workflow,
        item_patches,
        run.state,
        reducers=reducers,
    )
    state_changes = commit_state_patch(run.state, combined)
    append_step_result_trace(
        run,
        frame_id=frame.id,
        node_id=frame.node_id,
        step_type=step.type,
        next_node_id=next_node_id,
        result=StepExecutionResult(
            outcome=outcome,
            resolved_input={
                "count": barrier.next_index,
                "index": barrier.next_index,
                "committed_items": len(success_patches),
                "failed_items": len(error_records),
            },
            output={},
            state_changes=state_changes,
        ),
    )
    advance_frame(run, frame, outcome=outcome, next_node_id=next_node_id)
    return run
