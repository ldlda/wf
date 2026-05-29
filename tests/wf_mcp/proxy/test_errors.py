from __future__ import annotations

import sys

from wf_mcp.events import EventBus, InMemoryEventSink
from wf_mcp.models import BrokerConfig, ConnectionConfig
from wf_mcp.proxy import ProxyRuntime
from wf_mcp.proxy.reload_events import (
    ProxyReloadResult,
    reload_change_events,
)
from wf_mcp.proxy.tools import ProxyToolPayload, ProxyToolsPage

from ..test_support import fixture_server_path, local_temp_root


def test_proxy_runtime_reload_publishes_local_change_events() -> None:
    sink = InMemoryEventSink()
    event_bus = EventBus(sink)
    config = BrokerConfig(
        store_root=local_temp_root() / "proxy_reload_events_store",
        connections=[
            ConnectionConfig(
                id="fixture.personal",
                server="fixture",
                account="personal",
                metadata={
                    "transport": "stdio",
                    "command": sys.executable,
                    "args": [fixture_server_path()],
                },
            )
        ],
    )
    runtime = ProxyRuntime(config, event_bus=event_bus)
    initial_event_count = len(sink.list_events())

    result = runtime.reload()

    events = sink.list_events()[initial_event_count:]
    event_kinds = [event.kind for event in events]
    catalog_changed = [event for event in events if event.kind == "catalog_changed"]
    assert result["reloaded"] is True
    assert "tools_changed" in event_kinds
    assert "resources_changed" in event_kinds
    assert "prompts_changed" in event_kinds
    assert catalog_changed[0].payload["reason"] == "transparent_reload"


def test_proxy_runtime_reload_reuses_unchanged_mounts() -> None:
    config = BrokerConfig(
        store_root=local_temp_root() / "proxy_reuse_store",
        connections=[
            ConnectionConfig(
                id="fixture.personal",
                server="fixture",
                account="personal",
                metadata={
                    "transport": "stdio",
                    "command": sys.executable,
                    "args": [fixture_server_path()],
                },
            )
        ],
    )
    runtime = ProxyRuntime(config)
    first_mount = runtime.mounts.active_mounts_for(config)[0]

    result = runtime.reload()
    second_mount = runtime.mounts.active_mounts_for(config)[0]

    assert result["mounted_connections"] == ["fixture.personal"]
    assert result["connection_count"] == 1
    assert result["enabled_connection_count"] == 1
    assert first_mount is second_mount


def test_proxy_reload_result_serializes_and_drives_reload_events() -> None:
    result = ProxyReloadResult(
        mounted_connections=["fixture.personal"],
        connection_count=2,
        enabled_connection_count=1,
    )

    payload = result.to_payload()
    rehydrated = ProxyReloadResult.from_payload(payload)
    events = reload_change_events(result)

    assert payload["ok"] is True
    assert payload["reloaded"] is True
    assert payload["mounted_connections"] == ["fixture.personal"]
    assert payload["connection_count"] == 2
    assert payload["enabled_connection_count"] == 1
    assert rehydrated == result
    assert events[0].payload["mounted_connections"] == ["fixture.personal"]
    assert events[0].payload["enabled_connection_count"] == 1


def test_proxy_tool_payload_serializes_admin_tool_metadata() -> None:
    payload = ProxyToolPayload(
        proxy_name="fixture.personal.echo_tool",
        connection_id="fixture.personal",
        local_name="echo_tool",
        title="Echo Tool",
        description="Echo text back",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
    )

    minimal = payload.to_payload(include_schema=False)
    with_schema = payload.to_payload(include_schema=True)

    assert minimal["proxy_name"] == "fixture.personal.echo_tool"
    assert minimal["connection_id"] == "fixture.personal"
    assert minimal["local_name"] == "echo_tool"
    assert minimal["enabled"] is True
    assert "input_schema" not in minimal
    assert with_schema["input_schema"] == {"type": "object"}
    assert with_schema["output_schema"] == {"type": "object"}


def test_proxy_tools_page_serializes_paginated_payload() -> None:
    tool = ProxyToolPayload(
        proxy_name="fixture.personal.echo_tool",
        connection_id="fixture.personal",
        local_name="echo_tool",
    )
    page = ProxyToolsPage(
        tools=[tool],
        next_cursor="cursor-1",
        total=3,
    )

    payload = page.to_payload(include_schema=False)

    assert payload["nextCursor"] == "cursor-1"
    assert payload["total"] == 3
    assert payload["tools"][0]["proxy_name"] == "fixture.personal.echo_tool"
