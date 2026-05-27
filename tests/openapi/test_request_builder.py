from __future__ import annotations

from pathlib import Path

import pytest

from wf_openapi.request import build_http_request_parts
from wf_openapi.spec import load_openapi_operations

FIXTURE = Path(__file__).parent / "fixtures" / "petstore_minimal.openapi.json"


def test_build_http_request_parts_uses_public_openapi_names() -> None:
    operation = next(
        operation
        for operation in load_openapi_operations(FIXTURE)
        if operation.name == "get_pet"
    )

    parts = build_http_request_parts(
        operation,
        base_url="https://api.example.test/v1",
        payload={
            "path": {"petId": "pet 1"},
            "query": {"includeOwner": True},
            "header": {"X-Trace-ID": "trace-1"},
            "cookie": {"sessionId": "session-1"},
        },
    )

    assert parts.method == "GET"
    assert parts.url == "https://api.example.test/v1/pets/pet%201"
    assert parts.params["includeOwner"] is True
    assert parts.headers["X-Trace-ID"] == "trace-1"
    assert parts.cookies["sessionId"] == "session-1"


def test_build_http_request_parts_requires_path_parameters() -> None:
    operation = next(
        operation
        for operation in load_openapi_operations(FIXTURE)
        if operation.name == "get_pet"
    )

    with pytest.raises(ValueError, match="missing path parameter 'petId'"):
        build_http_request_parts(
            operation,
            base_url="https://api.example.test",
            payload={"path": {}},
        )


@pytest.mark.parametrize("group", ["path", "query", "header", "cookie"])
def test_build_http_request_parts_rejects_non_object_parameter_groups(
    group: str,
) -> None:
    operation = next(
        operation
        for operation in load_openapi_operations(FIXTURE)
        if operation.name == "get_pet"
    )

    with pytest.raises(ValueError, match=rf"{group} must be an object"):
        payload: dict[str, object] = {"path": {"petId": "pet-1"}}
        payload[group] = ["not", "an", "object"]
        build_http_request_parts(
            operation,
            base_url="https://api.example.test",
            payload=payload,
        )


def test_build_http_request_parts_passes_body_through_as_json() -> None:
    operation = next(
        operation
        for operation in load_openapi_operations(FIXTURE)
        if operation.name == "create_pet"
    )

    parts = build_http_request_parts(
        operation,
        base_url="https://api.example.test",
        payload={"body": {"name": "Fluffy"}},
    )

    assert parts.method == "POST"
    assert parts.url == "https://api.example.test/pets"
    assert isinstance(parts.json, dict)
    assert parts.json["name"] == "Fluffy"
