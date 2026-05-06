from __future__ import annotations

from typing import Any

from pydantic import BaseModel, TypeAdapter

from wf_core import SchemaRef, StateField, StateSchema

SchemaLike = SchemaRef | type[BaseModel] | type[Any] | dict[str, Any]
StateSchemaLike = StateSchema | type[BaseModel] | type[Any] | dict[str, Any]


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
    fields = {
        name: StateField(type=_state_field_type(property_schema))
        for name, property_schema in schema.properties.items()
    }
    return StateSchema(fields=fields)


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
