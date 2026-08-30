"""Immutable deployment snapshots and strict artifact deployment selection."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from wf_artifacts import DependencyDiagnostic, DriftPolicy, WorkflowDeployment

from .codec import (
    decode_dependency_diagnostics,
    decode_deployment,
    decode_deployment_validation,
    decode_deployments,
)
from .errors import DeploymentNotRunnable, DeploymentRequired, InvalidResponse
from .protocols import WorkflowClientPort
from .runs import Run


@dataclass(frozen=True, slots=True)
class DeploymentValidation:
    """Server readiness result for one saved deployment snapshot."""

    deployment_id: str
    artifact_id: str
    artifact_version: int
    status: str
    diagnostics: tuple[DependencyDiagnostic, ...]

    @property
    def runnable(self) -> bool:
        return self.status == "runnable"


@dataclass(frozen=True, slots=True)
class Deployment:
    """Immutable snapshot of one configured artifact deployment."""

    _port: WorkflowClientPort = field(repr=False, compare=False)
    model: WorkflowDeployment
    diagnostics: tuple[DependencyDiagnostic, ...] = ()
    runnable: bool | None = None

    @classmethod
    def from_payload(cls, port: WorkflowClientPort, payload: object) -> Deployment:
        return cls(_port=port, model=decode_deployment(payload))

    @property
    def deployment_id(self) -> str:
        return self.model.id

    @property
    def artifact_id(self) -> str:
        return self.model.artifact_id

    @property
    def artifact_version(self) -> int:
        return self.model.artifact_version

    @property
    def bindings(self) -> dict[str, str]:
        return self.model.binding_map()

    @property
    def drift_policy(self) -> DriftPolicy:
        return self.model.drift_policy

    async def validate(self) -> DeploymentValidation:
        payload = await self._port.validate_deployment(
            deployment_id=self.deployment_id,
        )
        result = decode_deployment_validation(payload)
        if result["deployment_id"] != self.deployment_id:
            raise InvalidResponse(
                operation="workflow.deployments.validate",
                details=(
                    f"validated deployment {result['deployment_id']!r} does not "
                    f"match requested {self.deployment_id!r}"
                ),
            )
        diagnostics = decode_dependency_diagnostics(result["diagnostics"])
        return DeploymentValidation(
            deployment_id=result["deployment_id"],
            artifact_id=result["artifact_id"],
            artifact_version=result["artifact_version"],
            status=result["status"],
            diagnostics=diagnostics,
        )

    async def run(self, workflow_input: Mapping[str, Any]) -> Run:
        from .codec import decode_run_result
        from .runs import _run_from_decoded

        decoded = decode_run_result(
            await self._port.run_deployment(
                deployment_id=self.deployment_id,
                workflow_input=dict(workflow_input),
            )
        )
        if decoded.run_id is None or decoded.status in {"unrunnable", "rejected"}:
            raise DeploymentNotRunnable(
                deployment_id=self.deployment_id,
                diagnostics=decoded.diagnostics,
                outcome=decoded.outcome,
                error=decoded.error,
            )
        return _run_from_decoded(self._port, decoded)


def _decode_summaries(payload: object) -> list[dict[str, Any]]:
    """Validate list metadata while keeping summaries as local dictionaries."""
    result = decode_deployments(payload)
    return [dict(item) for item in result["deployments"]]


async def run_artifact(
    artifact: Any,
    workflow_input: Mapping[str, Any],
    *,
    deployment_id: str | None,
    bindings: Mapping[str, str] | None,
    drift_policy: DriftPolicy | str,
) -> Run:
    """Apply the artifact's strict deployment-selection policy."""
    if deployment_id is not None:
        deployment = Deployment.from_payload(
            artifact._port,
            await artifact._port.inspect_deployment(deployment_id=deployment_id),
        )
        if deployment.deployment_id != deployment_id:
            raise InvalidResponse(
                operation="workflow.deployments.inspect",
                details=(
                    f"inspected deployment {deployment.deployment_id!r} does not "
                    f"match requested {deployment_id!r}"
                ),
            )
        return await deployment.run(workflow_input)

    summaries = _decode_summaries(await artifact._port.list_deployments())
    matches = sorted(
        (
            summary
            for summary in summaries
            if summary["artifact_id"] == artifact.artifact.id
            and summary["artifact_version"] == artifact.artifact.version
        ),
        key=lambda summary: summary["id"],
    )
    if len(matches) > 1:
        raise DeploymentRequired(
            candidate_deployment_ids=tuple(summary["id"] for summary in matches)
        )
    default_id = f"{artifact.artifact.id}.v{artifact.artifact.version}.default"
    if not matches:
        conflicting = next(
            (
                summary
                for summary in summaries
                if summary["id"] == default_id
                and (
                    summary["artifact_id"] != artifact.artifact.id
                    or summary["artifact_version"] != artifact.artifact.version
                )
            ),
            None,
        )
        if conflicting is not None:
            raise DeploymentRequired(candidate_deployment_ids=(default_id,))
        deployment = await artifact.deploy(
            default_id,
            bindings=bindings,
            drift_policy=drift_policy,
        )
        if deployment.runnable is not True:
            raise DeploymentRequired(diagnostics=deployment.diagnostics)
        return await deployment.run(workflow_input)

    deployment = Deployment.from_payload(
        artifact._port,
        await artifact._port.inspect_deployment(deployment_id=matches[0]["id"]),
    )
    if deployment.deployment_id != matches[0]["id"]:
        raise InvalidResponse(
            operation="workflow.deployments.inspect",
            details=(
                f"inspected deployment {deployment.deployment_id!r} does not "
                f"match requested {matches[0]['id']!r}"
            ),
        )
    return await deployment.run(workflow_input)
