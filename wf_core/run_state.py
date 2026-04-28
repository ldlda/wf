from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class RunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    INTERRUPTED = "interrupted"


@dataclass(slots=True)
class RuntimeContext:
    current_node_id: str
    retry_count: int = 0
    prior_outcome: str | None = None
    activated_incoming_edge: str | None = None


@dataclass(slots=True)
class TraceEntry:
    node_id: str
    step_type: str
    resolved_input: dict[str, Any]
    outcome: str
    next_node_id: str
    output: dict[str, Any] = field(default_factory=dict)
    state_changes: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class InterruptRequest:
    id: str
    node_id: str
    kind: str
    payload: dict[str, Any] = field(default_factory=dict)
    resumable: bool = True


@dataclass(slots=True)
class RunState:
    workflow_name: str
    status: RunStatus
    workflow_input: dict[str, Any]
    state: dict[str, Any]
    output: dict[str, Any] = field(default_factory=dict)
    trace: list[TraceEntry] = field(default_factory=list)
    current_node_id: str | None = None
    prior_outcome: str | None = None
    activated_incoming_edge: str | None = None
    error: str | None = None
    interrupt: InterruptRequest | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
