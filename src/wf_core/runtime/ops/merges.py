from __future__ import annotations

from typing import Any

from wf_core.errors import WorkflowExecutionError


def apply_builtin_merge(
    *,
    strategy: str,
    current_value: Any,
    incoming_value: Any,
    destination_path: str,
) -> Any:
    """Apply one built-in merge rule.

    This is the future seam for source-owned reducer libraries. The current core
    still supports only built-in rules and keeps them pure over current and
    incoming values.
    """
    if strategy == "replace":
        return incoming_value

    if strategy == "append":
        if current_value is None:
            return (
                [incoming_value]
                if not isinstance(incoming_value, list)
                else incoming_value
            )
        if not isinstance(current_value, list):
            raise WorkflowExecutionError(
                f"cannot append into non-list state path {destination_path!r}"
            )
        return (
            [
                *current_value,
                *incoming_value,
            ]
            if isinstance(incoming_value, list)
            else [*current_value, incoming_value]
        )

    if strategy == "merge_object":
        if current_value is None:
            if not isinstance(incoming_value, dict):
                raise WorkflowExecutionError(
                    f"cannot merge non-object value into {destination_path!r}"
                )
            return dict(incoming_value)
        if not isinstance(current_value, dict) or not isinstance(incoming_value, dict):
            raise WorkflowExecutionError(
                f"merge_object requires dict values at {destination_path!r}"
            )
        return current_value | incoming_value

    raise WorkflowExecutionError(f"unknown merge strategy {strategy!r}")
