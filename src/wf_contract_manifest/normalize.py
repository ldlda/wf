from __future__ import annotations

from collections.abc import Mapping

from .model import (
    ContractManifest,
    JsonSchema,
    JsonValue,
    ManifestError,
    ManifestOperation,
    ManifestParameter,
)


def _mapping(value: object, path: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ManifestError(path, "expected an object")
    return value


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
    # Generated titles are removed recursively; every other schema keyword/value stays opaque.
    if value is None or isinstance(value, bool | int | float | str):
        return value
    if isinstance(value, list):
        return [_json_value(item, f"{path}[{index}]") for index, item in enumerate(value)]
    if isinstance(value, Mapping):
        normalized: dict[str, JsonValue] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ManifestError(path, "expected string object keys")
            if key != "title":
                normalized[key] = _json_value(item, f"{path}.{key}")
        return normalized
    raise ManifestError(path, "expected a JSON value")


def _schema(value: object, path: str) -> JsonSchema:
    normalized = _json_value(value, path)
    if not isinstance(normalized, dict):
        raise ManifestError(path, "expected a schema object")
    return normalized


def manifest_from_openrpc(document: Mapping[str, object]) -> ContractManifest:
    """Normalize an OpenRPC document into the stable workflow contract shape."""
    openrpc_version = _string(document.get("openrpc"), "$.openrpc")
    methods = _list(document.get("methods"), "$.methods")
    components = _mapping(document.get("components"), "$.components")
    schemas = _mapping(components.get("schemas"), "$.components.schemas")
    component_errors = _mapping(components.get("errors"), "$.components.errors")

    operations: list[ManifestOperation] = []
    for method_index, method_value in enumerate(methods):
        method_path = f"$.methods[{method_index}]"
        method = _mapping(method_value, method_path)
        method_name = _string(method.get("name"), f"{method_path}.name")
        segments = method_name.split(".")
        if len(segments) < 2 or any(not segment for segment in segments):
            raise ManifestError(
                f"{method_path}.name",
                "expected a method name with non-empty dot-separated segments",
            )

        params: list[ManifestParameter] = []
        for parameter_index, parameter_value in enumerate(
            _list(method.get("params"), f"{method_path}.params")
        ):
            parameter_path = f"{method_path}.params[{parameter_index}]"
            parameter = _mapping(parameter_value, parameter_path)
            params.append(
                {
                    "name": _string(parameter.get("name"), f"{parameter_path}.name"),
                    "required": _boolean(
                        parameter.get("required"), f"{parameter_path}.required"
                    ),
                    "schema": _schema(
                        parameter.get("schema"), f"{parameter_path}.schema"
                    ),
                }
            )

        result_path = f"{method_path}.result"
        result = _mapping(method.get("result"), result_path)
        errors: list[JsonSchema] = []
        for error_index, error_value in enumerate(
            _list(method.get("errors"), f"{method_path}.errors")
        ):
            errors.append(
                _schema(error_value, f"{method_path}.errors[{error_index}]")
            )

        operations.append(
            {
                "method": method_name,
                "namespace": segments[:-1],
                "action": segments[-1],
                "params": params,
                "result": {"schema": _schema(result.get("schema"), f"{result_path}.schema")},
                "errors": errors,
            }
        )

    normalized_schemas = {
        key: _schema(schemas[key], f"$.components.schemas.{key}")
        for key in sorted(schemas)
    }
    normalized_errors = {
        key: _json_value(component_errors[key], f"$.components.errors.{key}")
        for key in sorted(component_errors)
    }

    return {
        "manifest_version": 1,
        "source": {"format": "openrpc", "openrpc_version": openrpc_version},
        "operations": sorted(operations, key=lambda operation: operation["method"]),
        "components": {"schemas": normalized_schemas, "errors": normalized_errors},
    }
