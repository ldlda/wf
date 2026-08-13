from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from wf_core.conditions import safe_resolve_path
from wf_core.errors import WorkflowExecutionError
from wf_core.local_paths import LocalPathError, set_local_value
from wf_core.models.input_bindings import (
    ArrayExpression,
    InputExpression,
    InputExpressionBinding,
    InputPathBinding,
    InputValueBinding,
    LiteralExpression,
    ObjectExpression,
    PathExpression,
    StepInputBinding,
)
from wf_core.models.json_values import JsonValue, validate_strict_json_value


def resolve_input_expression(
    expression: InputExpression,
    *,
    state: Mapping[str, Any],
    workflow_input: Mapping[str, Any],
    context: Mapping[str, Any],
    label: str,
    location: str,
) -> JsonValue:
    """Resolve one composite expression while preserving its payload location."""

    if isinstance(expression, LiteralExpression):
        return expression.value
    if isinstance(expression, PathExpression):
        try:
            value = safe_resolve_path(
                str(expression.path),
                state=state,
                workflow_input=workflow_input,
                context=context,
            )
            return validate_strict_json_value(value)
        except (ValueError, WorkflowExecutionError) as exc:
            raise WorkflowExecutionError(f"{label} {location}: {exc}") from exc
    if isinstance(expression, ArrayExpression):
        return [
            resolve_input_expression(
                item,
                state=state,
                workflow_input=workflow_input,
                context=context,
                label=label,
                location=f"{location}[{index}]",
            )
            for index, item in enumerate(expression.items)
        ]
    if isinstance(expression, ObjectExpression):
        return {
            field: resolve_input_expression(
                value,
                state=state,
                workflow_input=workflow_input,
                context=context,
                label=label,
                location=f"{location}.{field}",
            )
            for field, value in expression.fields.items()
        }
    raise WorkflowExecutionError(f"unsupported input expression for {label} {location}")


def resolve_step_input_bindings(
    bindings: Sequence[StepInputBinding],
    *,
    state: Mapping[str, Any],
    workflow_input: Mapping[str, Any],
    context: Mapping[str, Any],
    label: str,
) -> dict[str, Any]:
    """Build one node-local payload from simple or composite input bindings."""

    payload: dict[str, Any] = {}
    for binding in bindings:
        location = str(binding.target)
        if isinstance(binding, InputValueBinding):
            value = binding.value
        elif isinstance(binding, InputPathBinding):
            try:
                value = safe_resolve_path(
                    str(binding.path),
                    state=state,
                    workflow_input=workflow_input,
                    context=context,
                )
            except (ValueError, WorkflowExecutionError) as exc:
                raise WorkflowExecutionError(f"{label} {location}: {exc}") from exc
        elif isinstance(binding, InputExpressionBinding):
            value = resolve_input_expression(
                binding.expression,
                state=state,
                workflow_input=workflow_input,
                context=context,
                label=label,
                location=location,
            )
        else:
            raise WorkflowExecutionError(f"unsupported input binding for {label}")
        try:
            set_local_value(payload, binding.target, value)
        except LocalPathError as exc:
            raise WorkflowExecutionError(f"{label} {location}: {exc}") from exc
    return payload
