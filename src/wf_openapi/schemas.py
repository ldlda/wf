from __future__ import annotations

from copy import deepcopy
from typing import Any, cast

from .models import JsonObject, OpenApiOperation

PARAMETER_LOCATIONS = ("path", "query", "header", "cookie")


def input_schema_for_operation(operation: OpenApiOperation) -> JsonObject:
    """Build the node input JSON Schema from operation params and JSON body.

    OpenAPI schemas containing `$ref` are not self-contained; validate them
    with the original document context. This adapter intentionally does not
    resolve references.
    """
    properties: dict[str, Any] = {}
    required: list[str] = []

    for group_name, group_schema in _parameter_group_schemas(operation).items():
        properties[group_name] = group_schema
        if group_schema.get("required"):
            required.append(group_name)

    body_schema = _json_request_body_schema(operation)
    if body_schema is not None:
        properties["body"] = body_schema
        if _request_body_required(operation):
            required.append("body")

    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


def output_schema_for_operation(operation: OpenApiOperation) -> JsonObject:
    """Build generic transport output schema for one OpenAPI operation."""
    body_schema = _first_success_json_response_schema(operation) or {}
    return {
        "type": "object",
        "properties": {
            "status_code": {"type": "integer"},
            "headers": {
                "type": "object",
                "additionalProperties": {"type": "string"},
            },
            "body": body_schema,
        },
        "required": ["status_code", "headers", "body"],
        "additionalProperties": False,
    }


def _parameter_group_schemas(operation: OpenApiOperation) -> dict[str, JsonObject]:
    grouped: dict[str, dict[str, Any]] = {}
    for parameter in operation.effective_parameters:
        if not isinstance(parameter, dict):
            continue
        location = parameter.get("in")
        name = parameter.get("name")
        schema = parameter.get("schema")
        if location not in PARAMETER_LOCATIONS:
            continue
        if not isinstance(name, str) or not isinstance(schema, dict):
            continue

        # Group by OpenAPI parameter location so workflow inputs stay explicit:
        # {"path": {...}, "query": {...}} instead of one ambiguous flat object.
        group = grouped.setdefault(
            location,
            {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
        )
        group["properties"][name] = deepcopy(schema)
        if parameter.get("required") is True:
            group["required"].append(name)

    return {
        name: cast(JsonObject, grouped[name])
        for name in PARAMETER_LOCATIONS
        if name in grouped
    }


def _json_request_body_schema(operation: OpenApiOperation) -> JsonObject | None:
    request_body = operation.raw_operation.get("requestBody")
    if not isinstance(request_body, dict):
        return None
    content = request_body.get("content")
    if not isinstance(content, dict):
        return None
    json_media = content.get("application/json")
    if not isinstance(json_media, dict):
        return None
    schema = json_media.get("schema")
    return cast(JsonObject, deepcopy(schema)) if isinstance(schema, dict) else None


def _request_body_required(operation: OpenApiOperation) -> bool:
    request_body = operation.raw_operation.get("requestBody")
    return isinstance(request_body, dict) and request_body.get("required") is True


def _first_success_json_response_schema(
    operation: OpenApiOperation,
) -> JsonObject | None:
    responses = operation.raw_operation.get("responses")
    if not isinstance(responses, dict):
        return None

    for code in sorted(responses):
        if not str(code).startswith("2"):
            continue
        response = responses[code]
        if not isinstance(response, dict):
            continue
        content = response.get("content")
        if not isinstance(content, dict):
            continue
        json_media = content.get("application/json")
        if not isinstance(json_media, dict):
            continue
        schema = json_media.get("schema")
        if isinstance(schema, dict):
            return cast(JsonObject, deepcopy(schema))
    return None
