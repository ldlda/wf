from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from wf_artifacts import (
    AvailableCapability,
    AvailableSource,
    DependencyDiagnostic,
    DiagnosticSeverity,
    RequiredCapability,
    WorkflowArtifact,
    WorkflowDeployment,
    create_workflow_artifact_from_plan as build_workflow_artifact_from_plan,
    validate_deployment_dependencies,
)

from ..models import RawWorkflowPlan

if TYPE_CHECKING:
    from ..broker.service import WfMcpService


class WorkflowSurfaceHandlers:
    """Reusable implementation behind MCP workflow artifact tools."""

    def __init__(self, service: WfMcpService) -> None:
        self.service = service

    async def list_artifacts(self) -> dict[str, Any]:
        if self.service.artifact_store is None:
            return {"nodes": []}
        entries = [
            self.service.workflow_artifact_catalog_entry(artifact).model_dump(
                mode="json"
            )
            for artifact in self.service.artifact_store.list_artifacts()
        ]
        return {"nodes": entries}

    async def save_artifact(self, artifact: dict[str, Any]) -> dict[str, Any]:
        if self.service.artifact_store is None:
            raise KeyError("workflow artifact store is not configured")
        workflow_artifact = WorkflowArtifact.model_validate(artifact)
        self.service.artifact_store.save_artifact(workflow_artifact)
        return {
            "artifact_id": workflow_artifact.id,
            "version": workflow_artifact.version,
            "saved": True,
        }

    async def create_artifact_from_plan(
        self,
        *,
        artifact_id: str,
        version: int,
        title: str,
        plan: dict[str, Any],
        outcomes: Sequence[str],
        description: str | None = None,
        required_capabilities: dict[str, dict[str, Any]] | None = None,
        created_from_catalog_version: str | None = None,
    ) -> dict[str, Any]:
        if self.service.artifact_store is None:
            raise KeyError("workflow artifact store is not configured")
        workflow_artifact = build_workflow_artifact_from_plan(
            artifact_id=artifact_id,
            version=version,
            title=title,
            description=description,
            plan=plan,
            outcomes=tuple(outcomes),
            required_capabilities={
                name: RequiredCapability.model_validate(capability)
                for name, capability in (required_capabilities or {}).items()
            },
            created_from_catalog_version=created_from_catalog_version,
        )
        self.service.artifact_store.save_artifact(workflow_artifact)
        return {
            "artifact_id": workflow_artifact.id,
            "version": workflow_artifact.version,
            "saved": True,
        }

    async def inspect_artifact(
        self, *, artifact_id: str, version: int
    ) -> dict[str, Any]:
        if self.service.artifact_store is None:
            raise KeyError("workflow artifact store is not configured")
        artifact = self.service.artifact_store.get_artifact(artifact_id, version)
        return artifact.model_dump(mode="json")

    async def list_deployments(self) -> dict[str, Any]:
        if self.service.artifact_store is None:
            return {"deployments": []}
        return {
            "deployments": [
                deployment.model_dump(mode="json")
                for deployment in self.service.artifact_store.list_deployments()
            ]
        }

    async def save_deployment(self, deployment: dict[str, Any]) -> dict[str, Any]:
        if self.service.artifact_store is None:
            raise KeyError("workflow artifact store is not configured")
        workflow_deployment = WorkflowDeployment.model_validate(deployment)
        self.service.artifact_store.save_deployment(workflow_deployment)
        return {
            "deployment_id": workflow_deployment.id,
            "artifact_id": workflow_deployment.artifact_id,
            "artifact_version": workflow_deployment.artifact_version,
            "saved": True,
        }

    async def validate_deployment(self, *, deployment_id: str) -> dict[str, Any]:
        deployment, artifact, diagnostics = self._deployment_validation(deployment_id)
        return {
            "deployment_id": deployment.id,
            "artifact_id": artifact.id,
            "artifact_version": artifact.version,
            "status": "unrunnable" if diagnostics else "runnable",
            "diagnostics": [
                diagnostic.model_dump(mode="json") for diagnostic in diagnostics
            ],
        }

    async def run_deployment(
        self,
        *,
        deployment_id: str,
        workflow_input: dict[str, Any],
    ) -> dict[str, Any]:
        deployment, artifact, diagnostics = self._deployment_validation(deployment_id)
        if diagnostics:
            return _run_payload(
                deployment=deployment,
                artifact=artifact,
                status="unrunnable",
                diagnostics=diagnostics,
            )

        unsupported = _unsupported_interrupt_diagnostic(artifact)
        if unsupported is not None:
            return _run_payload(
                deployment=deployment,
                artifact=artifact,
                status="unsupported",
                diagnostics=[unsupported],
            )

        plan = _raw_plan_from_artifact(artifact)
        run = await self.service.run_workflow_from_plan(plan, workflow_input)
        return _run_payload(
            deployment=deployment,
            artifact=artifact,
            status=run.status.value,
            output=run.output,
            trace_count=len(run.trace),
        )

    def _deployment_validation(
        self,
        deployment_id: str,
    ) -> tuple[WorkflowDeployment, WorkflowArtifact, list[DependencyDiagnostic]]:
        if self.service.artifact_store is None:
            raise KeyError("workflow artifact store is not configured")
        deployment = self.service.artifact_store.get_deployment(deployment_id)
        artifact = self.service.artifact_store.get_artifact(
            deployment.artifact_id,
            deployment.artifact_version,
        )
        diagnostics = validate_deployment_dependencies(
            artifact=artifact,
            deployment=deployment,
            sources=_available_sources(self.service),
        )
        return deployment, artifact, diagnostics


def _available_sources(service: WfMcpService) -> list[AvailableSource]:
    """Convert broker capability sources into artifact validation snapshots."""
    sources: list[AvailableSource] = []
    for source in service.capability_sources.values():
        capabilities = {
            spec.name.rsplit(".", maxsplit=1)[-1]: AvailableCapability(
                name=spec.name.rsplit(".", maxsplit=1)[-1],
                kind="node_spec",
                input_schema_hash=None,
                output_schema_hash=None,
            )
            for spec in source.capabilities.node_specs.values()
        }
        sources.append(
            AvailableSource(
                id=source.id,
                enabled=source.enabled,
                capabilities=capabilities,
            )
        )
    return sources


def _raw_plan_from_artifact(artifact: WorkflowArtifact) -> RawWorkflowPlan:
    """Validate the stored plan shape expected by the broker workflow runner."""
    return RawWorkflowPlan(
        name=_plan_field(artifact, "name"),
        input_schema=_plan_field(artifact, "input_schema"),
        state_schema=_plan_field(artifact, "state_schema"),
        output_schema=_plan_field(artifact, "output_schema"),
        start=_plan_field(artifact, "start"),
        nodes=_plan_field(artifact, "nodes"),
        edges=_plan_field(artifact, "edges"),
    )


def _plan_field(artifact: WorkflowArtifact, field_name: str) -> Any:
    try:
        return artifact.plan[field_name]
    except KeyError as exc:
        raise ValueError(
            f"workflow artifact {artifact.id}@{artifact.version} "
            f"is missing plan field {field_name!r}"
        ) from exc


def _unsupported_interrupt_diagnostic(
    artifact: WorkflowArtifact,
) -> DependencyDiagnostic | None:
    if not any(node.get("type") == "interrupt" for node in _plan_nodes(artifact)):
        return None
    return DependencyDiagnostic(
        severity=DiagnosticSeverity.ERROR,
        code="interrupting_artifact_unsupported",
        logical_ref=f"workflow.{artifact.id}.v{artifact.version}",
        message=(
            "Running saved workflow artifacts with interrupt nodes is unsupported "
            "until nested run-state resume is implemented."
        ),
        repair_hint=(
            "Run this workflow as a top-level core workflow or remove interrupt "
            "nodes before saving it as a runnable deployment."
        ),
    )


def _plan_nodes(artifact: WorkflowArtifact) -> list[dict[str, Any]]:
    nodes = artifact.plan.get("nodes", [])
    return [node for node in nodes if isinstance(node, dict)]


def _run_payload(
    *,
    deployment: WorkflowDeployment,
    artifact: WorkflowArtifact,
    status: str,
    diagnostics: list[DependencyDiagnostic] | None = None,
    output: dict[str, Any] | None = None,
    trace_count: int = 0,
) -> dict[str, Any]:
    return {
        "deployment_id": deployment.id,
        "artifact_id": artifact.id,
        "artifact_version": artifact.version,
        "status": status,
        "output": output,
        "diagnostics": [
            diagnostic.model_dump(mode="json") for diagnostic in diagnostics or []
        ],
        "trace_count": trace_count,
    }
