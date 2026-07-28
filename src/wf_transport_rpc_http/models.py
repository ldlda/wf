from __future__ import annotations

from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from wf_api import CapabilityStepUpdate
from wf_api.models import TraceRange
from wf_artifacts.drafts.models import DraftStep
from wf_core.models.steps import InputBinding, OutputBinding


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


def _validate_workflow_outcomes(outcomes: list[str]) -> None:
    """Reject outcome lists that cannot form a public workflow contract."""
    if not outcomes:
        raise ValueError("workflow outcomes must contain at least one value")
    if any(not outcome.strip() for outcome in outcomes):
        raise ValueError("workflow outcomes must not contain blank values")
    if len({outcome.strip() for outcome in outcomes}) != len(outcomes):
        raise ValueError("workflow outcomes must be unique")


class CreateEmptyDraftWorkspaceParams(RpcParamsModel):
    workspace_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    title: str | None = None
    input_schema: dict[str, Any] | None = None
    state_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None
    outcomes: list[str] = Field(default_factory=lambda: ["ok"])

    @model_validator(mode="after")
    def validate_outcomes(self) -> Self:
        _validate_workflow_outcomes(self.outcomes)
        return self


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


class RouteSourceParams(RpcParamsModel):
    step_id: str = Field(min_length=1)
    outcome: str = Field(default="ok", min_length=1)


class AddDraftStepParams(RpcParamsModel):
    workspace_id: str = Field(min_length=1)
    revision: int = Field(ge=1)
    step_id: str = Field(min_length=1)
    step: DraftStep
    incoming: RouteSourceParams | None = None
    routes: dict[str, str] | None = None


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


class SetDraftStartParams(RpcParamsModel):
    workspace_id: str = Field(min_length=1)
    revision: int = Field(ge=1)
    step_id: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_step_id(self) -> Self:
        if not self.step_id.strip():
            raise ValueError("draft start step id must not be blank")
        return self


class SetDraftContractParams(RpcParamsModel):
    workspace_id: str = Field(min_length=1)
    revision: int = Field(ge=1)
    input_schema: dict[str, Any] | None = None
    state_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None
    outcomes: list[str] | None = None

    @model_validator(mode="after")
    def validate_contract_edit(self) -> Self:
        fields = (
            self.input_schema,
            self.state_schema,
            self.output_schema,
            self.outcomes,
        )
        if all(value is None for value in fields):
            raise ValueError("set_contract requires at least one contract field")
        if self.outcomes is not None:
            _validate_workflow_outcomes(self.outcomes)
        return self


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


class SetStepInputBindingsParams(RpcParamsModel):
    workspace_id: str = Field(min_length=1)
    revision: int = Field(ge=1)
    step_id: str = Field(min_length=1)
    bindings: list[InputBinding]


class SetStepOutputBindingsParams(RpcParamsModel):
    workspace_id: str = Field(min_length=1)
    revision: int = Field(ge=1)
    step_id: str = Field(min_length=1)
    bindings: list[OutputBinding]


class SetStepOutputMapParams(RpcParamsModel):
    workspace_id: str = Field(min_length=1)
    revision: int = Field(ge=1)
    step_id: str = Field(min_length=1)
    output_map: dict[str, str]
    merge: bool = False


class SetWorkflowOutputMapParams(RpcParamsModel):
    workspace_id: str = Field(min_length=1)
    revision: int = Field(ge=1)
    output_map: dict[str, str]
    merge: bool = False


class SetWorkflowOutputBindingsParams(RpcParamsModel):
    workspace_id: str = Field(min_length=1)
    revision: int = Field(ge=1)
    bindings: list[InputBinding]


class BindDraftParams(RpcParamsModel):
    workspace_id: str = Field(min_length=1)
    revision: int = Field(ge=1)
    step_id: str = Field(min_length=1)
    source_path: str = Field(min_length=1)
    target_path: str = Field(min_length=1)


class UpdateCapabilityStepParams(RpcParamsModel):
    workspace_id: str = Field(min_length=1)
    revision: int = Field(ge=1)
    step_id: str = Field(min_length=1)
    update: CapabilityStepUpdate


class AddStepFromCapabilityParams(RpcParamsModel):
    workspace_id: str = Field(min_length=1)
    revision: int = Field(ge=1)
    step_id: str = Field(min_length=1)
    capability_name: str = Field(min_length=1)
    route_from_step: str | None = None
    route_from_outcome: str = Field(default="ok", min_length=1)
    routes: dict[str, str] | None = None
    input_map: dict[str, str] | None = None
    input_bindings: list[InputBinding] | None = None
    bind_outputs: dict[str, str] = Field(default_factory=dict)
    desc: str | None = Field(default=None, min_length=1)
    retry: int | None = Field(default=None, ge=0)
    timeout_seconds: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_input_forms(self) -> Self:
        if {"input_map", "input_bindings"} <= self.model_fields_set:
            raise ValueError("input_map and input_bindings are mutually exclusive")
        return self


class BranchDraftParams(RpcParamsModel):
    workspace_id: str = Field(min_length=1)
    revision: int = Field(ge=1)
    step_id: str = Field(min_length=1)
    routes: dict[str, str]


class HandleDraftBranch(RpcParamsModel):
    step_id: str = Field(min_length=1)
    outcome: str = Field(min_length=1)


class HandleDraftParams(RpcParamsModel):
    workspace_id: str = Field(min_length=1)
    revision: int = Field(ge=1)
    branches: list[HandleDraftBranch]
    target: str = Field(min_length=1)


class RemoveDraftRouteParams(RpcParamsModel):
    workspace_id: str = Field(min_length=1)
    revision: int = Field(ge=1)
    step_id: str = Field(min_length=1)
    outcome: str = Field(min_length=1)


class RemoveDraftStepParams(RpcParamsModel):
    workspace_id: str = Field(min_length=1)
    revision: int = Field(ge=1)
    step_id: str = Field(min_length=1)


class RemoveDraftBindingParams(RpcParamsModel):
    workspace_id: str = Field(min_length=1)
    revision: int = Field(ge=1)
    step_id: str = Field(min_length=1)
    inputs: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)


class ValidateDraftWorkspaceParams(RpcParamsModel):
    workspace_id: str = Field(min_length=1)


class CompileDraftWorkspaceParams(RpcParamsModel):
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
