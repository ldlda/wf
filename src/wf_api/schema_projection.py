from __future__ import annotations

from copy import deepcopy
from typing import Any

from jsonschema import Draft202012Validator, SchemaError

JsonObject = dict[str, Any]


def project_output_property_to_state_schema(
    *,
    state_schema: JsonObject,
    output_schema: JsonObject,
    output_field: str,
    state_field: str,
) -> JsonObject:
    """Project one capability output property schema into workflow state schema.

    Capability output schemas may use local references such as
    ``{"$ref": "#/$defs/Snapshot"}``. Copying only the property schema would
    create dangling references, so this helper also merges local definition
    blocks and rejects conflicting definition names.
    """
    _check_schema("state_schema", state_schema)
    _check_schema("output_schema", output_schema)
    output_properties = output_schema.get("properties")
    if not isinstance(output_properties, dict) or output_field not in output_properties:
        raise ValueError(f"output field {output_field!r} is not declared")
    output_property = output_properties[output_field]
    if not isinstance(output_property, dict):
        raise ValueError(f"output field {output_field!r} is not a JSON Schema object")

    projected = deepcopy(state_schema)
    projected.setdefault("type", "object")
    properties = projected.setdefault("properties", {})
    if not isinstance(properties, dict):
        raise ValueError("state_schema.properties must be an object")
    properties[state_field] = deepcopy(output_property)

    _merge_definition_block(projected, output_schema, "$defs")
    _merge_definition_block(projected, output_schema, "definitions")
    _check_schema("projected state_schema", projected)
    return projected


def _check_schema(name: str, schema: JsonObject) -> None:
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        raise ValueError(f"{name} is not valid JSON Schema: {exc.message}") from exc


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
