from __future__ import annotations

from wf_mcp.broker import WfMcpService
from wf_mcp.broker.service.events import BrokerEventRecorder
from wf_mcp.capabilities import (
    CatalogNodeEntry,
    CatalogPromptEntry,
    CatalogResourceEntry,
)
from wf_mcp.events import EventBus, make_event
from wf_mcp.models import CatalogSnapshot
from wf_mcp.storage import FileStore

from ..test_support import local_temp_root


def test_broker_event_recorder_records_existing_event() -> None:
    bus = EventBus()
    recorder = BrokerEventRecorder(bus)
    event = make_event("connection_registered", connection_id="demo.personal")

    recorder.record_event(event)

    assert recorder.list_events()[0] is event
    assert bus.list_events()[0] is event


def test_broker_event_recorder_builds_simple_event() -> None:
    recorder = BrokerEventRecorder(EventBus())

    recorder.record_kind(
        "workflow_artifact_saved",
        capability_id="echo",
        payload={"version": 1},
    )

    event = recorder.list_events()[0]
    assert event.kind == "workflow_artifact_saved"
    assert event.capability_id == "echo"
    assert event.payload["version"] == 1


def test_broker_event_recorder_records_catalog_change_fanout() -> None:
    recorder = BrokerEventRecorder(EventBus())
    snapshot = CatalogSnapshot(
        connection_id="demo.personal",
        nodes=[
            CatalogNodeEntry(
                qualified_name="demo.personal.echo",
                connection_id="demo.personal",
                local_name="echo",
                title=None,
                description=None,
                outcomes=("ok",),
                input_schema={},
                output_schema={},
            ),
        ],
        resources=[
            CatalogResourceEntry(
                qualified_name="demo.personal.resource.welcome",
                connection_id="demo.personal",
                local_name="welcome",
                title=None,
                uri="demo://welcome",
                description=None,
            ),
        ],
        prompts=[
            CatalogPromptEntry(
                qualified_name="demo.personal.prompt.welcome",
                connection_id="demo.personal",
                local_name="welcome",
                title=None,
                description=None,
            ),
        ],
        fetched_at_epoch_ms=1,
        max_age_seconds=300,
    )

    recorder.record_catalog_change_events(
        "demo.personal",
        snapshot,
        reason="catalog_refresh",
    )

    events = recorder.list_events()
    event_kinds = [event.kind for event in events]
    assert event_kinds == [
        "tools_changed",
        "resources_changed",
        "prompts_changed",
        "catalog_changed",
    ]
    assert events[-1].payload["reason"] == "catalog_refresh"
    assert events[-1].payload["node_count"] == 1
    assert events[-1].payload["resource_count"] == 1
    assert events[-1].payload["prompt_count"] == 1


def test_wfmcpservice_uses_broker_event_recorder() -> None:
    bus = EventBus()
    service = WfMcpService(
        store=FileStore(local_temp_root() / "service_event_recorder"),
        event_bus=bus,
    )

    service._record_event(  # noqa: SLF001
        make_event("connection_registered", connection_id="demo.personal")
    )

    assert service.events.event_bus is bus
    assert service.list_events()[0].kind == "connection_registered"
