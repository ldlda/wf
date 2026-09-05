"""Immutable snapshots for durable workflow runs and bounded traces."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError

from wf_api import TraceRange
from wf_artifacts import DependencyDiagnostic
from wf_core import InterruptRequest, InterruptRoute, TraceEntry, WorkflowRef

from ._identity import require_response_identity
from ._repr import html_repr, short_repr
from .codec import DecodedRunResult, decode_run_result, decode_trace_result
from .errors import DeploymentNotRunnable, InvalidResponse
from .protocols import WorkflowClientPort


@dataclass(frozen=True, slots=True)
class TracePage:
    """One bounded, already-loaded slice of a durable run's execution trace."""

    start: int
    limit: int
    frames: tuple[TraceEntry, ...]
    truncated: bool
    trace_count: int

    def __repr__(self) -> str:
        return short_repr(
            type(self).__name__,
            start=self.start,
            limit=self.limit,
            frames=f"{len(self.frames)} loaded/{self.trace_count} total",
            truncated=self.truncated,
        )

    def _repr_html_(self) -> str:
        return html_repr(
            type(self).__name__,
            start=self.start,
            limit=self.limit,
            frames=f"{len(self.frames)} loaded/{self.trace_count} total",
            truncated=self.truncated,
        )


def _interrupt(
    payload: Mapping[str, Any] | None,
    *,
    operation: str,
) -> InterruptRequest | None:
    if payload is None:
        return None
    data = dict(payload)
    route_data = data.get("route")
    route = None
    if route_data is not None:
        route_values = dict(route_data)
        workflow_ref = route_values.get("workflow_ref")
        try:
            route = InterruptRoute(
                frame_id=route_values["frame_id"],
                node_id=route_values["node_id"],
                scope_id=route_values["scope_id"],
                lineage_id=route_values["lineage_id"],
                parent_frame_id=route_values["parent_frame_id"],
                workflow_ref=WorkflowRef.model_validate(workflow_ref),
            )
        except (KeyError, TypeError, ValueError, ValidationError) as exc:
            raise InvalidResponse(
                operation=operation,
                details=f"invalid interrupt route: {exc}",
            ) from exc
    data["route"] = route
    # ``InterruptPayload`` is intentionally consumed at this boundary; public
    # clients receive the core runtime request instead of a wire TypedDict.
    return InterruptRequest(**data)


def _run_from_decoded(
    port: WorkflowClientPort,
    decoded: DecodedRunResult,
    *,
    expected_run_id: str | None = None,
    expected_deployment_id: str | None = None,
    operation: str = "workflow.runs.inspect",
) -> Run:
    if expected_run_id is not None and decoded.run_id != expected_run_id:
        require_response_identity(
            operation=operation,
            actual={"run_id": decoded.run_id},
            expected={"run_id": expected_run_id},
        )
    if expected_deployment_id is not None:
        require_response_identity(
            operation=operation,
            actual={"deployment_id": decoded.deployment_id},
            expected={"deployment_id": expected_deployment_id},
        )
    if decoded.run_id is None:
        raise DeploymentNotRunnable(
            deployment_id=decoded.deployment_id,
            diagnostics=decoded.diagnostics,
            outcome=decoded.outcome,
            error=decoded.error,
        )
    return Run(
        _port=port,
        run_id=decoded.run_id,
        deployment_id=decoded.deployment_id,
        status=decoded.status,
        outcome=decoded.outcome,
        output=decoded.output,
        interrupt=_interrupt(decoded.interrupt, operation=operation),
        diagnostics=decoded.diagnostics,
        trace_count=decoded.trace_count,
        max_steps=decoded.max_steps,
        steps_executed=decoded.steps_executed,
        steps_remaining=decoded.steps_remaining,
    )


@dataclass(frozen=True, slots=True, init=False)
class Run:
    """Immutable client snapshot of one durable deployment run.

    ``max_steps``, ``steps_executed``, and ``steps_remaining`` are the
    server-effective budget values returned with every run response. The
    server substitutes its default limit when creation omits one, so
    refresh/resume reconstruction simply preserves whatever was returned.
    """

    _port: WorkflowClientPort = field(repr=False, compare=False)
    run_id: str
    deployment_id: str
    status: str
    outcome: str | None
    _output: dict[str, Any] | None = field(repr=False)
    _interrupt: InterruptRequest | None = field(repr=False)
    _diagnostics: tuple[DependencyDiagnostic, ...] = field(repr=False)
    trace_count: int
    max_steps: int
    steps_executed: int
    steps_remaining: int

    def __init__(
        self,
        *,
        _port: WorkflowClientPort,
        run_id: str,
        deployment_id: str,
        status: str,
        outcome: str | None,
        output: dict[str, Any] | None,
        interrupt: InterruptRequest | None,
        diagnostics: tuple[DependencyDiagnostic, ...],
        trace_count: int,
        max_steps: int,
        steps_executed: int,
        steps_remaining: int,
    ) -> None:
        object.__setattr__(self, "_port", _port)
        object.__setattr__(self, "run_id", run_id)
        object.__setattr__(self, "deployment_id", deployment_id)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "outcome", outcome)
        object.__setattr__(self, "_output", deepcopy(output))
        object.__setattr__(self, "_interrupt", deepcopy(interrupt))
        object.__setattr__(
            self,
            "_diagnostics",
            tuple(item.model_copy(deep=True) for item in diagnostics),
        )
        object.__setattr__(self, "trace_count", trace_count)
        object.__setattr__(self, "max_steps", max_steps)
        object.__setattr__(self, "steps_executed", steps_executed)
        object.__setattr__(self, "steps_remaining", steps_remaining)

    @property
    def output(self) -> dict[str, Any] | None:
        """Return a defensive copy of the already-loaded workflow output."""
        return deepcopy(self._output)

    @property
    def interrupt(self) -> InterruptRequest | None:
        """Return a defensive copy of the already-loaded interrupt contract."""
        return deepcopy(self._interrupt)

    @property
    def diagnostics(self) -> tuple[DependencyDiagnostic, ...]:
        """Return defensive copies of loaded dependency diagnostics."""
        return tuple(item.model_copy(deep=True) for item in self._diagnostics)

    def __repr__(self) -> str:
        return short_repr(
            type(self).__name__,
            run_id=self.run_id,
            deployment_id=self.deployment_id,
            status=self.status,
            outcome=self.outcome,
            output=self._output,
            diagnostics=f"{len(self._diagnostics)} diagnostics",
            trace=f"{self.trace_count} frames",
        )

    def _repr_html_(self) -> str:
        return html_repr(
            type(self).__name__,
            run_id=self.run_id,
            deployment_id=self.deployment_id,
            status=self.status,
            outcome=self.outcome,
            output=self._output,
            diagnostics=f"{len(self._diagnostics)} diagnostics",
            trace=f"{self.trace_count} frames (use trace() for a bounded page)",
        )

    @classmethod
    def from_payload(
        cls,
        port: WorkflowClientPort,
        payload: object,
        *,
        expected_run_id: str | None = None,
        expected_deployment_id: str | None = None,
        operation: str = "workflow.runs.inspect",
    ) -> Run:
        """Validate one run response and reconstruct its immutable snapshot."""
        return _run_from_decoded(
            port,
            decode_run_result(payload, operation=operation),
            expected_run_id=expected_run_id,
            expected_deployment_id=expected_deployment_id,
            operation=operation,
        )

    async def refresh(self) -> Run:
        """Read the current server snapshot without mutating this run."""
        return self.from_payload(
            self._port,
            await self._port.inspect_run(run_id=self.run_id),
            expected_run_id=self.run_id,
            expected_deployment_id=self.deployment_id,
            operation="workflow.runs.inspect",
        )

    async def resume(
        self,
        response: Mapping[str, Any],
        *,
        outcome: str = "submitted",
    ) -> Run:
        """Resume an interrupted run and return the server's new snapshot."""
        if self.status != "interrupted" or self._interrupt is None:
            raise ValueError("only interrupted runs can be resumed")
        if not self._interrupt.resumable:
            raise ValueError("run interrupt is not resumable")
        return self.from_payload(
            self._port,
            await self._port.resume_run(
                run_id=self.run_id,
                resume_payload=dict(response),
                resume_outcome=outcome,
            ),
            expected_run_id=self.run_id,
            expected_deployment_id=self.deployment_id,
            operation="workflow.runs.resume",
        )

    async def trace(self, *, start: int = 0, limit: int = 25) -> TracePage:
        """Read a bounded trace page, validating bounds before remote I/O."""
        if start < 0:
            raise ValueError("start must be >= 0")
        if limit <= 0 or limit > 100:
            raise ValueError("limit must be between 1 and 100")
        decoded = decode_trace_result(
            await self._port.read_run_trace(
                run_id=self.run_id,
                trace_range=TraceRange(start=start, limit=limit),
            )
        )
        require_response_identity(
            operation="workflow.runs.trace",
            actual={
                "run_id": decoded.run_id,
                "deployment_id": decoded.deployment_id,
                "trace_start": decoded.trace_start,
                "trace_limit": decoded.trace_limit,
            },
            expected={
                "run_id": self.run_id,
                "deployment_id": self.deployment_id,
                "trace_start": start,
                "trace_limit": limit,
            },
        )
        frames = tuple(TraceEntry(**dict(frame)) for frame in (decoded.trace or ()))
        return TracePage(
            start=start,
            limit=limit,
            frames=frames,
            truncated=bool(decoded.trace_truncated),
            trace_count=decoded.trace_count,
        )
