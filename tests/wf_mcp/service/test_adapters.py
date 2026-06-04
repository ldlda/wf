from __future__ import annotations

from wf_mcp.broker import WfMcpService
from wf_mcp.models import ConnectionConfig
from wf_mcp.storage import FileStore

from ..test_support import (
    FakeAdapter,
    local_temp_root,
)
from .conftest import ContentOnlyOutputAdapter


async def test_service_catalog_preserves_json_schema_description_metadata() -> None:
    service = WfMcpService(store=FileStore(local_temp_root() / "schema_doc_store"))
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_adapter("demo", FakeAdapter())

    await service.refresh_connection_catalog("demo.personal")

    payload = service.get_catalog().as_payload()
    node = payload["nodes"][0]
    assert node["input_schema"]["properties"]["text"]["description"] == "Text to echo"


async def test_service_preserves_content_only_tool_output_schema_for_workflows() -> None:
    service = WfMcpService(store=FileStore(local_temp_root() / "content_only_store"))
    service.register_connection(
        ConnectionConfig(
            id="everything.default", server="everything", account="default"
        )
    )
    service.register_adapter("everything", ContentOnlyOutputAdapter())

    await service.refresh_connection_catalog("everything.default")

    payload = service.get_catalog().as_payload()
    node = payload["nodes"][0]
    assert "content" in node["output_schema"]["properties"]
    assert node["output_schema"]["required"] == ["content"]


async def test_service_wrapped_tool_adapter_model_validates_simple_schema_types() -> None:
    service = WfMcpService(store=FileStore(local_temp_root() / "adapter_model_store"))
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_adapter("demo", FakeAdapter())

    await service.refresh_connection_catalog("demo.personal")

    source = service.capability_sources["demo.personal"]
    spec = source.capabilities.node_specs["demo.personal.echo_tool"]
    assert spec.input_model.model_fields["text"].annotation is str
    assert spec.output_model.model_fields["echoed"].annotation is str
