from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Literal

from jsonschema import Draft202012Validator, ValidationError

from wf_core.models.input_bindings import (
    ArrayExpression,
    InputExpression,
    LiteralExpression,
    ObjectExpression,
    PathExpression,
)

from .schema_projection import (
    JsonObject,
    SchemaLocationPart,
    _resolve_local_reference,
    project_schema_path_to_schema_path,
    schema_fragment_at_location,
    schema_path_exists,
)

Compatibility = Literal["compatible", "incompatible", "unsupported"]

_COMPOSITION_KEYWORDS = frozenset({"allOf", "anyOf", "oneOf", "if", "then", "else"})
_ANNOTATION_KEYWORDS = frozenset(
    {
        "title",
        "description",
        "default",
        "examples",
        "deprecated",
        "readOnly",
        "writeOnly",
    }
)
_STRUCTURAL_KEYWORDS = frozenset(
    {
        "type",
        "properties",
        "required",
        "additionalProperties",
        "items",
        "prefixItems",
        "minItems",
        "maxItems",
        "const",
        "enum",
        "$ref",
        "$defs",
        "definitions",
    }
)


@dataclass(frozen=True)
class ExpressionProjection:
    """Validated expression plus schemas inferred for missing graph sources."""

    input_schema: JsonObject
    state_schema: JsonObject
    deferred_paths: tuple[str, ...]


def validate_and_project_input_expression(
    expression: InputExpression,
    *,
    target_schema: JsonObject,
    input_schema: JsonObject,
    state_schema: JsonObject,
    target_location: Sequence[SchemaLocationPart] = (),
    label: str = "input expression",
) -> ExpressionProjection:
    """Validate one expression and project schemas for undeclared input/state paths.

    This is intentionally not a general JSON Schema subtype engine. It handles
    finite literals, primitive type widening (integer to number), declared
    object/array members, and const/enum subsets. Unsupported composition or
    constraints fail closed; context paths are the one deliberate exception
    because their schema is only authoritative at runtime.
    """
    target_fragment = schema_fragment_at_location(
        target_schema,
        tuple(target_location),
        label="capability input schema",
    )
    projected_input = deepcopy(input_schema)
    projected_state = deepcopy(state_schema)
    deferred_paths: list[str] = []

    def visit(
        current: InputExpression,
        fragment: JsonObject,
        location: tuple[SchemaLocationPart, ...],
    ) -> None:
        nonlocal projected_input, projected_state
        _ensure_supported_schema(fragment, label=_location_label(label, location))
        if isinstance(current, LiteralExpression):
            try:
                Draft202012Validator(fragment).validate(current.value)
            except ValidationError as exc:
                raise ValueError(
                    f"{_location_label(label, location)} literal does not satisfy "
                    f"the target schema: {exc.message}"
                ) from exc
            return

        if isinstance(current, PathExpression):
            source_path = current.path
            source_text = str(source_path)
            if source_path.root == "context":
                deferred_paths.append(source_text)
                return

            if source_path.root == "input":
                source_document = projected_input
            else:
                source_document = projected_state

            if schema_path_exists(source_document, source_path.parts):
                source_fragment = schema_fragment_at_location(
                    source_document,
                    source_path.parts,
                    label=f"{source_path.root} source schema",
                )
                compatibility = _schema_assignability(
                    source_fragment,
                    fragment,
                    source_label=f"{source_text} source",
                    target_label=_location_label(label, location),
                )
                if compatibility == "incompatible":
                    raise ValueError(
                        f"{_location_label(label, location)} source path "
                        f"{source_text!r} is incompatible with its target schema"
                    )
                if compatibility == "unsupported":
                    raise ValueError(
                        f"{_location_label(label, location)} source path "
                        f"{source_text!r} uses an unsupported schema comparison"
                    )
                return

            projected = _project_missing_source_schema(
                source_document,
                source_parts=source_path.parts,
                target_document=target_schema,
                target_location=location,
            )
            if source_path.root == "input":
                projected_input = projected
            else:
                projected_state = projected
            return

        if isinstance(current, ArrayExpression):
            _validate_array_length(
                current, fragment, label=_location_label(label, location)
            )
            for index, item in enumerate(current.items):
                child = schema_fragment_at_location(
                    fragment,
                    (index,),
                    label=_location_label(label, location),
                )
                visit(item, child, (*location, index))
            return

        if isinstance(current, ObjectExpression):
            resolved = _resolved_schema(
                fragment, label=_location_label(label, location)
            )
            properties = resolved.get("properties")
            declared = properties if isinstance(properties, Mapping) else {}
            required = resolved.get("required", [])
            if isinstance(required, list):
                missing = [name for name in required if name not in current.fields]
                if missing:
                    raise ValueError(
                        f"{_location_label(label, location)} is missing required "
                        f"fields {missing!r}"
                    )
            additional = resolved.get("additionalProperties", True)
            for name, item in current.fields.items():
                if isinstance(declared, Mapping) and name in declared:
                    child = schema_fragment_at_location(
                        fragment,
                        (name,),
                        label=_location_label(label, location),
                    )
                elif additional is False:
                    raise ValueError(
                        f"{_location_label(label, location)} field {name!r} "
                        "is not allowed by additionalProperties"
                    )
                else:
                    child = schema_fragment_at_location(
                        fragment,
                        (name,),
                        label=_location_label(label, location),
                    )
                visit(item, child, (*location, name))
            return

        raise TypeError(f"unsupported input expression {current!r}")

    visit(expression, target_fragment, tuple(target_location))
    return ExpressionProjection(
        input_schema=projected_input,
        state_schema=projected_state,
        deferred_paths=tuple(deferred_paths),
    )


def _validate_array_length(
    expression: ArrayExpression,
    schema: Mapping[str, Any],
    *,
    label: str,
) -> None:
    resolved = _resolved_schema(schema, label=label)
    schema_type = resolved.get("type")
    if schema_type is not None and schema_type != "array":
        raise ValueError(f"{label} array expression is incompatible with target schema")
    minimum = resolved.get("minItems")
    maximum = resolved.get("maxItems")
    if isinstance(minimum, int) and len(expression.items) < minimum:
        raise ValueError(f"{label} requires at least {minimum} array items")
    if isinstance(maximum, int) and len(expression.items) > maximum:
        raise ValueError(f"{label} allows at most {maximum} array items")


def _project_missing_source_schema(
    source_schema: JsonObject,
    *,
    source_parts: tuple[str, ...],
    target_document: JsonObject,
    target_location: tuple[SchemaLocationPart, ...],
) -> JsonObject:
    """Copy one target-position schema into an undeclared input/state path."""
    target_fragment = schema_fragment_at_location(
        target_document,
        target_location,
        label="capability input schema",
    )
    source_holder: JsonObject = {
        "type": "object",
        "properties": {"__wf_expression_value__": target_fragment},
    }
    for key in ("$defs", "definitions"):
        if key in target_document:
            source_holder[key] = deepcopy(target_document[key])
    return project_schema_path_to_schema_path(
        target_schema=source_schema,
        source_schema=source_holder,
        source_parts=("__wf_expression_value__",),
        target_parts=source_parts,
        allow_existing_equivalent=True,
    )


def _schema_assignability(
    source: Mapping[str, Any],
    target: Mapping[str, Any],
    *,
    source_label: str,
    target_label: str,
) -> Compatibility:
    try:
        source_normalized = _canonical_schema(source, label=source_label)
        target_normalized = _canonical_schema(target, label=target_label)
    except ValueError:
        return "unsupported"
    if source_normalized == target_normalized:
        return "compatible"

    source_types = _schema_types(source_normalized)
    target_types = _schema_types(target_normalized)
    if source_types is None or target_types is None:
        if source_types is None and target_types is not None:
            # An unconstrained source is not proven to satisfy a typed target.
            # Enum/const sources are handled separately because their finite
            # values can still be checked against the target constraint.
            if "const" not in source_normalized and "enum" not in source_normalized:
                return "unsupported"
        return _enum_assignability(source_normalized, target_normalized)
    if not _types_assignable(source_types, target_types):
        return "incompatible"

    if source_types & {"object"} or target_types & {"object"}:
        return _object_assignability(
            source_normalized, target_normalized, source_label, target_label
        )
    if source_types & {"array"} or target_types & {"array"}:
        return _array_assignability(
            source_normalized, target_normalized, source_label, target_label
        )

    constraint_keys = (set(source_normalized) | set(target_normalized)) - {
        "type",
        "const",
        "enum",
    }
    if constraint_keys:
        return "unsupported"
    return _enum_assignability(source_normalized, target_normalized)


def _object_assignability(
    source: Mapping[str, Any],
    target: Mapping[str, Any],
    source_label: str,
    target_label: str,
) -> Compatibility:
    source_properties = source.get("properties", {})
    target_properties = target.get("properties", {})
    if not isinstance(source_properties, Mapping) or not isinstance(
        target_properties, Mapping
    ):
        return "unsupported"
    source_required = set(source.get("required", []))
    target_required = set(target.get("required", []))
    if not target_required.issubset(source_required):
        return "incompatible"
    for name, source_child in source_properties.items():
        if name in target_properties:
            if not isinstance(source_child, Mapping) or not isinstance(
                target_properties[name], Mapping
            ):
                return "unsupported"
            status = _schema_assignability(
                source_child,
                target_properties[name],
                source_label=f"{source_label}.{name}",
                target_label=f"{target_label}.{name}",
            )
            if status != "compatible":
                return status
        elif target.get("additionalProperties") is False:
            return "incompatible"
    source_additional = source.get("additionalProperties", True)
    target_additional = target.get("additionalProperties", True)
    if target_additional is False and source_additional is not False:
        return "incompatible"
    if isinstance(source_additional, Mapping) and isinstance(
        target_additional, Mapping
    ):
        return _schema_assignability(
            source_additional,
            target_additional,
            source_label=f"{source_label}.additionalProperties",
            target_label=f"{target_label}.additionalProperties",
        )
    if isinstance(target_additional, Mapping) and source_additional is True:
        return "unsupported"
    return "compatible"


def _array_assignability(
    source: Mapping[str, Any],
    target: Mapping[str, Any],
    source_label: str,
    target_label: str,
) -> Compatibility:
    source_prefix = source.get("prefixItems")
    target_prefix = target.get("prefixItems")
    if source_prefix is not None or target_prefix is not None:
        if not isinstance(source_prefix, list) or not isinstance(target_prefix, list):
            return "unsupported"
        if len(source_prefix) != len(target_prefix):
            return "unsupported"
        for index, (source_item, target_item) in enumerate(
            zip(source_prefix, target_prefix, strict=True)
        ):
            if not isinstance(source_item, Mapping) or not isinstance(
                target_item, Mapping
            ):
                return "unsupported"
            status = _schema_assignability(
                source_item,
                target_item,
                source_label=f"{source_label}.prefixItems[{index}]",
                target_label=f"{target_label}.prefixItems[{index}]",
            )
            if status != "compatible":
                return status

    source_items = source.get("items")
    target_items = target.get("items")
    if isinstance(source_items, Mapping) and isinstance(target_items, Mapping):
        return _schema_assignability(
            source_items,
            target_items,
            source_label=f"{source_label}.items",
            target_label=f"{target_label}.items",
        )
    if source_items == target_items:
        return "compatible"
    if target_items is None or source_items is None:
        return "unsupported"
    return "incompatible"


def _enum_assignability(
    source: Mapping[str, Any],
    target: Mapping[str, Any],
) -> Compatibility:
    if "const" in target:
        if "const" in source:
            return (
                "compatible" if source["const"] == target["const"] else "incompatible"
            )
        if "enum" in source:
            values = source["enum"]
            return (
                "compatible"
                if isinstance(values, list) and values == [target["const"]]
                else "incompatible"
            )
        return "unsupported"
    if "enum" in target:
        accepted = target["enum"]
        if not isinstance(accepted, list):
            return "unsupported"
        if "const" in source:
            return "compatible" if source["const"] in accepted else "incompatible"
        if "enum" in source and isinstance(source["enum"], list):
            return (
                "compatible"
                if set(source["enum"]).issubset(accepted)
                else "incompatible"
            )
    return "compatible"


def _types_assignable(source: set[str], target: set[str]) -> bool:
    normalized_source = {"number" if item == "integer" else item for item in source}
    return normalized_source.issubset(target)


def _schema_types(schema: Mapping[str, Any]) -> set[str] | None:
    value = schema.get("type")
    if isinstance(value, str):
        return {value}
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return set(value)
    return None


def _ensure_supported_schema(schema: Mapping[str, Any], *, label: str) -> None:
    _canonical_schema(schema, label=label)


def _resolved_schema(
    schema: Mapping[str, Any],
    *,
    label: str,
    root_schema: Mapping[str, Any] | None = None,
) -> Mapping[str, Any]:
    resolved = _resolve_local_reference(
        root_schema if root_schema is not None else schema,
        schema,
        label=label,
    )
    if any(keyword in resolved for keyword in _COMPOSITION_KEYWORDS):
        raise ValueError(f"unsupported schema composition at {label}")
    return resolved


def _canonical_schema(
    schema: Mapping[str, Any],
    *,
    label: str,
    root_schema: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    canonical_root = root_schema if root_schema is not None else schema
    resolved = _resolved_schema(schema, label=label, root_schema=canonical_root)
    if any(keyword in resolved for keyword in _COMPOSITION_KEYWORDS):
        raise ValueError(f"unsupported schema composition at {label}")
    unknown = set(resolved) - _STRUCTURAL_KEYWORDS - _ANNOTATION_KEYWORDS
    if unknown:
        raise ValueError(
            f"unsupported schema keyword(s) at {label}: {sorted(unknown)!r}"
        )
    canonical: dict[str, Any] = {}
    for key, value in resolved.items():
        if key in _ANNOTATION_KEYWORDS or key in {"$defs", "definitions"}:
            continue
        if key == "properties" and isinstance(value, Mapping):
            canonical[key] = {
                name: _canonical_schema(
                    child,
                    label=f"{label}.{name}",
                    root_schema=canonical_root,
                )
                for name, child in value.items()
                if isinstance(name, str) and isinstance(child, Mapping)
            }
        elif key in {"items", "additionalProperties"} and isinstance(value, Mapping):
            canonical[key] = _canonical_schema(
                value,
                label=f"{label}.{key}",
                root_schema=canonical_root,
            )
        elif key == "prefixItems" and isinstance(value, list):
            canonical[key] = [
                _canonical_schema(
                    child,
                    label=f"{label}.prefixItems[{index}]",
                    root_schema=canonical_root,
                )
                for index, child in enumerate(value)
                if isinstance(child, Mapping)
            ]
        elif key == "required" and isinstance(value, list):
            canonical[key] = sorted(value)
        else:
            canonical[key] = deepcopy(value)
    return canonical


def _location_label(label: str, location: Sequence[SchemaLocationPart]) -> str:
    result = label
    for part in location:
        if isinstance(part, int):
            result += f"[{part}]"
        else:
            result += f".{part}"
    return result
