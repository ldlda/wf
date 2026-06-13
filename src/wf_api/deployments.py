"""Saved deployment operations and dependency validation."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from wf_artifacts import (
    AvailableCapability,
    AvailableSource,
    DependencyDiagnostic,
    WorkflowArtifact,
    WorkflowDeployment,
    validate_deployment_dependencies,
)
from wf_platform import CapabilitySource, hash_json_schema

from .next_actions import NextActions
from .operation_context import WorkflowOperationContext
from .saved_subgraphs import resolve_saved_subgraph_tree, validate_saved_subgraph_tree


class WorkflowDeploymentApi:
    """Saved deployment operations and dependency validation."""

    def __init__(self, context: WorkflowOperationContext) -> None:
        self.context = context

    def _artifact_store(self):
        if self.context.artifact_store is None:
            raise KeyError("workflow artifact store is not configured")
        return self.context.artifact_store

    async def list_deployments(self) -> dict[str, Any]:
        if self.context.artifact_store is None:
            return {"deployments": []}
        return {
            "deployments": [
                _deployment_summary(deployment)
                for deployment in self.context.artifact_store.list_deployments()
            ]
        }

    async def inspect_deployment(self, *, deployment_id: str) -> dict[str, Any]:
        return (
            self._artifact_store().get_deployment(deployment_id).model_dump(mode="json")
        )

    async def save_deployment(self, deployment: dict[str, Any]) -> dict[str, Any]:
        workflow_deployment = WorkflowDeployment.model_validate(deployment)
        self._artifact_store().save_deployment(workflow_deployment)
        self.context.events.record_workflow_event(
            "workflow_deployment_saved",
            capability_id=f"deployment.{workflow_deployment.id}",
            payload={
                "deployment_id": workflow_deployment.id,
                "artifact_id": workflow_deployment.artifact_id,
                "artifact_version": workflow_deployment.artifact_version,
            },
        )
        return {
            "deployment_id": workflow_deployment.id,
            "artifact_id": workflow_deployment.artifact_id,
            "artifact_version": workflow_deployment.artifact_version,
            "saved": True,
        }

    async def delete_deployment(self, *, deployment_id: str) -> dict[str, Any]:
        """Delete one mutable deployment environment binding."""
        self._artifact_store().delete_deployment(deployment_id)
        self.context.events.record_workflow_event(
            "workflow_deployment_deleted",
            capability_id=f"deployment.{deployment_id}",
            payload={"deployment_id": deployment_id},
        )
        return {"deployment_id": deployment_id, "deleted": True}

    async def validate_deployment(
        self,
        *,
        deployment_id: str,
        live_check: bool = False,
    ) -> dict[str, Any]:
        deployment, artifact, diagnostics, tree = self.deployment_validation(
            deployment_id
        )
        if live_check and self.context.live_sources is not None:
            diagnostics.extend(
                await self.context.live_sources.deployment_diagnostics(
                    deployment=deployment,
                    artifacts=[artifact, *tree.artifacts_by_ref.values()],
                )
            )
        return {
            "deployment_id": deployment.id,
            "artifact_id": artifact.id,
            "artifact_version": artifact.version,
            "status": "unrunnable" if diagnostics else "runnable",
            "diagnostics": [
                diagnostic.model_dump(mode="json") for diagnostic in diagnostics
            ],
            "next_actions": NextActions.from_deployment_validation(
                deployment_id=deployment.id,
                diagnostics=diagnostics,
            ).model_dump(mode="json"),
        }

    def deployment_validation(
        self,
        deployment_id: str,
    ) -> tuple[
        WorkflowDeployment,
        WorkflowArtifact,
        list[DependencyDiagnostic],
        Any,  # SavedSubgraphTree
    ]:
        store = self._artifact_store()
        deployment = store.get_deployment(deployment_id)
        artifact = store.get_artifact(
            deployment.artifact_id,
            deployment.artifact_version,
        )
        available_sources = _available_sources(self.context.specs.capability_sources)
        diagnostics = validate_deployment_dependencies(
            artifact=artifact,
            deployment=deployment,
            sources=available_sources,
        )
        tree = resolve_saved_subgraph_tree(
            root_artifact=artifact,
            artifact_store=store,
        )
        diagnostics.extend(
            validate_saved_subgraph_tree(
                tree=tree,
                deployment=deployment,
                sources=available_sources,
            )
        )
        return deployment, artifact, diagnostics, tree


def _available_sources(
    capability_sources: Mapping[str, CapabilitySource],
) -> list[AvailableSource]:
    """Convert broker capability sources into artifact validation snapshots."""
    sources: list[AvailableSource] = []
    for source in capability_sources.values():
        node_spec_details = {
            detail.name: detail
            for detail in source.as_inventory().capabilities.node_spec_details
        }
        capabilities = {
            capability_name: AvailableCapability(
                name=capability_name,
                kind="node_spec",
                input_schema_hash=hash_json_schema(detail.input_schema),
                output_schema_hash=hash_json_schema(detail.output_schema),
            )
            for spec in source.capabilities.node_specs.values()
            if (capability_name := _capability_name(spec.name)) is not None
            if (detail := node_spec_details.get(spec.name)) is not None
        }
        capabilities.update(
            {
                capability_name: AvailableCapability(
                    name=capability_name,
                    kind="reducer",
                )
                for reducer in source.capabilities.reducers.values()
                if (capability_name := _capability_name(reducer.name)) is not None
            }
        )
        sources.append(
            AvailableSource(
                id=source.id,
                enabled=source.enabled,
                platform=source.policy.platform,
                capabilities=capabilities,
            )
        )
    return sources


def _capability_name(qualified_name: str) -> str | None:
    """Return the local name of one qualified capability ref if it is valid."""
    from wf_api.refs import parse_workflow_surface_capability_id
    from wf_artifacts import WorkflowCapabilityRef

    try:
        parsed = parse_workflow_surface_capability_id(qualified_name)
    except ValueError:
        return None
    if isinstance(parsed, WorkflowCapabilityRef):
        return None
    return parsed.name


def _deployment_summary(deployment: WorkflowDeployment) -> dict[str, Any]:
    """Return compact deployment metadata for progressive list responses."""
    return {
        "id": deployment.id,
        "artifact_id": deployment.artifact_id,
        "artifact_version": deployment.artifact_version,
        "binding_count": len(deployment.binding_map()),
        "drift_policy": deployment.drift_policy.value,
    }


__all__ = [
    "WorkflowDeploymentApi",
]
