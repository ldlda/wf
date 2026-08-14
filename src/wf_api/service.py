from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from wf_artifacts import ArtifactKind, compile_workflow_draft
from wf_artifacts.drafts.models import DraftStep
from wf_core.analysis.context_scopes import context_analysis_warnings
from wf_core.models.steps import InputBinding, OutputBinding, StepInputBinding
from wf_core.models.workflow import Workflow

from .artifacts import WorkflowArtifactApi
from .authoring_contracts import (
    context_path_options_for_node,
    project_authoring_contract_inventory,
    project_authoring_step_contract,
    schema_path_options,
)
from .capabilities import WorkflowCapabilityApi
from .deployments import WorkflowDeploymentApi
from .draft_authoring import RouteSource, WorkflowDraftAuthoringApi
from .draft_updates import CapabilityStepUpdate
from .drafts import WorkflowDraftApi
from .models import (
    AuthoringContractInventoryPayload,
    CapabilityCallResult,
    CompileDraftWorkspaceResult,
    CompileDraftWorkspaceSuccess,
    CreateArtifactFromWorkspaceResult,
    CreateDraftWorkspaceFromCapabilityResult,
    DeleteArtifactResult,
    DeleteDeploymentResult,
    DeleteDraftWorkspaceResult,
    DraftWorkspaceResult,
    InspectCapabilityResult,
    ListArtifactsResult,
    ListCapabilitiesResult,
    ListDeploymentsResult,
    ListDraftWorkspacesResult,
    ListRunsResult,
    PatchDraftResult,
    RawWorkflowPlan,
    RunResult,
    RunTraceResult,
    SaveArtifactResult,
    SavedDraftArtifactResult,
    SaveDeploymentResult,
    ValidateDeploymentResult,
    ValidateDraftResult,
    WorkflowArtifactPayload,
    WorkflowDeploymentPayload,
)
from .operation_context import WorkflowOperationContext
from .runs import TraceRangeLike, WorkflowRunApi


def _authoring_schema(
    value: object,
    *,
    field_name: str,
    root: str,
    warnings: list[str],
) -> dict[str, Any]:
    """Return one valid persisted schema, isolating invalid projections."""
    if not isinstance(value, Mapping):
        warnings.append(
            f"{field_name} authoring choices unavailable: expected a schema object"
        )
        return {}
    schema = dict(value)
    try:
        schema_path_options(schema, root=root, uses=[])
    except ValueError as exc:
        warnings.append(f"{field_name} authoring choices unavailable: {exc}")
        return {}
    return schema


def _authoring_outcomes(value: object) -> list[str]:
    """Keep only a complete string outcome list for tolerant inventory output."""
    if not isinstance(value, list) or not all(
        isinstance(outcome, str) for outcome in value
    ):
        return []
    return list(value)


def _step_label(step_id: str) -> str:
    """Humanize a keyed draft step for compact executable choices."""
    return step_id.replace("_", " ").replace("-", " ").title()


class WorkflowApi:
    """Protocol-neutral workflow application facade.

    This facade owns the stable application entry point. It composes the
    domain APIs from a WorkflowOperationContext so MCP, CLI, and future HTTP
    callers share one operation surface without importing wf_mcp.
    """

    def __init__(self, context: WorkflowOperationContext) -> None:
        self.context = context
        self.capabilities = WorkflowCapabilityApi(context)
        self.drafts = WorkflowDraftApi(context)
        self.draft_authoring = WorkflowDraftAuthoringApi(context, self.drafts)
        self.artifacts = WorkflowArtifactApi(context)
        self.deployments = WorkflowDeploymentApi(context)
        self.runs = WorkflowRunApi(context)

    # -- capabilities --

    async def list_capabilities(
        self,
        *,
        query: str | None = None,
        source_id: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> ListCapabilitiesResult:
        return await self.capabilities.list_capabilities(
            query=query,
            source_id=source_id,
            cursor=cursor,
            limit=limit,
        )

    async def inspect_capability(
        self,
        *,
        qualified_name: str,
    ) -> InspectCapabilityResult:
        return await self.capabilities.inspect_capability(qualified_name=qualified_name)

    async def call_capability(
        self,
        *,
        qualified_name: str,
        payload: dict[str, Any],
        deployment_id: str | None = None,
    ) -> CapabilityCallResult:
        return await self.capabilities.call_capability(
            qualified_name=qualified_name,
            payload=payload,
            deployment_id=deployment_id,
        )

    # -- artifacts --

    async def list_artifacts(
        self,
        *,
        query: str | None = None,
        kind: ArtifactKind | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> ListArtifactsResult:
        return await self.artifacts.list_artifacts(
            query=query,
            kind=kind,
            cursor=cursor,
            limit=limit,
        )

    async def inspect_artifact(
        self,
        *,
        artifact_id: str,
        version: int,
    ) -> WorkflowArtifactPayload:
        return await self.artifacts.inspect_artifact(
            artifact_id=artifact_id,
            version=version,
        )

    async def delete_artifact(
        self,
        *,
        artifact_id: str,
        version: int,
    ) -> DeleteArtifactResult:
        return await self.artifacts.delete_artifact(
            artifact_id=artifact_id,
            version=version,
        )

    async def save_artifact(
        self,
        artifact: dict[str, Any],
    ) -> SaveArtifactResult:
        return await self.artifacts.save_artifact(artifact)

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
    ) -> SaveArtifactResult:
        return await self.artifacts.create_artifact_from_plan(
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
    ) -> SavedDraftArtifactResult:
        return await self.artifacts.create_artifact_from_draft(
            artifact_id=artifact_id,
            version=version,
            title=title,
            draft=draft,
            outcomes=outcomes,
            kind=kind,
            description=description,
            required_capabilities=required_capabilities,
            source_bindings=source_bindings,
            created_from_catalog_version=created_from_catalog_version,
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
    ) -> CreateArtifactFromWorkspaceResult:
        return await self.artifacts.create_artifact_from_workspace(
            workspace_id=workspace_id,
            artifact_id=artifact_id,
            version=version,
            title=title,
            outcomes=outcomes,
            kind=kind,
            description=description,
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
    ) -> CreateArtifactFromWorkspaceResult:
        return await self.artifacts.create_wrapper_from_workspace(
            workspace_id=workspace_id,
            artifact_id=artifact_id,
            version=version,
            title=title,
            outcomes=outcomes,
            description=description,
            required_capabilities=required_capabilities,
            source_bindings=source_bindings,
            created_from_catalog_version=created_from_catalog_version,
        )

    # -- drafts --

    async def validate_draft(
        self,
        *,
        draft: dict[str, Any],
    ) -> ValidateDraftResult:
        return await self.drafts.validate_draft(draft=draft)

    async def compile_draft(
        self,
        *,
        draft: dict[str, Any],
    ) -> CompileDraftWorkspaceSuccess:
        return await self.drafts.compile_draft(draft=draft)

    async def patch_draft(
        self,
        *,
        draft: dict[str, Any],
        patch: list[dict[str, Any]],
    ) -> PatchDraftResult:
        return await self.drafts.patch_draft(draft=draft, patch=patch)

    # -- draft workspaces --

    async def list_draft_workspaces(self) -> ListDraftWorkspacesResult:
        return await self.drafts.list_draft_workspaces()

    async def create_draft_workspace(
        self,
        *,
        workspace_id: str,
        draft: dict[str, Any],
        title: str | None = None,
    ) -> DraftWorkspaceResult:
        return await self.drafts.create_draft_workspace(
            workspace_id=workspace_id,
            draft=draft,
            title=title,
        )

    async def create_empty_draft_workspace(
        self,
        *,
        workspace_id: str,
        name: str,
        title: str | None = None,
        input_schema: dict[str, Any] | None = None,
        state_schema: dict[str, Any] | None = None,
        output_schema: dict[str, Any] | None = None,
        outcomes: Sequence[str] = ("ok",),
    ) -> DraftWorkspaceResult:
        return await self.drafts.create_empty_draft_workspace(
            workspace_id=workspace_id,
            name=name,
            title=title,
            input_schema=input_schema,
            state_schema=state_schema,
            output_schema=output_schema,
            outcomes=outcomes,
        )

    async def get_draft_workspace(
        self,
        *,
        workspace_id: str,
        include_draft: bool = False,
    ) -> DraftWorkspaceResult:
        return await self.drafts.get_draft_workspace(
            workspace_id=workspace_id,
            include_draft=include_draft,
        )

    async def inspect_draft_authoring_contract(
        self,
        *,
        workspace_id: str,
        revision: int,
        selected_step_id: str | None = None,
    ) -> AuthoringContractInventoryPayload | DraftWorkspaceResult:
        """Inspect revision-scoped authoring choices without persisting changes.

        The workspace revision check deliberately happens before interpreting a
        selected step. This preserves the draft APIs' canonical conflict
        precedence when an authoring client is holding an old revision.
        """
        checked = self.drafts._workspace_if_revision_matches(
            workspace_id=workspace_id,
            revision=revision,
        )
        if isinstance(checked, dict):
            return checked

        draft = checked.draft
        raw_steps = draft.get("steps")
        steps = raw_steps if isinstance(raw_steps, Mapping) else {}
        if selected_step_id is not None and selected_step_id not in steps:
            raise KeyError(f"unknown draft step {selected_step_id!r}")

        warnings: list[str] = []
        entry_steps = []
        selected_contract = None
        for raw_step_id, raw_step in steps.items():
            if not isinstance(raw_step_id, str) or raw_step_id == "__end__":
                continue
            if not isinstance(raw_step, Mapping):
                continue
            capability_name = raw_step.get("use")
            if not isinstance(capability_name, str):
                if raw_step_id == selected_step_id:
                    warnings.append(
                        f"selected step {raw_step_id!r} is not an executable capability"
                    )
                continue
            try:
                resolved_contract = self.capabilities.resolve_capability_contract(
                    capability_name
                )
            except (KeyError, TypeError, ValueError) as exc:
                if raw_step_id == selected_step_id:
                    warnings.append(
                        f"selected step {raw_step_id!r} cannot be interpreted: {exc}"
                    )
                continue

            description = raw_step.get("desc")
            if not isinstance(description, str):
                description = resolved_contract.description
            input_schema = _authoring_schema(
                resolved_contract.input_schema,
                field_name=f"step {raw_step_id!r} input schema",
                root="step_input",
                warnings=warnings,
            )
            output_schema = _authoring_schema(
                resolved_contract.output_schema,
                field_name=f"step {raw_step_id!r} output schema",
                root="step_output",
                warnings=warnings,
            )
            projected_contract = project_authoring_step_contract(
                step_id=raw_step_id,
                label=_step_label(raw_step_id),
                description=description,
                input_schema=input_schema,
                output_schema=output_schema,
                outcomes=resolved_contract.outcomes,
            )
            entry_steps.append(projected_contract)
            if raw_step_id == selected_step_id:
                selected_contract = projected_contract

        context_entries = []
        if selected_step_id is not None:
            try:
                compiled_plan = compile_workflow_draft(draft)
                workflow = Workflow.model_validate(compiled_plan)
                context_entries = context_path_options_for_node(
                    workflow,
                    selected_step_id,
                )
                warnings.extend(context_analysis_warnings(workflow))
            except (KeyError, TypeError, ValueError) as exc:
                warnings.append(
                    f"runtime context unavailable for selected step "
                    f"{selected_step_id!r}: {exc}"
                )

        selected_input_targets = []
        selected_output_sources = []
        if selected_contract is not None and selected_step_id is not None:
            if selected_contract["step_id"] == selected_step_id:
                selected_input_targets = selected_contract.get("input_targets", [])
                selected_output_sources = selected_contract.get("output_sources", [])

        return project_authoring_contract_inventory(
            workspace_id=workspace_id,
            revision=checked.revision,
            selected_step_id=selected_step_id,
            input_schema=_authoring_schema(
                draft.get("input_schema"),
                field_name="input_schema",
                root="input",
                warnings=warnings,
            ),
            state_schema=_authoring_schema(
                draft.get("state_schema"),
                field_name="state_schema",
                root="state",
                warnings=warnings,
            ),
            output_schema=_authoring_schema(
                draft.get("output_schema"),
                field_name="output_schema",
                root="output",
                warnings=warnings,
            ),
            context_entries=context_entries,
            step_input_targets=selected_input_targets,
            step_output_sources=selected_output_sources,
            entry_steps=entry_steps,
            workflow_outcomes=_authoring_outcomes(draft.get("outcomes")),
            warnings=warnings,
        )

    async def delete_draft_workspace(
        self,
        *,
        workspace_id: str,
    ) -> DeleteDraftWorkspaceResult:
        return await self.drafts.delete_draft_workspace(workspace_id=workspace_id)

    async def validate_draft_workspace(
        self,
        *,
        workspace_id: str,
    ) -> DraftWorkspaceResult:
        return await self.drafts.validate_draft_workspace(workspace_id=workspace_id)

    async def compile_draft_workspace(
        self,
        *,
        workspace_id: str,
    ) -> CompileDraftWorkspaceResult:
        return await self.drafts.compile_draft_workspace(workspace_id=workspace_id)

    async def patch_draft_workspace(
        self,
        *,
        workspace_id: str,
        revision: int,
        patch: list[dict[str, Any]],
    ) -> DraftWorkspaceResult:
        return await self.drafts.patch_draft_workspace(
            workspace_id=workspace_id,
            revision=revision,
            patch=patch,
        )

    async def replace_draft_workspace_document(
        self,
        *,
        workspace_id: str,
        revision: int,
        draft: dict[str, Any],
    ) -> DraftWorkspaceResult:
        """Replace and semantically revalidate one complete workspace draft."""
        return await self.drafts.replace_draft_workspace_document(
            workspace_id=workspace_id,
            revision=revision,
            draft=draft,
        )

    async def set_draft_name(
        self,
        *,
        workspace_id: str,
        revision: int,
        name: str,
    ) -> DraftWorkspaceResult:
        return await self.drafts.set_draft_name(
            workspace_id=workspace_id,
            revision=revision,
            name=name,
        )

    async def set_draft_start(
        self,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
    ) -> DraftWorkspaceResult:
        return await self.drafts.set_draft_start(
            workspace_id=workspace_id,
            revision=revision,
            step_id=step_id,
        )

    async def set_draft_contract(
        self,
        *,
        workspace_id: str,
        revision: int,
        input_schema: dict[str, Any] | None = None,
        state_schema: dict[str, Any] | None = None,
        output_schema: dict[str, Any] | None = None,
        outcomes: Sequence[str] | None = None,
    ) -> DraftWorkspaceResult:
        return await self.drafts.set_draft_contract(
            workspace_id=workspace_id,
            revision=revision,
            input_schema=input_schema,
            state_schema=state_schema,
            output_schema=output_schema,
            outcomes=outcomes,
        )

    async def set_draft_route(
        self,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        outcome: str,
        target: str,
    ) -> DraftWorkspaceResult:
        return await self.drafts.set_draft_route(
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
        merge: bool = False,
    ) -> DraftWorkspaceResult:
        return await self.drafts.set_step_input_map(
            workspace_id=workspace_id,
            revision=revision,
            step_id=step_id,
            input_map=input_map,
            merge=merge,
        )

    async def set_step_input_bindings(
        self,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        bindings: Sequence[StepInputBinding],
    ) -> DraftWorkspaceResult:
        return await self.draft_authoring.set_step_input_bindings(
            workspace_id=workspace_id,
            revision=revision,
            step_id=step_id,
            bindings=bindings,
        )

    async def set_step_output_bindings(
        self,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        bindings: Sequence[OutputBinding],
    ) -> DraftWorkspaceResult:
        return await self.draft_authoring.set_step_output_bindings(
            workspace_id=workspace_id,
            revision=revision,
            step_id=step_id,
            bindings=bindings,
        )

    async def update_capability_step(
        self,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        update: CapabilityStepUpdate,
    ) -> DraftWorkspaceResult:
        """Return the updated workspace summary or a revision-conflict payload."""
        return await self.draft_authoring.update_capability_step(
            workspace_id=workspace_id,
            revision=revision,
            step_id=step_id,
            update=update,
        )

    async def set_step_output_map(
        self,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        output_map: dict[str, str],
        merge: bool = False,
    ) -> DraftWorkspaceResult:
        return await self.drafts.set_step_output_map(
            workspace_id=workspace_id,
            revision=revision,
            step_id=step_id,
            output_map=output_map,
            merge=merge,
        )

    async def set_workflow_output_map(
        self,
        *,
        workspace_id: str,
        revision: int,
        output_map: dict[str, str],
        merge: bool = False,
    ) -> DraftWorkspaceResult:
        return await self.drafts.set_workflow_output_map(
            workspace_id=workspace_id,
            revision=revision,
            output_map=output_map,
            merge=merge,
        )

    async def set_workflow_output_bindings(
        self,
        *,
        workspace_id: str,
        revision: int,
        bindings: Sequence[InputBinding],
    ) -> DraftWorkspaceResult:
        return await self.draft_authoring.set_workflow_output_bindings(
            workspace_id=workspace_id,
            revision=revision,
            bindings=bindings,
        )

    async def bind_draft(
        self,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        source_path: str,
        target_path: str,
    ) -> DraftWorkspaceResult:
        return await self.draft_authoring.bind_draft(
            workspace_id=workspace_id,
            revision=revision,
            step_id=step_id,
            source_path=source_path,
            target_path=target_path,
        )

    async def add_step_from_capability(
        self,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        capability_name: str,
        route_from_step: str | None = None,
        route_from_outcome: str = "ok",
        routes: dict[str, str] | None = None,
        input_map: dict[str, str] | None = None,
        input_bindings: Sequence[StepInputBinding] | None = None,
        bind_outputs: dict[str, str] | None = None,
        desc: str | None = None,
        retry: int | None = None,
        timeout_seconds: int | None = None,
    ) -> DraftWorkspaceResult:
        return await self.draft_authoring.add_step_from_capability(
            workspace_id=workspace_id,
            revision=revision,
            step_id=step_id,
            capability_name=capability_name,
            route_from_step=route_from_step,
            route_from_outcome=route_from_outcome,
            routes=routes,
            input_map=input_map,
            input_bindings=input_bindings,
            bind_outputs=bind_outputs,
            desc=desc,
            retry=retry,
            timeout_seconds=timeout_seconds,
        )

    async def add_step(
        self,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        step: DraftStep,
        incoming: RouteSource | None = None,
        routes: dict[str, str] | None = None,
    ) -> DraftWorkspaceResult:
        return await self.draft_authoring.add_step(
            workspace_id=workspace_id,
            revision=revision,
            step_id=step_id,
            step=step,
            incoming=incoming,
            routes=routes,
        )

    async def branch_draft(
        self,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        routes: dict[str, str],
    ) -> DraftWorkspaceResult:
        return await self.draft_authoring.branch_draft(
            workspace_id=workspace_id,
            revision=revision,
            step_id=step_id,
            routes=routes,
        )

    async def handle_draft(
        self,
        *,
        workspace_id: str,
        revision: int,
        branches: list[dict[str, str]],
        target: str,
    ) -> DraftWorkspaceResult:
        refs = [
            RouteSource(step_id=b["step_id"], outcome=b["outcome"]) for b in branches
        ]
        return await self.draft_authoring.handle_draft(
            workspace_id=workspace_id,
            revision=revision,
            branches=refs,
            target=target,
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
        input: Sequence[StepInputBinding] | None = None,
        output: Sequence[OutputBinding] | None = None,
        input_map: dict[str, str] | None = None,
        output_map: dict[str, str] | None = None,
        error_message_source: Any | None = None,
        title: str | None = None,
    ) -> DraftWorkspaceResult:
        return await self.draft_authoring.create_minimal_draft_workspace(
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

    async def remove_draft_route(
        self,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        outcome: str,
    ) -> DraftWorkspaceResult:
        return await self.draft_authoring.remove_draft_route(
            workspace_id=workspace_id,
            revision=revision,
            step_id=step_id,
            outcome=outcome,
        )

    async def remove_draft_step(
        self,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
    ) -> DraftWorkspaceResult:
        return await self.draft_authoring.remove_draft_step(
            workspace_id=workspace_id,
            revision=revision,
            step_id=step_id,
        )

    async def remove_draft_binding(
        self,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        inputs: Sequence[str] = (),
        outputs: Sequence[str] = (),
    ) -> DraftWorkspaceResult:
        return await self.draft_authoring.remove_draft_binding(
            workspace_id=workspace_id,
            revision=revision,
            step_id=step_id,
            inputs=inputs,
            outputs=outputs,
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
        input: Sequence[StepInputBinding] | None = None,
        output: Sequence[OutputBinding] | None = None,
        input_map: dict[str, str] | None = None,
        output_map: dict[str, str] | None = None,
        error_message_source: Any | None = None,
    ) -> CreateDraftWorkspaceFromCapabilityResult:
        return await self.capabilities.create_draft_workspace_from_capability(
            workspace_id=workspace_id,
            capability_name=capability_name,
            name=name,
            title=title,
            input_schema=input_schema,
            state_schema=state_schema,
            output_schema=output_schema,
            input=input,
            output=output,
            input_map=input_map,
            output_map=output_map,
            error_message_source=error_message_source,
        )

    # -- deployments --

    async def list_deployments(self) -> ListDeploymentsResult:
        return await self.deployments.list_deployments()

    async def inspect_deployment(
        self,
        *,
        deployment_id: str,
    ) -> WorkflowDeploymentPayload:
        return await self.deployments.inspect_deployment(deployment_id=deployment_id)

    async def save_deployment(
        self,
        deployment: dict[str, Any],
    ) -> SaveDeploymentResult:
        return await self.deployments.save_deployment(deployment)

    async def delete_deployment(
        self,
        *,
        deployment_id: str,
    ) -> DeleteDeploymentResult:
        return await self.deployments.delete_deployment(deployment_id=deployment_id)

    async def validate_deployment(
        self,
        *,
        deployment_id: str,
        live_check: bool = False,
    ) -> ValidateDeploymentResult:
        return await self.deployments.validate_deployment(
            deployment_id=deployment_id,
            live_check=live_check,
        )

    # -- runs --

    async def list_runs(
        self,
        *,
        status: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> ListRunsResult:
        return await self.runs.list_runs(
            status=status,
            cursor=cursor,
            limit=limit,
        )

    async def run_deployment(
        self,
        *,
        deployment_id: str,
        workflow_input: dict[str, Any],
        trace_range: TraceRangeLike | None = None,
    ) -> RunResult:
        return await self.runs.run_deployment(
            deployment_id=deployment_id,
            workflow_input=workflow_input,
            trace_range=trace_range,
        )

    async def resume_run(
        self,
        *,
        run_id: str,
        resume_payload: dict[str, Any],
        resume_outcome: str = "submitted",
        trace_range: TraceRangeLike | None = None,
    ) -> RunResult:
        return await self.runs.resume_run(
            run_id=run_id,
            resume_payload=resume_payload,
            resume_outcome=resume_outcome,
            trace_range=trace_range,
        )

    async def inspect_run(
        self,
        *,
        run_id: str,
    ) -> RunResult:
        return await self.runs.inspect_run(run_id=run_id)

    async def read_run_trace(
        self,
        *,
        run_id: str,
        trace_range: TraceRangeLike,
    ) -> RunTraceResult:
        return await self.runs.read_run_trace(
            run_id=run_id,
            trace_range=trace_range,
        )
