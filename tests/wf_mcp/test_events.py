from __future__ import annotations

import asyncio
from collections.abc import Sequence
from pathlib import Path

from wf_mcp.broker import WfMcpService
from wf_mcp.events import EventBus, InMemoryEventSink, McpEvent, make_event
from wf_mcp.models import ConnectionConfig
from wf_mcp.storage import FileStore

from .test_support import FakeAdapter, echo_tool


def test_event_bus_fans_out_to_subscribers() -> None:
    sink = InMemoryEventSink()
    seen_kinds: list[str] = []
    bus = EventBus(sink)
    bus.subscribe(lambda event: seen_kinds.append(event.kind))

    bus.publish(make_event("catalog_changed", connection_id="demo.personal"))

    assert [event.kind for event in sink.list_events()] == ["catalog_changed"]
    assert sink.list_events()[0].connection_id == "demo.personal"
    assert seen_kinds == ["catalog_changed"]


def test_service_records_events_through_event_bus(tmp_path: Path) -> None:
    sink = InMemoryEventSink()
    bus = EventBus(sink)
    service = WfMcpService(
        store=FileStore(tmp_path / "event_bus_service_store"),
        event_bus=bus,
    )

    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )

    assert service.list_events()[0].kind == "connection_registered"
    assert sink.list_events()[0] is service.list_events()[0]


def test_register_specs_emits_tool_and_catalog_change_events(tmp_path: Path) -> None:
    service = WfMcpService(store=FileStore(tmp_path / "spec_change_store"))
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )

    service.register_specs("demo.personal", echo_tool)

    events = service.list_events()
    event_kinds = [event.kind for event in events]
    tools_changed = [
        event
        for event in events
        if event.kind == "tools_changed" and event.connection_id == "demo.personal"
    ]
    catalog_changed = [
        event
        for event in events
        if event.kind == "catalog_changed" and event.connection_id == "demo.personal"
    ]
    assert "tools_changed" in event_kinds
    assert "catalog_changed" in event_kinds
    assert tools_changed[0].payload["node_count"] == 1
    assert catalog_changed[0].payload["reason"] == "specs_registered"


def test_refresh_catalog_emits_capability_change_events(tmp_path: Path) -> None:
    service = WfMcpService(store=FileStore(tmp_path / "refresh_change_store"))
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_adapter("demo", FakeAdapter())

    asyncio.run(service.refresh_connection_catalog("demo.personal"))

    events = service.list_events()
    tools_changed = _first_event(events, "tools_changed")
    resources_changed = _first_event(events, "resources_changed")
    prompts_changed = _first_event(events, "prompts_changed")
    catalog_changed = _first_event(events, "catalog_changed")
    assert tools_changed.connection_id == "demo.personal"
    assert tools_changed.payload["node_count"] == 1
    assert resources_changed.payload["resource_count"] == 1
    assert prompts_changed.payload["prompt_count"] == 1
    assert catalog_changed.payload["reason"] == "catalog_refresh"


def _first_event(events: Sequence[McpEvent], kind: str) -> McpEvent:
    for event in events:
        if event.kind == kind:
            return event
    raise AssertionError(f"expected event {kind!r}")
