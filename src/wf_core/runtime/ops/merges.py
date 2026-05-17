from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from wf_core.errors import WorkflowExecutionError
from wf_core.models.reducers import ReducerRef, ReducerSpec
from wf_core.runtime.ops.schemas import validate_payload_against_schema

Reducer = Callable[[Any, Any, Mapping[str, Any]], Any]


def replace_reducer(
    _current_value: Any, incoming_value: Any, _config: Mapping[str, Any]
) -> Any:
    """Replace the current state value with the incoming value."""
    return incoming_value


def append_reducer(
    current_value: Any, incoming_value: Any, _config: Mapping[str, Any]
) -> Any:
    """Append one value or many values into a list-valued state path."""
    if current_value is None:
        return (
            [incoming_value] if not isinstance(incoming_value, list) else incoming_value
        )
    if not isinstance(current_value, list):
        raise TypeError("cannot append into non-list state value")
    return (
        [*current_value, *incoming_value]
        if isinstance(incoming_value, list)
        else [*current_value, incoming_value]
    )


def merge_object_reducer(
    current_value: Any, incoming_value: Any, _config: Mapping[str, Any]
) -> Any:
    """Shallow-merge object values at one exact state path."""
    if current_value is None:
        if not isinstance(incoming_value, dict):
            raise TypeError("cannot merge non-object value")
        return dict(incoming_value)
    if not isinstance(current_value, dict) or not isinstance(incoming_value, dict):
        raise TypeError("merge_object requires dict values")
    return current_value | incoming_value


def set_union_reducer(
    current_value: Any, incoming_value: Any, _config: Mapping[str, Any]
) -> Any:
    """Merge list values while preserving stable first-seen order."""
    if current_value is None:
        current_items: list[Any] = []
    elif isinstance(current_value, list):
        current_items = current_value
    else:
        raise TypeError("set_union requires list values")

    if not isinstance(incoming_value, list):
        raise TypeError("set_union requires list values")

    merged: list[Any] = []
    for item in [*current_items, *incoming_value]:
        if item not in merged:
            merged.append(item)
    return merged


def max_reducer(
    current_value: Any, incoming_value: Any, _config: Mapping[str, Any]
) -> Any:
    """Keep the larger of the current and incoming values."""
    return (
        incoming_value if current_value is None else max(current_value, incoming_value)
    )


DEFAULT_REDUCERS: Mapping[str, Reducer] = {
    "wf.std.replace": replace_reducer,
    "wf.std.append": append_reducer,
    "wf.std.merge_object": merge_object_reducer,
    "wf.std.set_union": set_union_reducer,
    "wf.std.max": max_reducer,
}

DEFAULT_REDUCER_SPECS: Mapping[str, ReducerSpec] = {
    name: ReducerSpec(name=name) for name in DEFAULT_REDUCERS
}


def apply_reducer(
    *,
    reducer: ReducerRef,
    current_value: Any,
    incoming_value: Any,
    destination_path: str,
    reducers: Mapping[str, Reducer] = DEFAULT_REDUCERS,
    reducer_specs: Mapping[str, ReducerSpec] = DEFAULT_REDUCER_SPECS,
) -> Any:
    """Apply one named pure reducer to a state write."""
    reducer_fn = reducers.get(reducer.name)
    if reducer_fn is None:
        raise WorkflowExecutionError(f"unknown reducer {reducer.name!r}")
    spec = reducer_specs.get(reducer.name)
    if spec is None:
        raise WorkflowExecutionError(f"unknown reducer spec {reducer.name!r}")
    validate_payload_against_schema(
        spec.config_schema,
        reducer.config,
        f"reducer config for {reducer.name!r}",
    )
    try:
        return reducer_fn(current_value, incoming_value, reducer.config)
    except TypeError as exc:
        raise WorkflowExecutionError(f"{exc} at {destination_path!r}") from exc
