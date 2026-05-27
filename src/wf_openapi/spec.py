from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Literal, cast

from .models import JsonObject, OpenApiOperation

HTTP_METHOD_ORDER: tuple[str, ...] = (
    "get",
    "post",
    "put",
    "patch",
    "delete",
    "options",
    "head",
)
HTTP_METHODS: set[str] = set(HTTP_METHOD_ORDER)


def load_openapi_document(path: Path) -> JsonObject:
    """Load one local OpenAPI JSON document.

    This is only file IO plus basic object-shape checking. Full OpenAPI
    validation belongs to an OpenAPI validator dependency, not this module.
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("OpenAPI document must be a JSON object")
    return cast(JsonObject, payload)


def load_openapi_operations(path: Path) -> list[OpenApiOperation]:
    """Return workflow-stable operation inventory from an OpenAPI document."""
    document = load_openapi_document(path)
    paths = document.get("paths")
    if not isinstance(paths, dict):
        raise ValueError("OpenAPI document must contain object field 'paths'")

    operations: list[OpenApiOperation] = []
    operation_names: set[str] = set()
    for raw_path in sorted(paths):
        path_item = paths[raw_path]
        if not isinstance(raw_path, str) or not isinstance(path_item, dict):
            continue
        for method in HTTP_METHOD_ORDER:
            raw_operation = path_item.get(method)
            if not isinstance(raw_operation, dict):
                continue
            operation_id = raw_operation.get("operationId")
            if operation_id is None:
                operation_name = _fallback_operation_name(method, raw_path)
                operation_id = operation_name
            elif isinstance(operation_id, str):
                operation_name = _operation_name(operation_id)
                if not operation_name:
                    raise ValueError(
                        f"OpenAPI operationId {operation_id!r} does not produce a usable operation name"
                    )
            else:
                operation_name = _fallback_operation_name(method, raw_path)
                operation_id = operation_name

            if operation_name in operation_names:
                raise ValueError(
                    f"Duplicate normalized OpenAPI operation name {operation_name!r}"
                )
            operation_names.add(operation_name)

            operations.append(
                OpenApiOperation(
                    name=operation_name,
                    operation_id=operation_id,
                    method=cast(
                        Literal[
                            "get", "post", "put", "patch", "delete", "options", "head"
                        ],
                        method,
                    ),
                    path=raw_path,
                    summary=_optional_string(raw_operation.get("summary")),
                    description=_optional_string(raw_operation.get("description")),
                    effective_parameters=_effective_parameters(
                        path_item, raw_operation
                    ),
                    has_request_body="requestBody" in raw_operation,
                    raw_operation=cast(dict[str, Any], raw_operation),
                    document_path=path,
                )
            )
    return operations


def _effective_parameters(
    path_item: dict[str, Any], raw_operation: dict[str, Any]
) -> tuple[JsonObject, ...]:
    """Merge inherited and local parameters using OpenAPI override identity.

    A parameter is identified by its public `(name, in)` pair. Operation-local
    entries replace matching path-item entries while retaining inherited entries
    that are not overridden.
    """
    merged: dict[tuple[object, object], JsonObject] = {}
    for owner in (path_item, raw_operation):
        parameters = owner.get("parameters", [])
        if not isinstance(parameters, list):
            continue
        for parameter in parameters:
            if not isinstance(parameter, dict):
                continue
            key = (parameter.get("name"), parameter.get("in"))
            merged[key] = cast(JsonObject, parameter)
    return tuple(merged.values())


def _operation_name(operation_id: str) -> str:
    """Convert operationId into a stable snake_case workflow capability key."""
    words = re.sub(r"(?<!^)(?=[A-Z])", "_", operation_id).replace("-", "_")
    return re.sub(r"_+", "_", re.sub(r"[^A-Za-z0-9_]+", "_", words)).strip("_").lower()


def _fallback_operation_name(method: str, raw_path: str) -> str:
    """Build a usable name for operations that omit operationId.

    The HTTP method alone is not specific enough, so paths with no usable
    normalized segments are rejected instead of producing ambiguous names.
    """
    path_segments = [
        normalized
        for segment in raw_path.split("/")
        if (normalized := _operation_name(segment.strip("{}")))
    ]
    if not path_segments:
        raise ValueError(
            f"OpenAPI fallback operation name for {method.upper()} {raw_path} "
            "does not produce a usable operation name"
        )
    return "_".join([method, *path_segments])


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) else None
