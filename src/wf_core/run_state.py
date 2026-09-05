from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from wf_core.models.reducers import ReducerRef
from wf_core.models.workflow_refs import WorkflowRef
from wf_core.paths import StatePath

if TYPE_CHECKING:
    from wf_core.runtime.limits import RunLimits

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
    workflow_input: dict[str, Any] = field(default_factory=dict)
    committed_state: dict[str, Any] = field(default_factory=dict)
    workflow_ref: WorkflowRef | None = None


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
    step_number: int | None = None


@dataclass(frozen=True, slots=True)
class ForeachContext:
    """Typed view of one active same-scope foreach iteration.

    The mapping key in ``RuntimeContext.foreach`` is the static
    ``ForeachNode.id`` within the current workflow scope. Identity fields
    disclose the dynamic activation/frame/scope/lineage when advanced
    runtime code needs them; normal node authors should use mapped inputs.
    """

    node_id: str
    activation_id: str
    frame_id: str
    scope_id: str
    lineage_id: str
    index: int
    item: Any


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
    platform: object | None = None
    foreach: dict[str, ForeachContext] = field(default_factory=dict)


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
class InterruptRoute:
    """Internal resume route for an interrupt raised below a graph boundary.

    `InterruptRequest.frame_id` and `.node_id` may describe the public parent
    subgraph boundary. This route retains the actual interrupted child frame so
    resume can continue inside its original workflow scope.
    """

    frame_id: str
    node_id: str
    scope_id: str
    lineage_id: str
    parent_frame_id: str
    workflow_ref: WorkflowRef


def _object_schema() -> dict[str, object]:
    """Default legacy interrupt contract used when older checkpoints are loaded."""
    return {"type": "object", "additionalProperties": True}


@dataclass(slots=True)
class InterruptRequest:
    id: str
    frame_id: str
    node_id: str
    kind: str
    payload: dict[str, Any] = field(default_factory=dict)
    resumable: bool = True
    route: InterruptRoute | None = None
    outcomes: list[str] = field(default_factory=lambda: ["submitted"])
    request_schema: dict[str, object] = field(default_factory=_object_schema)
    resume_schema: dict[str, object] = field(default_factory=_object_schema)
    typed: bool = False


def _default_run_limits() -> RunLimits:
    """Build the default budget without a top-level runtime import.

    Importing ``wf_core.runtime.limits`` at module top would execute the
    ``wf_core.runtime`` package, whose engine imports this module back.
    """
    from wf_core.runtime.limits import RunLimits

    return RunLimits()


@dataclass(slots=True)
class RunState:
    """Mutable execution state for one workflow run.

    ``limits``/``steps_executed`` form the persisted run-wide step budget (see
    ``wf_core.runtime.limits``); ``steps_remaining`` is computed from them.
    """

    workflow_name: str
    status: RunStatus
    workflow_input: dict[str, Any]
    state: dict[str, Any]
    outcome: str | None = None
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
    limits: RunLimits = field(default_factory=_default_run_limits)
    steps_executed: int = 0

    @property
    def steps_remaining(self) -> int:
        """Unspent step budget, floored at zero; computed, never persisted."""
        return max(self.limits.max_steps - self.steps_executed, 0)

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


# Deferred runtime import: binding ``RunLimits`` here (after every class is
# defined) lets ``wf_core.runtime`` engine modules import this module back
# without a cycle, and gives pydantic a resolvable annotation for the codec.
from wf_core.runtime.limits import RunLimits  # noqa: E402
