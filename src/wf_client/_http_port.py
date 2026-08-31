"""HTTP client-port adapter that exposes only public ``wf_client`` errors."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from json import JSONDecodeError
from typing import Any, Literal, TypeVar

import httpx

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
from wf_transport_rpc_http import RpcWorkflowApiClient
from wf_transport_rpc_http.client.base import RpcProtocolError

from .errors import (
    ArtifactNotFound,
    ArtifactVersionConflict,
    CapabilityNotFound,
    DeploymentNotRunnable,
    DeploymentRequired,
    ProtocolError,
    RevisionConflict,
    TransportError,
    WorkflowClientError,
)

_ResultT = TypeVar("_ResultT")


def _server_detail(error: RpcProtocolError) -> tuple[str | None, str]:
    data = error.data
    if not isinstance(data, dict):
        return error.code if isinstance(error.code, str) else None, error.message
    code = data.get("code")
    detail = data.get("message")
    return (
        (
            code
            if isinstance(code, str)
            else error.code
            if isinstance(error.code, str)
            else None
        ),
        detail if isinstance(detail, str) else error.message,
    )


def _known_protocol_error(
    operation: str,
    error: RpcProtocolError,
) -> WorkflowClientError | None:
    """Translate only stable codes or exact legacy missing-resource signals."""
    code, detail = _server_detail(error)
    normalized = code.casefold() if code is not None else ""
    if normalized in {"capability_not_found", "capabilitynotfound"}:
        return CapabilityNotFound(detail)
    if normalized in {"artifact_not_found", "artifactnotfound"}:
        return ArtifactNotFound(detail)
    if normalized in {"artifact_version_conflict", "artifactversionconflict"}:
        return ArtifactVersionConflict(detail)
    if normalized in {"revision_conflict", "revisionconflict"}:
        return RevisionConflict(detail)
    if normalized in {"deployment_required", "deploymentrequired"}:
        return DeploymentRequired()
    if normalized in {"deployment_not_runnable", "deploymentnotrunnable"}:
        return DeploymentNotRunnable(error=detail)

    # The current RPC server reports expected application exception class names
    # in ``data.code``. A generic KeyError is safe to specialize only when both
    # the operation and its exact resource phrase agree.
    if code == "KeyError":
        if operation.startswith("workflow.capabilities.") and (
            "unknown workflow capability" in detail
        ):
            return CapabilityNotFound(detail)
        if operation == "workflow.artifacts.inspect" and (
            "unknown workflow artifact" in detail
        ):
            return ArtifactNotFound(detail)
    return None


@dataclass(slots=True)
class PublicErrorWorkflowClientPort:
    """Delegate RPC operations while preventing transport exception leakage."""

    _rpc: RpcWorkflowApiClient

    async def _invoke(
        self,
        operation: str,
        call: Callable[..., Awaitable[_ResultT]],
        /,
        **params: Any,
    ) -> _ResultT:
        try:
            return await call(**params)
        except RpcProtocolError as exc:
            known = _known_protocol_error(operation, exc)
            if known is not None:
                raise known from exc
            raise ProtocolError(exc.code, exc.message, exc.data) from exc
        except (httpx.TransportError, httpx.HTTPStatusError, JSONDecodeError) as exc:
            raise TransportError(f"{operation} transport failed: {exc}") from exc
        except RuntimeError as exc:
            # The RPC transport uses RuntimeError only when a decoded JSON-RPC
            # result is not an object. That is a protocol failure, not a public
            # transport implementation detail.
            raise ProtocolError(None, f"{operation}: {exc}") from exc

    async def list_capabilities(
        self,
        *,
        query: str | None = None,
        source_id: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> ListCapabilitiesResult:
        return await self._invoke(
            "workflow.capabilities.list",
            self._rpc.list_capabilities,
            query=query,
            source_id=source_id,
            cursor=cursor,
            limit=limit,
        )

    async def inspect_capability(
        self, *, qualified_name: str
    ) -> InspectCapabilityResult:
        return await self._invoke(
            "workflow.capabilities.inspect",
            self._rpc.inspect_capability,
            qualified_name=qualified_name,
        )

    async def call_capability(
        self,
        *,
        qualified_name: str,
        payload: dict[str, Any],
        deployment_id: str | None = None,
    ) -> CapabilityCallResult:
        return await self._invoke(
            "workflow.capabilities.call",
            self._rpc.call_capability,
            qualified_name=qualified_name,
            payload=payload,
            deployment_id=deployment_id,
        )

    async def inspect_artifact(
        self, *, artifact_id: str, version: int
    ) -> WorkflowArtifactPayload:
        return await self._invoke(
            "workflow.artifacts.inspect",
            self._rpc.inspect_artifact,
            artifact_id=artifact_id,
            version=version,
        )

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
    ) -> SaveArtifactResult:
        return await self._invoke(
            "workflow.artifacts.create_from_plan",
            self._rpc.create_artifact_from_plan,
            artifact_id=artifact_id,
            version=version,
            title=title,
            plan=plan,
            outcomes=outcomes,
            kind=kind,
            description=description,
            required_capabilities=required_capabilities,
            source_bindings=source_bindings,
            created_from_catalog_version=created_from_catalog_version,
        )

    async def validate_artifact_plan(
        self,
        *,
        plan: dict[str, Any],
        outcomes: Sequence[str],
        required_capabilities: dict[str, dict[str, Any]] | None = None,
        source_bindings: dict[str, str] | None = None,
    ) -> ValidateArtifactPlanResult:
        return await self._invoke(
            "workflow.artifacts.validate_plan",
            self._rpc.validate_artifact_plan,
            plan=plan,
            outcomes=outcomes,
            required_capabilities=required_capabilities,
            source_bindings=source_bindings,
        )

    async def list_deployments(self) -> ListDeploymentsResult:
        return await self._invoke(
            "workflow.deployments.list",
            self._rpc.list_deployments,
        )

    async def inspect_deployment(
        self, *, deployment_id: str
    ) -> WorkflowDeploymentPayload:
        return await self._invoke(
            "workflow.deployments.inspect",
            self._rpc.inspect_deployment,
            deployment_id=deployment_id,
        )

    async def save_deployment(self, deployment: dict[str, Any]) -> SaveDeploymentResult:
        return await self._invoke(
            "workflow.deployments.save",
            self._rpc.save_deployment,
            deployment=deployment,
        )

    async def validate_deployment(
        self, *, deployment_id: str, live_check: bool = False
    ) -> ValidateDeploymentResult:
        return await self._invoke(
            "workflow.deployments.validate",
            self._rpc.validate_deployment,
            deployment_id=deployment_id,
            live_check=live_check,
        )

    async def run_deployment(
        self,
        *,
        deployment_id: str,
        workflow_input: dict[str, Any],
        trace_range: TraceRangeLike | None = None,
    ) -> RunResult:
        return await self._invoke(
            "workflow.runs.start",
            self._rpc.run_deployment,
            deployment_id=deployment_id,
            workflow_input=workflow_input,
            trace_range=trace_range,
        )

    async def inspect_run(self, *, run_id: str) -> RunResult:
        return await self._invoke(
            "workflow.runs.inspect",
            self._rpc.inspect_run,
            run_id=run_id,
        )

    async def resume_run(
        self,
        *,
        run_id: str,
        resume_payload: dict[str, Any],
        resume_outcome: str = "submitted",
        trace_range: TraceRangeLike | None = None,
    ) -> RunResult:
        return await self._invoke(
            "workflow.runs.resume",
            self._rpc.resume_run,
            run_id=run_id,
            resume_payload=resume_payload,
            resume_outcome=resume_outcome,
            trace_range=trace_range,
        )

    async def read_run_trace(
        self, *, run_id: str, trace_range: TraceRangeLike
    ) -> RunTraceResult:
        return await self._invoke(
            "workflow.runs.trace",
            self._rpc.read_run_trace,
            run_id=run_id,
            trace_range=trace_range,
        )
