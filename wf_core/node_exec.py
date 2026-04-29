from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from typing import Any, cast

from .conditions import safe_resolve_path
from .errors import WorkflowExecutionError
from .frame_ops import frame_context_values
from .model import NodeDef, NodeResult, NodeUse, Workflow
from .run_state import RunState, RuntimeContext, StepExecutionResult
from .schema_tools import validate_payload_against_schema
from .state_ops import apply_output_map

NodeHandler = Callable[[dict[str, Any], RuntimeContext], NodeResult | dict[str, Any]]
AsyncNodeHandler = Callable[
    [dict[str, Any], RuntimeContext],
    Awaitable[NodeResult | dict[str, Any]] | NodeResult | dict[str, Any],
]


def _resolve_node_execution(
    *,
    workflow: Workflow,
    run: RunState,
    node: NodeUse,
    node_def: NodeDef,
) -> tuple[dict[str, Any], RuntimeContext]:
    frame = run.current_frame()
    context_values = frame_context_values(frame)
    resolved_input = {
        destination_field: safe_resolve_path(
            source_path,
            state=run.state,
            workflow_input=run.workflow_input,
            context=context_values,
        )
        for source_path, destination_field in node.in_map.items()
    }
    validate_payload_against_schema(
        node_def.input_schema, resolved_input, f"node input for {node.id}"
    )

    context = RuntimeContext(
        current_node_id=node.id,
        frame_id=frame.id,
        prior_outcome=frame.prior_outcome,
        activated_incoming_edge=frame.activated_incoming_edge,
        metadata=dict(frame.metadata),
    )
    return resolved_input, context


def _finalize_node_execution(
    *,
    workflow: Workflow,
    run: RunState,
    node: NodeUse,
    node_def: NodeDef,
    resolved_input: dict[str, Any],
    raw_result: NodeResult | dict[str, Any],
) -> StepExecutionResult:
    result = coerce_node_result(raw_result)

    if result.outcome not in node_def.outcomes:
        raise WorkflowExecutionError(
            f"node {node.id!r} returned undeclared outcome {result.outcome!r}"
        )

    validate_payload_against_schema(
        node_def.output_schema, result.output, f"node output for {node.id}"
    )
    state_changes = apply_output_map(workflow, node, result.output, run.state)
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
) -> StepExecutionResult:
    handler = registry.get(node.node)
    if handler is None:
        raise WorkflowExecutionError(
            f"no handler registered for node def {node.node!r}"
        )

    resolved_input, context = _resolve_node_execution(
        workflow=workflow,
        run=run,
        node=node,
        node_def=node_def,
    )
    raw_result = handler(resolved_input, context)
    return _finalize_node_execution(
        workflow=workflow,
        run=run,
        node=node,
        node_def=node_def,
        resolved_input=resolved_input,
        raw_result=raw_result,
    )


async def execute_node_use_async(
    workflow: Workflow,
    run: RunState,
    node: NodeUse,
    node_def: NodeDef,
    registry: Mapping[str, AsyncNodeHandler],
) -> StepExecutionResult:
    handler = registry.get(node.node)
    if handler is None:
        raise WorkflowExecutionError(
            f"no handler registered for node def {node.node!r}"
        )

    resolved_input, context = _resolve_node_execution(
        workflow=workflow,
        run=run,
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
        node=node,
        node_def=node_def,
        resolved_input=resolved_input,
        raw_result=cast(NodeResult | dict[str, Any], raw_result),
    )


def coerce_node_result(raw_result: NodeResult | dict[str, Any]) -> NodeResult:
    if isinstance(raw_result, NodeResult):
        return raw_result
    if "outcome" in raw_result and "output" in raw_result:
        return NodeResult.model_validate(raw_result)
    return NodeResult(outcome="ok", output=raw_result)
