from __future__ import annotations

import math
from collections.abc import Iterator, Mapping
from typing import cast

from .model import (
    ContractManifest,
    JsonSchema,
    JsonValue,
    ManifestError,
    ManifestOperation,
    ManifestParameter,
)

type ComponentIndex = dict[str, set[str]]

_SCHEMA_MAP_KEYWORDS = {
    "$defs",
    "definitions",
    "dependentSchemas",
    "patternProperties",
    "properties",
}
_SINGLE_SCHEMA_KEYWORDS = {
    "additionalProperties",
    "contains",
    "contentSchema",
    "else",
    "if",
    "items",
    "not",
    "propertyNames",
    "then",
    "unevaluatedItems",
    "unevaluatedProperties",
}
_SCHEMA_ARRAY_KEYWORDS = {"allOf", "anyOf", "oneOf", "prefixItems"}


def _mapping(value: object, path: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ManifestError(path, "expected an object")
    return value


def _string_key_mapping(value: object, path: str) -> Mapping[str, object]:
    mapping = _mapping(value, path)
    if any(not isinstance(key, str) for key in mapping):
        raise ManifestError(path, "expected string object keys")
    return cast("Mapping[str, object]", mapping)


def _list(value: object, path: str) -> list[object]:
    if not isinstance(value, list):
        raise ManifestError(path, "expected an array")
    return value


def _string(value: object, path: str) -> str:
    if not isinstance(value, str) or not value:
        raise ManifestError(path, "expected a non-empty string")
    return value


def _boolean(value: object, path: str) -> bool:
    if not isinstance(value, bool):
        raise ManifestError(path, "expected a boolean")
    return value


def _json_value(value: object, path: str) -> JsonValue:
    if value is None or isinstance(value, bool | int | str):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ManifestError(path, "expected a finite JSON number")
        return value
    if isinstance(value, list):
        return [
            _json_value(item, f"{path}[{index}]") for index, item in enumerate(value)
        ]
    if isinstance(value, Mapping):
        normalized: dict[str, JsonValue] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ManifestError(path, "expected string object keys")
            normalized[key] = _json_value(item, f"{path}.{key}")
        return normalized
    raise ManifestError(path, "expected a JSON value")


def _schema_child(value: object, path: str) -> JsonValue:
    if isinstance(value, Mapping):
        return _schema(value, path)
    if isinstance(value, list):
        return [
            _schema_child(item, f"{path}[{index}]") for index, item in enumerate(value)
        ]
    return _json_value(value, path)


def _schema_map(value: object, path: str) -> JsonValue:
    if not isinstance(value, Mapping):
        return _json_value(value, path)
    mapping = _string_key_mapping(value, path)
    return {
        key: _schema_child(child, f"{path}.{key}") for key, child in mapping.items()
    }


def _schema(value: object, path: str) -> JsonSchema:
    if not isinstance(value, Mapping):
        raise ManifestError(path, "expected a schema object")
    mapping = _string_key_mapping(value, path)
    normalized: JsonSchema = {}
    for key, child in mapping.items():
        child_path = f"{path}.{key}"
        if key == "title":
            continue
        if key in _SCHEMA_MAP_KEYWORDS:
            normalized[key] = _schema_map(child, child_path)
        elif key in _SINGLE_SCHEMA_KEYWORDS:
            normalized[key] = _schema_child(child, child_path)
        elif key in _SCHEMA_ARRAY_KEYWORDS and isinstance(child, list):
            normalized[key] = [
                _schema_child(item, f"{child_path}[{index}]")
                for index, item in enumerate(child)
            ]
        else:
            normalized[key] = _json_value(child, child_path)
    return normalized


def _error_component(value: object, path: str) -> JsonValue:
    """Normalize an OpenRPC error object, whose ``data`` member is a schema."""
    if not isinstance(value, Mapping):
        return _json_value(value, path)
    mapping = _string_key_mapping(value, path)
    return {
        key: (
            _schema_child(child, f"{path}.{key}")
            if key == "data"
            else _json_value(child, f"{path}.{key}")
        )
        for key, child in mapping.items()
    }


def _walk_references(value: JsonValue, path: str) -> Iterator[tuple[str, str]]:
    """Yield every ``$ref`` while treating JSON Schema vocabulary as opaque."""
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key == "$ref":
                if not isinstance(child, str):
                    raise ManifestError(child_path, "expected a reference string")
                yield child_path, child
            else:
                yield from _walk_references(child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk_references(child, f"{path}[{index}]")


def _validate_references(
    manifest: ContractManifest, component_index: ComponentIndex
) -> None:
    values: list[tuple[str, JsonValue]] = []
    for operation_index, operation in enumerate(manifest["operations"]):
        operation_path = f"$.methods[{operation_index}]"
        for parameter_index, parameter in enumerate(operation["params"]):
            values.append(
                (
                    f"{operation_path}.params[{parameter_index}].schema",
                    parameter["schema"],
                )
            )
        values.append(
            (f"{operation_path}.result.schema", operation["result"]["schema"])
        )
        for error_index, error in enumerate(operation["errors"]):
            values.append((f"{operation_path}.errors[{error_index}]", error))

    for key, component in manifest["components"]["schemas"].items():
        values.append((f"$.components.schemas.{key}", component))
    for key, component in manifest["components"]["errors"].items():
        values.append((f"$.components.errors.{key}", component))

    for value_path, value in values:
        for reference_path, reference in _walk_references(value, value_path):
            if not reference.startswith("#/"):
                raise ManifestError(
                    reference_path, "external references are not supported"
                )

            parts = reference[2:].split("/")
            if len(parts) != 3 or parts[0] != "components":
                raise ManifestError(
                    reference_path, "unsupported local reference namespace"
                )
            namespace, key = parts[1], parts[2]
            if namespace not in component_index:
                raise ManifestError(
                    reference_path, "unsupported component reference namespace"
                )
            if "~0" in key or "~1" in key:
                raise ManifestError(
                    reference_path, "unsupported escaped component reference"
                )
            if key not in component_index[namespace]:
                raise ManifestError(reference_path, "dangling local reference")


def manifest_from_openrpc(document: Mapping[str, object]) -> ContractManifest:
    """Normalize an OpenRPC document into the stable workflow contract shape."""
    openrpc_version = _string(document.get("openrpc"), "$.openrpc")
    if openrpc_version != "1.2.6":
        raise ManifestError(
            "$.openrpc",
            f"unsupported OpenRPC version '{openrpc_version}'; expected '1.2.6'",
        )
    methods = _list(document.get("methods"), "$.methods")
    components = _mapping(document.get("components"), "$.components")
    schemas = _string_key_mapping(components.get("schemas"), "$.components.schemas")
    component_errors = _string_key_mapping(
        components.get("errors"), "$.components.errors"
    )

    operations: list[ManifestOperation] = []
    seen_methods: set[str] = set()
    for method_index, method_value in enumerate(methods):
        method_path = f"$.methods[{method_index}]"
        method = _mapping(method_value, method_path)
        method_name = _string(method.get("name"), f"{method_path}.name")
        segments = method_name.split(".")
        if len(segments) < 2 or any(not segment for segment in segments):
            raise ManifestError(
                f"{method_path}.name",
                "malformed dotted method name",
            )
        if method_name in seen_methods:
            raise ManifestError(
                f"{method_path}.name", f"duplicate method '{method_name}'"
            )
        seen_methods.add(method_name)

        params: list[ManifestParameter] = []
        for parameter_index, parameter_value in enumerate(
            _list(method.get("params"), f"{method_path}.params")
        ):
            parameter_path = f"{method_path}.params[{parameter_index}]"
            parameter = _mapping(parameter_value, parameter_path)
            raw_required = parameter.get("required", False)
            params.append(
                {
                    "name": _string(parameter.get("name"), f"{parameter_path}.name"),
                    "required": _boolean(
                        raw_required, f"{parameter_path}.required"
                    ),
                    "schema": _schema(
                        parameter.get("schema"), f"{parameter_path}.schema"
                    ),
                }
            )

        result_path = f"{method_path}.result"
        result = _mapping(method.get("result"), result_path)
        if "schema" not in result:
            raise ManifestError(
                f"{result_path}.schema", "missing success result schema"
            )
        raw_result_schema = result["schema"]
        if not isinstance(raw_result_schema, Mapping) or (
            set(raw_result_schema) != {"$ref"}
            or not (
                isinstance(raw_result_schema.get("$ref"), str)
                and raw_result_schema["$ref"].startswith("#/components/schemas/")
            )
        ):
            raise ManifestError(
                f"{result_path}.schema",
                "success result must reference a named schema component",
            )
        result_schema = _schema(raw_result_schema, f"{result_path}.schema")
        errors: list[JsonSchema] = []
        for error_index, error_value in enumerate(
            _list(method.get("errors"), f"{method_path}.errors")
        ):
            errors.append(_schema(error_value, f"{method_path}.errors[{error_index}]"))

        operations.append(
            {
                "method": method_name,
                "namespace": segments[:-1],
                "action": segments[-1],
                "params": params,
                "result": {"schema": result_schema},
                "errors": errors,
            }
        )

    normalized_schemas = {
        key: _schema(schemas[key], f"$.components.schemas.{key}")
        for key in sorted(schemas)
    }
    normalized_errors = {
        key: _error_component(component_errors[key], f"$.components.errors.{key}")
        for key in sorted(component_errors)
    }

    manifest: ContractManifest = {
        "manifest_version": 1,
        "source": {"format": "openrpc", "openrpc_version": openrpc_version},
        "operations": operations,
        "components": {"schemas": normalized_schemas, "errors": normalized_errors},
    }
    component_index = {
        "schemas": set(manifest["components"]["schemas"]),
        "errors": set(manifest["components"]["errors"]),
    }
    _validate_references(manifest, component_index)
    manifest["operations"] = sorted(
        manifest["operations"], key=lambda operation: operation["method"]
    )
    return manifest
