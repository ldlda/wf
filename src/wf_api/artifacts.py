"""Saved workflow artifact operations.

Event construction is intentionally delegated through
WorkflowOperationContext so this module stays protocol-neutral.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from wf_artifacts import (
    ArtifactKind,
    RequiredCapability,
    WorkflowArtifact,
    artifact_catalog_entry,
)
from wf_artifacts import (
    create_workflow_artifact_from_plan as build_workflow_artifact_from_plan,
)
from wf_platform import CapabilitySource

from .artifact_refs import artifact_capability_id
from .capability_requirements import observed_node_specs
from .drafts import WorkflowDraftApi
from .listing import matches_query, paged_list_payload
from .models import RawWorkflowPlan
from .operation_context import WorkflowOperationContext


class WorkflowArtifactApi:
    """Saved workflow artifact operations.

    Event construction is intentionally delegated through
    WorkflowOperationContext so this module stays protocol-neutral.
    """

    def __init__(self, context: WorkflowOperationContext) -> None:
        self.context = context
        self.drafts = WorkflowDraftApi(context)

    def _artifact_store(self):
        if self.context.artifact_store is None:
            raise KeyError("workflow artifact store is not configured")
        return self.context.artifact_store

    async def list_artifacts(
        self,
        *,
        query: str | None = None,
        kind: ArtifactKind | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Return compact paged saved artifact summaries.

        Saved artifacts can contain full raw workflow plans, so list results
        deliberately stay summary-only. Use inspect/run tools for detail.
        """
        if self.context.artifact_store is None:
            return paged_list_payload("nodes", [], cursor=cursor, limit=limit)
        entries = [
            artifact_catalog_entry(artifact).model_dump(mode="json")
            for artifact in self.context.artifact_store.list_artifacts()
            if kind is None or artifact.kind == kind
        ]
        entries = [
            entry
            for entry in entries
            if matches_query(
                entry.get("name"),
                entry.get("artifact_id"),
                entry.get("display_name"),
                entry.get("description"),
                entry.get("kind"),
                query=query,
            )
        ]
        entries.sort(key=lambda entry: str(entry.get("name", "")))
        return paged_list_payload("nodes", entries, cursor=cursor, limit=limit)

    async def save_artifact(self, artifact: dict[str, Any]) -> dict[str, Any]:
        workflow_artifact = WorkflowArtifact.model_validate(artifact)
        self._artifact_store().save_artifact(workflow_artifact)
        self.context.events.record_workflow_event(
            "workflow_artifact_saved",
            capability_id=artifact_capability_id(workflow_artifact),
            payload={
                "artifact_id": workflow_artifact.id,
                "version": workflow_artifact.version,
            },
        )
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
        plan: RawWorkflowPlan | dict[str, Any],
        outcomes: Sequence[str],
        kind: ArtifactKind = "workflow",
        description: str | None = None,
        required_capabilities: dict[str, dict[str, Any]] | None = None,
        source_bindings: dict[str, str] | None = None,
        created_from_catalog_version: str | None = None,
    ) -> dict[str, Any]:
        typed_plan = (
            plan
            if isinstance(plan, RawWorkflowPlan)
            else RawWorkflowPlan.model_validate(plan)
        )
        workflow_artifact = build_workflow_artifact_from_plan(
            artifact_id=artifact_id,
            version=version,
            title=title,
            kind=kind,
            description=description,
            plan=typed_plan.model_dump(mode="json", by_alias=True),
            outcomes=tuple(outcomes),
            required_capabilities={
                name: RequiredCapability.model_validate(capability)
                for name, capability in (required_capabilities or {}).items()
            },
            source_bindings=source_bindings,
            observed_node_specs=observed_node_specs(self.context),
            created_from_catalog_version=created_from_catalog_version,
        )
        self._artifact_store().save_artifact(workflow_artifact)
        self.context.events.record_workflow_event(
            "workflow_artifact_saved",
            capability_id=artifact_capability_id(workflow_artifact),
            payload={
                "artifact_id": workflow_artifact.id,
                "version": workflow_artifact.version,
                "created_from_plan": True,
            },
        )
        return {
            "artifact_id": workflow_artifact.id,
            "version": workflow_artifact.version,
            "saved": True,
        }

    async def create_artifact_from_draft(
        self,
        *,
        artifact_id: str,
        version: int,
        title: str,
        draft: dict[str, Any],
        outcomes: Sequence[str],
        kind: ArtifactKind = "workflow",
        description: str | None = None,
        required_capabilities: dict[str, dict[str, Any]] | None = None,
        source_bindings: dict[str, str] | None = None,
        created_from_catalog_version: str | None = None,
    ) -> dict[str, Any]:
        from wf_artifacts import compile_workflow_draft

        plan = compile_workflow_draft(draft)
        workflow_artifact = build_workflow_artifact_from_plan(
            artifact_id=artifact_id,
            version=version,
            title=title,
            kind=kind,
            description=description,
            plan=plan,
            outcomes=tuple(outcomes),
            required_capabilities={
                name: RequiredCapability.model_validate(capability)
                for name, capability in (required_capabilities or {}).items()
            },
            source_bindings=source_bindings,
            observed_node_specs=observed_node_specs(self.context),
            created_from_catalog_version=created_from_catalog_version,
        )
        self._artifact_store().save_artifact(workflow_artifact)
        self.context.events.record_workflow_event(
            "workflow_artifact_saved",
            capability_id=artifact_capability_id(workflow_artifact),
            payload={
                "artifact_id": workflow_artifact.id,
                "version": workflow_artifact.version,
                "created_from_draft": True,
            },
        )
        required_sources = _binding_required_sources(
            workflow_artifact.required_capability_map(),
            self.context.specs.capability_sources,
        )
        return {
            "artifact_id": workflow_artifact.id,
            "version": workflow_artifact.version,
            "saved": True,
            "required_logical_sources": required_sources,
            "suggested_bindings": _suggested_self_bindings(
                required_sources,
                self.context.specs.capability_sources,
            ),
        }

    async def create_artifact_from_workspace(
        self,
        *,
        workspace_id: str,
        artifact_id: str,
        version: int,
        title: str,
        outcomes: Sequence[str],
        kind: ArtifactKind = "workflow",
        description: str | None = None,
        required_capabilities: dict[str, dict[str, Any]] | None = None,
        source_bindings: dict[str, str] | None = None,
        created_from_catalog_version: str | None = None,
    ) -> dict[str, Any]:
        store = self.context.draft_workspace_store
        if store is None:
            raise KeyError("draft workspace store is not configured")
        workspace = store.get_workspace(workspace_id)
        validation = await self.drafts.validate_draft(draft=workspace.draft)
        if validation["status"] != "valid":
            return {
                "saved": False,
                "workspace_id": workspace_id,
                "revision": workspace.revision,
                "status": validation["status"],
                "diagnostics": validation["diagnostics"],
            }
        return await self.create_artifact_from_draft(
            artifact_id=artifact_id,
            version=version,
            title=title,
            kind=kind,
            description=description,
            draft=workspace.draft,
            outcomes=outcomes,
            required_capabilities=required_capabilities,
            source_bindings=source_bindings,
            created_from_catalog_version=created_from_catalog_version,
        )

    async def create_wrapper_from_workspace(
        self,
        *,
        workspace_id: str,
        artifact_id: str,
        version: int,
        title: str,
        outcomes: Sequence[str],
        description: str | None = None,
        required_capabilities: dict[str, dict[str, Any]] | None = None,
        source_bindings: dict[str, str] | None = None,
        created_from_catalog_version: str | None = None,
    ) -> dict[str, Any]:
        """Save the current draft workspace as a callable wrapper artifact."""
        return await self.create_artifact_from_workspace(
            workspace_id=workspace_id,
            artifact_id=artifact_id,
            version=version,
            title=title,
            outcomes=outcomes,
            kind="wrapper",
            description=description,
            required_capabilities=required_capabilities,
            source_bindings=source_bindings,
            created_from_catalog_version=created_from_catalog_version,
        )

    async def inspect_artifact(
        self, *, artifact_id: str, version: int
    ) -> dict[str, Any]:
        artifact = self._artifact_store().get_artifact(artifact_id, version)
        return artifact.model_dump(mode="json")

    async def delete_artifact(
        self, *, artifact_id: str, version: int
    ) -> dict[str, Any]:
        store = self._artifact_store()
        blockers = store.deployments_for_artifact(artifact_id, version)
        blocker_ids = [deployment.id for deployment in blockers]
        if blocker_ids:
            return {
                "artifact_id": artifact_id,
                "version": version,
                "deleted": False,
                "blocked_by_deployments": blocker_ids,
            }
        store.delete_artifact(artifact_id, version)
        self.context.events.record_workflow_event(
            "workflow_artifact_deleted",
            capability_id=f"{artifact_id}@{version}",
            payload={"artifact_id": artifact_id, "version": version},
        )
        return {
            "artifact_id": artifact_id,
            "version": version,
            "deleted": True,
            "blocked_by_deployments": [],
        }


def _suggested_self_bindings(
    required_sources: Sequence[str],
    sources: Mapping[str, CapabilitySource],
) -> dict[str, str]:
    """Suggest only exact, enabled concrete sources as deployment bindings.

    Ambiguous logical sources such as ``drive`` with multiple concrete accounts
    must stay unsuggested. Exact ids such as ``local.report`` are safe because
    the same source is already present in the active inventory.
    """
    return {
        source_id: source_id
        for source_id in required_sources
        if (source := sources.get(source_id)) is not None
        and source.enabled
        and source.policy.binding_required
    }


def _binding_required_sources(
    required_capabilities: dict[str, RequiredCapability],
    sources: Mapping[str, CapabilitySource],
) -> list[str]:
    return sorted(
        {
            capability.logical_source
            for capability in required_capabilities.values()
            if sources.get(capability.logical_source) is None
            or sources[capability.logical_source].policy.binding_required
        }
    )


__all__ = [
    "WorkflowArtifactApi",
]
