from __future__ import annotations

import pytest

from wf_mcp.broker.service.content_access import ContentAccessService
from wf_mcp.broker.service.connection_service import ConnectionService
from wf_mcp.broker.service.events import BrokerEventRecorder
from wf_mcp.broker.service.source_catalog import SourceCatalogService
from wf_mcp.broker.service.upstream_transport import UpstreamTransportService
from wf_mcp.events import EventBus
from wf_mcp.storage import FileStore
from wf_platform import (
    CapabilityBuckets,
    CapabilitySource,
    DocumentationPrompt,
    DocumentationResource,
    SourceVisibility,
)

from wf_mcp.broker import WfMcpService
from wf_mcp.models import ConnectionConfig

from ..test_support import FakeAdapter, local_temp_root


def _make_content_access(
    *,
    store_root: str = "content_access_default",
) -> tuple[ContentAccessService, BrokerEventRecorder]:
    store = FileStore(local_temp_root() / store_root)
    events = BrokerEventRecorder(EventBus())
    connection_service = ConnectionService(events=events)
    upstream = UpstreamTransportService(
        store=store,
        event_sink=events.record_event,
    )
    source_catalog = SourceCatalogService(
        store=store,
        connection_lookup=connection_service.get,
        connection_list_enabled=connection_service.list_enabled,
        connection_list_all=connection_service.list_all,
        tool_executor_for=upstream.tool_executor_for,
        load_auth=upstream.load_auth,
        emit_event=events.record_event,
    )
    connection_service.bind_source_catalog(source_catalog)
    _register_local_docs(source_catalog)
    content_access = ContentAccessService(
        source_catalog=source_catalog,
        upstream=upstream,
        connection_service=connection_service,
        event_sink=events.record_event,
    )
    return content_access, events


def _register_local_docs(source_catalog: SourceCatalogService) -> None:
    """Install deterministic local docs without depending on repo Markdown files."""
    source_catalog.register_capability_source(
        CapabilitySource(
            id="test.docs",
            kind="system",
            capabilities=CapabilityBuckets(
                resources={
                    "test.docs.example": DocumentationResource(
                        name="test.docs.example",
                        uri="wf://docs/example",
                        title="Example Doc",
                        description="Test documentation resource.",
                        mime_type="text/markdown",
                        text="# Example",
                    )
                },
                prompts={
                    "test.docs.guide": DocumentationPrompt(
                        name="test.docs.guide",
                        title="Guide Prompt",
                        description="Test documentation prompt.",
                        text="Use the test docs.",
                    )
                },
            ),
            visibility=SourceVisibility(planner=True),
        )
    )


async def test_content_access_reads_local_documentation_resource() -> None:
    content_access, events = _make_content_access()

    result = await content_access.read_resource("test.docs.example")

    assert result["contents"][0]["uri"] == "wf://docs/example"
    assert result["contents"][0]["text"] == "# Example"
    assert "resource_read_completed" in [e.kind for e in events.list_events()]


async def test_content_access_reads_upstream_resource_with_events() -> None:
    service = WfMcpService(
        store=FileStore(local_temp_root() / "content_upstream_resource")
    )
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_adapter("demo", FakeAdapter())
    await service.refresh_connection_catalog("demo.personal")

    result = await service.content_access.read_resource("demo.personal.resource.welcome")

    assert result["contents"][0]["text"] == "Welcome from the fake adapter resource."
    event_kinds = [e.kind for e in service.list_events()]
    assert "resource_read_started" in event_kinds
    assert "resource_read_completed" in event_kinds


async def test_content_access_renders_upstream_prompt_with_events() -> None:
    service = WfMcpService(
        store=FileStore(local_temp_root() / "content_upstream_prompt")
    )
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_adapter("demo", FakeAdapter())
    await service.refresh_connection_catalog("demo.personal")

    result = await service.content_access.render_prompt(
        "demo.personal.prompt.summarize",
        arguments={"text": "hello world"},
    )

    assert "hello world" in result["messages"][0]["content"]["text"]
    event_kinds = [e.kind for e in service.list_events()]
    assert "prompt_get_started" in event_kinds
    assert "prompt_get_completed" in event_kinds


async def test_content_access_renders_local_documentation_prompt() -> None:
    content_access, events = _make_content_access(
        store_root="content_access_local_prompt"
    )

    result = await content_access.render_prompt("test.docs.guide")

    assert result["description"] == "Test documentation prompt."
    assert result["messages"][0]["role"] == "user"
    assert result["messages"][0]["content"]["text"] == "Use the test docs."
    assert "prompt_get_completed" in [e.kind for e in events.list_events()]


async def test_content_access_raises_on_unknown_resource() -> None:
    content_access, _ = _make_content_access(
        store_root="content_access_missing_resource"
    )

    with pytest.raises(KeyError):
        await content_access.read_resource("nonexistent.resource")
