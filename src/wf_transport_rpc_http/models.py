from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from wf_api.models import TraceRange


class RpcParamsModel(BaseModel):
    """Base transport DTO: reject misspelled JSON-RPC params early."""

    model_config = ConfigDict(extra="forbid")


class TraceRangeParams(RpcParamsModel):
    start: int = Field(default=0, ge=0, description="Zero-based trace offset.")
    limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum trace entries to return; full traces are never implicit.",
    )

    def to_api_trace_range(self) -> TraceRange:
        return TraceRange(start=self.start, limit=self.limit)


class HealthParams(RpcParamsModel):
    pass


class AdminEmptyParams(RpcParamsModel):
    pass


class ListCapabilitiesParams(RpcParamsModel):
    query: str | None = Field(default=None)
    source_id: str | None = Field(default=None)
    cursor: str | None = Field(default=None)
    limit: int = Field(default=50, ge=1, le=200)


class ListSourcesParams(RpcParamsModel):
    cursor: str | None = Field(default=None)
    limit: int = Field(default=50, ge=1, le=100)


class InspectSourceParams(RpcParamsModel):
    source_id: str = Field(min_length=1)


class DiagnoseSourceParams(RpcParamsModel):
    source_id: str = Field(min_length=1)


class InspectCapabilityParams(RpcParamsModel):
    qualified_name: str = Field(min_length=1)


class CallCapabilityParams(RpcParamsModel):
    qualified_name: str = Field(min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)
    deployment_id: str | None = None


class CreateDraftFromCapabilityParams(RpcParamsModel):
    workspace_id: str = Field(min_length=1)
    capability_name: str = Field(min_length=1)
    name: str | None = None
    title: str | None = None
    input_schema: dict[str, Any] | None = None
    state_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None
    input: list[Any] | None = None
    output: list[Any] | None = None
    input_map: dict[str, str] | None = None
    output_map: dict[str, str] | None = None
    error_message_source: Any | None = None


class PatchDraftParams(RpcParamsModel):
    draft: dict[str, Any]
    patch: list[dict[str, Any]]


class ValidateDraftParams(RpcParamsModel):
    draft: dict[str, Any]


class SaveArtifactParams(RpcParamsModel):
    artifact: dict[str, Any]


class SaveDeploymentParams(RpcParamsModel):
    deployment: dict[str, Any]


class ListDraftWorkspacesParams(RpcParamsModel):
    pass


class GetDraftWorkspaceParams(RpcParamsModel):
    workspace_id: str = Field(min_length=1)
    include_draft: bool = False


class PatchDraftWorkspaceParams(RpcParamsModel):
    workspace_id: str = Field(min_length=1)
    revision: int = Field(ge=1)
    patch: list[dict[str, Any]]


class SetDraftNameParams(RpcParamsModel):
    workspace_id: str = Field(min_length=1)
    revision: int = Field(ge=1)
    name: str = Field(min_length=1)


class SetDraftRouteParams(RpcParamsModel):
    workspace_id: str = Field(min_length=1)
    revision: int = Field(ge=1)
    step_id: str = Field(min_length=1)
    outcome: str = Field(min_length=1)
    target: str = Field(min_length=1)


class SetStepInputMapParams(RpcParamsModel):
    workspace_id: str = Field(min_length=1)
    revision: int = Field(ge=1)
    step_id: str = Field(min_length=1)
    input_map: dict[str, str]
    merge: bool = False


class SetStepOutputMapParams(RpcParamsModel):
    workspace_id: str = Field(min_length=1)
    revision: int = Field(ge=1)
    step_id: str = Field(min_length=1)
    output_map: dict[str, str]
    merge: bool = False


class AddStateFromOutputParams(RpcParamsModel):
    workspace_id: str = Field(min_length=1)
    revision: int = Field(ge=1)
    step_id: str = Field(min_length=1)
    output_field: str = Field(min_length=1)
    state_path: str = Field(min_length=1)


class BindOutputToStateParams(RpcParamsModel):
    workspace_id: str = Field(min_length=1)
    revision: int = Field(ge=1)
    step_id: str = Field(min_length=1)
    output_field: str = Field(min_length=1)
    state_path: str = Field(min_length=1)


class AddStepFromCapabilityParams(RpcParamsModel):
    workspace_id: str = Field(min_length=1)
    revision: int = Field(ge=1)
    step_id: str = Field(min_length=1)
    capability_name: str = Field(min_length=1)
    route_from_step: str | None = None
    route_from_outcome: str = Field(default="ok", min_length=1)
    route_outcome: str = Field(default="ok", min_length=1)
    route_to: str = Field(default="__end__", min_length=1)
    input_map: dict[str, str] = Field(default_factory=dict)
    bind_outputs: dict[str, str] = Field(default_factory=dict)


class ValidateDraftWorkspaceParams(RpcParamsModel):
    workspace_id: str = Field(min_length=1)


class DeleteDraftWorkspaceParams(RpcParamsModel):
    workspace_id: str = Field(min_length=1)


class CreateArtifactFromWorkspaceParams(RpcParamsModel):
    workspace_id: str = Field(min_length=1)
    artifact_id: str = Field(min_length=1)
    version: int = Field(ge=1)
    title: str = Field(min_length=1)
    outcomes: list[str]
    kind: Literal["workflow", "wrapper"] = "workflow"
    description: str | None = None
    required_capabilities: dict[str, dict[str, Any]] | None = None
    source_bindings: dict[str, str] | None = None
    created_from_catalog_version: str | None = None


class CreateWrapperFromWorkspaceParams(RpcParamsModel):
    workspace_id: str = Field(min_length=1)
    artifact_id: str = Field(min_length=1)
    version: int = Field(ge=1)
    title: str = Field(min_length=1)
    outcomes: list[str]
    description: str | None = None
    required_capabilities: dict[str, dict[str, Any]] | None = None
    source_bindings: dict[str, str] | None = None
    created_from_catalog_version: str | None = None


class CreateArtifactFromPlanParams(RpcParamsModel):
    artifact_id: str = Field(min_length=1)
    version: int = Field(ge=1)
    title: str = Field(min_length=1)
    plan: dict[str, Any]
    outcomes: list[str]
    kind: Literal["workflow", "wrapper"] = "workflow"
    description: str | None = None
    required_capabilities: dict[str, dict[str, Any]] | None = None
    source_bindings: dict[str, str] | None = None
    created_from_catalog_version: str | None = None


class ListArtifactsParams(RpcParamsModel):
    query: str | None = None
    kind: Literal["workflow", "wrapper"] | None = None
    cursor: str | None = None
    limit: int = Field(default=50, ge=1, le=100)


class InspectArtifactParams(RpcParamsModel):
    artifact_id: str = Field(min_length=1)
    version: int = Field(ge=1)


class DeleteArtifactParams(RpcParamsModel):
    artifact_id: str = Field(min_length=1)
    version: int = Field(ge=1)


class ListDeploymentsParams(RpcParamsModel):
    pass


class InspectDeploymentParams(RpcParamsModel):
    deployment_id: str = Field(min_length=1)


class DeleteDeploymentParams(RpcParamsModel):
    deployment_id: str = Field(min_length=1)


class ValidateDeploymentParams(RpcParamsModel):
    deployment_id: str = Field(min_length=1)
    live_check: bool = False


class ListRunsParams(RpcParamsModel):
    status: Literal["completed", "failed", "interrupted"] | None = None
    cursor: str | None = None
    limit: int = Field(default=50, ge=1, le=100)


class StartRunParams(RpcParamsModel):
    deployment_id: str = Field(min_length=1)
    workflow_input: dict[str, Any] = Field(default_factory=dict)
    trace_range: TraceRangeParams | None = None


class InspectRunParams(RpcParamsModel):
    run_id: str = Field(min_length=1)


class ReadRunTraceParams(RpcParamsModel):
    run_id: str = Field(min_length=1)
    trace_range: TraceRangeParams


class ResumeRunParams(RpcParamsModel):
    run_id: str = Field(min_length=1)
    resume_payload: dict[str, Any] = Field(default_factory=dict)
    resume_outcome: str = Field(default="submitted", min_length=1)
    trace_range: TraceRangeParams | None = None


class ListRegistryEntriesParams(RpcParamsModel):
    cursor: str | None = Field(default=None)
    limit: int = Field(default=50, ge=1, le=100)


class InspectRegistryEntryParams(RpcParamsModel):
    source_id: str = Field(min_length=1)


class AddRegistryEntryParams(RpcParamsModel):
    entry: dict[str, Any]


class UpdateRegistryEntryParams(RpcParamsModel):
    source_id: str = Field(min_length=1)
    patch: dict[str, Any]


class RegistryEntryIdParams(RpcParamsModel):
    source_id: str = Field(min_length=1)


class ApplyRegistryChangesParams(RpcParamsModel):
    pass


class InspectAuthParams(RpcParamsModel):
    auth_ref: str = Field(min_length=1)


class SaveAuthParams(RpcParamsModel):
    auth_ref: str = Field(min_length=1)
    scheme: str = Field(min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DeleteAuthParams(RpcParamsModel):
    auth_ref: str = Field(min_length=1)
