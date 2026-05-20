from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Iterator

from pydantic import BaseModel, TypeAdapter

from wf_core import ReducerRef, SchemaRef, StateSchema

SchemaLike = SchemaRef | type[BaseModel] | type[Any] | dict[str, Any]
StateSchemaLike = StateSchema | type[BaseModel] | type[Any] | dict[str, Any]
ReducerLike = str | ReducerRef | Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class StateFieldMetadata:
    """Authoring metadata attached to BaseModel state fields."""

    reducer: ReducerRef = field(
        default_factory=lambda: ReducerRef(name="wf.std.replace")
    )
    trace: bool = True


def state_field(
    *,
    reducer: ReducerLike = "wf.std.replace",
    trace: bool = True,
) -> StateFieldMetadata:
    """Declare workflow state behavior for an Annotated BaseModel field."""
    return StateFieldMetadata(reducer=_reducer_ref_from(reducer), trace=trace)


def schema_ref_from(value: SchemaLike) -> SchemaRef:
    """Coerce an authoring schema declaration into a core schema reference."""
    if isinstance(value, SchemaRef):
        return value
    if isinstance(value, dict):
        return SchemaRef.model_validate(value)
    if isinstance(value, type) and issubclass(value, BaseModel):
        return SchemaRef.model_validate(value.model_json_schema())
    return SchemaRef.model_validate(TypeAdapter(value).json_schema())


def state_schema_from(value: StateSchemaLike) -> StateSchema:
    """Coerce an authoring state declaration into a core state schema."""
    if isinstance(value, StateSchema):
        return value
    if isinstance(value, dict):
        return StateSchema.model_validate(value)

    schema = schema_ref_from(value)
    schema_payload = schema.model_dump(mode="json", exclude_none=True)
    metadata_by_path = _state_metadata_by_path(value)
    for path, property_schema in _flatten_state_properties(schema):
        metadata = metadata_by_path.get(path, StateFieldMetadata())
        extension_schema = _lookup_mutable_property_schema(schema_payload, path)
        if extension_schema is None:
            extension_schema = property_schema
        extension_schema["reducer"] = _dump_reducer(metadata.reducer)
        if not metadata.trace:
            extension_schema["trace"] = False
        default = _state_field_default(value, path, property_schema)
        if default is not None:
            extension_schema["default"] = default
    return StateSchema.model_validate(schema_payload)


def _reducer_ref_from(value: ReducerLike) -> ReducerRef:
    if isinstance(value, ReducerRef):
        return value
    if isinstance(value, str):
        return ReducerRef(name=value)
    return ReducerRef.model_validate(value)


def _state_metadata_by_path(value: object) -> dict[tuple[str, ...], StateFieldMetadata]:
    if not isinstance(value, type) or not issubclass(value, BaseModel):
        return {}

    return dict(_iter_model_metadata(value))


def _iter_model_metadata(
    model_type: type[BaseModel],
    *,
    prefix: tuple[str, ...] = (),
) -> Iterator[tuple[tuple[str, ...], StateFieldMetadata]]:
    for name, field_info in model_type.model_fields.items():
        field_name = field_info.alias or name
        path = (*prefix, field_name)
        for item in field_info.metadata:
            if isinstance(item, StateFieldMetadata):
                yield path, item
                break
        annotation = field_info.annotation
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            yield from _iter_model_metadata(annotation, prefix=path)


def _flatten_state_properties(
    schema: SchemaRef,
) -> Iterator[tuple[tuple[str, ...], dict[str, Any]]]:
    raw_schema = schema.model_dump(exclude_none=True)
    yield from _iter_state_properties(
        raw_schema.get("properties", {}),
        raw_schema,
        prefix=(),
    )


def _iter_state_properties(
    properties: object,
    root_schema: dict[str, Any],
    *,
    prefix: tuple[str, ...],
) -> Iterator[tuple[tuple[str, ...], dict[str, Any]]]:
    if not isinstance(properties, dict):
        return

    for name, property_schema in properties.items():
        if not isinstance(property_schema, dict):
            continue
        path = (*prefix, name)
        resolved_schema = _resolve_property_schema(property_schema, root_schema)
        yield path, resolved_schema
        yield from _iter_state_properties(
            resolved_schema.get("properties", {}),
            root_schema,
            prefix=path,
        )


def _resolve_property_schema(
    property_schema: dict[str, Any],
    root_schema: dict[str, Any],
) -> dict[str, Any]:
    ref = property_schema.get("$ref")
    if not isinstance(ref, str) or not ref.startswith("#/$defs/"):
        return property_schema
    definition_name = ref.removeprefix("#/$defs/")
    definitions = root_schema.get("$defs", {})
    if not isinstance(definitions, dict):
        return property_schema
    resolved = definitions.get(definition_name)
    return resolved if isinstance(resolved, dict) else property_schema


def _dump_reducer(reducer: ReducerRef) -> str | dict[str, Any]:
    if not reducer.config:
        return reducer.name
    return reducer.model_dump(mode="json")


def _lookup_mutable_property_schema(
    schema: dict[str, Any],
    path: tuple[str, ...],
) -> dict[str, Any] | None:
    """Find a property schema, following local Pydantic ``$defs`` references."""
    current: dict[str, Any] = schema
    for part in path:
        properties = current.get("properties")
        if not isinstance(properties, dict):
            return None
        raw_child = properties.get(part)
        if not isinstance(raw_child, dict):
            return None
        current = _resolve_mutable_property_schema(raw_child, schema)
    return current


def _resolve_mutable_property_schema(
    property_schema: dict[str, Any],
    root_schema: dict[str, Any],
) -> dict[str, Any]:
    ref = property_schema.get("$ref")
    if not isinstance(ref, str) or not ref.startswith("#/$defs/"):
        return property_schema
    definitions = root_schema.get("$defs", {})
    if not isinstance(definitions, dict):
        return property_schema
    resolved = definitions.get(ref.removeprefix("#/$defs/"))
    return resolved if isinstance(resolved, dict) else property_schema


def _state_field_default(
    value: object,
    field_path: tuple[str, ...],
    property_schema: object,
) -> object:
    if (
        len(field_path) == 1
        and isinstance(value, type)
        and issubclass(value, BaseModel)
    ):
        field_info = _model_field_by_schema_name(value, field_path[0])
        if field_info is None:
            return None
        if not field_info.is_required():
            return field_info.get_default(call_default_factory=True)

    return None


def _model_field_by_schema_name(model_type: type[BaseModel], name: str) -> Any | None:
    """Return a model field by Python name or serialized alias."""
    field_info = model_type.model_fields.get(name)
    if field_info is not None:
        return field_info
    for candidate in model_type.model_fields.values():
        if candidate.alias == name:
            return candidate
    return None
