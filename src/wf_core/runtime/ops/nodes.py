from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any, cast

from wf_core.conditions import safe_resolve_path
from wf_core.errors import WorkflowExecutionError
from wf_core.local_paths import LocalPathError, set_local_value
from wf_core.models.results import NodeResult
from wf_core.models.schemas import NodeDef
from wf_core.models.steps import InputPathBinding, InputValueBinding, NodeUse
from wf_core.models.workflow import Workflow
from wf_core.run_state import (
    ExecutionFrame,
    RunState,
    RuntimeContext,
    StepExecutionResult,
)
from wf_core.runtime.foreach_state import ForeachBarrierState, item_frame_owner
from wf_core.runtime.lineage import (
    append_lineage_writes,
    commit_patch_for_frame,
    scope_input_for_frame,
)
from wf_core.runtime.ops.frames import frame_context_values
from wf_core.runtime.ops.merges import ReducerDefinition
from wf_core.runtime.ops.overlays import state_view_for_frame
from wf_core.runtime.ops.schemas import validate_payload_against_schema
from wf_core.runtime.ops.state import StatePatch, build_output_patch

NodeHandler = Callable[[dict[str, Any], RuntimeContext], NodeResult | dict[str, Any]]
AsyncNodeHandler = Callable[
    [dict[str, Any], RuntimeContext],
    Awaitable[NodeResult | dict[str, Any]] | NodeResult | dict[str, Any],
]


@dataclass(slots=True)
class PendingAsyncNodeResult:
    """Async handler result captured before sequential state finalization."""

    frame: ExecutionFrame
    node: NodeUse
    node_def: NodeDef
    resolved_input: dict[str, Any]
    raw_result: NodeResult | dict[str, Any]
    state_view: dict[str, Any]


def _resolve_node_execution(
    *,
    workflow: Workflow,
    run: RunState,
    frame: ExecutionFrame,
    node: NodeUse,
    node_def: NodeDef,
) -> tuple[dict[str, Any], RuntimeContext, dict[str, Any]]:
    context_values = frame_context_values(frame)
    state_view = state_view_for_frame(run, frame)
    resolved_input: dict[str, Any] = {}
    for binding in node.input:
        if isinstance(binding, InputValueBinding):
            value = binding.value
        elif isinstance(binding, InputPathBinding):
            value = safe_resolve_path(
                str(binding.path),
                state=state_view,
                workflow_input=scope_input_for_frame(run, frame),
                context=context_values,
            )
        else:
            raise WorkflowExecutionError(
                f"unsupported input binding for node {node.id!r}"
            )
        try:
            set_local_value(resolved_input, binding.target, value)
        except LocalPathError as exc:
            raise WorkflowExecutionError(str(exc)) from exc
    validate_payload_against_schema(
        node_def.input_schema, resolved_input, f"node input for {node.id}"
    )

    context = RuntimeContext(
        current_node_id=node.id,
        frame_id=frame.id,
        scope_id=frame.scope_id,
        lineage_id=frame.lineage_id,
        parent_lineage_id=frame.parent_lineage_id,
        prior_outcome=frame.prior_outcome,
        activated_incoming_edge=frame.activated_incoming_edge,
        metadata=dict(frame.metadata),
    )
    return resolved_input, context, state_view


def _finalize_node_execution(
    *,
    workflow: Workflow,
    run: RunState,
    frame: ExecutionFrame,
    node: NodeUse,
    node_def: NodeDef,
    resolved_input: dict[str, Any],
    raw_result: NodeResult | dict[str, Any],
    state_view: dict[str, Any],
    reducers: Mapping[str, ReducerDefinition] | None = None,
) -> StepExecutionResult:
    result = coerce_node_result(raw_result)

    if result.outcome not in node_def.outcomes:
        raise WorkflowExecutionError(
            f"node {node.id!r} returned undeclared outcome {result.outcome!r}"
        )

    validate_payload_against_schema(
        node_def.output_schema, result.output, f"node output for {node.id}"
    )
    patch = build_output_patch(
        workflow,
        node.output,
        result.output,
        state_view,
        reducers=reducers,
    )
    owner = item_frame_owner(frame)
    if owner is None:
        state_changes = commit_patch_for_frame(run, frame, patch)
    else:
        parent_frame_id, foreach_node_id, item_index = owner
        parent_frame = run.frames[parent_frame_id]
        barrier = ForeachBarrierState.from_frame(parent_frame, foreach_node_id)
        if barrier is not None and barrier.mode == "concurrent":
            # New concurrent foreach stores writes in the child lineage; the
            # barrier keeps only result metadata plus old patch fallback.
            append_lineage_writes(
                run,
                scope_id=frame.scope_id,
                lineage_id=frame.lineage_id,
                writes=patch.writes,
            )
            barrier.add_success_patch(
                index=item_index,
                frame_id=frame.id,
                patch=StatePatch(),
                lineage_id=frame.lineage_id,
            )
            barrier.save_to_frame(parent_frame, foreach_node_id)
            state_changes = {}
        else:
            state_changes = commit_patch_for_frame(run, parent_frame, patch)
    return StepExecutionResult(
        outcome=result.outcome,
        resolved_input=resolved_input,
        output=result.output,
        state_changes=state_changes,
    )


def execute_node_use(
    workflow: Workflow,
    run: RunState,
    node: NodeUse,
    node_def: NodeDef,
    registry: Mapping[str, NodeHandler],
    reducers: Mapping[str, ReducerDefinition] | None = None,
) -> StepExecutionResult:
    handler = registry.get(node.node)
    if handler is None:
        raise WorkflowExecutionError(
            f"no handler registered for node def {node.node!r}"
        )

    frame = run.current_frame()
    resolved_input, context, state_view = _resolve_node_execution(
        workflow=workflow,
        run=run,
        frame=frame,
        node=node,
        node_def=node_def,
    )
    raw_result = handler(resolved_input, context)
    return _finalize_node_execution(
        workflow=workflow,
        run=run,
        frame=frame,
        node=node,
        node_def=node_def,
        resolved_input=resolved_input,
        raw_result=raw_result,
        state_view=state_view,
        reducers=reducers,
    )


async def execute_node_use_async(
    workflow: Workflow,
    run: RunState,
    node: NodeUse,
    node_def: NodeDef,
    registry: Mapping[str, AsyncNodeHandler],
    reducers: Mapping[str, ReducerDefinition] | None = None,
) -> StepExecutionResult:
    handler = registry.get(node.node)
    if handler is None:
        raise WorkflowExecutionError(
            f"no handler registered for node def {node.node!r}"
        )

    frame = run.current_frame()
    resolved_input, context, state_view = _resolve_node_execution(
        workflow=workflow,
        run=run,
        frame=frame,
        node=node,
        node_def=node_def,
    )
    raw_or_awaitable = handler(resolved_input, context)
    if isinstance(raw_or_awaitable, Awaitable):
        raw_result = await raw_or_awaitable
    else:
        raw_result = raw_or_awaitable
    return _finalize_node_execution(
        workflow=workflow,
        run=run,
        frame=frame,
        node=node,
        node_def=node_def,
        resolved_input=resolved_input,
        raw_result=cast(NodeResult | dict[str, Any], raw_result),
        state_view=state_view,
        reducers=reducers,
    )


async def invoke_node_use_async_for_frame(
    workflow: Workflow,
    run: RunState,
    frame: ExecutionFrame,
    node: NodeUse,
    node_def: NodeDef,
    registry: Mapping[str, AsyncNodeHandler],
) -> PendingAsyncNodeResult:
    """Resolve input, await the async handler, and defer state finalization.

    Async concurrent foreach can run handler awaits concurrently, but state
    patches and traces must still be finalized sequentially against `RunState`.
    """
    handler = registry.get(node.node)
    if handler is None:
        raise WorkflowExecutionError(
            f"no handler registered for node def {node.node!r}"
        )

    resolved_input, context, state_view = _resolve_node_execution(
        workflow=workflow,
        run=run,
        frame=frame,
        node=node,
        node_def=node_def,
    )
    raw_or_awaitable = handler(resolved_input, context)
    if isinstance(raw_or_awaitable, Awaitable):
        raw_result = await raw_or_awaitable
    else:
        raw_result = raw_or_awaitable
    return PendingAsyncNodeResult(
        frame=frame,
        node=node,
        node_def=node_def,
        resolved_input=resolved_input,
        raw_result=cast(NodeResult | dict[str, Any], raw_result),
        state_view=state_view,
    )


def finalize_pending_async_node_result(
    workflow: Workflow,
    run: RunState,
    pending: PendingAsyncNodeResult,
    reducers: Mapping[str, ReducerDefinition] | None = None,
) -> StepExecutionResult:
    """Finalize a previously awaited async node result sequentially."""
    return _finalize_node_execution(
        workflow=workflow,
        run=run,
        frame=pending.frame,
        node=pending.node,
        node_def=pending.node_def,
        resolved_input=pending.resolved_input,
        raw_result=pending.raw_result,
        state_view=pending.state_view,
        reducers=reducers,
    )


async def execute_node_use_async_for_frame(
    workflow: Workflow,
    run: RunState,
    frame: ExecutionFrame,
    node: NodeUse,
    node_def: NodeDef,
    registry: Mapping[str, AsyncNodeHandler],
    reducers: Mapping[str, ReducerDefinition] | None = None,
) -> StepExecutionResult:
    """Execute one async node against an explicit frame.

    Async concurrent foreach cannot rely on `run.current_frame()` while several
    handlers are in flight. This explicit-frame helper keeps input resolution
    and item-local overlay lookup tied to the frame that launched the handler.
    """
    pending = await invoke_node_use_async_for_frame(
        workflow,
        run,
        frame=frame,
        node=node,
        node_def=node_def,
        registry=registry,
    )
    return finalize_pending_async_node_result(
        workflow=workflow,
        run=run,
        pending=pending,
        reducers=reducers,
    )


def coerce_node_result(raw_result: NodeResult | dict[str, Any]) -> NodeResult:
    if isinstance(raw_result, NodeResult):
        return raw_result
    if "outcome" in raw_result and "output" in raw_result:
        return NodeResult.model_validate(raw_result)
    return NodeResult(outcome="ok", output=raw_result)
