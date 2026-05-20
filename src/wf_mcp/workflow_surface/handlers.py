from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from wf_artifacts import (
    ArtifactKind,
    AvailableCapability,
    AvailableSource,
    DependencyDiagnostic,
    DiagnosticSeverity,
    DraftWorkspaceStore,
    RequiredCapability,
    WorkflowArtifact,
    WorkflowCapabilityRef,
    WorkflowDeployment,
    compile_workflow_draft,
    create_draft_workspace as create_draft_workspace_record,
    create_workflow_artifact_from_plan as build_workflow_artifact_from_plan,
    get_draft_workspace as get_draft_workspace_record,
    patch_draft_workspace as patch_draft_workspace_record,
    patch_workflow_draft,
    validate_workflow_draft,
    validate_deployment_dependencies,
)
from wf_platform import (
    CapabilityRef,
    CapabilitySource,
    NodeSpecInventory,
    hash_json_schema,
    page_items,
)
from wf_authoring import build_async_registry
from wf_core import RuntimeContext

from ..events import make_event
from ..models import RawWorkflowPlan
from .constants import (
    DEFAULT_CALL_STEP_ID,
    DEFAULT_ERROR_OUTCOME,
    DEFAULT_ERROR_STEP_ID,
    DEFAULT_OK_OUTCOME,
    RUNTIME_ERROR_CAPABILITY,
)
from .refs import parse_workflow_surface_capability_id
from .wrapper_hints import wrapper_hints_for_capability

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
                "output_fields": _schema_field_names(detail.output_schema),
            }
            for source in sorted(
                self.service.capability_sources.values(),
                key=lambda source: source.id,
            )
            if source.enabled and source.visibility.planner
            if source_id is None or source.id == source_id
            for detail in source.as_inventory().capabilities.node_spec_details
            if query is None
            or query.casefold() in detail.name.casefold()
            or (
                detail.description is not None
                and query.casefold() in detail.description.casefold()
            )
        ]
        capabilities.extend(
            self._wrapper_capability_summaries(query=query, source_id=source_id)
        )
        capabilities.sort(key=lambda capability: capability["name"])
        page = page_items(capabilities, cursor=cursor, limit=limit)
        return {
            "capabilities": list(page.items),
            "next_cursor": page.next_cursor,
            "total": page.total,
        }

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
        result = await handler(payload, RuntimeContext(current_node_id=spec.name))
        return {
            "qualified_name": spec.name,
            "source_id": _source_id_for_capability(
                self.service.capability_sources,
                spec.name,
            ),
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
            if not _matches_capability_query(
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
        unsupported = _unsupported_interrupt_diagnostic(artifact)
        if unsupported is not None:
            raise ValueError(unsupported.message)

        # For now only wrapper artifacts are honest node capabilities here.
        # Full saved workflows stay on `run_deployment` until core supports
        # graph-as-node semantics instead of us faking subgraphs at this layer.
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
        return validate_workflow_draft(
            draft,
            outcome_lookup=self._outcomes_for_capability,
        )

    async def compile_draft(self, *, draft: dict[str, Any]) -> dict[str, Any]:
        plan = compile_workflow_draft(draft)
        return {
            "compiled_plan": plan,
            "required_capabilities": _required_capability_payloads(
                _required_capabilities_for_plan(
                    plan,
                    source_bindings=None,
                    service=self.service,
                )
            ),
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
        return patch_workflow_draft(draft, patch)

    def _draft_store(self) -> DraftWorkspaceStore:
        if self.service.draft_workspace_store is None:
            raise KeyError("draft workspace store is not configured")
        return self.service.draft_workspace_store

    async def list_draft_workspaces(self) -> dict[str, Any]:
        """Return compact summaries for stored draft workspaces."""
        store = self._draft_store()
        return {
            "workspaces": [
                get_draft_workspace_record(store, workspace_id=workspace.id)
                for workspace in store.list_workspaces()
            ]
        }

    async def create_draft_workspace(
        self,
        *,
        workspace_id: str,
        draft: dict[str, Any],
        title: str | None = None,
    ) -> dict[str, Any]:
        return create_draft_workspace_record(
            self._draft_store(),
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
        return get_draft_workspace_record(
            self._draft_store(),
            workspace_id=workspace_id,
            include_draft=include_draft,
        )

    async def delete_draft_workspace(self, *, workspace_id: str) -> dict[str, Any]:
        deleted = self._draft_store().delete_workspace(workspace_id)
        return {
            "workspace_id": workspace_id,
            "deleted": deleted,
            "status": "deleted" if deleted else "not_found",
        }

    async def validate_draft_workspace(self, *, workspace_id: str) -> dict[str, Any]:
        """Refresh stored validation status without changing draft revision."""
        store = self._draft_store()
        workspace = store.get_workspace(workspace_id)
        validation = await self.validate_draft(draft=workspace.draft)
        refreshed = workspace.model_copy(
            update={
                "status": validation["status"],
                "diagnostics": validation["diagnostics"],
            }
        )
        store.save_workspace(refreshed)
        return get_draft_workspace_record(store, workspace_id=workspace_id)

    async def patch_draft_workspace(
        self,
        *,
        workspace_id: str,
        revision: int,
        patch: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return patch_draft_workspace_record(
            self._draft_store(),
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
        return await self.patch_draft_workspace(
            workspace_id=workspace_id,
            revision=revision,
            patch=[{"op": "replace", "path": "/name", "value": name}],
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
        return await self.patch_draft_workspace(
            workspace_id=workspace_id,
            revision=revision,
            patch=[
                {
                    "op": "add",
                    "path": (
                        f"/routes/{_escape_json_pointer(step_id)}/"
                        f"{_escape_json_pointer(outcome)}"
                    ),
                    "value": target,
                }
            ],
        )

    async def set_step_input_map(
        self,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        input_map: dict[str, str],
    ) -> dict[str, Any]:
        return await self.patch_draft_workspace(
            workspace_id=workspace_id,
            revision=revision,
            patch=[
                {
                    "op": "replace",
                    "path": f"/steps/{_escape_json_pointer(step_id)}/in",
                    "value": input_map,
                }
            ],
        )

    async def set_step_output_map(
        self,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        output_map: dict[str, str],
    ) -> dict[str, Any]:
        return await self.patch_draft_workspace(
            workspace_id=workspace_id,
            revision=revision,
            patch=[
                {
                    "op": "replace",
                    "path": f"/steps/{_escape_json_pointer(step_id)}/out",
                    "value": output_map,
                }
            ],
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
        input_map: dict[str, str],
        output_map: dict[str, str],
        error_message_source: str | None = None,
        title: str | None = None,
    ) -> dict[str, Any]:
        """Bootstrap the smallest patchable draft around one workflow capability."""
        outcomes = self._outcomes_for_capability(capability_name) or (
            DEFAULT_OK_OUTCOME,
        )
        steps: dict[str, Any] = {
            DEFAULT_CALL_STEP_ID: {
                "use": capability_name,
                "in": input_map,
                "out": output_map,
            }
        }
        routes: dict[str, dict[str, str]] = {
            DEFAULT_CALL_STEP_ID: {DEFAULT_OK_OUTCOME: "__end__"}
        }
        error_source = error_message_source or _first_state_path(output_map)
        if DEFAULT_ERROR_OUTCOME in outcomes and error_source is not None:
            # The bootstrapper cannot infer provider-specific error envelopes.
            # It only wires an error route when the caller gave, or output_map
            # exposes, a concrete state path that can become a runtime message.
            steps[DEFAULT_ERROR_STEP_ID] = {
                "use": RUNTIME_ERROR_CAPABILITY,
                "in": {error_source: "message"},
                "out": {},
            }
            routes[DEFAULT_CALL_STEP_ID][DEFAULT_ERROR_OUTCOME] = DEFAULT_ERROR_STEP_ID
            routes[DEFAULT_ERROR_STEP_ID] = {DEFAULT_OK_OUTCOME: "__end__"}
        draft = {
            "name": name,
            "input_schema": input_schema,
            "state_schema": state_schema,
            "output_schema": output_schema,
            "start": DEFAULT_CALL_STEP_ID,
            "steps": steps,
            "routes": routes,
        }
        return await self.create_draft_workspace(
            workspace_id=workspace_id,
            title=title,
            draft=draft,
        )

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

    def _outcomes_for_capability(self, qualified_name: str) -> tuple[str, ...] | None:
        try:
            return self.service._get_qualified_spec(qualified_name).outcomes
        except KeyError:
            return None

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
        run = await self.service.run_workflow_from_plan(
            plan,
            workflow_input,
            deployment=deployment,
            artifact=artifact,
        )
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


def _matches_capability_query(
    name: str,
    description: str | None,
    *,
    query: str | None,
) -> bool:
    """Apply the same compact capability search semantics to every row kind."""
    if query is None:
        return True
    lowered = query.casefold()
    return lowered in name.casefold() or (
        description is not None and lowered in description.casefold()
    )


def _first_state_path(output_map: dict[str, str]) -> str | None:
    """Return the first mapped state path for minimal error-route bootstraps."""
    for target in output_map.values():
        if target.startswith("state."):
            return target
    return None


def _escape_json_pointer(value: str) -> str:
    """Escape one JSON Pointer path segment for generated JSON Patch helpers."""
    return value.replace("~", "~0").replace("/", "~1")


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
