from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, cast

from wf_core.errors import WorkflowExecutionError
from wf_core.models.reducers import ReducerRef, ReducerSpec
from wf_core.runtime.ops.schemas import validate_payload_against_schema

PlainReducer = Callable[[Any, Any], Any]
ConfigReducer = Callable[[Any, Any, Mapping[str, Any]], Any]
Reducer = PlainReducer | ConfigReducer


@dataclass(frozen=True, slots=True)
class ReducerDefinition:
    """Runtime reducer implementation paired with its inspectable spec."""

    spec: ReducerSpec
    fn: Reducer
    accepts_config: bool = False

    def apply(
        self,
        *,
        reducer: ReducerRef,
        current_value: Any,
        incoming_value: Any,
        destination_path: str,
    ) -> Any:
        """Validate config, then apply the pure reducer function."""
        validate_payload_against_schema(
            self.spec.config_schema,
            reducer.config,
            f"reducer config for {self.spec.name!r}",
        )
        try:
            if self.accepts_config:
                return cast(ConfigReducer, self.fn)(
                    current_value,
                    incoming_value,
                    reducer.config,
                )
            return cast(PlainReducer, self.fn)(current_value, incoming_value)
        except TypeError as exc:
            raise WorkflowExecutionError(f"{exc} at {destination_path!r}") from exc


def replace_reducer(_current_value: Any, incoming_value: Any) -> Any:
    """Replace the current state value with the incoming value."""
    return incoming_value


def append_reducer(current_value: Any, incoming_value: Any) -> Any:
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


def merge_object_reducer(current_value: Any, incoming_value: Any) -> Any:
    """Shallow-merge object values at one exact state path."""
    if current_value is None:
        if not isinstance(incoming_value, dict):
            raise TypeError("cannot merge non-object value")
        return dict(incoming_value)
    if not isinstance(current_value, dict) or not isinstance(incoming_value, dict):
        raise TypeError("merge_object requires dict values")
    return current_value | incoming_value


def set_union_reducer(current_value: Any, incoming_value: Any) -> Any:
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


def max_reducer(current_value: Any, incoming_value: Any) -> Any:
    """Keep the larger of the current and incoming values."""
    return (
        incoming_value if current_value is None else max(current_value, incoming_value)
    )


DEFAULT_REDUCER_DEFINITIONS: Mapping[str, ReducerDefinition] = {
    "wf.std.replace": ReducerDefinition(
        spec=ReducerSpec(
            name="wf.std.replace",
            description="Replace the current state value with the incoming value.",
        ),
        fn=replace_reducer,
    ),
    "wf.std.append": ReducerDefinition(
        spec=ReducerSpec(
            name="wf.std.append",
            description="Append one value or many values into a list-valued state path.",
        ),
        fn=append_reducer,
    ),
    "wf.std.merge_object": ReducerDefinition(
        spec=ReducerSpec(
            name="wf.std.merge_object",
            description="Shallow-merge object values at one exact state path.",
        ),
        fn=merge_object_reducer,
    ),
    "wf.std.set_union": ReducerDefinition(
        spec=ReducerSpec(
            name="wf.std.set_union",
            description="Merge list values while preserving stable first-seen order.",
        ),
        fn=set_union_reducer,
    ),
    "wf.std.max": ReducerDefinition(
        spec=ReducerSpec(
            name="wf.std.max",
            description="Keep the larger of the current and incoming values.",
        ),
        fn=max_reducer,
    ),
}


def apply_reducer(
    *,
    reducer: ReducerRef,
    current_value: Any,
    incoming_value: Any,
    destination_path: str,
    reducers: Mapping[str, ReducerDefinition] = DEFAULT_REDUCER_DEFINITIONS,
) -> Any:
    """Apply one named pure reducer to a state write."""
    definition = reducers.get(reducer.name)
    if definition is None:
        raise WorkflowExecutionError(f"unknown reducer {reducer.name!r}")
    return definition.apply(
        reducer=reducer,
        current_value=current_value,
        incoming_value=incoming_value,
        destination_path=destination_path,
    )
