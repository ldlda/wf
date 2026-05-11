from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP
from wf_artifacts import (
    AvailableCapability,
    AvailableSource,
    DependencyDiagnostic,
    DiagnosticSeverity,
    WorkflowArtifact,
    WorkflowDeployment,
    validate_deployment_dependencies,
)

from ..models import RawWorkflowPlan
from .service import WfMcpService


def register_artifact_tools(server: FastMCP, service: WfMcpService) -> None:
    """Register stable MCP tools for saved workflow artifact inspection."""

    @server.tool()
    async def list_workflow_artifacts() -> dict[str, Any]:
        if service.artifact_store is None:
            return {"nodes": []}
        entries = [
            service.workflow_artifact_catalog_entry(artifact).model_dump(mode="json")
            for artifact in service.artifact_store.list_artifacts()
        ]
        return {"nodes": entries}

    @server.tool()
    async def save_workflow_artifact(artifact: dict[str, Any]) -> dict[str, Any]:
        if service.artifact_store is None:
            raise KeyError("workflow artifact store is not configured")
        workflow_artifact = WorkflowArtifact.model_validate(artifact)
        service.artifact_store.save_artifact(workflow_artifact)
        return {
            "artifact_id": workflow_artifact.id,
            "version": workflow_artifact.version,
            "saved": True,
        }

    @server.tool()
    async def inspect_workflow_artifact(
        artifact_id: str,
        version: int,
    ) -> dict[str, Any]:
        if service.artifact_store is None:
            raise KeyError("workflow artifact store is not configured")
        artifact = service.artifact_store.get_artifact(artifact_id, version)
        return artifact.model_dump(mode="json")

    @server.tool()
    async def list_workflow_deployments() -> dict[str, Any]:
        if service.artifact_store is None:
            return {"deployments": []}
        return {
            "deployments": [
                deployment.model_dump(mode="json")
                for deployment in service.artifact_store.list_deployments()
            ]
        }

    @server.tool()
    async def save_workflow_deployment(deployment: dict[str, Any]) -> dict[str, Any]:
        if service.artifact_store is None:
            raise KeyError("workflow artifact store is not configured")
        workflow_deployment = WorkflowDeployment.model_validate(deployment)
        service.artifact_store.save_deployment(workflow_deployment)
        return {
            "deployment_id": workflow_deployment.id,
            "artifact_id": workflow_deployment.artifact_id,
            "artifact_version": workflow_deployment.artifact_version,
            "saved": True,
        }

    @server.tool()
    async def validate_workflow_deployment(deployment_id: str) -> dict[str, Any]:
        if service.artifact_store is None:
            raise KeyError("workflow artifact store is not configured")
        deployment = service.artifact_store.get_deployment(deployment_id)
        artifact = service.artifact_store.get_artifact(
            deployment.artifact_id,
            deployment.artifact_version,
        )
        diagnostics = validate_deployment_dependencies(
            artifact=artifact,
            deployment=deployment,
            sources=_available_sources(service),
        )
        return {
            "deployment_id": deployment.id,
            "artifact_id": artifact.id,
            "artifact_version": artifact.version,
            "status": "unrunnable" if diagnostics else "runnable",
            "diagnostics": [
                diagnostic.model_dump(mode="json") for diagnostic in diagnostics
            ],
        }

    @server.tool()
    async def run_workflow_deployment(
        deployment_id: str,
        workflow_input: dict[str, Any],
    ) -> dict[str, Any]:
        if service.artifact_store is None:
            raise KeyError("workflow artifact store is not configured")

        deployment = service.artifact_store.get_deployment(deployment_id)
        artifact = service.artifact_store.get_artifact(
            deployment.artifact_id,
            deployment.artifact_version,
        )
        diagnostics = validate_deployment_dependencies(
            artifact=artifact,
            deployment=deployment,
            sources=_available_sources(service),
        )
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
        run = await service.run_workflow_from_plan(plan, workflow_input)
        return _run_payload(
            deployment=deployment,
            artifact=artifact,
            status=run.status.value,
            output=run.output,
            trace_count=len(run.trace),
        )


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
