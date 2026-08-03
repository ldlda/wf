from __future__ import annotations

from collections.abc import Iterator, Mapping

from .model import (
    ContractManifest,
    JsonSchema,
    JsonValue,
    ManifestError,
    ManifestOperation,
    ManifestParameter,
)

type ComponentIndex = dict[str, set[str]]


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
        operation_path = f"$.operations[{operation_index}]"
        for parameter_index, parameter in enumerate(operation["params"]):
            values.append(
                (
                    f"{operation_path}.params[{parameter_index}].schema",
                    parameter["schema"],
                )
            )
        values.append((f"{operation_path}.result.schema", operation["result"]["schema"]))
        for error_index, error in enumerate(operation["errors"]):
            values.append((f"{operation_path}.errors[{error_index}]", error))

    for key, component in manifest["components"]["schemas"].items():
        values.append((f"$.components.schemas.{key}", component))
    for key, component in manifest["components"]["errors"].items():
        values.append((f"$.components.errors.{key}", component))

    for value_path, value in values:
        for reference_path, reference in _walk_references(value, value_path):
            if not reference.startswith("#/"):
                raise ManifestError(reference_path, "external references are not supported")

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
    schemas = _mapping(components.get("schemas"), "$.components.schemas")
    component_errors = _mapping(components.get("errors"), "$.components.errors")

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
        if "schema" not in result:
            raise ManifestError(f"{result_path}.schema", "expected an object")
        result_schema = _schema(result["schema"], f"{result_path}.schema")
        if set(result_schema) != {"$ref"} or not (
            isinstance(result_schema["$ref"], str)
            and result_schema["$ref"].startswith("#/components/schemas/")
        ):
            raise ManifestError(
                f"{result_path}.schema",
                "success result must reference a named schema component",
            )
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
                "result": {"schema": result_schema},
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

    manifest: ContractManifest = {
        "manifest_version": 1,
        "source": {"format": "openrpc", "openrpc_version": openrpc_version},
        "operations": sorted(operations, key=lambda operation: operation["method"]),
        "components": {"schemas": normalized_schemas, "errors": normalized_errors},
    }
    component_index = {
        "schemas": set(manifest["components"]["schemas"]),
        "errors": set(manifest["components"]["errors"]),
    }
    _validate_references(manifest, component_index)
    return manifest
