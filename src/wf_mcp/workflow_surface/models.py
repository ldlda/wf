from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

from wf_artifacts import ArtifactKind
from wf_artifacts.draft_workspaces.models import WORKSPACE_ID_PATTERN

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
            "Map local draft paths to workflow paths, for example "
            "{'input.text': 'text'} or {'echoed': 'state.echoed'}."
        )
    ),
]
JsonPatchOperations = Annotated[
    list[dict[str, Any]],
    Field(description="RFC 6902 JSON Patch operations."),
]
SourceBindings = Annotated[
    dict[str, str],
    Field(description="Map logical source ids to concrete source ids."),
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


class CreateDraftWorkspaceRequest(BaseModel):
    """Typed MCP request payload for creating a stored draft workspace."""

    workspace_id: WorkspaceId
    draft: dict[str, Any] = Field(description="WorkflowDraft JSON document.")
    title: str | None = Field(default=None, description="Optional workspace title.")


class PatchDraftWorkspaceRequest(BaseModel):
    """Typed MCP request payload for revision-checked draft workspace patching."""

    workspace_id: WorkspaceId
    revision: int = Field(ge=1, description="Expected current workspace revision.")
    patch: JsonPatchOperations


class CreateMinimalDraftWorkspaceRequest(BaseModel):
    """Typed MCP request payload for bootstrapping one-capability drafts."""

    workspace_id: WorkspaceId
    name: str = Field(description="Workflow draft name.")
    capability_name: str = Field(
        description="Workflow capability to call, such as demo.default.echo_tool."
    )
    input_schema: JsonSchemaObject
    state_schema: JsonSchemaObject
    output_schema: JsonSchemaObject
    input_map: DraftPathMap
    output_map: DraftPathMap
    error_message_source: str | None = Field(
        default=None,
        description=(
            "Optional state path used as runtime_error.message when the capability "
            "has an error outcome, for example state.error_message."
        ),
    )
    title: str | None = Field(default=None, description="Optional workspace title.")


class CreateArtifactFromWorkspaceRequest(BaseModel):
    """Typed MCP request payload for saving a draft workspace as an artifact."""

    workspace_id: WorkspaceId
    artifact_id: str = Field(description="Immutable artifact id to write.")
    version: int = Field(ge=1, description="Artifact version to write.")
    title: str = Field(description="Human-readable artifact title.")
    outcomes: list[str] = Field(description="Artifact-level outcomes.")
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
