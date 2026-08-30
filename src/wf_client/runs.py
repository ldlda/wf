"""Immutable snapshots for durable workflow runs and bounded traces."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError

from wf_api import TraceRange
from wf_artifacts import DependencyDiagnostic
from wf_core import InterruptRequest, InterruptRoute, TraceEntry, WorkflowRef

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
    operation: str = "workflow.runs.inspect",
) -> Run:
    if expected_run_id is not None and decoded.run_id != expected_run_id:
        raise InvalidResponse(
            operation=operation,
            details=(
                f"returned run {decoded.run_id!r} does not match requested "
                f"{expected_run_id!r}"
            ),
        )
    if decoded.run_id is None:
        raise DeploymentNotRunnable(
            deployment_id=decoded.deployment_id,
            diagnostics=decoded.diagnostics,
            outcome=decoded.outcome,
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
    )


@dataclass(frozen=True, slots=True)
class Run:
    """Immutable client snapshot of one durable deployment run."""

    _port: WorkflowClientPort = field(repr=False, compare=False)
    run_id: str
    deployment_id: str
    status: str
    outcome: str | None
    output: dict[str, Any] | None
    interrupt: InterruptRequest | None
    diagnostics: tuple[DependencyDiagnostic, ...]
    trace_count: int

    @classmethod
    def from_payload(
        cls,
        port: WorkflowClientPort,
        payload: object,
        *,
        expected_run_id: str | None = None,
        operation: str = "workflow.runs.inspect",
    ) -> Run:
        """Validate one run response and reconstruct its immutable snapshot."""
        return _run_from_decoded(
            port,
            decode_run_result(payload, operation=operation),
            expected_run_id=expected_run_id,
            operation=operation,
        )

    async def refresh(self) -> Run:
        """Read the current server snapshot without mutating this run."""
        return self.from_payload(
            self._port,
            await self._port.inspect_run(run_id=self.run_id),
            expected_run_id=self.run_id,
            operation="workflow.runs.inspect",
        )

    async def resume(
        self,
        response: Mapping[str, Any],
        *,
        outcome: str = "submitted",
    ) -> Run:
        """Resume an interrupted run and return the server's new snapshot."""
        if self.status != "interrupted" or self.interrupt is None:
            raise ValueError("only interrupted runs can be resumed")
        if not self.interrupt.resumable:
            raise ValueError("run interrupt is not resumable")
        return self.from_payload(
            self._port,
            await self._port.resume_run(
                run_id=self.run_id,
                resume_payload=dict(response),
                resume_outcome=outcome,
            ),
            expected_run_id=self.run_id,
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
        frames = tuple(TraceEntry(**dict(frame)) for frame in (decoded.trace or ()))
        return TracePage(
            start=decoded.trace_start if decoded.trace_start is not None else start,
            limit=decoded.trace_limit if decoded.trace_limit is not None else limit,
            frames=frames,
            truncated=bool(decoded.trace_truncated),
            trace_count=decoded.trace_count,
        )
