from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import Any

from jsonschema import Draft202012Validator, SchemaError

JsonObject = dict[str, Any]


def schema_path_exists(
    schema: Mapping[str, Any],
    parts: Sequence[str],
) -> bool:
    """Return whether an object-property path exists in a JSON Schema document."""
    try:
        _schema_at_path(schema, parts, label="schema")
    except ValueError:
        return False
    return True


def project_schema_path_to_schema_path(
    *,
    target_schema: JsonObject,
    source_schema: JsonObject,
    source_parts: tuple[str, ...],
    target_parts: tuple[str, ...],
    allow_existing_equivalent: bool = False,
) -> JsonObject:
    """Copy one nested source subschema into a target object-property path."""
    if not source_parts:
        raise ValueError("source schema path must not be empty")
    if not target_parts:
        raise ValueError("target schema path must not be empty")
    _check_schema("target_schema", target_schema)
    _check_schema("source_schema", source_schema)
    source_value = _schema_at_path(
        source_schema,
        source_parts,
        label="source schema",
    )

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
        if allow_existing_equivalent and properties[leaf] == source_value:
            _merge_definition_block(projected, source_schema, "$defs")
            _merge_definition_block(projected, source_schema, "definitions")
            _check_schema("projected target_schema", projected)
            return projected
        raise ValueError(f"schema path {'.'.join(target_parts)!r} already exists")
    properties[leaf] = deepcopy(source_value)

    _merge_definition_block(projected, source_schema, "$defs")
    _merge_definition_block(projected, source_schema, "definitions")
    _check_schema("projected target_schema", projected)
    return projected


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
    try:
        return project_schema_path_to_schema_path(
            target_schema=target_schema,
            source_schema=source_schema,
            source_parts=(source_field,),
            target_parts=target_parts,
            allow_existing_equivalent=allow_existing_equivalent,
        )
    except ValueError as exc:
        message = str(exc)
        if message == f"source schema path {source_field!r} is not declared":
            raise ValueError(f"source field {source_field!r} is not declared") from exc
        if message == (
            f"source schema path {source_field!r} is not a JSON Schema object"
        ):
            raise ValueError(
                f"source field {source_field!r} is not a JSON Schema object"
            ) from exc
        raise


def project_output_property_to_state_schema(
    *,
    state_schema: JsonObject,
    output_schema: JsonObject,
    output_field: str,
    state_field: str,
    allow_existing_equivalent: bool = False,
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
            allow_existing_equivalent=allow_existing_equivalent,
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


def _schema_at_path(
    root_schema: Mapping[str, Any],
    parts: Sequence[str],
    *,
    label: str,
) -> Mapping[str, Any]:
    """Select an object-property subschema, following bounded local references."""
    current = root_schema
    traversed: tuple[str, ...] = ()
    for part in parts:
        current = _resolve_local_reference(
            root_schema,
            current,
            label=".".join(traversed) or label,
        )
        schema_type = current.get("type")
        if schema_type is not None and schema_type != "object":
            blocking_path = ".".join(traversed) or label
            raise ValueError(f"{label} path {blocking_path!r} is not an object")
        properties = current.get("properties")
        full_path = ".".join((*traversed, part))
        if not isinstance(properties, Mapping) or part not in properties:
            raise ValueError(f"{label} path {full_path!r} is not declared")
        child = properties[part]
        if not isinstance(child, Mapping):
            raise ValueError(f"{label} path {full_path!r} is not a JSON Schema object")
        current = child
        traversed = (*traversed, part)
    if parts:
        # Validate a selected leaf reference without replacing it. Projection must
        # preserve the reference itself so the copied schema can share merged defs.
        _resolve_local_reference(
            root_schema,
            current,
            label=".".join(traversed),
        )
    return current


def _resolve_local_reference(
    root_schema: Mapping[str, Any],
    candidate: Mapping[str, Any],
    *,
    label: str,
) -> Mapping[str, Any]:
    """Resolve repository-generated local refs without becoming a full resolver."""
    current = candidate
    seen: set[str] = set()
    while "$ref" in current:
        reference = current["$ref"]
        if not isinstance(reference, str):
            raise ValueError(f"schema path {label!r} has a non-string reference")
        if reference in seen:
            raise ValueError(f"cyclic reference {reference!r} at schema path {label!r}")
        seen.add(reference)

        if reference.startswith("#/$defs/"):
            pointer = reference.removeprefix("#/")
        elif reference.startswith("#/definitions/"):
            pointer = reference.removeprefix("#/")
        else:
            raise ValueError(
                f"unsupported reference {reference!r} at schema path {label!r}"
            )

        resolved: Any = root_schema
        for raw_part in pointer.split("/"):
            part = raw_part.replace("~1", "/").replace("~0", "~")
            if not isinstance(resolved, Mapping) or part not in resolved:
                raise ValueError(
                    f"unresolved reference {reference!r} at schema path {label!r}"
                )
            resolved = resolved[part]
        if not isinstance(resolved, Mapping):
            raise ValueError(
                f"reference {reference!r} at schema path {label!r} "
                "does not select a JSON Schema object"
            )
        current = resolved
    return current


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
