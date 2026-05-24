from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any

from wf_core.models.reducers import ReducerRef
from wf_core.paths import StatePath

ROOT_SCOPE_ID = "root"
ROOT_LINEAGE_ID = "root"
ROOT_FRAME_ID = "root"


class RunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    INTERRUPTED = "interrupted"


class FrameStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"
    INTERRUPTED = "interrupted"


@dataclass(slots=True)
class StateWrite:
    """One reducer-aware state write.

    `incoming_value` is the value contributed by the node or lineage and is the
    value barriers/gathers must replay. `visible_value` is what later steps in
    the same lineage should read after reducer application.
    """

    path: StatePath
    incoming_value: Any
    visible_value: Any
    reducer: ReducerRef


@dataclass(slots=True)
class RuntimeScope:
    """Committed workflow state root for one workflow activation.

    During migration, the root scope intentionally shares `RunState.state` so
    existing runtime code can keep using the compatibility state dict.
    """

    id: str
    workflow_name: str
    committed_state: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class LineageState:
    """Ordered pending writes owned by one lineage inside a runtime scope."""

    id: str
    scope_id: str
    parent_id: str | None = None
    writes: list[StateWrite] = field(default_factory=list)


@dataclass(slots=True)
class ExecutionFrame:
    id: str
    kind: str
    node_id: str
    status: FrameStatus = FrameStatus.PENDING
    parent_frame_id: str | None = None
    scope_id: str = ROOT_SCOPE_ID
    lineage_id: str = ROOT_LINEAGE_ID
    parent_lineage_id: str | None = None
    prior_outcome: str | None = None
    activated_incoming_edge: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    finished_at_node_id: str | None = None


@dataclass(slots=True)
class RuntimeContext:
    current_node_id: str
    frame_id: str = ROOT_FRAME_ID
    scope_id: str = ROOT_SCOPE_ID
    lineage_id: str = ROOT_LINEAGE_ID
    parent_lineage_id: str | None = None
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
    scopes: dict[str, RuntimeScope] = field(default_factory=dict)
    lineages: dict[str, LineageState] = field(default_factory=dict)
    ready_frame_ids: list[str] = field(default_factory=list)
    current_frame_id: str | None = None
    current_node_id: str | None = None
    prior_outcome: str | None = None
    activated_incoming_edge: str | None = None
    error: str | None = None
    interrupt: InterruptRequest | None = None

    def current_frame(self) -> ExecutionFrame:
        if self.current_frame_id is None:
            raise ValueError("run has no current frame")
        frame = self.frames.get(self.current_frame_id)
        if frame is None:
            raise ValueError(
                "run current frame id is missing from frames: "
                f"current_frame_id={self.current_frame_id!r}, "
                f"frames={sorted(self.frames)!r}"
            )
        return frame

    def sync_from_current_frame(self) -> None:
        frame = self.current_frame()
        self.current_node_id = frame.node_id
        self.prior_outcome = frame.prior_outcome
        self.activated_incoming_edge = frame.activated_incoming_edge

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
