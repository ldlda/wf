from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from wf_core.errors import WorkflowExecutionError

Reducer = Callable[[Any, Any], Any]


def replace_reducer(_current_value: Any, incoming_value: Any) -> Any:
    """Replace the current state value with the incoming value."""
    return incoming_value


def append_reducer(current_value: Any, incoming_value: Any) -> Any:
    """Append one value or many values into a list-valued state path."""
    if current_value is None:
        return [incoming_value] if not isinstance(incoming_value, list) else incoming_value
    if not isinstance(current_value, list):
        raise TypeError("cannot append into non-list state value")
    return (
        [*current_value, *incoming_value]
        if isinstance(incoming_value, list)
        else [*current_value, incoming_value]
    )


def merge_object_reducer(current_value: Any, incoming_value: Any) -> Any:
    """Shallow-merge object values at one exact state path."""
    if current_value is None:
        if not isinstance(incoming_value, dict):
            raise TypeError("cannot merge non-object value")
        return dict(incoming_value)
    if not isinstance(current_value, dict) or not isinstance(incoming_value, dict):
        raise TypeError("merge_object requires dict values")
    return current_value | incoming_value


DEFAULT_REDUCERS: Mapping[str, Reducer] = {
    "wf.std.replace": replace_reducer,
    "wf.std.append": append_reducer,
    "wf.std.merge_object": merge_object_reducer,
}


def apply_reducer(
    *,
    reducer_name: str,
    current_value: Any,
    incoming_value: Any,
    destination_path: str,
    reducers: Mapping[str, Reducer] = DEFAULT_REDUCERS,
) -> Any:
    """Apply one named pure reducer to a state write."""
    reducer = reducers.get(reducer_name)
    if reducer is None:
        raise WorkflowExecutionError(f"unknown reducer {reducer_name!r}")
    try:
        return reducer(current_value, incoming_value)
    except TypeError as exc:
        raise WorkflowExecutionError(f"{exc} at {destination_path!r}") from exc
