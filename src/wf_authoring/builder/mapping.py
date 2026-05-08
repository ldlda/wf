from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeAlias

from wf_core import SchemaRef, StateSchema

from ..dsl import GraphPath
from ..nodes import NodeSpec

MapArg: TypeAlias = Mapping[Any, Any]


def coerce_path(value: object) -> str:
    """Normalize an authoring path object or string into a core path string."""
    if isinstance(value, str):
        return value
    if isinstance(value, GraphPath):
        return value.value
    raise TypeError(f"unsupported graph path value {value!r}")


def normalize_mapping(mapping: MapArg | None) -> dict[str, str]:
    """Normalize authoring map declarations into core string-to-string maps."""
    if mapping is None:
        return {}
    return {
        coerce_path(source): coerce_path(destination)
        for source, destination in mapping.items()
    }


def auto_input_map(
    spec: NodeSpec[Any, Any],
    *,
    input_schema: SchemaRef,
    state_schema: StateSchema,
) -> dict[str, str]:
    """Map node input fields from state first, then workflow input."""
    return {
        _auto_source_path(
            field, input_schema=input_schema, state_schema=state_schema
        ): field
        for field in spec.input_model.model_json_schema().get("properties", {})
    }


def auto_output_map(
    spec: NodeSpec[Any, Any],
    *,
    state_schema: StateSchema,
) -> dict[str, str]:
    """Map node output fields back into matching state fields."""
    return {
        field: f"state.{field}"
        for field in spec.output_model.model_json_schema().get("properties", {})
        if field in state_schema.fields
    }


def _auto_source_path(
    field: str,
    *,
    input_schema: SchemaRef,
    state_schema: StateSchema,
) -> str:
    if field in state_schema.fields:
        return f"state.{field}"
    if field in input_schema.properties:
        return f"input.{field}"
    return f"state.{field}"
