from __future__ import annotations

import asyncio
from pathlib import Path

import httpx

from wf_authoring import NodeReturn
from wf_openapi.executor import OpenApiExecutionConfig, call_openapi_operation
from wf_openapi.executor import OpenApiOperationOutput
from wf_openapi.spec import load_openapi_operations
from wf_openapi.validation import load_openapi_app

FIXTURE = Path("tests/openapi/fixtures/petstore_minimal.openapi.json")


def test_call_openapi_operation_maps_success() -> None:
    app = load_openapi_app(FIXTURE)
    operation = next(
        op for op in load_openapi_operations(FIXTURE) if op.name == "get_pet"
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/pets/pet-1"
        assert request.url.params["includeOwner"] == "true"
        return httpx.Response(200, json={"id": "pet-1", "name": "Fluffy"})

    async def run() -> NodeReturn[OpenApiOperationOutput]:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await call_openapi_operation(
                app,
                operation,
                OpenApiExecutionConfig(base_url="https://api.example.test"),
                {"path": {"petId": "pet-1"}, "query": {"includeOwner": "true"}},
                client=client,
            )

    result = asyncio.run(run())

    assert result.outcome == "ok"
    assert result.output.status_code == 200
    assert result.output.body["id"] == "pet-1"


def test_call_openapi_operation_maps_declared_http_error() -> None:
    app = load_openapi_app(FIXTURE)
    operation = next(
        op for op in load_openapi_operations(FIXTURE) if op.name == "get_pet"
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        _ = request
        return httpx.Response(404, json={"message": "missing"})

    async def run() -> NodeReturn[OpenApiOperationOutput]:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await call_openapi_operation(
                app,
                operation,
                OpenApiExecutionConfig(base_url="https://api.example.test"),
                {"path": {"petId": "missing"}},
                client=client,
            )

    result = asyncio.run(run())

    assert result.outcome == "http_error"
    assert result.output.status_code == 404
    assert result.output.body["message"] == "missing"


def test_call_openapi_operation_maps_unexpected_status() -> None:
    app = load_openapi_app(FIXTURE)
    operation = next(
        op for op in load_openapi_operations(FIXTURE) if op.name == "get_pet"
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        _ = request
        return httpx.Response(418, json={"message": "teapot"})

    async def run() -> NodeReturn[OpenApiOperationOutput]:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await call_openapi_operation(
                app,
                operation,
                OpenApiExecutionConfig(base_url="https://api.example.test"),
                {"path": {"petId": "pet-1"}},
                client=client,
            )

    result = asyncio.run(run())

    assert result.outcome == "unexpected_status"
    assert result.output.status_code == 418
    assert result.output.validation_errors


def test_call_openapi_operation_maps_invalid_request_to_validation_error() -> None:
    app = load_openapi_app(FIXTURE)
    operation = next(
        op for op in load_openapi_operations(FIXTURE) if op.name == "create_pet"
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("invalid request should not be sent")

    async def run() -> NodeReturn[OpenApiOperationOutput]:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await call_openapi_operation(
                app,
                operation,
                OpenApiExecutionConfig(base_url="https://api.example.test"),
                {"body": {"extra": "field"}},
                client=client,
            )

    result = asyncio.run(run())

    assert result.outcome == "validation_error"
    assert result.output.status_code == 0
    assert result.output.validation_errors


def test_call_openapi_operation_maps_invalid_response_to_validation_error() -> None:
    app = load_openapi_app(FIXTURE)
    operation = next(
        op for op in load_openapi_operations(FIXTURE) if op.name == "get_pet"
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        _ = request
        return httpx.Response(200, json={"id": "pet-1"})

    async def run() -> NodeReturn[OpenApiOperationOutput]:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await call_openapi_operation(
                app,
                operation,
                OpenApiExecutionConfig(base_url="https://api.example.test"),
                {"path": {"petId": "pet-1"}},
                client=client,
            )

    result = asyncio.run(run())

    assert result.outcome == "validation_error"
    assert result.output.status_code == 200
    assert result.output.validation_errors


def test_call_openapi_operation_maps_transport_error() -> None:
    app = load_openapi_app(FIXTURE)
    operation = next(
        op for op in load_openapi_operations(FIXTURE) if op.name == "get_pet"
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        _ = request
        raise httpx.ConnectError("offline")

    async def run() -> NodeReturn[OpenApiOperationOutput]:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await call_openapi_operation(
                app,
                operation,
                OpenApiExecutionConfig(base_url="https://api.example.test"),
                {"path": {"petId": "pet-1"}},
                client=client,
            )

    result = asyncio.run(run())

    assert result.outcome == "transport_error"
    assert result.output.status_code == 0
    assert result.output.validation_errors == ["offline"]
