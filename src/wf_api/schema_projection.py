from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import Any

from jsonschema import Draft202012Validator, SchemaError, ValidationError

JsonObject = dict[str, Any]
SchemaLocationPart = str | int

_MAX_LOCAL_SCHEMA_REFERENCE_DEPTH = 32


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


def schema_fragment_at_path(
    schema: JsonObject,
    parts: Sequence[str],
    *,
    label: str = "schema",
) -> JsonObject:
    """Return a self-contained selected object-property fragment.

    This compatibility wrapper intentionally keeps the historical object-only
    path semantics: undeclared properties are errors even when JSON Schema's
    default ``additionalProperties`` behavior would allow them.
    """
    _check_schema(label, schema)
    fragment = deepcopy(dict(_schema_at_path(schema, parts, label=label)))
    _merge_definition_block(
        fragment,
        schema,
        "$defs",
        target_label=f"{label} fragment",
        source_label=label,
    )
    _merge_definition_block(
        fragment,
        schema,
        "definitions",
        target_label=f"{label} fragment",
        source_label=label,
    )
    _check_schema(f"{label} fragment", fragment)
    return fragment


def schema_fragment_at_location(
    schema: JsonObject,
    location: Sequence[SchemaLocationPart],
    *,
    label: str = "schema",
) -> JsonObject:
    """Return a self-contained schema fragment at an object/array location.

    The navigator deliberately supports only the structural JSON Schema forms
    needed by workflow input contracts: object properties and schema-valued
    ``additionalProperties``, homogeneous ``items``, tuple ``prefixItems``,
    and bounded local ``$defs``/``definitions`` references. Composition and
    advanced validation keywords remain visible to the caller so the
    expression validator can fail closed instead of guessing their meaning.
    """
    _check_schema(label, schema)
    current: Mapping[str, Any] = schema
    traversed: list[SchemaLocationPart] = []
    for part in location:
        current = _resolve_local_reference(
            schema,
            current,
            label=_format_schema_location(traversed) or label,
        )
        if isinstance(part, int):
            if part < 0:
                raise ValueError(
                    f"{label} array position {part} is negative at "
                    f"{_format_schema_location(traversed) or label!r}"
                )
            child = _array_item_schema(
                current,
                part,
                label=label,
                location=(*traversed, part),
            )
        else:
            child = _object_property_schema(
                current,
                part,
                label=label,
                location=(*traversed, part),
            )
        if not isinstance(child, Mapping):
            raise ValueError(
                f"{label} location {_format_schema_location((*traversed, part))!r} "
                "does not select a JSON Schema object"
            )
        current = child
        traversed.append(part)

    _resolve_local_reference(
        schema,
        current,
        label=_format_schema_location(traversed) or label,
    )
    fragment = deepcopy(dict(current))
    _merge_definition_block(
        fragment,
        schema,
        "$defs",
        target_label=f"{label} fragment",
        source_label=label,
    )
    _merge_definition_block(
        fragment,
        schema,
        "definitions",
        target_label=f"{label} fragment",
        source_label=label,
    )
    _check_schema(f"{label} fragment", fragment)
    return fragment


def schema_location_is_explicit(
    schema: JsonObject,
    location: Sequence[SchemaLocationPart],
    *,
    label: str = "schema",
) -> bool:
    """Return whether a location has a declared or schema-valued path.

    JSON Schema treats ``additionalProperties: true`` as an open-ended,
    unconstrained object.  That is different from a schema-valued
    ``additionalProperties`` entry, which gives authoring a concrete fragment
    to validate against.  Callers use this distinction to preserve deferred
    projection for genuinely unknown source paths.
    """
    _check_schema(label, schema)
    current: Mapping[str, Any] = schema
    traversed: list[SchemaLocationPart] = []
    for part in location:
        current = _resolve_local_reference(
            schema,
            current,
            label=_format_schema_location(traversed) or label,
        )
        if isinstance(part, int):
            if current.get("items") is True and not (
                isinstance(current.get("prefixItems"), list)
                and part < len(current["prefixItems"])
            ):
                return False
            try:
                child = _array_item_schema(
                    current,
                    part,
                    label=label,
                    location=(*traversed, part),
                )
            except ValueError:
                # Predicates remain total for invalid or unconstrained paths.
                return False
        else:
            properties = current.get("properties")
            if isinstance(properties, Mapping) and part in properties:
                child = properties[part]
            else:
                additional = current.get("additionalProperties", True)
                if not isinstance(additional, Mapping):
                    return False
                child = additional
        if not isinstance(child, Mapping):
            return False
        current = child
        traversed.append(part)
    return True


def validate_json_value_at_schema_path(
    *,
    schema: JsonObject,
    parts: Sequence[str],
    value: object,
    label: str,
    schema_label: str = "capability input schema",
) -> None:
    """Validate one JSON-compatible literal against a selected schema path."""
    fragment = schema_fragment_at_path(
        schema,
        parts,
        label=schema_label,
    )
    path = ".".join(parts) or "."
    try:
        Draft202012Validator(fragment).validate(value)
    except ValidationError as exc:
        raise ValueError(
            f"{label} does not satisfy schema at {path!r}: {exc.message}"
        ) from exc


def validate_json_value_at_schema_location(
    *,
    schema: JsonObject,
    location: Sequence[SchemaLocationPart],
    value: object,
    label: str,
    schema_label: str = "capability input schema",
) -> None:
    """Validate one JSON-compatible literal at an object/array schema location."""
    fragment = schema_fragment_at_location(schema, location, label=schema_label)
    path = _format_schema_location(location) or "."
    try:
        Draft202012Validator(fragment).validate(value)
    except ValidationError as exc:
        raise ValueError(
            f"{label} does not satisfy schema at {path!r}: {exc.message}"
        ) from exc


def project_schema_path_to_schema_path(
    *,
    target_schema: JsonObject,
    source_schema: JsonObject,
    source_parts: tuple[str, ...],
    target_parts: tuple[str, ...],
    allow_existing_equivalent: bool = False,
    allow_additional_properties: bool = False,
) -> JsonObject:
    """Copy one nested source subschema into a target object-property path."""
    if not target_parts:
        raise ValueError("target schema path must not be empty")
    _check_schema("target_schema", target_schema)
    _check_schema("source_schema", source_schema)
    # An empty source path means the complete capability payload. This is
    # distinct from an empty target path, which cannot be inserted into a parent.
    source_value = (
        source_schema
        if not source_parts
        else (
            _schema_at_location(source_schema, source_parts, label="source schema")
            if allow_additional_properties
            else _schema_at_path(source_schema, source_parts, label="source schema")
        )
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
        target_label = ".".join(target_parts[: index + 1])
        # Mutate the referenced definition rather than adding sibling schema
        # keywords beside $ref, which path lookup intentionally does not merge.
        resolved_child = _resolve_local_reference(
            projected,
            child,
            label=target_label,
        )
        if not isinstance(resolved_child, dict):
            raise ValueError(f"schema path {target_label!r} is not mutable")
        _ensure_object_schema(resolved_child, target_label)
        parent = resolved_child

    properties = _properties_for_object(
        parent, ".".join(target_parts[:-1]) or "target_schema"
    )
    leaf = target_parts[-1]
    if leaf in properties:
        # Validate an existing target reference against the target document
        # before source definitions are merged. Otherwise an unresolved target
        # could be silently repaired by an equivalent source-side definition.
        _resolve_local_reference(
            projected,
            properties[leaf],
            label=".".join(target_parts),
        )
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


def _schema_at_location(
    root_schema: Mapping[str, Any],
    location: Sequence[SchemaLocationPart],
    *,
    label: str,
) -> Mapping[str, Any]:
    """Select a raw fragment while allowing schema-valued additional properties."""
    current: Mapping[str, Any] = root_schema
    traversed: list[SchemaLocationPart] = []
    for part in location:
        current = _resolve_local_reference(
            root_schema,
            current,
            label=_format_schema_location(traversed) or label,
        )
        if isinstance(part, int):
            child = _array_item_schema(
                current,
                part,
                label=label,
                location=(*traversed, part),
            )
        else:
            properties = current.get("properties")
            if isinstance(properties, Mapping) and part in properties:
                child = properties[part]
            else:
                additional = current.get("additionalProperties", True)
                if not isinstance(additional, Mapping):
                    raise ValueError(
                        f"{label} location "
                        f"{_format_schema_location((*traversed, part))!r} "
                        "is not declared"
                    )
                child = additional
        if not isinstance(child, Mapping):
            raise ValueError(
                f"{label} location "
                f"{_format_schema_location((*traversed, part))!r} "
                "is not a JSON Schema object"
            )
        current = child
        traversed.append(part)
    return current


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
        if len(seen) >= _MAX_LOCAL_SCHEMA_REFERENCE_DEPTH:
            raise ValueError(
                f"local reference depth exceeds {_MAX_LOCAL_SCHEMA_REFERENCE_DEPTH} "
                f"at schema path {label!r}"
            )
        seen.add(reference)

        if reference.startswith("#/$defs/") or reference.startswith("#/definitions/"):
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


def _format_schema_location(location: Sequence[SchemaLocationPart]) -> str:
    """Format mixed object/array schema locations for stable diagnostics."""
    result = ""
    for part in location:
        if isinstance(part, int):
            result += f"[{part}]"
        elif not result:
            result = part
        else:
            result += f".{part}"
    return result


def _object_property_schema(
    schema: Mapping[str, Any],
    part: str,
    *,
    label: str,
    location: Sequence[SchemaLocationPart],
) -> object:
    schema_type = schema.get("type")
    if schema_type is not None and schema_type != "object":
        raise ValueError(
            f"{label} location {_format_schema_location(location[:-1])!r} "
            "is not an object"
        )
    properties = schema.get("properties")
    if isinstance(properties, Mapping) and part in properties:
        return properties[part]
    additional = schema.get("additionalProperties", True)
    if additional is False:
        raise ValueError(
            f"{label} location {_format_schema_location(location)!r} is not declared"
        )
    if additional is True:
        return {}
    if isinstance(additional, Mapping):
        return additional
    raise ValueError(
        f"{label} additionalProperties at "
        f"{_format_schema_location(location[:-1]) or label!r} is invalid"
    )


def _array_item_schema(
    schema: Mapping[str, Any],
    index: int,
    *,
    label: str,
    location: Sequence[SchemaLocationPart],
) -> object:
    if index < 0:
        raise ValueError(
            f"{label} array position {index} is negative at "
            f"{_format_schema_location(location[:-1]) or label!r}"
        )
    schema_type = schema.get("type")
    if schema_type is not None and schema_type != "array":
        raise ValueError(
            f"{label} location {_format_schema_location(location[:-1])!r} "
            "is not an array"
        )
    prefix_items = schema.get("prefixItems")
    if isinstance(prefix_items, list) and index < len(prefix_items):
        return prefix_items[index]
    items = schema.get("items")
    if items is None:
        raise ValueError(
            f"{label} array position {index} is out of range at "
            f"{_format_schema_location(location[:-1]) or label!r}"
        )
    if isinstance(items, bool):
        if items:
            return {}
        raise ValueError(
            f"{label} array position {index} is out of range at "
            f"{_format_schema_location(location[:-1]) or label!r}"
        )
    return items


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
    *,
    target_label: str = "state_schema",
    source_label: str = "output_schema",
) -> None:
    source_defs = source_schema.get(key)
    if source_defs is None:
        return
    if not isinstance(source_defs, dict):
        raise ValueError(f"{source_label}.{key} must be an object")
    target_defs = target_schema.setdefault(key, {})
    if not isinstance(target_defs, dict):
        raise ValueError(f"{target_label}.{key} must be an object")
    for name, definition in source_defs.items():
        if name in target_defs and target_defs[name] != definition:
            raise ValueError(f"conflicting {key}.{name}")
        target_defs[name] = deepcopy(definition)
