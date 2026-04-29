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


class FrameStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    INTERRUPTED = "interrupted"


@dataclass(slots=True)
class ExecutionFrame:
    id: str
    kind: str
    node_id: str
    status: FrameStatus = FrameStatus.PENDING
    parent_frame_id: str | None = None
    prior_outcome: str | None = None
    activated_incoming_edge: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    finished_at_node_id: str | None = None


@dataclass(slots=True)
class RuntimeContext:
    current_node_id: str
    frame_id: str = "root"
    retry_count: int = 0
    prior_outcome: str | None = None
    activated_incoming_edge: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class TraceEntry:
    frame_id: str
    node_id: str
    step_type: str
    resolved_input: dict[str, Any]
    outcome: str
    next_node_id: str
    output: dict[str, Any] = field(default_factory=dict)
    state_changes: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class StepExecutionResult:
    outcome: str
    resolved_input: dict[str, Any] = field(default_factory=dict)
    output: dict[str, Any] = field(default_factory=dict)
    state_changes: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class InterruptRequest:
    id: str
    frame_id: str
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
    frames: dict[str, ExecutionFrame] = field(default_factory=dict)
    current_frame_id: str | None = None
    current_node_id: str | None = None
    prior_outcome: str | None = None
    activated_incoming_edge: str | None = None
    error: str | None = None
    interrupt: InterruptRequest | None = None

    def current_frame(self) -> ExecutionFrame:
        if self.current_frame_id is None:
            raise ValueError("run has no current frame")
        return self.frames[self.current_frame_id]

    def sync_from_current_frame(self) -> None:
        frame = self.current_frame()
        self.current_node_id = frame.node_id
        self.prior_outcome = frame.prior_outcome
        self.activated_incoming_edge = frame.activated_incoming_edge

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
