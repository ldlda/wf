from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

from wf_artifacts import ArtifactKind
from wf_artifacts.draft_workspaces.models import WORKSPACE_ID_PATTERN
from wf_core.models.steps import InputBinding, OutputBinding
from wf_core.paths import GraphSourcePath

WorkspaceId = Annotated[
    str,
    Field(
        pattern=WORKSPACE_ID_PATTERN,
        description="Draft workspace id. Use letters, numbers, underscore, dot, or dash.",
    ),
]
JsonSchemaObject = Annotated[
    dict[str, Any],
    Field(
        description=(
            "JSON Schema object. Keep this as ordinary JSON; nested schema fields "
            "are passed through unchanged."
        )
    ),
]
DraftPathMap = Annotated[
    dict[str, str],
    Field(
        description=(
            "Compatibility map form for draft paths. Prefer canonical input/output "
            "binding lists for new MCP/JSON clients."
        )
    ),
]
DraftInputBindings = Annotated[
    list[InputBinding],
    Field(
        description=(
            "Canonical node input bindings. Use path bindings such as "
            "{'target': {'root': 'local', 'parts': ['text']}, "
            "'path': {'root': 'input', 'parts': ['text']}} or value bindings "
            "with {'target': ..., 'value': ...}."
        )
    ),
]
DraftOutputBindings = Annotated[
    list[OutputBinding],
    Field(
        description=(
            "Canonical node output bindings. Example: {'source': {'root': "
            "'local', 'parts': ['echoed']}, 'target': {'root': 'state', "
            "'parts': ['echoed']}}."
        )
    ),
]
JsonPatchOperations = Annotated[
    list[dict[str, Any]],
    Field(description="RFC 6902 JSON Patch operations."),
]
SourceBindings = Annotated[
    dict[str, str],
    Field(
        description=(
            "Map logical source ids in the draft/artifact to concrete runtime "
            "sources, for example {'demo': 'demo.personal', 'wf.std': 'wf.std'}."
        )
    ),
]
ErrorMessageSource = Annotated[
    GraphSourcePath | str,
    Field(
        description=(
            "State path for runtime_error.message. Prefer structural paths such "
            "as {'root': 'state', 'parts': ['error_message']}; strings like "
            "state.error_message remain compatibility input."
        )
    ),
]


class CallCapabilityResult(BaseModel):
    """Inspector-visible response contract for testing one workflow capability."""

    qualified_name: str = Field(description="Capability name that was executed.")
    source_id: str | None = Field(
        default=None,
        description="Capability source that owned the executed node spec.",
    )
    kind: Literal["node_spec", "wrapper_artifact"] = Field(
        description=(
            "Indicates whether this call executed a live NodeSpec or a saved "
            "wrapper artifact."
        )
    )
    deployment_id: str | None = Field(
        default=None,
        description="Deployment used to resolve logical bindings, if any.",
    )
    outcome: str = Field(description="Workflow outcome returned by the capability.")
    output: dict[str, Any] | None = Field(
        default=None,
        description="Normalized workflow-facing output payload.",
    )
    diagnostics: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Structured diagnostics. Empty for successful calls.",
    )


class TraceRange(BaseModel):
    """Bounded debug trace slice request for deployment runs."""

    start: int = Field(
        default=0,
        ge=0,
        description="Zero-based trace entry offset to start reading from.",
    )
    limit: int = Field(
        default=25,
        ge=1,
        le=100,
        description="Maximum trace entries to return. Keep this small.",
    )


class DraftWorkspaceResult(BaseModel):
    """Inspector-visible response contract for draft workspace operations."""

    workspace_id: str = Field(description="Mutable draft workspace id.")
    revision: int = Field(description="Current optimistic-concurrency revision.")
    title: str | None = Field(default=None, description="Optional workspace title.")
    status: str = Field(description="Workspace validation status.")
    diagnostics: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Structured diagnostics for invalid or conflicted workspaces.",
    )
    summary: dict[str, Any] = Field(
        description="Compact draft summary for progressive MCP clients."
    )
    draft: dict[str, Any] | None = Field(
        default=None,
        description="Full draft document, only returned when requested.",
    )


class DraftWorkspaceListResult(BaseModel):
    """Inspector-visible response for listing stored draft workspaces."""

    workspaces: list[dict[str, Any]] = Field(
        description="Compact draft workspace summaries. Full drafts are omitted."
    )


class CreateDraftWorkspaceRequest(BaseModel):
    """Typed MCP request payload for creating a stored draft workspace."""

    workspace_id: WorkspaceId
    draft: dict[str, Any] = Field(
        description=(
            "WorkflowDraft JSON document. Prefer create_minimal_draft_workspace "
            "for a one-capability bootstrap, then patch this workspace by revision."
        )
    )
    title: str | None = Field(default=None, description="Optional workspace title.")


class PatchDraftWorkspaceRequest(BaseModel):
    """Typed MCP request payload for revision-checked draft workspace patching."""

    workspace_id: WorkspaceId
    revision: int = Field(ge=1, description="Expected current workspace revision.")
    patch: JsonPatchOperations = Field(
        description=(
            "RFC 6902 JSON Patch operations against the stored WorkflowDraft. "
            "Use focused helpers such as set_draft_route or set_step_input_map "
            "when possible."
        )
    )


class ValidateDraftWorkspaceRequest(BaseModel):
    """Typed MCP request for refreshing one workspace validation status."""

    workspace_id: WorkspaceId


class SetDraftNameRequest(BaseModel):
    """Typed MCP request for changing the workflow draft name."""

    workspace_id: WorkspaceId
    revision: int = Field(ge=1, description="Expected current workspace revision.")
    name: str = Field(description="New workflow draft name.")


class SetDraftRouteRequest(BaseModel):
    """Typed MCP request for setting one outcome route on one draft step."""

    workspace_id: WorkspaceId
    revision: int = Field(ge=1, description="Expected current workspace revision.")
    step_id: str = Field(description="Draft step id whose route should be edited.")
    outcome: str = Field(description="Outcome label to route, for example ok or error.")
    target: str = Field(description="Target step id or __end__.")


class SetStepInputMapRequest(BaseModel):
    """Typed MCP request for replacing one step input map."""

    workspace_id: WorkspaceId
    revision: int = Field(ge=1, description="Expected current workspace revision.")
    step_id: str = Field(description="Draft step id whose input map should change.")
    input_map: DraftPathMap


class SetStepOutputMapRequest(BaseModel):
    """Typed MCP request for replacing one step output map."""

    workspace_id: WorkspaceId
    revision: int = Field(ge=1, description="Expected current workspace revision.")
    step_id: str = Field(description="Draft step id whose output map should change.")
    output_map: DraftPathMap


class DeleteDraftWorkspaceRequest(BaseModel):
    """Typed MCP request payload for deleting one draft workspace."""

    workspace_id: WorkspaceId


class DeleteDraftWorkspaceResult(BaseModel):
    """Inspector-visible response for draft workspace cleanup."""

    workspace_id: str = Field(description="Draft workspace id targeted for deletion.")
    deleted: bool = Field(description="True when a stored workspace was removed.")
    status: Literal["deleted", "not_found"] = Field(description="Cleanup result.")


class CreateMinimalDraftWorkspaceRequest(BaseModel):
    """Typed MCP request payload for bootstrapping one-capability drafts."""

    workspace_id: WorkspaceId
    name: str = Field(description="Workflow draft name.")
    capability_name: str = Field(
        description=(
            "Workflow capability to call, such as demo.default.echo_tool or "
            "workflow.echo_wrapper.v1. Inspect it first when unsure."
        )
    )
    input_schema: JsonSchemaObject = Field(
        description="Public input JSON Schema for the workflow or wrapper being drafted."
    )
    state_schema: JsonSchemaObject = Field(
        description=(
            "Workflow state JSON Schema. Prefer object properties with reducer "
            "extension keywords; legacy fields input is compatibility-only."
        )
    )
    output_schema: JsonSchemaObject = Field(
        description="Public output JSON Schema for the workflow or wrapper being drafted."
    )
    input: DraftInputBindings | None = Field(
        default=None,
        description=(
            "Preferred canonical input bindings for the called capability. "
            "Use this instead of input_map for new clients."
        ),
    )
    output: DraftOutputBindings | None = Field(
        default=None,
        description=(
            "Preferred canonical output bindings for writes into workflow state. "
            "Use this instead of output_map for new clients."
        ),
    )
    input_map: DraftPathMap | None = Field(
        default=None,
        description=(
            "Deprecated compatibility map from workflow paths to local capability "
            "input paths, for example {'input.text': 'message'}."
        ),
    )
    output_map: DraftPathMap | None = Field(
        default=None,
        description=(
            "Deprecated compatibility map from local capability output paths to "
            "workflow state paths, for example {'echoed': 'state.echoed'}."
        ),
    )
    error_message_source: ErrorMessageSource | None = Field(
        default=None,
        description=(
            "Optional state path used as runtime_error.message when the capability "
            "has an error outcome, for example state.error_message. If omitted, "
            "the generated error route uses a static default message."
        ),
    )
    title: str | None = Field(default=None, description="Optional workspace title.")


class CreateDraftWorkspaceFromCapabilityRequest(BaseModel):
    """Typed MCP request for bootstrapping a draft from wrapper hints."""

    workspace_id: WorkspaceId
    capability_name: str = Field(
        description=(
            "Workflow capability to inspect and call, such as "
            "demo.default.echo_tool or workflow.echo_wrapper.v1."
        )
    )
    name: str | None = Field(
        default=None,
        description="Optional workflow draft name. Defaults to a safe capability name.",
    )
    title: str | None = Field(default=None, description="Optional workspace title.")
    input_schema: JsonSchemaObject | None = Field(
        default=None,
        description="Optional override for the hinted public input schema.",
    )
    state_schema: JsonSchemaObject | None = Field(
        default=None,
        description="Optional override for the hinted workflow state schema.",
    )
    output_schema: JsonSchemaObject | None = Field(
        default=None,
        description="Optional override for the hinted public output schema.",
    )
    input: DraftInputBindings | None = Field(
        default=None,
        description="Optional canonical override for the hinted workflow input bindings.",
    )
    output: DraftOutputBindings | None = Field(
        default=None,
        description="Optional canonical override for the hinted capability output bindings.",
    )
    input_map: DraftPathMap | None = Field(
        default=None,
        description="Deprecated compatibility override for the hinted workflow input map.",
    )
    output_map: DraftPathMap | None = Field(
        default=None,
        description=(
            "Deprecated compatibility override for the hinted capability output map."
        ),
    )
    error_message_source: ErrorMessageSource | None = Field(
        default=None,
        description=(
            "Optional state path used as runtime_error.message when the capability "
            "has an error outcome, for example state.error_message. If omitted, "
            "the generated error route uses a static default message."
        ),
    )


class CreateDraftWorkspaceFromCapabilityResult(DraftWorkspaceResult):
    """Draft workspace result plus the wrapper hints used to bootstrap it."""

    wrapper_hints: dict[str, Any] = Field(
        description=(
            "The wrapper_hints payload used before applying request overrides. "
            "Use this to patch uncertain maps or schemas by revision."
        )
    )


class CreateArtifactFromWorkspaceRequest(BaseModel):
    """Typed MCP request payload for saving a draft workspace as an artifact."""

    workspace_id: WorkspaceId
    artifact_id: str = Field(
        description=(
            "Immutable artifact id to write. Use a stable snake_case name; each "
            "version is saved separately."
        )
    )
    version: int = Field(ge=1, description="Artifact version to write.")
    title: str = Field(description="Human-readable artifact title.")
    outcomes: list[str] = Field(
        description=(
            "Public outcomes for this saved artifact, for example ['completed'] "
            "or ['completed', 'failed']."
        )
    )
    kind: ArtifactKind = Field(default="workflow", description="Artifact kind.")
    description: str | None = Field(default=None, description="Optional description.")
    required_capabilities: dict[str, dict[str, Any]] | None = Field(
        default=None,
        description="Optional explicit dependency contract override.",
    )
    source_bindings: SourceBindings | None = Field(
        default=None,
        description="Optional logical-to-concrete source bindings.",
    )
    created_from_catalog_version: str | None = Field(
        default=None,
        description="Optional catalog version used while authoring.",
    )


class CreateWrapperFromWorkspaceRequest(BaseModel):
    """Typed MCP request for saving a draft workspace as a wrapper artifact."""

    workspace_id: WorkspaceId
    artifact_id: str = Field(
        description=(
            "Immutable wrapper artifact id to write. The callable capability name "
            "will be workflow.<artifact_id>.v<version>."
        )
    )
    version: int = Field(ge=1, description="Wrapper artifact version to write.")
    title: str = Field(description="Human-readable wrapper title.")
    outcomes: list[str] = Field(
        description=(
            "Wrapper-level outcomes exposed to graphs and call_capability. Use "
            "explicit outcomes when the wrapper normalizes provider status/error shapes."
        )
    )
    description: str | None = Field(
        default=None,
        description=(
            "Optional description of what raw capability shape this wrapper normalizes."
        ),
    )
    required_capabilities: dict[str, dict[str, Any]] | None = Field(
        default=None,
        description="Optional explicit dependency contract override.",
    )
    source_bindings: SourceBindings | None = Field(
        default=None,
        description="Optional logical-to-concrete source bindings.",
    )
    created_from_catalog_version: str | None = Field(
        default=None,
        description="Optional catalog version used while authoring.",
    )
