from __future__ import annotations

from types import NoneType, UnionType
from typing import Any, Union, cast, get_args, get_origin

from pydantic import BaseModel, ConfigDict, Field, create_model

_JSON_TYPE_MAP: dict[str, object] = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
    "object": dict[str, Any],
}


def _python_type_from_schema(schema: object) -> object:
    """Map the supported MCP JSON Schema subset into a Pydantic annotation.

    This is intentionally not a full JSON Schema compiler. Unsupported shapes
    become `Any` so discovery remains tolerant while the original schema
    contract stays available on generated NodeSpecs.
    """
    if not isinstance(schema, dict):
        return Any

    if "enum" in schema:
        return Any

    schema_type = schema.get("type")
    if isinstance(schema_type, list):
        non_null_types = [item for item in schema_type if item != "null"]
        if len(non_null_types) == 1:
            return _optional_type(
                _python_type_from_schema({**schema, "type": non_null_types[0]})
            )
        return Any

    if schema_type == "array":
        item_type = _python_type_from_schema(schema.get("items", {}))
        return list[item_type]

    if not isinstance(schema_type, str):
        return Any
    return _JSON_TYPE_MAP.get(schema_type, Any)


def _optional_type(annotation: object) -> object:
    """Return an optional version of a supported runtime annotation."""
    if annotation is Any:
        return Any
    origin = get_origin(annotation)
    if origin in {Union, UnionType} and NoneType in get_args(annotation):
        return annotation
    return cast(Any, annotation) | None


def _field_default(
    field_name: str,
    property_schema: object,
    required: set[str],
) -> object:
    """Return the Pydantic default for one MCP tool input property."""
    if isinstance(property_schema, dict) and "default" in property_schema:
        return property_schema["default"]
    return ... if field_name in required else None


def model_from_schema(name: str, schema: dict[str, Any]) -> type[BaseModel]:
    """Create a loose Pydantic adapter model for an MCP JSON Schema object.

    Input should be object-like JSON Schema with `properties` and optional
    `required`. The returned model is the Python-call boundary for generated
    NodeSpecs; the original JSON Schema remains the public contract.
    """
    properties = cast(dict[str, Any], schema.get("properties", {}))
    required = set(cast(list[str], schema.get("required", [])))
    field_defs: dict[str, tuple[object, object]] = {}

    for field_name, property_schema in properties.items():
        annotation = _python_type_from_schema(property_schema)
        default = _field_default(field_name, property_schema, required)
        description = (
            property_schema.get("description")
            if isinstance(property_schema, dict)
            else None
        )
        field_defs[field_name] = (
            annotation,
            Field(default=default, description=description),
        )

    raw_field_defs = cast(dict[str, Any], field_defs)
    model = create_model(
        name,
        __config__=ConfigDict(extra="allow"),
        **raw_field_defs,
    )
    return cast(type[BaseModel], model)


__all__ = ["model_from_schema"]
