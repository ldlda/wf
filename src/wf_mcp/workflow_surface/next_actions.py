from __future__ import annotations

from enum import StrEnum
from typing import Any, Self

from pydantic import BaseModel, Field

from .wrapper_hints import WrapperAuthoringHints


class NextActionTool(StrEnum):
    """Stable MCP workflow tools that guidance may recommend."""

    PATCH_DRAFT_WORKSPACE = "wf.workflow.patch_draft_workspace"
    VALIDATE_DRAFT_WORKSPACE = "wf.workflow.validate_draft_workspace"
    VALIDATE_DEPLOYMENT = "wf.workflow.validate_deployment"
    RUN_DEPLOYMENT = "wf.workflow.run_deployment"
    RESUME_RUN = "wf.workflow.resume_run"
    READ_RUN_TRACE = "wf.workflow.read_run_trace"


class NextActionPatchExample(BaseModel):
    """Concrete example request for a recommended MCP workflow tool."""

    description: str = Field(description="Human-readable reason for this example.")
    tool: NextActionTool = Field(description="MCP workflow tool to call.")
    request: dict[str, Any] = Field(
        description="JSON request payload to pass to the tool."
    )


class NextActions(BaseModel):
    """Advisory continuation hints for MCP workflow clients.

    This object is guidance, not authority. Validation diagnostics and runtime
    status remain the source of truth; clients should treat this as a compact
    answer to "what tool should I call next?"
    """

    can_continue: bool = Field(
        description=(
            "Whether there is an obvious next workflow-surface tool call. "
            "Advisory only."
        )
    )
    can_save_now: bool | None = Field(
        default=None,
        description=(
            "Advisory wrapper-authoring signal. False means review is "
            "recommended before saving; the server does not enforce this."
        ),
    )
    recommended_next_tool: NextActionTool | None = Field(
        default=None,
        description="Suggested next MCP workflow tool, if one is obvious.",
    )
    reason: str = Field(description="Short explanation for the recommendation.")
    patch_examples: list[NextActionPatchExample] = Field(
        default_factory=list,
        description="Concrete JSON Patch examples for common missing decisions.",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Non-blocking warnings copied from low-confidence hints.",
    )

    @classmethod
    def from_wrapper_hints(
        cls,
        *,
        workspace_id: str,
        revision: int,
        hints: WrapperAuthoringHints | dict[str, Any],
    ) -> Self:
        """Create guidance after bootstrapping a wrapper draft workspace."""
        payload = (
            hints.model_dump(mode="json")
            if isinstance(hints, WrapperAuthoringHints)
            else hints
        )
        confidence = str(payload.get("confidence", "low"))
        missing_decisions = payload.get("missing_decisions")
        notes = [note for note in payload.get("notes", []) if isinstance(note, str)]
        has_missing = isinstance(missing_decisions, list) and len(missing_decisions) > 0
        can_save_now = confidence == "high" and not has_missing
        if can_save_now:
            return cls(
                can_continue=True,
                can_save_now=True,
                recommended_next_tool=NextActionTool.VALIDATE_DRAFT_WORKSPACE,
                reason="Wrapper hints are high confidence and have no missing decisions.",
                patch_examples=[],
                warnings=[],
            )

        return cls(
            can_continue=True,
            can_save_now=False,
            recommended_next_tool=NextActionTool.PATCH_DRAFT_WORKSPACE,
            reason="Review missing wrapper decisions before saving.",
            patch_examples=_wrapper_draft_patch_examples(
                workspace_id=workspace_id,
                revision=revision,
                hints=payload,
            ),
            warnings=notes,
        )


def _wrapper_draft_patch_examples(
    *,
    workspace_id: str,
    revision: int,
    hints: dict[str, Any],
) -> list[NextActionPatchExample]:
    """Return conservative JSON Patch examples without guessing semantics."""
    examples: list[NextActionPatchExample] = []
    missing_decisions = hints.get("missing_decisions")
    if not isinstance(missing_decisions, list):
        return examples
    decision_kinds = {
        str(decision.get("kind"))
        for decision in missing_decisions
        if isinstance(decision, dict)
    }
    if {"choose_output_fields", "review_nested_output"} & decision_kinds:
        examples.append(
            NextActionPatchExample(
                description=(
                    "Replace output bindings after choosing which capability "
                    "outputs should be written to workflow state."
                ),
                tool=NextActionTool.PATCH_DRAFT_WORKSPACE,
                request={
                    "workspace_id": workspace_id,
                    "revision": revision,
                    "patch": [
                        {
                            "op": "replace",
                            "path": "/draft/steps/call/output",
                            "value": [],
                        }
                    ],
                },
            )
        )
    if "confirm_boolean_outcomes" in decision_kinds:
        examples.append(
            NextActionPatchExample(
                description=(
                    "Review boolean output candidates before adding routing; "
                    "do not route on boolean fields automatically."
                ),
                tool=NextActionTool.PATCH_DRAFT_WORKSPACE,
                request={
                    "workspace_id": workspace_id,
                    "revision": revision,
                    "patch": [],
                },
            )
        )
    return examples
