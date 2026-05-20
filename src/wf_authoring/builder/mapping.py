from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, TypeAlias

from wf_core import SchemaRef, StateSchema
from wf_core.models.steps import (
    InputBinding,
    InputPathBinding,
    InputValueBinding,
    OutputBinding,
)
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
InputBindingArg: TypeAlias = InputBinding | Mapping[str, object]
OutputBindingArg: TypeAlias = OutputBinding | Mapping[str, object]


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


def _reject_mapping_path_key(value: object, *, field_name: str) -> None:
    """Reject structural dict keys; use canonical binding lists for JSON shapes."""
    if isinstance(value, Mapping):
        raise TypeError(
            f"structural path dicts cannot be map keys in {field_name}; "
            "use canonical input/output binding lists instead"
        )


def normalize_input_mapping(mapping: MapArg | None) -> InputMap:
    """Normalize `in_map`: graph source path -> node-local input path."""
    if mapping is None:
        return {}
    normalized: InputMap = {}
    for source, destination in mapping.items():
        _reject_mapping_path_key(source, field_name="in_map")
        normalized[
            coerce_graph_path(source.path if isinstance(source, GraphPath) else source)
        ] = coerce_local_path(destination)
    return normalized


def normalize_input_values(mapping: Mapping[Any, Any] | None) -> InputValues:
    """Normalize `input_values`: node-local input path -> literal value."""
    if mapping is None:
        return {}
    return {coerce_local_path(target): value for target, value in mapping.items()}


def normalize_input_bindings(
    bindings: Sequence[InputBindingArg] | None,
) -> list[InputBinding]:
    """Validate canonical input binding structs for WorkflowBuilder.use()."""
    if bindings is None:
        return []
    normalized: list[InputBinding] = []
    for binding in bindings:
        if isinstance(binding, InputPathBinding | InputValueBinding):
            normalized.append(binding)
            continue
        if not isinstance(binding, Mapping):
            raise TypeError(f"unsupported input binding {binding!r}")
        if "path" in binding:
            normalized.append(InputPathBinding.model_validate(binding))
        elif "value" in binding:
            normalized.append(InputValueBinding.model_validate(binding))
        else:
            raise TypeError("input binding must contain either 'path' or 'value'")
    return normalized


def normalize_output_mapping(mapping: MapArg | None) -> OutputMap:
    """Normalize `out_map`: node-local output path -> workflow state path."""
    if mapping is None:
        return {}
    normalized: OutputMap = {}
    for source, target in mapping.items():
        _reject_mapping_path_key(source, field_name="out_map")
        normalized[coerce_local_path(source)] = coerce_state_path(
            target.path if isinstance(target, GraphPath) else target,
            allow_legacy_root=True,
        )
    return normalized


def normalize_output_bindings(
    bindings: Sequence[OutputBindingArg] | None,
) -> list[OutputBinding]:
    """Validate canonical output binding structs for WorkflowBuilder.use()."""
    if bindings is None:
        return []
    normalized: list[OutputBinding] = []
    for binding in bindings:
        if isinstance(binding, OutputBinding):
            normalized.append(binding)
            continue
        if not isinstance(binding, Mapping):
            raise TypeError(f"unsupported output binding {binding!r}")
        normalized.append(OutputBinding.model_validate(binding))
    return normalized


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
