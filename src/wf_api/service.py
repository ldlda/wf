from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from wf_artifacts import ArtifactKind

from .backend import TraceRange, WorkflowApiBackend


class WorkflowApi:
    """Protocol-neutral workflow application facade.

    Delegates every operation to a WorkflowApiBackend implementation.
    This class owns no business logic; it exists so that callers
    (wf_cli, wf_mcp tools, future HTTP adapters) share one entry point
    that does not import wf_mcp.
    """

    def __init__(self, backend: WorkflowApiBackend) -> None:
        self.backend: WorkflowApiBackend = backend

    # -- capabilities --

    async def list_capabilities(
        self,
        *,
        query: str | None = None,
        source_id: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        return await self.backend.list_capabilities(
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
        return await self.backend.inspect_capability(qualified_name=qualified_name)

    async def call_capability(
        self,
        *,
        qualified_name: str,
        payload: dict[str, Any],
        deployment_id: str | None = None,
    ) -> dict[str, Any]:
        return await self.backend.call_capability(
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
        return await self.backend.list_artifacts(
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
        return await self.backend.inspect_artifact(
            artifact_id=artifact_id,
            version=version,
        )

    async def save_artifact(
        self,
        artifact: dict[str, Any],
    ) -> dict[str, Any]:
        return await self.backend.save_artifact(artifact)

    async def create_artifact_from_plan(
        self,
        *,
        artifact_id: str,
        version: int,
        title: str,
        plan: dict[str, Any],
        outcomes: Sequence[str],
        kind: ArtifactKind = "workflow",
        description: str | None = None,
        required_capabilities: dict[str, dict[str, Any]] | None = None,
        source_bindings: dict[str, str] | None = None,
        created_from_catalog_version: str | None = None,
    ) -> dict[str, Any]:
        return await self.backend.create_artifact_from_plan(
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
        return await self.backend.create_artifact_from_draft(
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
        return await self.backend.create_artifact_from_workspace(
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
        return await self.backend.create_wrapper_from_workspace(
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
        return await self.backend.validate_draft(draft=draft)

    async def compile_draft(
        self,
        *,
        draft: dict[str, Any],
    ) -> dict[str, Any]:
        return await self.backend.compile_draft(draft=draft)

    async def patch_draft(
        self,
        *,
        draft: dict[str, Any],
        patch: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return await self.backend.patch_draft(draft=draft, patch=patch)

    # -- draft workspaces --

    async def list_draft_workspaces(self) -> dict[str, Any]:
        return await self.backend.list_draft_workspaces()

    async def create_draft_workspace(
        self,
        *,
        workspace_id: str,
        draft: dict[str, Any],
        title: str | None = None,
    ) -> dict[str, Any]:
        return await self.backend.create_draft_workspace(
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
        return await self.backend.get_draft_workspace(
            workspace_id=workspace_id,
            include_draft=include_draft,
        )

    async def delete_draft_workspace(
        self,
        *,
        workspace_id: str,
    ) -> dict[str, Any]:
        return await self.backend.delete_draft_workspace(workspace_id=workspace_id)

    async def validate_draft_workspace(
        self,
        *,
        workspace_id: str,
    ) -> dict[str, Any]:
        return await self.backend.validate_draft_workspace(workspace_id=workspace_id)

    async def patch_draft_workspace(
        self,
        *,
        workspace_id: str,
        revision: int,
        patch: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return await self.backend.patch_draft_workspace(
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
        return await self.backend.set_draft_name(
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
        return await self.backend.set_draft_route(
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
        return await self.backend.set_step_input_map(
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
        return await self.backend.set_step_output_map(
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
        input: Sequence[Any] | None = None,
        output: Sequence[Any] | None = None,
        input_map: dict[str, str] | None = None,
        output_map: dict[str, str] | None = None,
        error_message_source: Any | None = None,
        title: str | None = None,
    ) -> dict[str, Any]:
        return await self.backend.create_minimal_draft_workspace(
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
        input: Sequence[Any] | None = None,
        output: Sequence[Any] | None = None,
        input_map: dict[str, str] | None = None,
        output_map: dict[str, str] | None = None,
        error_message_source: Any | None = None,
    ) -> dict[str, Any]:
        return await self.backend.create_draft_workspace_from_capability(
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
        return await self.backend.list_deployments()

    async def inspect_deployment(
        self,
        *,
        deployment_id: str,
    ) -> dict[str, Any]:
        return await self.backend.inspect_deployment(deployment_id=deployment_id)

    async def save_deployment(
        self,
        deployment: dict[str, Any],
    ) -> dict[str, Any]:
        return await self.backend.save_deployment(deployment)

    async def delete_deployment(
        self,
        *,
        deployment_id: str,
    ) -> dict[str, Any]:
        return await self.backend.delete_deployment(deployment_id=deployment_id)

    async def validate_deployment(
        self,
        *,
        deployment_id: str,
        live_check: bool = False,
    ) -> dict[str, Any]:
        return await self.backend.validate_deployment(
            deployment_id=deployment_id,
            live_check=live_check,
        )

    # -- runs --

    async def run_deployment(
        self,
        *,
        deployment_id: str,
        workflow_input: dict[str, Any],
        trace_range: TraceRange | None = None,
    ) -> dict[str, Any]:
        return await self.backend.run_deployment(
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
        trace_range: TraceRange | None = None,
    ) -> dict[str, Any]:
        return await self.backend.resume_run(
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
        return await self.backend.inspect_run(run_id=run_id)

    async def read_run_trace(
        self,
        *,
        run_id: str,
        trace_range: TraceRange,
    ) -> dict[str, Any]:
        return await self.backend.read_run_trace(
            run_id=run_id,
            trace_range=trace_range,
        )
