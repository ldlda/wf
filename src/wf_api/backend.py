from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from wf_artifacts import ArtifactKind


@dataclass(frozen=True, slots=True)
class TraceRange:
    """Caller-bounded debug trace slice for durable deployment runs."""

    start: int = 0
    limit: int = 25


@runtime_checkable
class WorkflowApiBackend(Protocol):
    """High-level workflow operation protocol.

    Implementations wrap a concrete service (e.g. WorkflowSurfaceHandlers
    backed by WfMcpService) so that wf_api never imports wf_mcp.
    """

    # -- capabilities --

    async def list_capabilities(
        self,
        *,
        query: str | None = None,
        source_id: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]: ...

    async def inspect_capability(
        self,
        *,
        qualified_name: str,
    ) -> dict[str, Any]: ...

    async def call_capability(
        self,
        *,
        qualified_name: str,
        payload: dict[str, Any],
        deployment_id: str | None = None,
    ) -> dict[str, Any]: ...

    # -- artifacts --

    async def list_artifacts(
        self,
        *,
        query: str | None = None,
        kind: ArtifactKind | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]: ...

    async def inspect_artifact(
        self,
        *,
        artifact_id: str,
        version: int,
    ) -> dict[str, Any]: ...

    async def save_artifact(
        self,
        artifact: dict[str, Any],
    ) -> dict[str, Any]: ...

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
    ) -> dict[str, Any]: ...

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
    ) -> dict[str, Any]: ...

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
    ) -> dict[str, Any]: ...

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
    ) -> dict[str, Any]: ...

    # -- drafts --

    async def validate_draft(
        self,
        *,
        draft: dict[str, Any],
    ) -> dict[str, Any]: ...

    async def compile_draft(
        self,
        *,
        draft: dict[str, Any],
    ) -> dict[str, Any]: ...

    async def patch_draft(
        self,
        *,
        draft: dict[str, Any],
        patch: list[dict[str, Any]],
    ) -> dict[str, Any]: ...

    # -- draft workspaces --

    async def list_draft_workspaces(self) -> dict[str, Any]: ...

    async def create_draft_workspace(
        self,
        *,
        workspace_id: str,
        draft: dict[str, Any],
        title: str | None = None,
    ) -> dict[str, Any]: ...

    async def get_draft_workspace(
        self,
        *,
        workspace_id: str,
        include_draft: bool = False,
    ) -> dict[str, Any]: ...

    async def delete_draft_workspace(
        self,
        *,
        workspace_id: str,
    ) -> dict[str, Any]: ...

    async def validate_draft_workspace(
        self,
        *,
        workspace_id: str,
    ) -> dict[str, Any]: ...

    async def patch_draft_workspace(
        self,
        *,
        workspace_id: str,
        revision: int,
        patch: list[dict[str, Any]],
    ) -> dict[str, Any]: ...

    async def set_draft_name(
        self,
        *,
        workspace_id: str,
        revision: int,
        name: str,
    ) -> dict[str, Any]: ...

    async def set_draft_route(
        self,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        outcome: str,
        target: str,
    ) -> dict[str, Any]: ...

    async def set_step_input_map(
        self,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        input_map: dict[str, str],
    ) -> dict[str, Any]: ...

    async def set_step_output_map(
        self,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        output_map: dict[str, str],
    ) -> dict[str, Any]: ...

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
    ) -> dict[str, Any]: ...

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
    ) -> dict[str, Any]: ...

    # -- deployments --

    async def list_deployments(self) -> dict[str, Any]: ...

    async def inspect_deployment(
        self,
        *,
        deployment_id: str,
    ) -> dict[str, Any]: ...

    async def save_deployment(
        self,
        deployment: dict[str, Any],
    ) -> dict[str, Any]: ...

    async def delete_deployment(
        self,
        *,
        deployment_id: str,
    ) -> dict[str, Any]: ...

    async def validate_deployment(
        self,
        *,
        deployment_id: str,
        live_check: bool = False,
    ) -> dict[str, Any]: ...

    # -- runs --

    async def run_deployment(
        self,
        *,
        deployment_id: str,
        workflow_input: dict[str, Any],
        trace_range: TraceRange | None = None,
    ) -> dict[str, Any]: ...

    async def resume_run(
        self,
        *,
        run_id: str,
        resume_payload: dict[str, Any],
        resume_outcome: str = "submitted",
        trace_range: TraceRange | None = None,
    ) -> dict[str, Any]: ...

    async def inspect_run(
        self,
        *,
        run_id: str,
    ) -> dict[str, Any]: ...

    async def read_run_trace(
        self,
        *,
        run_id: str,
        trace_range: TraceRange,
    ) -> dict[str, Any]: ...
