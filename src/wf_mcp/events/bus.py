from __future__ import annotations

from collections.abc import Callable

from .models import McpEvent

EventSubscriber = Callable[[McpEvent], None]


class InMemoryEventSink:
    """Append-only event sink used by current broker history APIs."""

    def __init__(self) -> None:
        self._events: list[McpEvent] = []

    def __call__(self, event: McpEvent) -> None:
        self._events.append(event)

    def list_events(self) -> list[McpEvent]:
        """Return a defensive copy of recorded events."""
        return list(self._events)


class EventBus:
    """Synchronous in-process fanout for broker-local events.

    This is intentionally not an MCP notification system. Protocol projections
    can subscribe later without changing service code that emits events.
    """

    def __init__(self, history: InMemoryEventSink | None = None) -> None:
        self._history = history or InMemoryEventSink()
        self._subscribers: list[EventSubscriber] = [self._history]

    def subscribe(self, subscriber: EventSubscriber) -> None:
        self._subscribers.append(subscriber)

    def publish(self, event: McpEvent) -> None:
        for subscriber in self._subscribers:
            subscriber(event)

    def list_events(self) -> list[McpEvent]:
        """Expose the default history sink for compatibility tools/resources."""
        return self._history.list_events()
