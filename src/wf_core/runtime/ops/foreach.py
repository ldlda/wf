from __future__ import annotations

from collections.abc import Mapping

from wf_core.conditions import safe_resolve_path
from wf_core.errors import WorkflowExecutionError
from wf_core.models.steps import ForeachNode
from wf_core.models.workflow import Workflow
from wf_core.run_state import ExecutionFrame, FrameStatus, RunState, StepExecutionResult
from wf_core.runtime.foreach_state import (
    ForeachActivationState,
    ForeachBarrierState,
    ItemErrorRecord,
    PendingItemResult,
    close_foreach_activation,
    load_or_begin_foreach_activation,
    save_foreach_activation,
)
from wf_core.runtime.lineage import (
    add_lineage,
    commit_patch_for_frame,
    lineage_patch,
    scope_input_for_frame,
)
from wf_core.runtime.ops.flow import advance_frame, append_step_result_trace
from wf_core.runtime.ops.frames import frame_context_values
from wf_core.runtime.ops.index import WorkflowIndex
from wf_core.runtime.ops.merges import ReducerDefinition
from wf_core.runtime.ops.overlays import state_view_for_frame
from wf_core.runtime.ops.state import (
    StatePatch,
    build_barrier_patch,
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
    activation = load_or_begin_foreach_activation(frame, step.id, mode="serial")
    barrier = activation.barrier
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
        # Close the visit before following `done` so a self-looping completion
        # edge or a later revisit starts a fresh activation.
        close_foreach_activation(frame, activation)
        advance_frame(run, frame, outcome=outcome, next_node_id=next_node_id)
        return run

    loop_start = index.next_node_id(frame.node_id, "loop")
    item = iterable[loop_index]
    loop_start, child_id = _admit_item_frame(
        run=run,
        frame=frame,
        step=step,
        index=index,
        activation=activation,
        loop_index=loop_index,
        item=item,
    )
    save_foreach_activation(frame, activation)
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
    activation = load_or_begin_foreach_activation(frame, step.id, mode="concurrent")
    barrier = activation.barrier

    _finish_completed_children(run, step, barrier)
    iterable = _resolve_foreach_iterable(run, frame, step)
    _admit_concurrent_children(
        run=run,
        frame=frame,
        step=step,
        index=index,
        activation=activation,
        iterable=iterable,
    )

    if barrier.next_index >= len(iterable) and not barrier.outstanding_frame_ids:
        return _finish_concurrent_foreach(
            workflow=workflow,
            run=run,
            frame=frame,
            step=step,
            index=index,
            activation=activation,
            reducers=reducers,
        )

    save_foreach_activation(frame, activation)
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
        state=state_view_for_frame(run, frame),
        workflow_input=scope_input_for_frame(run, frame),
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


def _admit_item_frame(
    *,
    run: RunState,
    frame: ExecutionFrame,
    step: ForeachNode,
    index: WorkflowIndex,
    activation: ForeachActivationState,
    loop_index: int,
    item: object,
) -> tuple[str, str]:
    """Create one activation-qualified child frame and lineage.

    Every item owns a lineage so nested subgraph/boundary commits have a
    parent lineage to buffer into; top-level serial writes still commit
    through the parent scope root. Returns the loop start node and child id;
    barrier child bookkeeping stays with the caller. Compare ids by name;
    never parse them.
    """
    loop_start = index.next_node_id(frame.node_id, "loop")
    child_id = _child_frame_id(activation, loop_index)
    child_lineage_id = _child_lineage_id(activation, loop_index)
    add_lineage(
        run,
        scope_id=frame.scope_id,
        lineage_id=child_lineage_id,
        parent_id=frame.lineage_id,
    )
    activation.barrier.next_index = loop_index + 1
    add_frame(
        run,
        ExecutionFrame(
            id=child_id,
            kind="foreach_iteration",
            node_id=loop_start,
            status=FrameStatus.PENDING,
            parent_frame_id=frame.id,
            scope_id=frame.scope_id,
            lineage_id=child_lineage_id,
            parent_lineage_id=frame.lineage_id,
            metadata=ForeachIterationMetadata(
                foreach_node_id=step.id,
                activation_id=activation.id,
                loop_index=loop_index,
                loop_item=item,
                loop_alias=step.as_,
            ).to_metadata(),
        ),
        ready=True,
    )
    return loop_start, child_id


def _admit_concurrent_children(
    *,
    run: RunState,
    frame: ExecutionFrame,
    step: ForeachNode,
    index: WorkflowIndex,
    activation: ForeachActivationState,
    iterable: list[object],
) -> None:
    if step.concurrent is None:
        raise WorkflowExecutionError("concurrent foreach requires concurrent policy")

    barrier = activation.barrier
    loop_start = index.next_node_id(frame.node_id, "loop")
    while (
        barrier.next_index < len(iterable)
        and len(barrier.active_frame_ids) < step.concurrent.max_active
        and len(barrier.outstanding_frame_ids) < step.concurrent.max_outstanding
    ):
        loop_index = barrier.next_index
        item = iterable[loop_index]
        active_count = len(barrier.active_frame_ids)
        loop_start, child_id = _admit_item_frame(
            run=run,
            frame=frame,
            step=step,
            index=index,
            activation=activation,
            loop_index=loop_index,
            item=item,
        )
        barrier.start_child(child_id)
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
    activation: ForeachActivationState,
    reducers: Mapping[str, ReducerDefinition] | None = None,
) -> RunState:
    barrier = activation.barrier
    # Coherence is enforced at load, but re-check here: a failed result
    # without an error must never silent-commit as `done`.
    error_records = []
    for result in sorted(barrier.pending_results.values(), key=lambda item: item.index):
        if result.status != "failed":
            continue
        if result.error is None:
            raise WorkflowExecutionError(
                f"foreach item result for index {result.index!r} is failed "
                "but carries no error"
            )
        error_records.append(result.error.to_metadata())
    outcome = "completed_with_errors" if error_records else "done"
    next_node_id = index.next_node_id(frame.node_id, outcome)
    success_patches = [
        _patch_for_successful_item(run, frame, result)
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
        # Collect-error records are generated by the barrier itself, not by an
        # item lineage, so they still enter as a compatibility `changes` patch.
        item_patches.append(StatePatch(changes={str(collect_to): error_records}))
    combined = build_barrier_patch(
        workflow,
        item_patches,
        state_view_for_frame(run, frame),
        reducers=reducers,
    )
    state_changes = commit_patch_for_frame(run, frame, combined)
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
    # Close the visit before following completion so later revisits start fresh.
    close_foreach_activation(frame, activation)
    advance_frame(run, frame, outcome=outcome, next_node_id=next_node_id)
    return run


def _child_frame_id(activation: ForeachActivationState, loop_index: int) -> str:
    """Return a deterministic opaque child frame id for one activation item.

    The id embeds the activation so a later visit at item zero cannot collide
    with the first visit. Compare full ids; never parse them.
    """
    return f"{activation.id}:{loop_index}"


def _child_lineage_id(activation: ForeachActivationState, loop_index: int) -> str:
    """Return a deterministic opaque lineage id for one activation item.

    The readable shape is only for diagnostics. Runtime code should compare the
    full id, not parse it; future structured lineage refs can replace this.
    """
    return f"{activation.id}[{loop_index}]"


def _patch_for_successful_item(
    run: RunState,
    frame: ExecutionFrame,
    result: PendingItemResult,
) -> StatePatch:
    """Return the replayable patch for a completed foreach item.

    Item writes live in `RunState.lineages`; a success without a known
    lineage is corrupt state and fails closed.
    """
    if result.lineage_id is None or result.lineage_id not in run.lineages:
        raise WorkflowExecutionError(
            f"foreach item result for index {result.index!r} references "
            f"unknown lineage {result.lineage_id!r}"
        )
    return lineage_patch(
        run,
        scope_id=frame.scope_id,
        lineage_id=result.lineage_id,
    )
