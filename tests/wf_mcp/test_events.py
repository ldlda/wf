from __future__ import annotations

from wf_mcp.broker import WfMcpService
from wf_mcp.events import EventBus, InMemoryEventSink, make_event
from wf_mcp.models import ConnectionConfig
from wf_mcp.storage import FileStore

from .test_support import local_temp_root


def test_event_bus_fans_out_to_subscribers() -> None:
    sink = InMemoryEventSink()
    seen_kinds: list[str] = []
    bus = EventBus(sink)
    bus.subscribe(lambda event: seen_kinds.append(event.kind))

    bus.publish(make_event("catalog_changed", connection_id="demo.personal"))

    assert [event.kind for event in sink.list_events()] == ["catalog_changed"]
    assert sink.list_events()[0].connection_id == "demo.personal"
    assert seen_kinds == ["catalog_changed"]


def test_service_records_events_through_event_bus() -> None:
    sink = InMemoryEventSink()
    bus = EventBus(sink)
    service = WfMcpService(
        store=FileStore(local_temp_root() / "event_bus_service_store"),
        event_bus=bus,
    )

    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )

    assert service.list_events()[0].kind == "connection_registered"
    assert sink.list_events()[0] is service.list_events()[0]
