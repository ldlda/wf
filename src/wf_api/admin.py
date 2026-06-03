from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, is_dataclass
from typing import Any, Protocol


class WorkflowAdminConnectionProvider(Protocol):
    """Provides read-only connection inventory for admin frontends."""

    def list_connections(self) -> Sequence[Mapping[str, Any] | object]: ...

    def get_connection_statuses(self) -> Sequence[Mapping[str, Any] | object]: ...


class WorkflowAdminEventProvider(Protocol):
    """Provides read-only event history for admin frontends."""

    def list_events(self) -> Sequence[Mapping[str, Any] | object]: ...


class WorkflowAdminApi:
    """Protocol-neutral read-only broker/server admin operations.

    This surface is intentionally not part of WorkflowApiSurface. Connections
    and event history are platform management data, not workflow lifecycle data.
    """

    def __init__(
        self,
        *,
        connections: WorkflowAdminConnectionProvider,
        events: WorkflowAdminEventProvider,
    ) -> None:
        self.connections = connections
        self.events = events

    async def list_connections(self) -> dict[str, Any]:
        connections = sorted(
            (_payload(item) for item in self.connections.list_connections()),
            key=lambda item: str(item.get("id", item.get("connection_id", ""))),
        )
        return {"connections": connections, "total": len(connections)}

    async def get_connection_statuses(self) -> dict[str, Any]:
        statuses = sorted(
            (_payload(item) for item in self.connections.get_connection_statuses()),
            key=lambda item: str(item.get("connection_id", item.get("id", ""))),
        )
        return {"statuses": statuses, "total": len(statuses)}

    async def list_events(self) -> dict[str, Any]:
        events = [_payload(event) for event in self.events.list_events()]
        return {"events": events, "total": len(events)}


def _payload(value: Mapping[str, Any] | object) -> dict[str, Any]:
    """Normalize provider objects without depending on MCP event/config types."""
    if isinstance(value, Mapping):
        return dict(value)
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        result = model_dump(mode="json")
        if isinstance(result, dict):
            return result
    raise TypeError(f"admin payload object is not serializable: {type(value)!r}")
