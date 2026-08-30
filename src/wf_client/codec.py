"""Validated conversions from workflow API wire payloads to domain values."""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import fields as dataclass_fields
from typing import Any, TypeVar

from pydantic import BaseModel, TypeAdapter, ValidationError

from wf_api.models import (
    CapabilityCallResult,
    DependencyDiagnosticPayload,
    InspectCapabilityResult,
    ListCapabilitiesResult,
    ListDeploymentsResult,
    RawWorkflowPlan,
    RunResult,
    RunTraceResult,
    ValidateArtifactPlanResult,
    ValidateDeploymentResult,
    WorkflowArtifactPayload,
    WorkflowDeploymentPayload,
)
from wf_artifacts.models import (
    DependencyDiagnostic,
    WorkflowArtifact,
    WorkflowDeployment,
)
from wf_core.models.workflow import Workflow

from .errors import InvalidResponse


@dataclass(frozen=True, slots=True)
class _DecodedRunFields:
    """Domain-shaped run fields shared by normal and trace responses."""

    artifact_id: str
    artifact_version: int
    deployment_id: str
    status: str
    run_id: str | None
    resume_readiness: str | None
    interrupt: dict[str, Any] | None
    outcome: str | None
    error: str | None
    output: dict[str, Any] | None
    trace_count: int
    diagnostics: tuple[DependencyDiagnostic, ...]
    next_actions: dict[str, Any]
    trace: tuple[dict[str, Any], ...] | None = None
    trace_start: int | None = None
    trace_limit: int | None = None
    trace_truncated: bool | None = None


@dataclass(frozen=True, slots=True)
class DecodedRunResult(_DecodedRunFields):
    """Validated run result without exposing a wire ``TypedDict``."""


@dataclass(frozen=True, slots=True)
class DecodedTracePage(_DecodedRunFields):
    """Validated bounded trace result without exposing wire dictionaries."""


_PayloadT = TypeVar("_PayloadT")


def _validate(payload: object, schema: object, operation: str) -> _PayloadT:
    try:
        return TypeAdapter(schema).validate_python(payload)
    except (TypeError, ValueError, ValidationError) as exc:
        raise InvalidResponse(operation=operation, details=str(exc)) from exc


def decode_capability_inspect(payload: object) -> InspectCapabilityResult:
    """Validate one capability contract returned by discovery inspection."""
    return _validate(
        payload,
        InspectCapabilityResult,
        "workflow.capabilities.inspect",
    )


def decode_capability_call(payload: object) -> CapabilityCallResult:
    """Validate one direct capability-call result at the transport boundary."""
    return _validate(
        payload,
        CapabilityCallResult,
        "workflow.capabilities.call",
    )


def decode_capability_diagnostics(
    payload: object,
) -> tuple[DependencyDiagnostic, ...]:
    """Decode diagnostics attached to a capability invocation."""
    return _decode_dependency_diagnostics(
        payload,
        "workflow.capabilities.call",
    )


def decode_capabilities_page(payload: object) -> ListCapabilitiesResult:
    """Validate one cursor-paged capability discovery response."""
    return _validate(
        payload,
        ListCapabilitiesResult,
        "workflow.capabilities.list",
    )


def decode_validate_artifact_plan(payload: object) -> ValidateArtifactPlanResult:
    """Validate a non-persisting artifact-plan response at the client boundary."""
    return _validate(
        payload,
        ValidateArtifactPlanResult,
        "workflow.artifacts.validate_plan",
    )


_ModelT = TypeVar("_ModelT", bound=BaseModel)


def _model_validate(model: type[_ModelT], payload: object, operation: str) -> _ModelT:
    try:
        # Pydantic models are the canonical domain validation boundary. This
        # helper keeps all malformed-response errors tied to their operation.
        return model.model_validate(payload)
    except (TypeError, ValueError, ValidationError) as exc:
        raise InvalidResponse(operation=operation, details=str(exc)) from exc


def decode_workflow_artifact(
    payload: object,
) -> tuple[WorkflowArtifact, Workflow]:
    """Validate an artifact envelope and reconstruct its executable workflow."""
    operation = "workflow.artifacts.inspect"
    wire = _validate(payload, WorkflowArtifactPayload, operation)
    artifact = _model_validate(WorkflowArtifact, wire, operation)
    raw_plan = _model_validate(RawWorkflowPlan, wire["plan"], operation)
    workflow_payload = raw_plan.model_dump(mode="python", by_alias=True)
    # Raw artifact plans normally omit node definitions because the server
    # inventories remote contracts. Preserve them when a caller supplies them
    # so an inspect/edit/save round trip remains lossless.
    raw_node_defs = wire["plan"].get("node_defs")
    if isinstance(raw_node_defs, list):
        workflow_payload["node_defs"] = raw_node_defs
    workflow = _model_validate(Workflow, workflow_payload, operation)
    return artifact, workflow


def decode_deployment(payload: object) -> WorkflowDeployment:
    """Validate and reconstruct one immutable deployment model."""
    operation = "workflow.deployments.inspect"
    wire = _validate(payload, WorkflowDeploymentPayload, operation)
    return _model_validate(WorkflowDeployment, wire, operation)


def decode_deployments(payload: object) -> ListDeploymentsResult:
    """Validate compact deployment discovery rows at the client boundary."""
    return _validate(payload, ListDeploymentsResult, "workflow.deployments.list")


def decode_deployment_validation(payload: object) -> ValidateDeploymentResult:
    """Validate one deployment readiness response."""
    return _validate(
        payload,
        ValidateDeploymentResult,
        "workflow.deployments.validate",
    )


def decode_dependency_diagnostics(
    payload: object,
) -> tuple[DependencyDiagnostic, ...]:
    """Decode deployment diagnostics into domain models."""
    return _decode_dependency_diagnostics(payload, "workflow.deployments.validate")


def _decode_dependency_diagnostics(
    payload: object,
    operation: str,
) -> tuple[DependencyDiagnostic, ...]:
    wire = _validate(payload, list[DependencyDiagnosticPayload], operation)
    return tuple(
        _model_validate(DependencyDiagnostic, diagnostic, operation)
        for diagnostic in wire
    )


def _decode_run_fields(
    wire: RunResult | RunTraceResult,
    *,
    trace_required: bool,
    operation: str,
) -> _DecodedRunFields:
    diagnostics = _decode_dependency_diagnostics(wire["diagnostics"], operation)
    raw_trace = wire.get("trace")
    trace = None
    if raw_trace is not None:
        # Copy validated TypedDict values into ordinary dictionaries at the
        # boundary so callers never receive transport DTO instances/types.
        trace = tuple(dict(entry) for entry in raw_trace)
    if trace_required and trace is None:
        # RunTraceResult validation makes this unreachable; retain a defensive
        # guard should its contract evolve.
        raise InvalidResponse(
            operation=operation,
            details="trace result did not include a trace page",
        )
    return _DecodedRunFields(
        artifact_id=wire["artifact_id"],
        artifact_version=wire["artifact_version"],
        deployment_id=wire["deployment_id"],
        status=wire["status"],
        run_id=wire["run_id"],
        resume_readiness=wire["resume_readiness"],
        interrupt=dict(wire["interrupt"]) if wire["interrupt"] is not None else None,
        outcome=wire["outcome"],
        error=wire["error"],
        output=dict(wire["output"]) if wire["output"] is not None else None,
        trace_count=wire["trace_count"],
        diagnostics=diagnostics,
        next_actions=dict(wire["next_actions"]),
        trace=trace,
        trace_start=wire.get("trace_start"),
        trace_limit=wire.get("trace_limit"),
        trace_truncated=wire.get("trace_truncated"),
    )


def decode_run_result(payload: object) -> DecodedRunResult:
    """Validate and decode a start/inspect/resume run response."""
    operation = "workflow.runs.inspect"
    wire = _validate(payload, RunResult, operation)
    fields = _decode_run_fields(
        wire,
        trace_required=False,
        operation=operation,
    )
    return DecodedRunResult(
        *(getattr(fields, field.name) for field in dataclass_fields(_DecodedRunFields))
    )


def decode_trace_result(payload: object) -> DecodedTracePage:
    """Validate and decode a bounded run trace response."""
    operation = "workflow.runs.trace"
    wire = _validate(payload, RunTraceResult, operation)
    fields = _decode_run_fields(
        wire,
        trace_required=True,
        operation=operation,
    )
    return DecodedTracePage(
        *(getattr(fields, field.name) for field in dataclass_fields(_DecodedRunFields))
    )
