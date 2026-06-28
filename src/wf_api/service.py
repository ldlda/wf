from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from wf_artifacts import ArtifactKind

from .artifacts import WorkflowArtifactApi
from .capabilities import WorkflowCapabilityApi
from .deployments import WorkflowDeploymentApi
from .draft_authoring import DraftOutcomeRef, WorkflowDraftAuthoringApi
from .drafts import WorkflowDraftApi
from .models import RawWorkflowPlan
from .operation_context import WorkflowOperationContext
from .runs import TraceRangeLike, WorkflowRunApi


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
    ) -> dict[str, Any]:
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
    ) -> dict[str, Any]:
        return await self.capabilities.inspect_capability(qualified_name=qualified_name)

    async def call_capability(
        self,
        *,
        qualified_name: str,
        payload: dict[str, Any],
        deployment_id: str | None = None,
    ) -> dict[str, Any]:
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
    ) -> dict[str, Any]:
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
    ) -> dict[str, Any]:
        return await self.artifacts.inspect_artifact(
            artifact_id=artifact_id,
            version=version,
        )

    async def delete_artifact(
        self,
        *,
        artifact_id: str,
        version: int,
    ) -> dict[str, Any]:
        return await self.artifacts.delete_artifact(
            artifact_id=artifact_id,
            version=version,
        )

    async def save_artifact(
        self,
        artifact: dict[str, Any],
    ) -> dict[str, Any]:
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
    ) -> dict[str, Any]:
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
    ) -> dict[str, Any]:
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
    ) -> dict[str, Any]:
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
    ) -> dict[str, Any]:
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
    ) -> dict[str, Any]:
        return await self.drafts.validate_draft(draft=draft)

    async def compile_draft(
        self,
        *,
        draft: dict[str, Any],
    ) -> dict[str, Any]:
        return await self.drafts.compile_draft(draft=draft)

    async def patch_draft(
        self,
        *,
        draft: dict[str, Any],
        patch: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return await self.drafts.patch_draft(draft=draft, patch=patch)

    # -- draft workspaces --

    async def list_draft_workspaces(self) -> dict[str, Any]:
        return await self.drafts.list_draft_workspaces()

    async def create_draft_workspace(
        self,
        *,
        workspace_id: str,
        draft: dict[str, Any],
        title: str | None = None,
    ) -> dict[str, Any]:
        return await self.drafts.create_draft_workspace(
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
        return await self.drafts.get_draft_workspace(
            workspace_id=workspace_id,
            include_draft=include_draft,
        )

    async def delete_draft_workspace(
        self,
        *,
        workspace_id: str,
    ) -> dict[str, Any]:
        return await self.drafts.delete_draft_workspace(workspace_id=workspace_id)

    async def validate_draft_workspace(
        self,
        *,
        workspace_id: str,
    ) -> dict[str, Any]:
        return await self.drafts.validate_draft_workspace(workspace_id=workspace_id)

    async def compile_draft_workspace(
        self,
        *,
        workspace_id: str,
    ) -> dict[str, Any]:
        return await self.drafts.compile_draft_workspace(workspace_id=workspace_id)

    async def patch_draft_workspace(
        self,
        *,
        workspace_id: str,
        revision: int,
        patch: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return await self.drafts.patch_draft_workspace(
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
        return await self.drafts.set_draft_name(
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
    ) -> dict[str, Any]:
        return await self.drafts.set_step_input_map(
            workspace_id=workspace_id,
            revision=revision,
            step_id=step_id,
            input_map=input_map,
            merge=merge,
        )

    async def set_step_output_map(
        self,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        output_map: dict[str, str],
        merge: bool = False,
    ) -> dict[str, Any]:
        return await self.drafts.set_step_output_map(
            workspace_id=workspace_id,
            revision=revision,
            step_id=step_id,
            output_map=output_map,
            merge=merge,
        )

    async def bind_draft(
        self,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        source_path: str,
        target_path: str,
    ) -> dict[str, Any]:
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
        bind_outputs: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        return await self.draft_authoring.add_step_from_capability(
            workspace_id=workspace_id,
            revision=revision,
            step_id=step_id,
            capability_name=capability_name,
            route_from_step=route_from_step,
            route_from_outcome=route_from_outcome,
            routes=routes,
            input_map=input_map,
            bind_outputs=bind_outputs,
        )

    async def branch_draft(
        self,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        routes: dict[str, str],
    ) -> dict[str, Any]:
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
    ) -> dict[str, Any]:
        refs = [
            DraftOutcomeRef(step_id=b["step_id"], outcome=b["outcome"])
            for b in branches
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
        input: Sequence[Any] | None = None,
        output: Sequence[Any] | None = None,
        input_map: dict[str, str] | None = None,
        output_map: dict[str, str] | None = None,
        error_message_source: Any | None = None,
        title: str | None = None,
    ) -> dict[str, Any]:
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
    ) -> dict[str, Any]:
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
    ) -> dict[str, Any]:
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
    ) -> dict[str, Any]:
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
        input: Sequence[Any] | None = None,
        output: Sequence[Any] | None = None,
        input_map: dict[str, str] | None = None,
        output_map: dict[str, str] | None = None,
        error_message_source: Any | None = None,
    ) -> dict[str, Any]:
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

    async def list_deployments(self) -> dict[str, Any]:
        return await self.deployments.list_deployments()

    async def inspect_deployment(
        self,
        *,
        deployment_id: str,
    ) -> dict[str, Any]:
        return await self.deployments.inspect_deployment(deployment_id=deployment_id)

    async def save_deployment(
        self,
        deployment: dict[str, Any],
    ) -> dict[str, Any]:
        return await self.deployments.save_deployment(deployment)

    async def delete_deployment(
        self,
        *,
        deployment_id: str,
    ) -> dict[str, Any]:
        return await self.deployments.delete_deployment(deployment_id=deployment_id)

    async def validate_deployment(
        self,
        *,
        deployment_id: str,
        live_check: bool = False,
    ) -> dict[str, Any]:
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
    ) -> dict[str, Any]:
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
    ) -> dict[str, Any]:
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
    ) -> dict[str, Any]:
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
    ) -> dict[str, Any]:
        return await self.runs.inspect_run(run_id=run_id)

    async def read_run_trace(
        self,
        *,
        run_id: str,
        trace_range: TraceRangeLike,
    ) -> dict[str, Any]:
        return await self.runs.read_run_trace(
            run_id=run_id,
            trace_range=trace_range,
        )
