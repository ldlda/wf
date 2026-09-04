from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .errors import WorkflowExecutionError
from .models.conditions import (
    BinaryCondition,
    Condition,
    ExistsCondition,
    LiteralOperand,
    NotCondition,
    PathOperand,
    VariadicCondition,
)
from .paths import PathResolutionError, path_exists, resolve_graph_path


def eval_condition(
    condition: Condition,
    state: Mapping[str, Any],
    workflow_input: Mapping[str, Any],
    context_data: str | None,
    *,
    context: Mapping[str, Any] | None = None,
) -> bool:
    """Evaluate a condition against state, input, and context.

    ``context`` is the frame's structured context graph (see
    ``frame_context_view``); when omitted, evaluation falls back to the
    legacy ``{"prior_outcome": context_data}`` stub so direct unit callers
    keep working. The graph always carries ``prior_outcome``, so passing it
    preserves legacy behavior while also resolving structured paths such as
    ``context.foreach.<id>.item``.
    """
    resolved = context if context is not None else {"prior_outcome": context_data}
    if isinstance(condition, ExistsCondition):
        return path_exists(
            condition.path,
            state=state,
            workflow_input=workflow_input,
            context=resolved,
        )
    if isinstance(condition, NotCondition):
        return not eval_condition(
            condition.arg, state, workflow_input, context_data, context=resolved
        )
    if isinstance(condition, VariadicCondition):
        values = [
            eval_condition(arg, state, workflow_input, context_data, context=resolved)
            for arg in condition.args
        ]
        return all(values) if condition.op == "and" else any(values)
    if isinstance(condition, BinaryCondition):
        left = resolve_operand(
            condition.left, state, workflow_input, context_data, context=resolved
        )
        right = resolve_operand(
            condition.right, state, workflow_input, context_data, context=resolved
        )
        if condition.op == "eq":
            return left == right
        if condition.op == "ne":
            return left != right
        if condition.op == "gt":
            return left > right
        if condition.op == "ge":
            return left >= right
        if condition.op == "lt":
            return left < right
        if condition.op == "le":
            return left <= right
    raise WorkflowExecutionError(f"unsupported condition operator {condition.op!r}")


def resolve_operand(
    operand: PathOperand | LiteralOperand,
    state: Mapping[str, Any],
    workflow_input: Mapping[str, Any],
    context_data: str | None,
    *,
    context: Mapping[str, Any] | None = None,
) -> Any:
    if isinstance(operand, LiteralOperand):
        return operand.value
    return safe_resolve_path(
        str(operand.path),
        state=state,
        workflow_input=workflow_input,
        context=context if context is not None else {"prior_outcome": context_data},
    )


def safe_resolve_path(
    path: str,
    *,
    state: Mapping[str, Any],
    workflow_input: Mapping[str, Any],
    context: Mapping[str, Any],
) -> Any:
    try:
        return resolve_graph_path(
            path,
            state=state,
            workflow_input=workflow_input,
            context=context,
        )
    except PathResolutionError as exc:
        raise WorkflowExecutionError(str(exc)) from exc
