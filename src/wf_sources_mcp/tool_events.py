from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class ToolWrapperEvent:
    """Neutral tool-wrapper event before broker-specific event projection."""

    kind: str
    connection_id: str
    capability_id: str
    payload: dict[str, Any] = field(default_factory=dict)


ToolWrapperEventSink = Callable[[ToolWrapperEvent], None]


def tool_call_started_event(
    *,
    connection_id: str,
    capability_id: str,
    input_payload: dict[str, Any],
) -> ToolWrapperEvent:
    return ToolWrapperEvent(
        kind="tool_call_started",
        connection_id=connection_id,
        capability_id=capability_id,
        payload={"input": input_payload},
    )


def tool_call_completed_event(
    *,
    connection_id: str,
    capability_id: str,
    outcome: str,
    meta: dict[str, Any],
) -> ToolWrapperEvent:
    return ToolWrapperEvent(
        kind="tool_call_completed",
        connection_id=connection_id,
        capability_id=capability_id,
        payload={"outcome": outcome, "meta": meta},
    )


__all__ = [
    "ToolWrapperEvent",
    "ToolWrapperEventSink",
    "tool_call_completed_event",
    "tool_call_started_event",
]
