from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from openapi_core import OpenAPI

from wf_authoring import NodeReturn
from wf_core import RuntimeContext
from wf_mcp.broker import WfMcpService
from wf_mcp.storage import FileStore
from wf_openapi import source as source_module
from wf_openapi.executor import OpenApiExecutionConfig, OpenApiOperationOutput
from wf_openapi.models import OpenApiOperation
from wf_openapi.source import build_openapi_capability_source

FIXTURE = Path(__file__).parent / "fixtures" / "petstore_minimal.openapi.json"


def test_build_openapi_capability_source_exposes_operations_as_node_specs() -> None:
    source = build_openapi_capability_source(
        source_id="petstore.default",
        document_path=FIXTURE,
        base_url="https://api.example.test",
    )

    assert source.id == "petstore.default"
    assert source.kind == "connection"
    assert sorted(source.capabilities.node_specs) == [
        "petstore.default.create_pet",
        "petstore.default.get_pet",
    ]

    spec = source.capabilities.node_specs["petstore.default.get_pet"]
    node_def = spec.to_node_def()

    assert spec.name == "petstore.default.get_pet"
    assert spec.is_async is True
    assert (
        node_def.input_schema.properties["path"]["properties"]["petId"]["type"]
        == "string"
    )
    assert (
        node_def.output_schema.properties["body"]["$ref"] == "#/components/schemas/Pet"
    )
    assert spec.outcomes == (
        "ok",
        "http_error",
        "unexpected_status",
        "validation_error",
        "transport_error",
    )


def test_openapi_source_can_be_registered_and_inspected_by_service(
    tmp_path: Path,
) -> None:
    service = WfMcpService(store=FileStore(tmp_path / "store"))
    source = build_openapi_capability_source(
        source_id="petstore.default",
        document_path=FIXTURE,
        base_url="https://api.example.test",
    )

    service.register_capability_source(source)

    source_summaries = service.list_source_summaries(limit=100)
    source_by_id = {
        source_summary["id"]: source_summary
        for source_summary in source_summaries["sources"]
    }
    summary = source_by_id["petstore.default"]
    assert summary["kind"] == "connection"
    assert summary["node_spec_count"] == 2
    assert summary["preview"]["node_specs"] == [
        "petstore.default.create_pet",
        "petstore.default.get_pet",
    ]

    inventory = service.inspect_source("petstore.default")
    assert inventory["capabilities"]["node_specs"] == [
        "petstore.default.create_pet",
        "petstore.default.get_pet",
    ]
    detail_by_name = {
        detail["name"]: detail
        for detail in inventory["capabilities"]["node_spec_details"]
    }
    get_pet = detail_by_name["petstore.default.get_pet"]
    assert get_pet["is_async"] is True
    assert "transport_error" in get_pet["outcomes"]
    assert (
        get_pet["input_schema"]["properties"]["path"]["properties"]["petId"]["type"]
        == "string"
    )


async def test_source_node_passes_operation_config_and_payload_to_execution(
    monkeypatch,
) -> None:
    captured: dict[str, Any] = {}

    async def capture_call(
        app: OpenAPI,
        operation: OpenApiOperation,
        config: OpenApiExecutionConfig,
        payload: dict[str, object],
    ) -> NodeReturn[OpenApiOperationOutput]:
        captured["app"] = app
        captured["operation"] = operation
        captured["config"] = config
        captured["payload"] = payload
        return NodeReturn(
            outcome="ok",
            output=OpenApiOperationOutput(
                status_code=200,
                headers={},
                body={},
                validation_errors=[],
            ),
        )

    monkeypatch.setattr(source_module, "call_openapi_operation", capture_call)
    source = build_openapi_capability_source(
        source_id="petstore.default",
        document_path=FIXTURE,
        base_url="https://api.example.test",
    )
    handler = source.capabilities.node_specs[
        "petstore.default.get_pet"
    ].to_async_registry_handler()

    async def run_handler() -> dict[str, object]:
        return await handler(
            {"path": {"petId": "pet-1"}},
            RuntimeContext(current_node_id="petstore.default.get_pet"),
        )

    await run_handler()

    operation = captured["operation"]
    config = captured["config"]
    assert isinstance(captured["app"], OpenAPI)
    assert isinstance(operation, OpenApiOperation)
    assert operation.name == "get_pet"
    assert isinstance(config, OpenApiExecutionConfig)
    assert config.base_url == "https://api.example.test"
    assert captured["payload"]["path"]["petId"] == "pet-1"
