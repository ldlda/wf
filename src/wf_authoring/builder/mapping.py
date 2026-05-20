from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeAlias

from wf_core import SchemaRef, StateSchema
from wf_core.paths import GraphSourcePath, LocalPath, StatePath

from ..dsl import GraphPath
from ..dsl.path_inputs import (
    coerce_graph_path,
    coerce_local_path,
    coerce_state_path,
)
from ..nodes import NodeSpec

MapArg: TypeAlias = Mapping[Any, Any]
InputMap: TypeAlias = dict[GraphSourcePath, LocalPath]
OutputMap: TypeAlias = dict[LocalPath, StatePath]
InputValues: TypeAlias = dict[LocalPath, Any]


def coerce_path(value: object) -> str:
    """Normalize an authoring path object or string into a core path string."""
    if isinstance(value, str):
        return value
    if isinstance(value, GraphPath):
        return value.value
    if isinstance(value, GraphSourcePath | StatePath | LocalPath):
        return str(value)
    raise TypeError(f"unsupported graph path value {value!r}")


def normalize_mapping(mapping: MapArg | None) -> dict[str, str]:
    """Normalize authoring map declarations into core string-to-string maps."""
    if mapping is None:
        return {}
    return {
        coerce_path(source): coerce_path(destination)
        for source, destination in mapping.items()
    }


def normalize_input_mapping(mapping: MapArg | None) -> InputMap:
    """Normalize `in_map`: graph source path -> node-local input path."""
    if mapping is None:
        return {}
    return {
        coerce_graph_path(source.path if isinstance(source, GraphPath) else source): (
            coerce_local_path(destination)
        )
        for source, destination in mapping.items()
    }


def normalize_input_values(mapping: Mapping[Any, Any] | None) -> InputValues:
    """Normalize `input_values`: node-local input path -> literal value."""
    if mapping is None:
        return {}
    return {coerce_local_path(target): value for target, value in mapping.items()}


def normalize_output_mapping(mapping: MapArg | None) -> OutputMap:
    """Normalize `out_map`: node-local output path -> workflow state path."""
    if mapping is None:
        return {}
    return {
        coerce_local_path(source): coerce_state_path(
            target.path if isinstance(target, GraphPath) else target,
            allow_legacy_root=True,
        )
        for source, target in mapping.items()
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
    state_fields = state_schema.field_map()
    return {
        field: f"state.{field}"
        for field in spec.output_model.model_json_schema().get("properties", {})
        if field in state_fields
    }


def _auto_source_path(
    field: str,
    *,
    input_schema: SchemaRef,
    state_schema: StateSchema,
) -> str:
    if field in state_schema.root_fields():
        return f"state.{field}"
    if field in input_schema.properties:
        return f"input.{field}"
    return f"state.{field}"
