from __future__ import annotations

from typing import Protocol

import mcp.types as mcp_types

from wf_mcp.events import McpEvent

from .mapping import map_event_to_notifications


class NotificationSink(Protocol):
    """Consumes local events and emits or records MCP notifications."""

    def __call__(self, event: McpEvent) -> None: ...


class RecordingNotificationSink:
    """Test sink that records MCP notifications projected from local events."""

    def __init__(self) -> None:
        self._notifications: list[mcp_types.ServerNotification] = []

    def __call__(self, event: McpEvent) -> None:
        self._notifications.extend(map_event_to_notifications(event))

    def list_notifications(self) -> list[mcp_types.ServerNotification]:
        """Return a defensive copy of projected notifications."""
        return list(self._notifications)


class FastMcpNotificationContext(Protocol):
    """Small protocol for the FastMCP context method we need."""

    async def send_notification(
        self,
        notification: mcp_types.ServerNotificationType,
    ) -> None: ...


class FastMcpContextNotificationSink:
    """Send projected local events through a request-scoped FastMCP context."""

    def __init__(self, context: FastMcpNotificationContext) -> None:
        self._context = context

    async def send_event(self, event: McpEvent) -> None:
        for notification in map_event_to_notifications(event):
            await self._context.send_notification(notification.root)
