from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import asdict
from typing import TYPE_CHECKING, Any

import anyio
import httpx
from mcp.client.streamable_http import StreamableHTTPError
from mcp.shared.exceptions import McpError

from wf_artifacts import (
    ArtifactKind,
    AvailableCapability,
    AvailableSource,
    DependencyDiagnostic,
    DiagnosticSeverity,
    DraftWorkspaceStore,
    RequiredCapability,
    RunStore,
    WorkflowArtifact,
    WorkflowCapabilityRef,
    WorkflowDeployment,
    compile_workflow_draft,
    create_workflow_artifact_from_plan as build_workflow_artifact_from_plan,
    validate_deployment_dependencies,
)
from wf_platform import (
    CapabilityRef,
    CapabilitySource,
    NodeSpecInventory,
    hash_json_schema,
)
from wf_authoring import build_async_registry
from wf_core import RuntimeContext
from wf_core.models.steps import (
    InputBinding,
    OutputBinding,
)
from wf_core.paths import GraphSourcePath

from wf_api.drafts import WorkflowDraftApi
from wf_api.models import RawWorkflowPlan
from wf_api.next_actions import NextActions
from wf_api.refs import parse_workflow_surface_capability_id
from wf_api.saved_subgraphs import (
    SavedSubgraphTree,
    direct_wrapper_interrupt_diagnostic,
    resolve_saved_subgraph_tree,
    saved_subgraph_tree_from_snapshots,
    validate_saved_subgraph_tree,
)
from wf_api.wrapper_hints import (
    workflow_output_schema_for_authoring,
    wrapper_hints_for_capability,
)

from ..broker.service.adapters import require_adapter
from ..broker.service.workflow_operation_context import context_from_service
from ..events import make_event
from ..shared import matches_query, paged_list_payload
from .models import TraceRange
from wf_api.run_lifecycle import (
    create_pinned_environment,
    has_blocking_diagnostics,
    load_stored_run,
    mark_resume_blocked,
    persist_stopped_run,
    restore_interrupted_run,
    validate_pinned_resume_environment,
)

LIVE_SOURCE_CHECK_TIMEOUT_SECONDS = 8.0
_LIVE_SOURCE_CHECK_FAILURES = (
    KeyError,
    TimeoutError,
    OSError,
    anyio.ClosedResourceError,
    anyio.EndOfStream,
    anyio.BrokenResourceError,
    httpx.HTTPError,
    McpError,
    StreamableHTTPError,
)

if TYPE_CHECKING:
    from wf_core import RunState

    from ..broker.service import WfMcpService


class WorkflowSurfaceHandlers:
    """Reusable implementation behind MCP workflow artifact tools."""

    def __init__(self, service: WfMcpService) -> None:
        self.service = service
        self._drafts = WorkflowDraftApi(context_from_service(service))

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
        if self.service.artifact_store is None:
            return paged_list_payload("nodes", [], cursor=cursor, limit=limit)
        entries = [
            self.service.workflow_artifact_catalog_entry(artifact).model_dump(
                mode="json"
            )
            for artifact in self.service.artifact_store.list_artifacts()
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
        entries.sort(key=lambda entry: str(entry["name"]))
        return paged_list_payload("nodes", entries, cursor=cursor, limit=limit)

    async def list_capabilities(
        self,
        *,
        query: str | None = None,
        source_id: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Return compact paged planner-visible workflow capability summaries."""
        capabilities = [
            {
                "name": detail.name,
                "source_id": source.id,
                "kind": "node_spec",
                "description": detail.description,
                "outcomes": list(detail.outcomes),
                "is_async": detail.is_async,
                "input_fields": _schema_field_names(detail.input_schema),
                "output_fields": _schema_field_names(
                    workflow_output_schema_for_authoring(detail.output_schema)
                ),
            }
            for source in sorted(
                self.service.capability_sources.values(),
                key=lambda source: source.id,
            )
            if source.enabled and source.visibility.planner
            if source_id is None or source.id == source_id
            for detail in source.as_inventory().capabilities.node_spec_details
            if matches_query(
                detail.name,
                detail.description,
                query=query,
            )
        ]
        capabilities.extend(
            self._wrapper_capability_summaries(query=query, source_id=source_id)
        )
        capabilities.sort(key=lambda capability: capability["name"])
        return paged_list_payload(
            "capabilities",
            capabilities,
            cursor=cursor,
            limit=limit,
        )

    async def inspect_capability(self, *, qualified_name: str) -> dict[str, Any]:
        """Return one planner-visible workflow capability contract."""
        for source in self.service.capability_sources.values():
            if not source.enabled or not source.visibility.planner:
                continue
            for detail in source.as_inventory().capabilities.node_spec_details:
                if detail.name == qualified_name:
                    detail_payload = detail.model_dump(mode="json")
                    detail_payload["wrapper_hints"] = wrapper_hints_for_capability(
                        capability_name=detail.name,
                        input_schema=detail.input_schema,
                        output_schema=detail.output_schema,
                        outcomes=detail.outcomes,
                    ).model_dump(mode="json")
                    return detail_payload
        wrapper_detail = self._wrapper_capability_detail(qualified_name)
        if wrapper_detail is not None:
            return wrapper_detail
        raise KeyError(f"unknown workflow capability {qualified_name!r}")

    async def call_capability(
        self,
        *,
        qualified_name: str,
        payload: dict[str, Any],
        deployment_id: str | None = None,
    ) -> dict[str, Any]:
        """Execute one planner-visible workflow capability for authoring tests."""
        wrapper_artifact = self._wrapper_artifact_for_capability_name(qualified_name)
        if wrapper_artifact is not None:
            return await self._call_wrapper_artifact(
                wrapper_artifact,
                payload,
                deployment_id=deployment_id,
            )

        spec = self.service._get_qualified_spec(qualified_name)
        handler = build_async_registry(spec)[spec.name]
        source_id = _source_id_for_capability(
            self.service.capability_sources,
            spec.name,
        )
        try:
            result = await handler(payload, RuntimeContext(current_node_id=spec.name))
        except Exception as exc:
            return {
                "qualified_name": spec.name,
                "source_id": source_id,
                "kind": "node_spec",
                "deployment_id": None,
                "outcome": "runtime_error",
                "output": None,
                "diagnostics": [
                    DependencyDiagnostic(
                        severity=DiagnosticSeverity.ERROR,
                        code="capability_call_failed",
                        logical_ref=spec.name,
                        bound_source=source_id,
                        message=(
                            f"Capability {spec.name!r} failed during test call: {exc}"
                        ),
                        repair_hint=(
                            "Check the source runtime, then retry the capability "
                            "or inspect the deployment run if this happened inside "
                            "a workflow."
                        ),
                    ).model_dump(mode="json")
                ],
            }
        return {
            "qualified_name": spec.name,
            "source_id": source_id,
            "kind": "node_spec",
            "deployment_id": None,
            "outcome": result["outcome"],
            "output": result["output"],
            "diagnostics": [],
        }

    def _wrapper_artifact_for_capability_name(
        self,
        qualified_name: str,
    ) -> WorkflowArtifact | None:
        """Resolve a saved node-like wrapper artifact from its stable capability name."""
        try:
            capability_id = parse_workflow_surface_capability_id(qualified_name)
        except ValueError:
            return None
        if (
            not isinstance(capability_id, WorkflowCapabilityRef)
            or self.service.artifact_store is None
        ):
            return None
        try:
            artifact = self.service.artifact_store.get_artifact(
                capability_id.artifact_id,
                capability_id.version,
            )
        except KeyError:
            return None
        if artifact.kind != "wrapper":
            return None
        return artifact

    def _wrapper_capability_summaries(
        self,
        *,
        query: str | None,
        source_id: str | None,
    ) -> list[dict[str, Any]]:
        """Project saved wrappers into workflow capability discovery rows.

        Wrapper artifacts are not live source NodeSpecs, but authors need to
        discover and test them through the same workflow-facing REPL surface.
        Full saved workflows stay out of this projection until graph-as-node is
        real in core.
        """
        if source_id not in {None, "workflow"} or self.service.artifact_store is None:
            return []
        rows: list[dict[str, Any]] = []
        for artifact in self.service.artifact_store.list_artifacts():
            if artifact.kind != "wrapper":
                continue
            name = _artifact_capability_id(artifact)
            if not matches_query(
                name,
                artifact.description,
                query=query,
            ):
                continue
            rows.append(
                {
                    "name": name,
                    "source_id": "workflow",
                    "kind": "wrapper_artifact",
                    "artifact_id": artifact.id,
                    "version": artifact.version,
                    "title": artifact.title,
                    "description": artifact.description,
                    "outcomes": list(artifact.outcomes),
                    "is_async": True,
                    "input_fields": _schema_field_names(artifact.input_schema),
                    "output_fields": _schema_field_names(artifact.output_schema),
                }
            )
        return rows

    def _wrapper_capability_detail(
        self,
        qualified_name: str,
    ) -> dict[str, Any] | None:
        """Return a NodeSpec-like contract for one saved wrapper artifact."""
        artifact = self._wrapper_artifact_for_capability_name(qualified_name)
        if artifact is None:
            return None
        return {
            "name": _artifact_capability_id(artifact),
            "source_id": "workflow",
            "kind": "wrapper_artifact",
            "artifact_id": artifact.id,
            "version": artifact.version,
            "title": artifact.title,
            "description": artifact.description,
            "outcomes": list(artifact.outcomes),
            "is_async": True,
            "input_schema": artifact.input_schema,
            "output_schema": artifact.output_schema,
            "required_capabilities": _required_capability_payloads(
                artifact.required_capability_map()
            ),
            "wrapper_hints": wrapper_hints_for_capability(
                capability_name=_artifact_capability_id(artifact),
                input_schema=artifact.input_schema,
                output_schema=artifact.output_schema,
                outcomes=list(artifact.outcomes),
            ).model_dump(mode="json"),
        }

    async def _call_wrapper_artifact(
        self,
        artifact: WorkflowArtifact,
        payload: dict[str, Any],
        *,
        deployment_id: str | None,
    ) -> dict[str, Any]:
        """Execute a saved wrapper artifact through the workflow runner."""
        unsupported = direct_wrapper_interrupt_diagnostic(artifact)
        if unsupported is not None:
            raise ValueError(unsupported.message)

        # Direct capability calls remain wrapper-only. Full saved workflows run
        # through deployments, where native subgraph dependencies and bindings
        # are prepared before core execution.
        plan = _raw_plan_from_artifact(artifact)
        deployment = None
        if deployment_id is not None:
            if self.service.artifact_store is None:
                raise KeyError("workflow artifact store is not configured")
            deployment = self.service.artifact_store.get_deployment(deployment_id)
            if (
                deployment.artifact_id != artifact.id
                or deployment.artifact_version != artifact.version
            ):
                raise ValueError(
                    f"deployment {deployment_id!r} does not target "
                    f"workflow.{artifact.id}.v{artifact.version}"
                )
        run = await self.service.run_workflow_from_plan(
            plan,
            payload,
            deployment=deployment,
            artifact=artifact,
        )
        return {
            "qualified_name": _artifact_capability_id(artifact),
            "source_id": "workflow",
            "kind": "wrapper_artifact",
            "deployment_id": deployment_id,
            "outcome": run.status.value,
            "output": run.output,
            "diagnostics": [],
        }

    async def save_artifact(self, artifact: dict[str, Any]) -> dict[str, Any]:
        if self.service.artifact_store is None:
            raise KeyError("workflow artifact store is not configured")
        workflow_artifact = WorkflowArtifact.model_validate(artifact)
        self.service.artifact_store.save_artifact(workflow_artifact)
        self.service._record_event(
            make_event(
                "workflow_artifact_saved",
                capability_id=_artifact_capability_id(workflow_artifact),
                payload={
                    "artifact_id": workflow_artifact.id,
                    "version": workflow_artifact.version,
                },
            )
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
        if self.service.artifact_store is None:
            raise KeyError("workflow artifact store is not configured")
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
            observed_node_specs=_observed_node_specs(self.service),
            created_from_catalog_version=created_from_catalog_version,
        )
        self.service.artifact_store.save_artifact(workflow_artifact)
        self.service._record_event(
            make_event(
                "workflow_artifact_saved",
                capability_id=_artifact_capability_id(workflow_artifact),
                payload={
                    "artifact_id": workflow_artifact.id,
                    "version": workflow_artifact.version,
                    "created_from_plan": True,
                },
            )
        )
        return {
            "artifact_id": workflow_artifact.id,
            "version": workflow_artifact.version,
            "saved": True,
        }

    async def validate_draft(self, *, draft: dict[str, Any]) -> dict[str, Any]:
        return await self._drafts.validate_draft(draft=draft)

    async def compile_draft(self, *, draft: dict[str, Any]) -> dict[str, Any]:
        return await self._drafts.compile_draft(draft=draft)

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
        if self.service.artifact_store is None:
            raise KeyError("workflow artifact store is not configured")
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
            observed_node_specs=_observed_node_specs(self.service),
            created_from_catalog_version=created_from_catalog_version,
        )
        self.service.artifact_store.save_artifact(workflow_artifact)
        self.service._record_event(
            make_event(
                "workflow_artifact_saved",
                capability_id=_artifact_capability_id(workflow_artifact),
                payload={
                    "artifact_id": workflow_artifact.id,
                    "version": workflow_artifact.version,
                    "created_from_draft": True,
                },
            )
        )
        required_sources = sorted(
            {
                capability.logical_source
                for capability in workflow_artifact.required_capability_map().values()
            }
        )
        return {
            "artifact_id": workflow_artifact.id,
            "version": workflow_artifact.version,
            "saved": True,
            "required_logical_sources": required_sources,
            "suggested_bindings": _suggested_self_bindings(required_sources),
        }

    async def patch_draft(
        self,
        *,
        draft: dict[str, Any],
        patch: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return await self._drafts.patch_draft(draft=draft, patch=patch)

    def _draft_store(self) -> DraftWorkspaceStore:
        if self.service.draft_workspace_store is None:
            raise KeyError("draft workspace store is not configured")
        return self.service.draft_workspace_store

    async def list_draft_workspaces(self) -> dict[str, Any]:
        """Return compact summaries for stored draft workspaces."""
        return await self._drafts.list_draft_workspaces()

    async def create_draft_workspace(
        self,
        *,
        workspace_id: str,
        draft: dict[str, Any],
        title: str | None = None,
    ) -> dict[str, Any]:
        return await self._drafts.create_draft_workspace(
            workspace_id=workspace_id,
            draft=draft,
            title=title,
        )

    async def get_draft_workspace(
        self,
        *,
        workspace_id: str,
        include_draft: bool = False,
    ) -> dict[str, Any]:
        return await self._drafts.get_draft_workspace(
            workspace_id=workspace_id,
            include_draft=include_draft,
        )

    async def delete_draft_workspace(self, *, workspace_id: str) -> dict[str, Any]:
        return await self._drafts.delete_draft_workspace(workspace_id=workspace_id)

    async def validate_draft_workspace(self, *, workspace_id: str) -> dict[str, Any]:
        """Refresh stored validation status without changing draft revision."""
        return await self._drafts.validate_draft_workspace(workspace_id=workspace_id)

    async def patch_draft_workspace(
        self,
        *,
        workspace_id: str,
        revision: int,
        patch: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return await self._drafts.patch_draft_workspace(
            workspace_id=workspace_id,
            revision=revision,
            patch=patch,
        )

    async def set_draft_name(
        self,
        *,
        workspace_id: str,
        revision: int,
        name: str,
    ) -> dict[str, Any]:
        return await self._drafts.set_draft_name(
            workspace_id=workspace_id,
            revision=revision,
            name=name,
        )

    async def set_draft_route(
        self,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        outcome: str,
        target: str,
    ) -> dict[str, Any]:
        return await self._drafts.set_draft_route(
            workspace_id=workspace_id,
            revision=revision,
            step_id=step_id,
            outcome=outcome,
            target=target,
        )

    async def set_step_input_map(
        self,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        input_map: dict[str, str],
    ) -> dict[str, Any]:
        return await self._drafts.set_step_input_map(
            workspace_id=workspace_id,
            revision=revision,
            step_id=step_id,
            input_map=input_map,
        )

    async def set_step_output_map(
        self,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        output_map: dict[str, str],
    ) -> dict[str, Any]:
        return await self._drafts.set_step_output_map(
            workspace_id=workspace_id,
            revision=revision,
            step_id=step_id,
            output_map=output_map,
        )

    async def create_minimal_draft_workspace(
        self,
        *,
        workspace_id: str,
        name: str,
        capability_name: str,
        input_schema: dict[str, Any],
        state_schema: dict[str, Any],
        output_schema: dict[str, Any],
        input: Sequence[InputBinding] | None = None,
        output: Sequence[OutputBinding] | None = None,
        input_map: dict[str, str] | None = None,
        output_map: dict[str, str] | None = None,
        error_message_source: str | GraphSourcePath | None = None,
        title: str | None = None,
    ) -> dict[str, Any]:
        """Bootstrap the smallest patchable draft around one workflow capability."""
        return await self._drafts.create_minimal_draft_workspace(
            workspace_id=workspace_id,
            name=name,
            capability_name=capability_name,
            input_schema=input_schema,
            state_schema=state_schema,
            output_schema=output_schema,
            input=input,
            output=output,
            input_map=input_map,
            output_map=output_map,
            error_message_source=error_message_source,
            title=title,
        )

    async def create_draft_workspace_from_capability(
        self,
        *,
        workspace_id: str,
        capability_name: str,
        name: str | None = None,
        title: str | None = None,
        input_schema: dict[str, Any] | None = None,
        state_schema: dict[str, Any] | None = None,
        output_schema: dict[str, Any] | None = None,
        input: Sequence[InputBinding] | None = None,
        output: Sequence[OutputBinding] | None = None,
        input_map: dict[str, str] | None = None,
        output_map: dict[str, str] | None = None,
        error_message_source: str | GraphSourcePath | None = None,
    ) -> dict[str, Any]:
        """Create a patchable draft workspace from inspect_capability hints."""
        capability = await self.inspect_capability(qualified_name=capability_name)
        hints = capability["wrapper_hints"]
        result = await self.create_minimal_draft_workspace(
            workspace_id=workspace_id,
            name=name or _draft_name_from_capability(capability_name),
            capability_name=capability_name,
            input_schema=input_schema or hints["input_schema"],
            state_schema=state_schema or hints["state_schema"],
            output_schema=output_schema or hints["output_schema"],
            input=input,
            output=output,
            input_map=None if input is not None else (input_map or hints["input_map"]),
            output_map=None
            if output is not None
            else (output_map or hints["output_map"]),
            error_message_source=error_message_source,
            title=title,
        )
        return {
            **result,
            "wrapper_hints": hints,
            "next_actions": NextActions.from_wrapper_hints(
                workspace_id=workspace_id,
                revision=int(result["revision"]),
                hints=hints,
            ).model_dump(mode="json"),
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
        workspace = self._draft_store().get_workspace(workspace_id)
        validation = await self.validate_draft(draft=workspace.draft)
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
        if self.service.artifact_store is None:
            raise KeyError("workflow artifact store is not configured")
        artifact = self.service.artifact_store.get_artifact(artifact_id, version)
        return artifact.model_dump(mode="json")

    async def list_deployments(self) -> dict[str, Any]:
        if self.service.artifact_store is None:
            return {"deployments": []}
        return {
            "deployments": [
                _deployment_summary(deployment)
                for deployment in self.service.artifact_store.list_deployments()
            ]
        }

    async def inspect_deployment(self, *, deployment_id: str) -> dict[str, Any]:
        if self.service.artifact_store is None:
            raise KeyError("workflow artifact store is not configured")
        return self.service.artifact_store.get_deployment(deployment_id).model_dump(
            mode="json"
        )

    async def save_deployment(self, deployment: dict[str, Any]) -> dict[str, Any]:
        if self.service.artifact_store is None:
            raise KeyError("workflow artifact store is not configured")
        workflow_deployment = WorkflowDeployment.model_validate(deployment)
        self.service.artifact_store.save_deployment(workflow_deployment)
        self.service._record_event(
            make_event(
                "workflow_deployment_saved",
                capability_id=f"deployment.{workflow_deployment.id}",
                payload={
                    "deployment_id": workflow_deployment.id,
                    "artifact_id": workflow_deployment.artifact_id,
                    "artifact_version": workflow_deployment.artifact_version,
                },
            )
        )
        return {
            "deployment_id": workflow_deployment.id,
            "artifact_id": workflow_deployment.artifact_id,
            "artifact_version": workflow_deployment.artifact_version,
            "saved": True,
        }

    async def delete_deployment(self, *, deployment_id: str) -> dict[str, Any]:
        """Delete one mutable deployment environment binding."""
        if self.service.artifact_store is None:
            raise KeyError("workflow artifact store is not configured")
        self.service.artifact_store.delete_deployment(deployment_id)
        self.service._record_event(
            make_event(
                "workflow_deployment_deleted",
                capability_id=f"deployment.{deployment_id}",
                payload={"deployment_id": deployment_id},
            )
        )
        return {"deployment_id": deployment_id, "deleted": True}

    async def validate_deployment(
        self,
        *,
        deployment_id: str,
        live_check: bool = False,
    ) -> dict[str, Any]:
        deployment, artifact, diagnostics, tree = self._deployment_validation(
            deployment_id
        )
        if live_check:
            diagnostics.extend(
                await _live_source_diagnostics(
                    self.service,
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

    async def run_deployment(
        self,
        *,
        deployment_id: str,
        workflow_input: dict[str, Any],
        trace_range: TraceRange | None = None,
    ) -> dict[str, Any]:
        deployment, artifact, diagnostics, tree = self._deployment_validation(
            deployment_id
        )
        if diagnostics:
            return _run_payload(
                deployment=deployment,
                artifact=artifact,
                status="unrunnable",
                diagnostics=diagnostics,
            )

        plan = _raw_plan_from_artifact(artifact)
        run = await self.service.run_workflow_from_plan(
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
        trace_range: TraceRange | None = None,
    ) -> dict[str, Any]:
        """Resume one durable interrupted deployment run."""
        record, stopped_run = restore_interrupted_run(self._run_store(), run_id)
        environment = record.environment
        diagnostics = validate_pinned_resume_environment(
            record=record,
            sources=_available_sources(self.service),
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
        run = await self.service.resume_workflow_from_plan(
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
        trace_range: TraceRange,
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

    def _run_store(self) -> RunStore:
        """Return the configured durable run store required by workflow runs."""
        if self.service.run_store is None:
            raise KeyError("workflow run store is not configured")
        return self.service.run_store

    def _deployment_validation(
        self,
        deployment_id: str,
    ) -> tuple[
        WorkflowDeployment,
        WorkflowArtifact,
        list[DependencyDiagnostic],
        SavedSubgraphTree,
    ]:
        if self.service.artifact_store is None:
            raise KeyError("workflow artifact store is not configured")
        deployment = self.service.artifact_store.get_deployment(deployment_id)
        artifact = self.service.artifact_store.get_artifact(
            deployment.artifact_id,
            deployment.artifact_version,
        )
        available_sources = _available_sources(self.service)
        diagnostics = validate_deployment_dependencies(
            artifact=artifact,
            deployment=deployment,
            sources=available_sources,
        )
        tree = resolve_saved_subgraph_tree(
            root_artifact=artifact,
            artifact_store=self.service.artifact_store,
        )
        diagnostics.extend(
            validate_saved_subgraph_tree(
                tree=tree,
                deployment=deployment,
                sources=available_sources,
            )
        )
        return deployment, artifact, diagnostics, tree


def _available_sources(service: WfMcpService) -> list[AvailableSource]:
    """Convert broker capability sources into artifact validation snapshots."""
    sources: list[AvailableSource] = []
    for source in service.capability_sources.values():
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
                capabilities=capabilities,
            )
        )
    return sources


async def _live_source_diagnostics(
    service: WfMcpService,
    *,
    deployment: WorkflowDeployment,
    artifacts: Sequence[WorkflowArtifact],
) -> list[DependencyDiagnostic]:
    """Return opt-in diagnostics for bound upstream sources that cannot answer.

    Static deployment validation only checks the last known source catalog.
    This probe intentionally performs live upstream I/O, so MCP tools keep it
    disabled by default and only run it when the caller asks for liveness.
    """
    diagnostics: list[DependencyDiagnostic] = []
    for source_id, logical_ref in _required_live_sources(deployment, artifacts).items():
        source = service.capability_sources.get(source_id)
        if (
            source is None
            or not source.enabled
            or not source.permissions.calls_upstream
        ):
            continue
        try:
            connection = service.connections.get(source_id)
            adapter = require_adapter(connection, service.adapters)
            auth = service.load_auth(source_id)
            await asyncio.wait_for(
                adapter.list_tools(connection, auth),
                timeout=LIVE_SOURCE_CHECK_TIMEOUT_SECONDS,
            )
        except _LIVE_SOURCE_CHECK_FAILURES as exc:
            diagnostics.append(
                DependencyDiagnostic(
                    severity=DiagnosticSeverity.ERROR,
                    code="source_unreachable",
                    logical_ref=logical_ref,
                    bound_source=source_id,
                    message=(
                        f"Live check for upstream source {source_id!r} failed: "
                        f"{type(exc).__name__}: {exc}"
                    ),
                    repair_hint=(
                        "Start or reconnect the source, fix its transport/auth "
                        "configuration, or bind this deployment to another source."
                    ),
                )
            )
    return diagnostics


def _required_live_sources(
    deployment: WorkflowDeployment,
    artifacts: Sequence[WorkflowArtifact],
) -> dict[str, str]:
    """Return concrete upstream source ids to live-check, with one logical ref."""
    bindings = deployment.binding_map()
    required: dict[str, str] = {}
    for artifact in artifacts:
        for logical_ref, capability in artifact.required_capability_map().items():
            source_id = bindings.get(capability.logical_source)
            if source_id is not None:
                required.setdefault(source_id, logical_ref)
    return required


def _required_capabilities_for_plan(
    plan: dict[str, Any],
    *,
    source_bindings: dict[str, str] | None,
    service: WfMcpService,
) -> dict[str, RequiredCapability]:
    """Infer a draft dependency summary without persisting an artifact."""
    artifact = build_workflow_artifact_from_plan(
        artifact_id="draft_preview",
        version=1,
        title="Draft Preview",
        plan=plan,
        outcomes=("completed",),
        source_bindings=source_bindings,
        observed_node_specs=_observed_node_specs(service),
    )
    requirements = artifact.required_capability_map()
    for node in _plan_nodes(artifact):
        raw_ref = node.get("node")
        if not isinstance(raw_ref, str) or raw_ref in requirements:
            continue
        try:
            parsed = CapabilityRef.parse(raw_ref)
        except ValueError:
            continue
        requirements[raw_ref] = RequiredCapability(
            ref=parsed,
            kind="node_spec",
        )
    return requirements


def _required_capability_payloads(
    requirements: dict[str, RequiredCapability],
) -> dict[str, dict[str, Any]]:
    return {
        name: capability.model_dump(mode="json")
        for name, capability in sorted(requirements.items())
    }


def _suggested_self_bindings(required_sources: Sequence[str]) -> dict[str, str]:
    """Suggest local bindings for built-in sources that deploy to themselves."""
    return {
        source: source for source in required_sources if source in {"wf.std", "wf.mcp"}
    }


def _observed_node_specs(service: WfMcpService) -> dict[str, NodeSpecInventory]:
    """Project current executable specs into serializable observed contracts."""
    observed: dict[str, NodeSpecInventory] = {}
    for source in service.capability_sources.values():
        inventory = source.as_inventory()
        observed.update(
            {detail.name: detail for detail in inventory.capabilities.node_spec_details}
        )
    return observed


def _schema_field_names(schema: dict[str, Any]) -> list[str]:
    """Return top-level JSON object property names for compact discovery rows."""
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return []
    return sorted(str(name) for name in properties)


def _draft_name_from_capability(capability_name: str) -> str:
    """Return a stable draft name when caller does not provide one."""
    return capability_name.replace(".", "_").replace("-", "_")


def _source_id_for_capability(
    sources: dict[str, CapabilitySource],
    qualified_name: str,
) -> str | None:
    """Return the source that currently owns one workflow capability."""
    for source in sources.values():
        if qualified_name in source.capabilities.node_specs:
            return source.id
    return None


def _capability_name(qualified_name: str) -> str | None:
    """Return the local name of one qualified capability ref if it is valid."""
    try:
        parsed = parse_workflow_surface_capability_id(qualified_name)
    except ValueError:
        return None
    if isinstance(parsed, WorkflowCapabilityRef):
        return None
    return parsed.name


def _artifact_capability_id(artifact: WorkflowArtifact) -> str:
    """Use the same stable name shape as workflow artifact catalog entries."""
    return str(
        WorkflowCapabilityRef(
            artifact_id=artifact.id,
            version=artifact.version,
        )
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


def _plan_nodes(artifact: WorkflowArtifact) -> list[dict[str, Any]]:
    nodes = artifact.plan.get("nodes", [])
    return [node for node in nodes if isinstance(node, dict)]


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


def _deployment_summary(deployment: WorkflowDeployment) -> dict[str, Any]:
    """Return compact deployment metadata for progressive list responses."""
    return {
        "id": deployment.id,
        "artifact_id": deployment.artifact_id,
        "artifact_version": deployment.artifact_version,
        "binding_count": len(deployment.binding_map()),
        "drift_policy": deployment.drift_policy.value,
    }
