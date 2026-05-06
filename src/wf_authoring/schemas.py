from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, TypeAdapter

from wf_core import SchemaRef, StateField, StateSchema

SchemaLike = SchemaRef | type[BaseModel] | type[Any] | dict[str, Any]
StateSchemaLike = StateSchema | type[BaseModel] | type[Any] | dict[str, Any]


@dataclass(frozen=True, slots=True)
class StateFieldMetadata:
    """Authoring metadata attached to BaseModel state fields."""

    merge_strategy: Literal["replace", "append", "merge_object"] = "replace"
    trace: bool = True


def state_field(
    *,
    merge_strategy: Literal["replace", "append", "merge_object"] = "replace",
    trace: bool = True,
) -> StateFieldMetadata:
    """Declare workflow state behavior for an Annotated BaseModel field."""
    return StateFieldMetadata(merge_strategy=merge_strategy, trace=trace)


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
        name: StateField(
            type=_state_field_type(property_schema),
            merge_strategy=metadata_by_name.get(
                name, StateFieldMetadata()
            ).merge_strategy,
            trace=metadata_by_name.get(name, StateFieldMetadata()).trace,
            default=_state_field_default(value, name, property_schema),
        )
        for name, property_schema in schema.properties.items()
    }
    return StateSchema(fields=fields)


def _state_metadata_by_name(value: object) -> dict[str, StateFieldMetadata]:
    if not isinstance(value, type) or not issubclass(value, BaseModel):
        return {}

    metadata: dict[str, StateFieldMetadata] = {}
    for name, field_info in value.model_fields.items():
        for item in field_info.metadata:
            if isinstance(item, StateFieldMetadata):
                metadata[name] = item
                break
    return metadata


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
    if isinstance(value, type) and issubclass(value, BaseModel):
        field_info = value.model_fields[field_name]
        if not field_info.is_required():
            return field_info.get_default(call_default_factory=True)

    return None
