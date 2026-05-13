from __future__ import annotations

import mcp.types as mcp_types

from wf_mcp.events import McpEvent


def map_event_to_notifications(event: McpEvent) -> list[mcp_types.ServerNotification]:
    """Project broker-local events into MCP server notifications.

    The event bus is intentionally protocol-neutral. This function is the
    boundary where local capability changes become official MCP notification
    payloads that a FastMCP transport can later send to connected clients.
    """
    notification = _list_changed_notification(event)
    if notification is None:
        return []
    return [mcp_types.ServerNotification(notification)]


def _list_changed_notification(
    event: McpEvent,
) -> (
    mcp_types.ToolListChangedNotification
    | mcp_types.ResourceListChangedNotification
    | mcp_types.PromptListChangedNotification
    | None
):
    if event.kind == "tools_changed":
        return mcp_types.ToolListChangedNotification()
    if event.kind == "resources_changed":
        return mcp_types.ResourceListChangedNotification()
    if event.kind == "prompts_changed":
        return mcp_types.PromptListChangedNotification()
    return None
