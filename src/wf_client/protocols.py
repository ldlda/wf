"""The narrow transport port consumed by rich workflow client objects."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Literal, Protocol

from wf_api.models import (
    CapabilityCallResult,
    InspectCapabilityResult,
    ListCapabilitiesResult,
    ListDeploymentsResult,
    RunResult,
    RunTraceResult,
    SaveArtifactResult,
    SaveDeploymentResult,
    ValidateArtifactPlanResult,
    ValidateDeploymentResult,
    WorkflowArtifactPayload,
    WorkflowDeploymentPayload,
)
from wf_api.runs import TraceRangeLike


class WorkflowClientPort(Protocol):
    """Minimum operation port required by transport-independent rich objects.

    This deliberately does not inherit ``WorkflowApiSurface``: that protocol
    includes draft, source-admin, registry, and other operations that rich
    workflow objects do not need.
    """

    async def list_capabilities(
        self,
        *,
        query: str | None = None,
        source_id: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> ListCapabilitiesResult: ...

    async def inspect_capability(
        self,
        *,
        qualified_name: str,
    ) -> InspectCapabilityResult: ...

    async def call_capability(
        self,
        *,
        qualified_name: str,
        payload: dict[str, Any],
        deployment_id: str | None = None,
    ) -> CapabilityCallResult: ...

    async def inspect_artifact(
        self,
        *,
        artifact_id: str,
        version: int,
    ) -> WorkflowArtifactPayload: ...

    async def create_artifact_from_plan(
        self,
        *,
        artifact_id: str,
        version: int,
        title: str,
        plan: dict[str, Any],
        outcomes: Sequence[str],
        kind: Literal["workflow", "wrapper"] = "workflow",
        description: str | None = None,
        required_capabilities: dict[str, dict[str, Any]] | None = None,
        source_bindings: dict[str, str] | None = None,
        created_from_catalog_version: str | None = None,
    ) -> SaveArtifactResult: ...

    async def validate_artifact_plan(
        self,
        *,
        plan: dict[str, Any],
        outcomes: Sequence[str],
        required_capabilities: dict[str, dict[str, Any]] | None = None,
        source_bindings: dict[str, str] | None = None,
    ) -> ValidateArtifactPlanResult: ...

    async def list_deployments(self) -> ListDeploymentsResult: ...

    async def inspect_deployment(
        self,
        *,
        deployment_id: str,
    ) -> WorkflowDeploymentPayload: ...

    async def save_deployment(
        self,
        deployment: dict[str, Any],
    ) -> SaveDeploymentResult: ...

    async def validate_deployment(
        self,
        *,
        deployment_id: str,
        live_check: bool = False,
    ) -> ValidateDeploymentResult: ...

    async def run_deployment(
        self,
        *,
        deployment_id: str,
        workflow_input: dict[str, Any],
        trace_range: TraceRangeLike | None = None,
    ) -> RunResult: ...

    async def inspect_run(self, *, run_id: str) -> RunResult: ...

    async def resume_run(
        self,
        *,
        run_id: str,
        resume_payload: dict[str, Any],
        resume_outcome: str = "submitted",
        trace_range: TraceRangeLike | None = None,
    ) -> RunResult: ...

    async def read_run_trace(
        self,
        *,
        run_id: str,
        trace_range: TraceRangeLike,
    ) -> RunTraceResult: ...
