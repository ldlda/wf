from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Protocol

from wf_artifacts import ArtifactKind

from .runs import TraceRangeLike


class WorkflowCapabilitySurface(Protocol):
    """Capability discovery methods exposed by workflow frontends."""

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


class WorkflowDraftSurface(Protocol):
    """Draft workspace methods exposed by workflow frontends.

    This protocol intentionally describes the transport-facing workflow surface,
    not every same-process authoring helper on ``WorkflowApi``.
    """

    async def list_draft_workspaces(self) -> dict[str, Any]: ...

    async def get_draft_workspace(
        self,
        *,
        workspace_id: str,
        include_draft: bool = False,
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
        merge: bool = False,
    ) -> dict[str, Any]: ...

    async def set_step_output_map(
        self,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        output_map: dict[str, str],
        merge: bool = False,
    ) -> dict[str, Any]: ...

    async def bind_draft(
        self,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        source_path: str,
        target_path: str,
    ) -> dict[str, Any]: ...

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
    ) -> dict[str, Any]: ...

    async def branch_draft(
        self,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        routes: dict[str, str],
    ) -> dict[str, Any]: ...

    async def handle_draft(
        self,
        *,
        workspace_id: str,
        revision: int,
        branches: list[dict[str, str]],
        target: str,
    ) -> dict[str, Any]: ...

    async def validate_draft_workspace(
        self,
        *,
        workspace_id: str,
    ) -> dict[str, Any]: ...

    async def compile_draft_workspace(
        self,
        *,
        workspace_id: str,
    ) -> dict[str, Any]: ...

    async def delete_draft_workspace(
        self,
        *,
        workspace_id: str,
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


class WorkflowArtifactSurface(Protocol):
    """Artifact catalog methods exposed by workflow frontends."""

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

    async def delete_artifact(
        self,
        *,
        artifact_id: str,
        version: int,
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


class WorkflowDeploymentSurface(Protocol):
    """Deployment methods exposed by workflow frontends."""

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


class WorkflowRunSurface(Protocol):
    """Run lifecycle methods exposed by workflow frontends."""

    async def list_runs(
        self,
        *,
        status: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]: ...

    async def run_deployment(
        self,
        *,
        deployment_id: str,
        workflow_input: dict[str, Any],
        trace_range: TraceRangeLike | None = None,
    ) -> dict[str, Any]: ...

    async def resume_run(
        self,
        *,
        run_id: str,
        resume_payload: dict[str, Any],
        resume_outcome: str = "submitted",
        trace_range: TraceRangeLike | None = None,
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
        trace_range: TraceRangeLike,
    ) -> dict[str, Any]: ...


class WorkflowApiSurface(
    WorkflowCapabilitySurface,
    WorkflowDraftSurface,
    WorkflowArtifactSurface,
    WorkflowDeploymentSurface,
    WorkflowRunSurface,
    Protocol,
):
    """Public workflow operation surface shared by local and remote adapters."""


class WorkflowSourceAdminSurface(Protocol):
    """Read-only source/admin methods exposed by platform frontends."""

    async def list_sources(
        self,
        *,
        cursor: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]: ...

    async def inspect_source(
        self,
        *,
        source_id: str,
    ) -> dict[str, Any]: ...

    async def diagnose_source(
        self,
        *,
        source_id: str,
    ) -> dict[str, Any]: ...


class WorkflowAdminSurface(Protocol):
    """Read-only connection/config admin methods exposed by platform frontends."""

    async def list_connections(self) -> dict[str, Any]: ...

    async def get_connection_statuses(self) -> dict[str, Any]: ...

    async def list_events(self) -> dict[str, Any]: ...

    async def list_auth_records(self) -> dict[str, Any]: ...

    async def inspect_auth_record(self, auth_ref: str) -> dict[str, Any]: ...

    async def save_auth_record(
        self,
        *,
        auth_ref: str,
        scheme: str,
        payload: Mapping[str, object],
        metadata: Mapping[str, object] | None = None,
    ) -> dict[str, Any]: ...

    async def delete_auth_record(self, auth_ref: str) -> dict[str, Any]: ...


class WorkflowSourceRegistrySurface(Protocol):
    """Desired source registry methods exposed by platform frontends."""

    async def list_registry_entries(
        self,
        *,
        cursor: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]: ...

    async def inspect_registry_entry(
        self,
        *,
        source_id: str,
    ) -> dict[str, Any]: ...

    async def add_registry_entry(
        self,
        *,
        entry: dict[str, Any],
    ) -> dict[str, Any]: ...

    async def update_registry_entry(
        self,
        *,
        source_id: str,
        patch: dict[str, Any],
    ) -> dict[str, Any]: ...

    async def enable_registry_entry(
        self,
        *,
        source_id: str,
    ) -> dict[str, Any]: ...

    async def disable_registry_entry(
        self,
        *,
        source_id: str,
    ) -> dict[str, Any]: ...

    async def remove_registry_entry(
        self,
        *,
        source_id: str,
    ) -> dict[str, Any]: ...

    async def apply_registry_changes(self) -> dict[str, Any]: ...


__all__ = [
    "WorkflowAdminSurface",
    "WorkflowApiSurface",
    "WorkflowArtifactSurface",
    "WorkflowCapabilitySurface",
    "WorkflowDeploymentSurface",
    "WorkflowDraftSurface",
    "WorkflowRunSurface",
    "WorkflowSourceAdminSurface",
    "WorkflowSourceRegistrySurface",
]
