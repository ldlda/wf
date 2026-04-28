from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .conditions import safe_resolve_path
from .errors import WorkflowExecutionError
from .frame_ops import frame_context_values
from .model import NodeDef, NodeResult, NodeUse, Workflow
from .run_state import RunState, RuntimeContext, StepExecutionResult
from .schema_tools import validate_payload_against_schema
from .state_ops import apply_output_map

NodeHandler = Callable[[dict[str, Any], RuntimeContext], NodeResult | dict[str, Any]]


def execute_node_use(
    workflow: Workflow,
    run: RunState,
    node: NodeUse,
    node_def: NodeDef,
    registry: dict[str, NodeHandler],
) -> StepExecutionResult:
    handler = registry.get(node.node)
    if handler is None:
        raise WorkflowExecutionError(
            f"no handler registered for node def {node.node!r}"
        )

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
    raw_result = handler(resolved_input, context)
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


def coerce_node_result(raw_result: NodeResult | dict[str, Any]) -> NodeResult:
    if isinstance(raw_result, NodeResult):
        return raw_result
    if "outcome" in raw_result and "output" in raw_result:
        return NodeResult.model_validate(raw_result)
    return NodeResult(outcome="ok", output=raw_result)
