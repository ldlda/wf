from __future__ import annotations

from dataclasses import asdict
from typing import Any, Protocol

from wf_artifacts import (
    DependencyDiagnostic,
    RunStore,
    WorkflowArtifact,
    WorkflowDeployment,
)
from wf_core import RunState

from .deployments import WorkflowDeploymentApi, _available_sources
from .models import RawWorkflowPlan
from .next_actions import NextActions
from .run_lifecycle import (
    create_pinned_environment,
    has_blocking_diagnostics,
    load_stored_run,
    mark_resume_blocked,
    persist_stopped_run,
    restore_interrupted_run,
    validate_pinned_resume_environment,
)
from .saved_subgraphs import saved_subgraph_tree_from_snapshots
from .operation_context import WorkflowOperationContext


class TraceRangeLike(Protocol):
    """Small structural trace range accepted from MCP, CLI, or HTTP adapters."""

    start: int
    limit: int


class WorkflowRunApi:
    """Deployment run lifecycle operations.

    Runtime execution stays behind WorkflowOperationContext.runtime so wf_api
    does not depend on MCP service internals.
    """

    def __init__(self, context: WorkflowOperationContext) -> None:
        self.context = context
        self.deployments = WorkflowDeploymentApi(context)

    def _run_store(self) -> RunStore:
        if self.context.run_store is None:
            raise KeyError("workflow run store is not configured")
        return self.context.run_store

    async def run_deployment(
        self,
        *,
        deployment_id: str,
        workflow_input: dict[str, Any],
        trace_range: TraceRangeLike | None = None,
    ) -> dict[str, Any]:
        deployment, artifact, diagnostics, tree = (
            self.deployments.deployment_validation(deployment_id)
        )
        if diagnostics:
            return _run_payload(
                deployment=deployment,
                artifact=artifact,
                status="unrunnable",
                diagnostics=diagnostics,
            )

        plan = _raw_plan_from_artifact(artifact)
        run = await self.context.runtime.run_workflow_from_plan(
            plan,
            workflow_input,
            deployment=deployment,
            artifact=artifact,
            saved_subgraph_tree=tree,
        )
        record = persist_stopped_run(
            store=self._run_store(),
            environment=create_pinned_environment(
                deployment=deployment,
                artifact=artifact,
                tree=tree,
            ),
            run=run,
        )
        return _run_payload(
            deployment=deployment,
            artifact=artifact,
            status=run.status.value,
            run_id=record.id,
            resume_readiness=record.resume_readiness.value,
            interrupt=_interrupt_payload(run),
            outcome=run.outcome,
            error=run.error,
            output=run.output,
            trace_count=len(run.trace),
            trace=(
                [
                    asdict(entry)
                    for entry in run.trace[
                        trace_range.start : trace_range.start + trace_range.limit
                    ]
                ]
                if trace_range is not None
                else None
            ),
            trace_start=trace_range.start if trace_range is not None else None,
            trace_limit=trace_range.limit if trace_range is not None else None,
            trace_truncated=(
                trace_range is not None
                and len(run.trace) > trace_range.start + trace_range.limit
            ),
        )

    async def resume_run(
        self,
        *,
        run_id: str,
        resume_payload: dict[str, Any],
        resume_outcome: str = "submitted",
        trace_range: TraceRangeLike | None = None,
    ) -> dict[str, Any]:
        """Resume one durable interrupted deployment run."""
        record, stopped_run = restore_interrupted_run(self._run_store(), run_id)
        environment = record.environment
        diagnostics = validate_pinned_resume_environment(
            record=record,
            sources=_available_sources(self.context.capability_sources),
        )
        if has_blocking_diagnostics(diagnostics):
            blocked = mark_resume_blocked(
                store=self._run_store(),
                record=record,
                diagnostics=diagnostics,
            )
            return _run_payload(
                deployment=environment.deployment,
                artifact=environment.root_artifact,
                status=stopped_run.status.value,
                run_id=blocked.id,
                resume_readiness=blocked.resume_readiness.value,
                interrupt=_interrupt_payload(stopped_run),
                outcome=stopped_run.outcome,
                error=stopped_run.error,
                output=stopped_run.output,
                diagnostics=diagnostics,
                trace_count=len(stopped_run.trace),
            )
        plan = _raw_plan_from_artifact(environment.root_artifact)
        tree = saved_subgraph_tree_from_snapshots(environment.child_artifacts)
        run = await self.context.runtime.resume_workflow_from_plan(
            plan,
            stopped_run,
            resume_payload=resume_payload,
            resume_outcome=resume_outcome,
            deployment=environment.deployment,
            artifact=environment.root_artifact,
            saved_subgraph_tree=tree,
        )
        next_record = persist_stopped_run(
            store=self._run_store(),
            environment=environment,
            run=run,
            run_id=run_id,
        )
        return _run_payload(
            deployment=environment.deployment,
            artifact=environment.root_artifact,
            status=run.status.value,
            run_id=next_record.id,
            resume_readiness=next_record.resume_readiness.value,
            interrupt=_interrupt_payload(run),
            outcome=run.outcome,
            error=run.error,
            output=run.output,
            trace_count=len(run.trace),
            trace=(
                [
                    asdict(entry)
                    for entry in run.trace[
                        trace_range.start : trace_range.start + trace_range.limit
                    ]
                ]
                if trace_range is not None
                else None
            ),
            trace_start=trace_range.start if trace_range is not None else None,
            trace_limit=trace_range.limit if trace_range is not None else None,
            trace_truncated=(
                trace_range is not None
                and len(run.trace) > trace_range.start + trace_range.limit
            ),
        )

    async def inspect_run(self, *, run_id: str) -> dict[str, Any]:
        """Return one durable stopped-run summary without debug trace entries."""
        record, run = load_stored_run(self._run_store(), run_id)
        environment = record.environment
        return _run_payload(
            deployment=environment.deployment,
            artifact=environment.root_artifact,
            status=record.status.value,
            run_id=record.id,
            resume_readiness=record.resume_readiness.value,
            interrupt=_interrupt_payload(run),
            outcome=run.outcome,
            error=run.error,
            output=run.output,
            diagnostics=record.diagnostics,
            trace_count=len(run.trace),
        )

    async def read_run_trace(
        self,
        *,
        run_id: str,
        trace_range: TraceRangeLike,
    ) -> dict[str, Any]:
        """Return only a caller-bounded debug trace slice from a stopped run."""
        record, run = load_stored_run(self._run_store(), run_id)
        environment = record.environment
        end = trace_range.start + trace_range.limit
        return _run_payload(
            deployment=environment.deployment,
            artifact=environment.root_artifact,
            status=record.status.value,
            run_id=record.id,
            resume_readiness=record.resume_readiness.value,
            diagnostics=record.diagnostics,
            trace_count=len(run.trace),
            trace=[asdict(entry) for entry in run.trace[trace_range.start : end]],
            trace_start=trace_range.start,
            trace_limit=trace_range.limit,
            trace_truncated=len(run.trace) > end,
        )


def _raw_plan_from_artifact(artifact: WorkflowArtifact) -> RawWorkflowPlan:
    """Validate the stored plan shape expected by the broker workflow runner."""
    return RawWorkflowPlan.model_validate(
        {
            "name": _plan_field(artifact, "name"),
            "input_schema": _plan_field(artifact, "input_schema"),
            "state_schema": _plan_field(artifact, "state_schema"),
            "output_schema": _plan_field(artifact, "output_schema"),
            "outcomes": artifact.plan.get("outcomes", ["ok"]),
            "output": artifact.plan.get("output", []),
            "start": _plan_field(artifact, "start"),
            "nodes": _plan_field(artifact, "nodes"),
            "edges": _plan_field(artifact, "edges"),
        }
    )


def _plan_field(artifact: WorkflowArtifact, field_name: str) -> Any:
    try:
        return artifact.plan[field_name]
    except KeyError as exc:
        raise ValueError(
            f"workflow artifact {artifact.id}@{artifact.version} "
            f"is missing plan field {field_name!r}"
        ) from exc


def _run_payload(
    *,
    deployment: WorkflowDeployment,
    artifact: WorkflowArtifact,
    status: str,
    run_id: str | None = None,
    resume_readiness: str | None = None,
    interrupt: dict[str, Any] | None = None,
    outcome: str | None = None,
    error: str | None = None,
    diagnostics: list[DependencyDiagnostic] | None = None,
    output: dict[str, Any] | None = None,
    trace_count: int = 0,
    trace: list[dict[str, Any]] | None = None,
    trace_start: int | None = None,
    trace_limit: int | None = None,
    trace_truncated: bool = False,
) -> dict[str, Any]:
    payload = {
        "deployment_id": deployment.id,
        "artifact_id": artifact.id,
        "artifact_version": artifact.version,
        "status": status,
        "run_id": run_id,
        "resume_readiness": resume_readiness,
        "interrupt": interrupt,
        "outcome": outcome,
        "error": error,
        "output": output,
        "diagnostics": [
            diagnostic.model_dump(mode="json") for diagnostic in diagnostics or []
        ],
        "trace_count": trace_count,
        "next_actions": NextActions.from_run_result(
            run_id=run_id,
            status=status,
            trace_count=trace_count,
            diagnostics=diagnostics or [],
        ).model_dump(mode="json"),
    }
    if trace is not None:
        # Trace entries can grow quickly, so the public run tool only includes
        # a bounded debug slice when the caller explicitly asks for a range.
        payload["trace_start"] = trace_start
        payload["trace_limit"] = trace_limit
        payload["trace"] = trace
        payload["trace_truncated"] = trace_truncated
    return payload


def _interrupt_payload(run: RunState) -> dict[str, Any] | None:
    """Return a JSON-safe interrupt payload for the current run, if paused."""
    if run.interrupt is None:
        return None
    payload = asdict(run.interrupt)
    route = payload.get("route")
    if isinstance(route, dict) and "workflow_ref" in route:
        workflow_ref = route["workflow_ref"]
        if hasattr(workflow_ref, "model_dump"):
            route["workflow_ref"] = workflow_ref.model_dump(mode="json")
    return payload
