from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from typing import Any

from .model import (
    BinaryCondition,
    Condition,
    ConditionNode,
    ExistsCondition,
    ForeachNode,
    JoinNode,
    LiteralOperand,
    NodeDef,
    NodeResult,
    NodeUse,
    NotCondition,
    PathOperand,
    VariadicCondition,
    Workflow,
)


class WorkflowExecutionError(RuntimeError):
    pass


@dataclass(slots=True)
class RuntimeContext:
    current_node_id: str
    retry_count: int = 0
    prior_outcome: str | None = None
    activated_incoming_edge: str | None = None


@dataclass(slots=True)
class TraceEntry:
    node_id: str
    step_type: str
    resolved_input: dict[str, Any]
    outcome: str
    next_node_id: str
    output: dict[str, Any] = field(default_factory=dict)
    state_changes: dict[str, Any] = field(default_factory=dict)


NodeHandler = Callable[[dict[str, Any], RuntimeContext], NodeResult | dict[str, Any]]


def execute_workflow(
    workflow: Workflow,
    workflow_input: dict[str, Any],
    registry: dict[str, NodeHandler],
) -> dict[str, Any]:
    report = workflow.validate_structure()
    report.raise_for_errors()

    _validate_payload_against_schema(
        workflow.input_schema, workflow_input, "workflow input"
    )

    node_defs = {node_def.name: node_def for node_def in workflow.node_defs}
    nodes_by_id = {node.id: node for node in workflow.nodes}
    edge_map = {(edge.from_, edge.outcome): edge.to for edge in workflow.edges}

    state = dict(workflow_input)
    trace: list[TraceEntry] = []
    current_node_id = workflow.start
    prior_outcome: str | None = None
    activated_incoming_edge: str | None = None

    while current_node_id != "__end__":
        step = nodes_by_id[current_node_id]

        if isinstance(step, NodeUse):
            node_def = node_defs[step.node]
            node_result = _execute_node_use(
                step,
                node_def,
                state,
                workflow_input,
                registry,
                prior_outcome,
                activated_incoming_edge,
                workflow,
            )
            outcome = node_result["outcome"]
        elif isinstance(step, ConditionNode):
            predicate = _eval_condition(
                step.check, state, workflow_input, prior_outcome
            )
            outcome = "true" if predicate else "false"
            node_result = {
                "resolved_input": {},
                "output": {"predicate": predicate},
                "state_changes": {},
            }
        elif isinstance(step, JoinNode):
            outcome = "done"
            node_result = {
                "resolved_input": {},
                "output": {},
                "state_changes": {},
            }
        elif isinstance(step, ForeachNode):
            raise WorkflowExecutionError("foreach execution is not implemented yet")
        else:
            raise WorkflowExecutionError(f"unsupported step type {step.type!r}")

        next_node_id = edge_map.get((current_node_id, outcome))
        if next_node_id is None:
            raise WorkflowExecutionError(
                f"no edge found for node {current_node_id!r} and outcome {outcome!r}"
            )

        trace.append(
            TraceEntry(
                node_id=current_node_id,
                step_type=step.type,
                resolved_input=node_result["resolved_input"],
                outcome=outcome,
                next_node_id=next_node_id,
                output=node_result["output"],
                state_changes=node_result["state_changes"],
            )
        )

        prior_outcome = outcome
        activated_incoming_edge = current_node_id
        current_node_id = next_node_id

    final_output = _project_output(workflow, state)
    _validate_payload_against_schema(
        workflow.output_schema, final_output, "workflow output"
    )
    return {
        "state": state,
        "output": final_output,
        "trace": [asdict(entry) for entry in trace],
    }


def _execute_node_use(
    node: NodeUse,
    node_def: NodeDef,
    state: dict[str, Any],
    workflow_input: dict[str, Any],
    registry: dict[str, NodeHandler],
    prior_outcome: str | None,
    activated_incoming_edge: str | None,
    workflow: Workflow,
) -> dict[str, Any]:
    handler = registry.get(node.node)
    if handler is None:
        raise WorkflowExecutionError(
            f"no handler registered for node def {node.node!r}"
        )

    resolved_input = {
        destination_field: _resolve_path(source_path, state, workflow_input, {})
        for source_path, destination_field in node.in_map.items()
    }
    _validate_payload_against_schema(
        node_def.input_schema, resolved_input, f"node input for {node.id}"
    )

    context = RuntimeContext(
        current_node_id=node.id,
        prior_outcome=prior_outcome,
        activated_incoming_edge=activated_incoming_edge,
    )
    raw_result = handler(resolved_input, context)
    result = _coerce_node_result(raw_result)

    if result.outcome not in node_def.outcomes:
        raise WorkflowExecutionError(
            f"node {node.id!r} returned undeclared outcome {result.outcome!r}"
        )

    _validate_payload_against_schema(
        node_def.output_schema, result.output, f"node output for {node.id}"
    )
    state_changes = _apply_output_map(workflow, node, result.output, state)
    return {
        "outcome": result.outcome,
        "resolved_input": resolved_input,
        "output": result.output,
        "state_changes": state_changes,
    }


def _coerce_node_result(raw_result: NodeResult | dict[str, Any]) -> NodeResult:
    if isinstance(raw_result, NodeResult):
        return raw_result
    if "outcome" in raw_result and "output" in raw_result:
        return NodeResult.model_validate(raw_result)
    return NodeResult(outcome="ok", output=raw_result)


def _apply_output_map(
    workflow: Workflow,
    node: NodeUse,
    node_output: dict[str, Any],
    state: dict[str, Any],
) -> dict[str, Any]:
    state_changes: dict[str, Any] = {}
    for source_field, destination_path in node.out_map.items():
        if source_field not in node_output:
            raise WorkflowExecutionError(
                f"node {node.id!r} did not return required mapped field {source_field!r}"
            )
        value = node_output[source_field]
        _write_state_value(workflow, state, destination_path, value)
        state_changes[destination_path] = value
    return state_changes


def _write_state_value(
    workflow: Workflow, state: dict[str, Any], destination_path: str, value: Any
) -> None:
    root, field_name, *rest = destination_path.split(".")
    if root != "state":
        raise WorkflowExecutionError(
            f"executor only supports writes into state.*, got {destination_path!r}"
        )
    declared_field = workflow.state_schema.fields.get(field_name)
    merge_strategy = declared_field.merge_strategy if declared_field else "replace"
    key_path = [field_name, *rest]

    if merge_strategy == "replace":
        _set_nested_value(state, key_path, value)
        return

    current_value = _get_nested_value(state, key_path)
    if merge_strategy == "append":
        if current_value is None:
            _set_nested_value(
                state, key_path, [value] if not isinstance(value, list) else value
            )
            return
        if not isinstance(current_value, list):
            raise WorkflowExecutionError(
                f"cannot append into non-list state path {destination_path!r}"
            )
        if isinstance(value, list):
            current_value.extend(value)
        else:
            current_value.append(value)
        return

    if merge_strategy == "merge_object":
        if current_value is None:
            if not isinstance(value, dict):
                raise WorkflowExecutionError(
                    f"cannot merge non-object value into {destination_path!r}"
                )
            _set_nested_value(state, key_path, dict(value))
            return
        if not isinstance(current_value, dict) or not isinstance(value, dict):
            raise WorkflowExecutionError(
                f"merge_object requires dict values at {destination_path!r}"
            )
        current_value.update(value)
        return

    raise WorkflowExecutionError(f"unknown merge strategy {merge_strategy!r}")


def _project_output(workflow: Workflow, state: dict[str, Any]) -> dict[str, Any]:
    return {
        key: state[key] for key in workflow.output_schema.properties if key in state
    }


def _validate_payload_against_schema(schema: Any, payload: Any, label: str) -> None:
    if schema.type == "object":
        if not isinstance(payload, dict):
            raise WorkflowExecutionError(f"{label} must be an object")
        for required_key in schema.required:
            if required_key not in payload:
                raise WorkflowExecutionError(
                    f"{label} is missing required field {required_key!r}"
                )


def _eval_condition(
    condition: Condition,
    state: dict[str, Any],
    workflow_input: dict[str, Any],
    context_data: str | None,
) -> bool:
    if isinstance(condition, ExistsCondition):
        return _path_exists(condition.path, state, workflow_input, context_data)
    if isinstance(condition, NotCondition):
        return not _eval_condition(condition.arg, state, workflow_input, context_data)
    if isinstance(condition, VariadicCondition):
        values = [
            _eval_condition(arg, state, workflow_input, context_data)
            for arg in condition.args
        ]
        return all(values) if condition.op == "and" else any(values)
    if isinstance(condition, BinaryCondition):
        left = _resolve_operand(condition.left, state, workflow_input, context_data)
        right = _resolve_operand(condition.right, state, workflow_input, context_data)
        if condition.op == "eq":
            return left == right
        if condition.op == "ne":
            return left != right
        if condition.op == "gt":
            return left > right
        if condition.op == "lt":
            return left < right
    raise WorkflowExecutionError(f"unsupported condition operator {condition.op!r}")


def _resolve_operand(
    operand: PathOperand | LiteralOperand,
    state: dict[str, Any],
    workflow_input: dict[str, Any],
    context_data: str | None,
) -> Any:
    if isinstance(operand, LiteralOperand):
        return operand.value
    return _resolve_path(
        operand.path,
        state,
        workflow_input,
        {"prior_outcome": context_data},
    )


def _path_exists(
    path: str,
    state: dict[str, Any],
    workflow_input: dict[str, Any],
    context_data: str | None,
) -> bool:
    try:
        _resolve_path(path, state, workflow_input, {"prior_outcome": context_data})
    except WorkflowExecutionError:
        return False
    return True


def _resolve_path(
    path: str,
    state: dict[str, Any],
    workflow_input: dict[str, Any],
    context: dict[str, Any],
) -> Any:
    root, *parts = path.split(".")
    if not parts:
        raise WorkflowExecutionError(f"invalid path {path!r}")

    if root == "state":
        source = state
    elif root == "input":
        source = workflow_input
    elif root == "context":
        source = context
    else:
        raise WorkflowExecutionError(f"unknown path root {root!r}")

    current: Any = source
    for part in parts:
        if not isinstance(current, dict) or part not in current:
            raise WorkflowExecutionError(f"path {path!r} could not be resolved")
        current = current[part]
    return current


def _get_nested_value(state: dict[str, Any], path_parts: list[str]) -> Any:
    current: Any = state
    for part in path_parts:
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _set_nested_value(state: dict[str, Any], path_parts: list[str], value: Any) -> None:
    current = state
    for part in path_parts[:-1]:
        next_value = current.get(part)
        if next_value is None:
            next_value = {}
            current[part] = next_value
        if not isinstance(next_value, dict):
            raise WorkflowExecutionError(
                f"cannot descend into non-object state field {part!r}"
            )
        current = next_value
    current[path_parts[-1]] = value
