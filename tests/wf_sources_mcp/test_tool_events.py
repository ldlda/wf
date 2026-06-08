from __future__ import annotations

from wf_sources_mcp.tool_events import (
    ToolWrapperEvent,
    tool_call_completed_event,
    tool_call_started_event,
)


def test_tool_call_started_event_shape() -> None:
    event = tool_call_started_event(
        connection_id="demo.default",
        capability_id="demo.default.echo",
        input_payload={"message": "hello"},
    )

    assert event == ToolWrapperEvent(
        kind="tool_call_started",
        connection_id="demo.default",
        capability_id="demo.default.echo",
        payload={"input": {"message": "hello"}},
    )


def test_tool_call_completed_event_shape() -> None:
    event = tool_call_completed_event(
        connection_id="demo.default",
        capability_id="demo.default.echo",
        outcome="ok",
        meta={"duration_ms": 3},
    )

    assert event.kind == "tool_call_completed"
    assert event.connection_id == "demo.default"
    assert event.capability_id == "demo.default.echo"
    assert event.payload == {"outcome": "ok", "meta": {"duration_ms": 3}}


def test_tool_event_symbols_export_from_package_root() -> None:
    from wf_sources_mcp import ToolWrapperEvent as RootToolWrapperEvent
    from wf_sources_mcp import tool_call_started_event as root_started
    from wf_sources_mcp.tool_events import ToolWrapperEvent, tool_call_started_event

    assert RootToolWrapperEvent is ToolWrapperEvent
    assert root_started is tool_call_started_event
