"""Canonical result models for persisted draft-workspace operations."""

from typing import Any, Literal, NotRequired, TypedDict

from .artifacts import RequiredCapabilityPayload
from .common import JsonObject, NextActionsPayload


class DraftDiagnosticPayload(TypedDict):
    """One validation or revision diagnostic attached to a draft workspace."""

    code: str
    path: str
    message: str
    step_id: NotRequired[str | None]
    repair_hint: NotRequired[str | None]
    details: NotRequired[JsonObject]


class DraftWorkspaceSummary(TypedDict):
    """Compact graph facts included with every persisted workspace result."""

    # Invalid workspaces preserve malformed authoring values for later repair.
    name: Any
    start: Any
    step_count: int
    route_count: int
    steps: list[str]


class DraftWorkspaceResult(TypedDict):
    """Canonical persisted workspace envelope returned after reads and edits."""

    workspace_id: str
    revision: int
    title: str | None
    status: Literal["valid", "invalid", "conflict"]
    diagnostics: list[DraftDiagnosticPayload]
    summary: DraftWorkspaceSummary
    draft: NotRequired[JsonObject]


class ListDraftWorkspacesResult(TypedDict):
    """All persisted draft-workspace summaries."""

    workspaces: list[DraftWorkspaceResult]


class DeleteDraftWorkspaceResult(TypedDict):
    """Outcome of deleting one persisted draft workspace."""

    workspace_id: str
    deleted: bool
    status: Literal["deleted", "not_found"]


class InvalidDraftResult(TypedDict):
    """Validation-only result returned when a draft cannot be compiled."""

    status: Literal["invalid"]
    diagnostics: list[DraftDiagnosticPayload]


class CompileDraftWorkspaceSuccess(TypedDict):
    """Compiled raw plan and dependencies for one valid draft workspace."""

    compiled_plan: JsonObject
    required_capabilities: dict[str, RequiredCapabilityPayload]


type CompileDraftWorkspaceResult = CompileDraftWorkspaceSuccess | InvalidDraftResult


class WrapperOutcomeCandidatePayload(TypedDict):
    """Possible wrapper outcome mapping that still requires caller judgment."""

    kind: Literal["boolean_control_field"]
    source: str
    candidate_outcomes: list[str]
    confidence: Literal["high", "medium", "low"]
    reason: str
    automatic: bool


class WrapperMissingDecisionPayload(TypedDict):
    """One unresolved wrapper-authoring decision."""

    kind: Literal[
        "choose_output_fields",
        "review_nested_output",
        "confirm_boolean_outcomes",
        "choose_error_mapping",
    ]
    message: str


class WrapperAuthoringHintsPayload(TypedDict):
    """Transport-neutral projection of conservative wrapper scaffolding hints."""

    capability_name: str
    confidence: Literal["high", "medium", "low"]
    declared_outcomes: list[str]
    suggested_wrapper_outcomes: list[str]
    outcome_policy: Literal[
        "preserve_declared",
        "manual_mapping_required",
    ]
    input_schema: JsonObject
    state_schema: JsonObject
    output_schema: JsonObject
    input_map: dict[str, str]
    output_map: dict[str, str]
    outcome_candidates: list[WrapperOutcomeCandidatePayload]
    missing_decisions: list[WrapperMissingDecisionPayload]
    notes: list[str]


class CreateDraftWorkspaceFromCapabilityResult(DraftWorkspaceResult):
    """Bootstrapped workspace plus the hints and next actions that shaped it."""

    wrapper_hints: WrapperAuthoringHintsPayload
    next_actions: NextActionsPayload


class UnsavedDraftArtifactResult(TypedDict):
    """Validation result when an invalid workspace is not saved as an artifact."""

    saved: Literal[False]
    workspace_id: str
    revision: int
    status: Literal["invalid"]
    diagnostics: list[DraftDiagnosticPayload]


class SavedDraftArtifactResult(TypedDict):
    """Saved artifact result with source-binding guidance derived from a draft."""

    artifact_id: str
    version: int
    saved: Literal[True]
    required_logical_sources: list[str]
    suggested_bindings: dict[str, str]


type CreateArtifactFromWorkspaceResult = (
    SavedDraftArtifactResult | UnsavedDraftArtifactResult
)
