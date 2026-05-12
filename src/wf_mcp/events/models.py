from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class McpEvent:
    """Broker-local event record before protocol-specific projection."""

    kind: str
    timestamp_epoch_ms: int
    connection_id: str | None = None
    capability_id: str | None = None
    workflow_name: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)


def make_event(
    kind: str,
    *,
    connection_id: str | None = None,
    capability_id: str | None = None,
    workflow_name: str | None = None,
    payload: dict[str, Any] | None = None,
) -> McpEvent:
    """Create a timestamped event with optional routing metadata."""
    return McpEvent(
        kind=kind,
        timestamp_epoch_ms=int(time.time() * 1000),
        connection_id=connection_id,
        capability_id=capability_id,
        workflow_name=workflow_name,
        payload=payload or {},
    )
