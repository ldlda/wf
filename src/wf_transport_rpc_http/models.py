from __future__ import annotations

from typing import Any

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


class ListCapabilitiesParams(RpcParamsModel):
    query: str | None = Field(default=None)
    source_id: str | None = Field(default=None)
    cursor: str | None = Field(default=None)
    limit: int = Field(default=50, ge=1, le=200)


class InspectCapabilityParams(RpcParamsModel):
    qualified_name: str = Field(min_length=1)


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


class ValidateDeploymentParams(RpcParamsModel):
    deployment_id: str = Field(min_length=1)
    live_check: bool = False


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
