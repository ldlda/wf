from __future__ import annotations

from pathlib import Path

import httpx2
import pytest

from wf_authoring import NodeReturn
from wf_openapi.executor import (
    OpenApiExecutionConfig,
    OpenApiOperationOutput,
    call_openapi_operation,
)
from wf_openapi.spec import load_openapi_operations
from wf_openapi.validation import load_openapi_app

FIXTURE = Path(__file__).parent / "fixtures" / "petstore_minimal.openapi.json"


@pytest.mark.asyncio
async def test_call_openapi_operation_maps_success() -> None:
    app = load_openapi_app(FIXTURE)
    operation = next(
        op for op in load_openapi_operations(FIXTURE) if op.name == "get_pet"
    )

    async def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.url.path == "/pets/pet-1"
        assert request.url.params["includeOwner"] == "true"
        return httpx2.Response(200, json={"id": "pet-1", "name": "Fluffy"})

    async def run() -> NodeReturn[OpenApiOperationOutput]:
        async with httpx2.AsyncClient(
            transport=httpx2.MockTransport(handler)
        ) as client:
            return await call_openapi_operation(
                app,
                operation,
                OpenApiExecutionConfig(base_url="https://api.example.test"),
                {"path": {"petId": "pet-1"}, "query": {"includeOwner": "true"}},
                client=client,
            )

    result = await run()

    assert result.outcome == "ok"
    assert result.output.status_code == 200
    assert result.output.body["id"] == "pet-1"


@pytest.mark.asyncio
async def test_call_openapi_operation_maps_declared_http_error() -> None:
    app = load_openapi_app(FIXTURE)
    operation = next(
        op for op in load_openapi_operations(FIXTURE) if op.name == "get_pet"
    )

    async def handler(request: httpx2.Request) -> httpx2.Response:
        _ = request
        return httpx2.Response(404, json={"message": "missing"})

    async def run() -> NodeReturn[OpenApiOperationOutput]:
        async with httpx2.AsyncClient(
            transport=httpx2.MockTransport(handler)
        ) as client:
            return await call_openapi_operation(
                app,
                operation,
                OpenApiExecutionConfig(base_url="https://api.example.test"),
                {"path": {"petId": "missing"}},
                client=client,
            )

    result = await run()

    assert result.outcome == "http_error"
    assert result.output.status_code == 404
    assert result.output.body["message"] == "missing"


@pytest.mark.asyncio
async def test_call_openapi_operation_maps_unexpected_status() -> None:
    app = load_openapi_app(FIXTURE)
    operation = next(
        op for op in load_openapi_operations(FIXTURE) if op.name == "get_pet"
    )

    async def handler(request: httpx2.Request) -> httpx2.Response:
        _ = request
        return httpx2.Response(418, json={"message": "teapot"})

    async def run() -> NodeReturn[OpenApiOperationOutput]:
        async with httpx2.AsyncClient(
            transport=httpx2.MockTransport(handler)
        ) as client:
            return await call_openapi_operation(
                app,
                operation,
                OpenApiExecutionConfig(base_url="https://api.example.test"),
                {"path": {"petId": "pet-1"}},
                client=client,
            )

    result = await run()

    assert result.outcome == "unexpected_status"
    assert result.output.status_code == 418
    assert result.output.validation_errors


@pytest.mark.asyncio
async def test_call_openapi_operation_maps_invalid_request_to_validation_error() -> (
    None
):
    app = load_openapi_app(FIXTURE)
    operation = next(
        op for op in load_openapi_operations(FIXTURE) if op.name == "create_pet"
    )

    async def handler(request: httpx2.Request) -> httpx2.Response:
        raise AssertionError("invalid request should not be sent")

    async def run() -> NodeReturn[OpenApiOperationOutput]:
        async with httpx2.AsyncClient(
            transport=httpx2.MockTransport(handler)
        ) as client:
            return await call_openapi_operation(
                app,
                operation,
                OpenApiExecutionConfig(base_url="https://api.example.test"),
                {"body": {"extra": "field"}},
                client=client,
            )

    result = await run()

    assert result.outcome == "validation_error"
    assert result.output.status_code == 0
    assert result.output.validation_errors


@pytest.mark.asyncio
async def test_call_openapi_operation_maps_invalid_response_to_validation_error() -> (
    None
):
    app = load_openapi_app(FIXTURE)
    operation = next(
        op for op in load_openapi_operations(FIXTURE) if op.name == "get_pet"
    )

    async def handler(request: httpx2.Request) -> httpx2.Response:
        _ = request
        return httpx2.Response(200, json={"id": "pet-1"})

    async def run() -> NodeReturn[OpenApiOperationOutput]:
        async with httpx2.AsyncClient(
            transport=httpx2.MockTransport(handler)
        ) as client:
            return await call_openapi_operation(
                app,
                operation,
                OpenApiExecutionConfig(base_url="https://api.example.test"),
                {"path": {"petId": "pet-1"}},
                client=client,
            )

    result = await run()

    assert result.outcome == "validation_error"
    assert result.output.status_code == 200
    assert result.output.validation_errors


@pytest.mark.asyncio
async def test_call_openapi_operation_maps_malformed_json_response_to_validation_error() -> (
    None
):
    app = load_openapi_app(FIXTURE)
    operation = next(
        op for op in load_openapi_operations(FIXTURE) if op.name == "get_pet"
    )

    async def handler(request: httpx2.Request) -> httpx2.Response:
        _ = request
        return httpx2.Response(
            200,
            headers={"content-type": "application/json"},
            content=b"{not json",
        )

    async def run() -> NodeReturn[OpenApiOperationOutput]:
        async with httpx2.AsyncClient(
            transport=httpx2.MockTransport(handler)
        ) as client:
            return await call_openapi_operation(
                app,
                operation,
                OpenApiExecutionConfig(base_url="https://api.example.test"),
                {"path": {"petId": "pet-1"}},
                client=client,
            )

    result = await run()

    assert result.outcome == "validation_error"
    assert result.output.status_code == 200
    assert result.output.validation_errors


@pytest.mark.asyncio
async def test_call_openapi_operation_maps_transport_error() -> None:
    app = load_openapi_app(FIXTURE)
    operation = next(
        op for op in load_openapi_operations(FIXTURE) if op.name == "get_pet"
    )

    async def handler(request: httpx2.Request) -> httpx2.Response:
        _ = request
        raise httpx2.ConnectError("offline")

    async def run() -> NodeReturn[OpenApiOperationOutput]:
        async with httpx2.AsyncClient(
            transport=httpx2.MockTransport(handler)
        ) as client:
            return await call_openapi_operation(
                app,
                operation,
                OpenApiExecutionConfig(base_url="https://api.example.test"),
                {"path": {"petId": "pet-1"}},
                client=client,
            )

    result = await run()

    assert result.outcome == "transport_error"
    assert result.output.status_code == 0
    assert result.output.validation_errors == ["offline"]
