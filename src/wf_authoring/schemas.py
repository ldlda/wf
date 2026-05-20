from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Iterator

from pydantic import BaseModel, TypeAdapter

from wf_core import ReducerRef, SchemaRef, StateField, StateSchema

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
    if isinstance(value, dict) and "fields" in value:
        return StateSchema.model_validate(value)

    schema = schema_ref_from(value)
    metadata_by_name = _state_metadata_by_name(value)
    fields = {
        path: StateField(
            type=_state_field_type(property_schema),
            reducer=metadata_by_name.get(path, StateFieldMetadata()).reducer,
            trace=metadata_by_name.get(path, StateFieldMetadata()).trace,
            default=_state_field_default(value, path, property_schema),
        )
        for path, property_schema in _flatten_state_properties(schema)
    }
    return StateSchema.from_field_map(fields)


def _reducer_ref_from(value: ReducerLike) -> ReducerRef:
    if isinstance(value, ReducerRef):
        return value
    if isinstance(value, str):
        return ReducerRef(name=value)
    return ReducerRef.model_validate(value)


def _state_metadata_by_name(value: object) -> dict[str, StateFieldMetadata]:
    if not isinstance(value, type) or not issubclass(value, BaseModel):
        return {}

    return dict(_iter_model_metadata(value))


def _iter_model_metadata(
    model_type: type[BaseModel],
    *,
    prefix: str = "",
) -> Iterator[tuple[str, StateFieldMetadata]]:
    for name, field_info in model_type.model_fields.items():
        path = f"{prefix}.{name}" if prefix else name
        for item in field_info.metadata:
            if isinstance(item, StateFieldMetadata):
                yield path, item
                break
        annotation = field_info.annotation
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            yield from _iter_model_metadata(annotation, prefix=path)


def _flatten_state_properties(
    schema: SchemaRef,
) -> Iterator[tuple[str, dict[str, Any]]]:
    raw_schema = schema.model_dump(exclude_none=True)
    yield from _iter_state_properties(raw_schema.get("properties", {}), raw_schema)


def _iter_state_properties(
    properties: object,
    root_schema: dict[str, Any],
    *,
    prefix: str = "",
) -> Iterator[tuple[str, dict[str, Any]]]:
    if not isinstance(properties, dict):
        return

    for name, property_schema in properties.items():
        if not isinstance(property_schema, dict):
            continue
        path = f"{prefix}.{name}" if prefix else name
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


def _state_field_type(property_schema: object) -> str:
    if not isinstance(property_schema, dict):
        return "object"
    field_type = property_schema.get("type")
    if isinstance(field_type, str):
        return field_type
    if "$ref" in property_schema or "properties" in property_schema:
        return "object"
    if "items" in property_schema:
        return "array"
    return "object"


def _state_field_default(
    value: object,
    field_name: str,
    property_schema: object,
) -> object:
    if (
        "." not in field_name
        and isinstance(value, type)
        and issubclass(value, BaseModel)
    ):
        field_info = value.model_fields[field_name]
        if not field_info.is_required():
            return field_info.get_default(call_default_factory=True)

    return None
