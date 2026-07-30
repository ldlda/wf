from __future__ import annotations

from typing import NotRequired, TypedDict

from .common import (
    ArtifactVersionPayload,
    GuidedResultPayload,
    JsonObject,
    JsonSchema,
)

type RunStatus = str
type ResumeReadiness = str


class WorkflowRefPayload(TypedDict, total=False):
    name: str
    artifact_id: str
    version: int


class InterruptRoutePayload(TypedDict):
    frame_id: str
    node_id: str
    scope_id: str
    lineage_id: str
    parent_frame_id: str
    workflow_ref: WorkflowRefPayload


class InterruptPayload(TypedDict):
    """Persisted typed interrupt contract exposed to API clients."""

    id: str
    frame_id: str
    node_id: str
    kind: str
    payload: JsonObject
    resumable: bool
    route: InterruptRoutePayload | None
    outcomes: list[str]
    request_schema: JsonSchema
    resume_schema: JsonSchema
    typed: bool


class TraceEntryPayload(TypedDict):
    frame_id: str
    node_id: str
    step_type: str
    resolved_input: JsonObject
    outcome: str
    next_node_id: str
    output: JsonObject
    state_changes: JsonObject


class RunSummary(ArtifactVersionPayload):
    run_id: str
    deployment_id: str
    status: RunStatus
    resume_readiness: ResumeReadiness
    diagnostic_count: int
    created_at: str
    updated_at: str


class ListRunsResult(TypedDict):
    runs: list[RunSummary]
    total: int
    cursor: str | None
    next_cursor: str | None
    limit: int


class RunResultBase(ArtifactVersionPayload, GuidedResultPayload):
    deployment_id: str
    status: RunStatus
    run_id: str | None
    resume_readiness: ResumeReadiness | None
    interrupt: InterruptPayload | None
    outcome: str | None
    error: str | None
    output: JsonObject | None
    trace_count: int


class RunResult(RunResultBase):
    """Run operation result with an optional caller-requested trace slice."""

    trace: NotRequired[list[TraceEntryPayload]]
    trace_start: NotRequired[int]
    trace_limit: NotRequired[int]
    trace_truncated: NotRequired[bool]


class RunTraceResult(RunResultBase):
    """Run result where a bounded trace slice is always present."""

    trace: list[TraceEntryPayload]
    trace_start: int
    trace_limit: int
    trace_truncated: bool
