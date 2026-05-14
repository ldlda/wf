from __future__ import annotations

import asyncio

import mcp.types as mcp_types

from wf_mcp.events import EventBus, make_event
from wf_mcp.notifications import (
    FastMcpContextNotificationSink,
    RecordingNotificationSink,
    map_event_to_notifications,
)


class FakeFastMcpContext:
    def __init__(self) -> None:
        self.sent: list[mcp_types.ServerNotificationType] = []

    async def send_notification(
        self,
        notification: mcp_types.ServerNotificationType,
    ) -> None:
        self.sent.append(notification)


def test_maps_capability_change_events_to_mcp_list_changed_notifications() -> None:
    tool_event = make_event("tools_changed", connection_id="demo.personal")
    resource_event = make_event("resources_changed", connection_id="demo.personal")
    prompt_event = make_event("prompts_changed", connection_id="demo.personal")

    tool_notifications = map_event_to_notifications(tool_event)
    resource_notifications = map_event_to_notifications(resource_event)
    prompt_notifications = map_event_to_notifications(prompt_event)

    assert isinstance(tool_notifications[0].root, mcp_types.ToolListChangedNotification)
    assert tool_notifications[0].root.method == "notifications/tools/list_changed"
    assert isinstance(
        resource_notifications[0].root,
        mcp_types.ResourceListChangedNotification,
    )
    assert (
        resource_notifications[0].root.method == "notifications/resources/list_changed"
    )
    assert isinstance(
        prompt_notifications[0].root,
        mcp_types.PromptListChangedNotification,
    )
    assert prompt_notifications[0].root.method == "notifications/prompts/list_changed"


def test_ignores_events_that_do_not_have_an_mcp_notification_projection() -> None:
    event = make_event("workflow_artifact_saved", workflow_name="demo")

    assert map_event_to_notifications(event) == []


def test_recording_notification_sink_projects_events_from_event_bus() -> None:
    bus = EventBus()
    sink = RecordingNotificationSink()
    bus.subscribe(sink)

    bus.publish(make_event("tools_changed", connection_id="demo.personal"))
    bus.publish(make_event("workflow_deployment_saved", workflow_name="demo"))
    bus.publish(make_event("prompts_changed", connection_id="demo.personal"))

    notifications = sink.list_notifications()
    assert len(notifications) == 2
    assert notifications[0].root.method == "notifications/tools/list_changed"
    assert notifications[1].root.method == "notifications/prompts/list_changed"


def test_fastmcp_context_notification_sink_sends_projected_notifications() -> None:
    context = FakeFastMcpContext()
    sink = FastMcpContextNotificationSink(context)

    async def run() -> None:
        await sink.send_event(
            make_event("resources_changed", connection_id="demo.personal")
        )
        await sink.send_event(
            make_event("workflow_artifact_saved", workflow_name="demo")
        )

    asyncio.run(run())

    assert len(context.sent) == 1
    assert isinstance(context.sent[0], mcp_types.ResourceListChangedNotification)
    assert context.sent[0].method == "notifications/resources/list_changed"
