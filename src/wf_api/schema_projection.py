from __future__ import annotations

from copy import deepcopy
from typing import Any

from jsonschema import Draft202012Validator, SchemaError

JsonObject = dict[str, Any]


def project_property_to_schema_path(
    *,
    target_schema: JsonObject,
    source_schema: JsonObject,
    source_field: str,
    target_parts: tuple[str, ...],
    allow_existing_equivalent: bool = False,
) -> JsonObject:
    """Copy one source property schema into a target JSON Schema object path.

    ``allow_existing_equivalent`` accepts exact schema equality only. It does
    not attempt semantic JSON Schema compatibility analysis.
    """
    if not target_parts:
        raise ValueError("target schema path must not be empty")
    _check_schema("target_schema", target_schema)
    _check_schema("source_schema", source_schema)
    source_properties = source_schema.get("properties")
    if not isinstance(source_properties, dict) or source_field not in source_properties:
        raise ValueError(f"source field {source_field!r} is not declared")
    source_property = source_properties[source_field]
    if not isinstance(source_property, dict):
        raise ValueError(f"source field {source_field!r} is not a JSON Schema object")

    projected = deepcopy(target_schema)
    _ensure_object_schema(projected, "target_schema")
    parent = projected
    for index, part in enumerate(target_parts[:-1]):
        properties = _properties_for_object(
            parent, ".".join(target_parts[:index]) or "target_schema"
        )
        child = properties.get(part)
        if child is None:
            child = {"type": "object", "properties": {}}
            properties[part] = child
        if not isinstance(child, dict):
            raise ValueError(
                f"schema path {'.'.join(target_parts[: index + 1])!r} is not an object"
            )
        _ensure_object_schema(child, ".".join(target_parts[: index + 1]))
        parent = child

    properties = _properties_for_object(
        parent, ".".join(target_parts[:-1]) or "target_schema"
    )
    leaf = target_parts[-1]
    if leaf in properties:
        if allow_existing_equivalent and properties[leaf] == source_property:
            _merge_definition_block(projected, source_schema, "$defs")
            _merge_definition_block(projected, source_schema, "definitions")
            _check_schema("projected target_schema", projected)
            return projected
        raise ValueError(f"schema path {'.'.join(target_parts)!r} already exists")
    properties[leaf] = deepcopy(source_property)

    _merge_definition_block(projected, source_schema, "$defs")
    _merge_definition_block(projected, source_schema, "definitions")
    _check_schema("projected target_schema", projected)
    return projected


def project_output_property_to_state_schema(
    *,
    state_schema: JsonObject,
    output_schema: JsonObject,
    output_field: str,
    state_field: str,
) -> JsonObject:
    """Root state projection convenience wrapper.

    Preserves the original error message wording for backward compatibility.
    """
    try:
        return project_property_to_schema_path(
            target_schema=state_schema,
            source_schema=output_schema,
            source_field=output_field,
            target_parts=(state_field,),
        )
    except ValueError as exc:
        msg = str(exc)
        if msg.startswith("source field ") and "is not declared" in msg:
            raise ValueError(f"output field {output_field!r} is not declared") from exc
        if msg.startswith("source field ") and "not a JSON Schema" in msg:
            raise ValueError(
                f"output field {output_field!r} is not a JSON Schema object"
            ) from exc
        if "schema path 'target_schema'" in msg and "is not an object" in msg:
            raise ValueError("state_schema must be an object schema") from exc
        if msg.startswith("schema path ") and "already exists" in msg:
            raise ValueError(f"state field {state_field!r} already exists") from exc
        if "target_schema is not valid JSON Schema" in msg:
            raise ValueError(
                f"state_schema is not valid JSON Schema: {msg.split(': ', 1)[1]}"
            ) from exc
        if "source_schema is not valid JSON Schema" in msg:
            raise ValueError(
                f"output_schema is not valid JSON Schema: {msg.split(': ', 1)[1]}"
            ) from exc
        raise


def _check_schema(name: str, schema: JsonObject) -> None:
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        raise ValueError(f"{name} is not valid JSON Schema: {exc.message}") from exc


def _ensure_object_schema(schema: JsonObject, label: str) -> None:
    schema_type = schema.get("type")
    if schema_type is not None and schema_type != "object":
        raise ValueError(f"schema path {label!r} is not an object")
    schema.setdefault("type", "object")


def _properties_for_object(schema: JsonObject, label: str) -> JsonObject:
    properties = schema.setdefault("properties", {})
    if not isinstance(properties, dict):
        raise ValueError(f"{label}.properties must be an object")
    return properties


def _merge_definition_block(
    target_schema: JsonObject,
    source_schema: JsonObject,
    key: str,
) -> None:
    source_defs = source_schema.get(key)
    if source_defs is None:
        return
    if not isinstance(source_defs, dict):
        raise ValueError(f"output_schema.{key} must be an object")
    target_defs = target_schema.setdefault(key, {})
    if not isinstance(target_defs, dict):
        raise ValueError(f"state_schema.{key} must be an object")
    for name, definition in source_defs.items():
        if name in target_defs and target_defs[name] != definition:
            raise ValueError(f"conflicting {key}.{name}")
        target_defs[name] = deepcopy(definition)
