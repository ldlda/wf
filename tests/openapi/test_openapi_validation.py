from __future__ import annotations

import json
from pathlib import Path

from wf_openapi.request import HttpRequestParts, build_http_request_parts
from wf_openapi.spec import load_openapi_operations
from wf_openapi.validation import (
    HttpResponseParts,
    load_openapi_app,
    validate_openapi_request,
    validate_openapi_response,
)

FIXTURE = Path(__file__).parent / "fixtures" / "petstore_minimal.openapi.json"


def test_validate_openapi_request_accepts_public_payload() -> None:
    app = load_openapi_app(FIXTURE)
    operation = next(
        operation
        for operation in load_openapi_operations(FIXTURE)
        if operation.name == "get_pet"
    )
    parts = build_http_request_parts(
        operation,
        base_url="https://api.example.test",
        payload={"path": {"petId": "pet-1"}, "query": {"includeOwner": "true"}},
    )

    result = validate_openapi_request(app, parts)

    assert result.valid is True
    assert result.errors == []


def test_validate_openapi_request_reports_invalid_body() -> None:
    app = load_openapi_app(FIXTURE)
    operation = next(
        operation
        for operation in load_openapi_operations(FIXTURE)
        if operation.name == "create_pet"
    )
    parts = build_http_request_parts(
        operation,
        base_url="https://api.example.test",
        payload={"body": {"extra": "field"}},
    )

    result = validate_openapi_request(app, parts)

    assert result.valid is False
    assert result.errors


def test_validate_openapi_response_accepts_declared_response() -> None:
    app = load_openapi_app(FIXTURE)
    operation = next(
        operation
        for operation in load_openapi_operations(FIXTURE)
        if operation.name == "get_pet"
    )
    request = build_http_request_parts(
        operation,
        base_url="https://api.example.test",
        payload={"path": {"petId": "pet-1"}},
    )
    response = HttpResponseParts(
        status_code=200,
        headers={"content-type": "application/json"},
        data=json.dumps({"id": "pet-1", "name": "Fluffy"}).encode(),
    )

    result = validate_openapi_response(app, request, response)

    assert result.valid is True
    assert result.errors == []
    assert result.data["id"] == "pet-1"


def test_validate_openapi_response_reports_undeclared_status() -> None:
    app = load_openapi_app(FIXTURE)
    request = HttpRequestParts(
        method="GET",
        url="https://api.example.test/pets/pet-1",
    )
    response = HttpResponseParts(
        status_code=418,
        headers={"content-type": "application/json"},
        data=b'{"message": "teapot"}',
    )

    result = validate_openapi_response(app, request, response)

    assert result.valid is False
    assert result.errors
