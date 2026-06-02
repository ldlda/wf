from __future__ import annotations

from collections.abc import Sequence
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

    @classmethod
    def from_deployment_validation(
        cls,
        *,
        deployment_id: str,
        diagnostics: Sequence[object],
    ) -> Self:
        """Create guidance after validate_deployment."""
        if not diagnostics:
            return cls(
                can_continue=True,
                can_save_now=None,
                recommended_next_tool=NextActionTool.RUN_DEPLOYMENT,
                reason=(
                    f"Deployment {deployment_id!r} is runnable; call "
                    "wf.workflow.run_deployment with workflow_input."
                ),
                patch_examples=[],
                warnings=[],
            )

        codes = {_diagnostic_field(diagnostic, "code") for diagnostic in diagnostics}
        warnings = [_diagnostic_warning(diagnostic) for diagnostic in diagnostics]
        if "source_unreachable" in codes:
            reason = (
                "One or more live sources are unreachable; fix or reconnect the "
                "source, then rerun wf.workflow.validate_deployment with live_check=true."
            )
        elif "source_missing" in codes or "binding_missing" in codes:
            reason = (
                "Deployment bindings or sources are missing; inspect the deployment "
                "and save corrected bindings before running."
            )
        elif "capability_missing" in codes or "schema_changed" in codes:
            reason = (
                "A required capability is missing or drifted; inspect capabilities "
                "or refresh sources, then validate again."
            )
        else:
            reason = (
                "Deployment is not runnable; inspect diagnostics, repair the "
                "deployment or sources, then validate again."
            )
        return cls(
            can_continue=True,
            can_save_now=None,
            recommended_next_tool=NextActionTool.VALIDATE_DEPLOYMENT,
            reason=reason,
            patch_examples=[],
            warnings=warnings,
        )

    @classmethod
    def from_run_result(
        cls,
        *,
        run_id: str | None,
        status: str,
        trace_count: int,
        diagnostics: Sequence[object],
    ) -> Self:
        """Create guidance after run_deployment, inspect_run, resume_run, or read_run_trace."""
        warnings = [_diagnostic_warning(diagnostic) for diagnostic in diagnostics]
        if status == "interrupted" and run_id is not None:
            return cls(
                can_continue=True,
                can_save_now=None,
                recommended_next_tool=NextActionTool.RESUME_RUN,
                reason=(
                    "Run is interrupted; call wf.workflow.resume_run with this "
                    "run_id and the interrupt response payload."
                ),
                patch_examples=[],
                warnings=warnings,
            )
        if status in {"failed", "unrunnable"}:
            examples = (
                [_bounded_trace_example(run_id=run_id, trace_count=trace_count)]
                if run_id is not None and trace_count > 0
                else []
            )
            return cls(
                can_continue=bool(examples),
                can_save_now=None,
                recommended_next_tool=(
                    NextActionTool.READ_RUN_TRACE if examples else None
                ),
                reason=(
                    "Run failed; read a bounded trace slice for debugging."
                    if examples
                    else "Run failed before producing trace entries; inspect diagnostics and error."
                ),
                patch_examples=examples,
                warnings=warnings,
            )
        if status == "completed":
            return cls(
                can_continue=False,
                can_save_now=None,
                recommended_next_tool=None,
                reason=(
                    "Run completed. No required next workflow tool; use read_run_trace "
                    "with a bounded trace_range only if debugging."
                ),
                patch_examples=[],
                warnings=warnings,
            )
        return cls(
            can_continue=False,
            can_save_now=None,
            recommended_next_tool=None,
            reason=f"Run status {status!r} has no obvious next workflow tool.",
            patch_examples=[],
            warnings=warnings,
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


def _diagnostic_field(diagnostic: object, field: str) -> str | None:
    """Read a diagnostic field from either a Pydantic model or a JSON dict."""
    if isinstance(diagnostic, dict):
        value = diagnostic.get(field)
    else:
        value = getattr(diagnostic, field, None)
    return value if isinstance(value, str) else None


def _diagnostic_warning(diagnostic: object) -> str:
    """Format one compact diagnostic warning for next_actions."""
    code = _diagnostic_field(diagnostic, "code") or "diagnostic"
    bound_source = _diagnostic_field(diagnostic, "bound_source")
    logical_ref = _diagnostic_field(diagnostic, "logical_ref")
    if bound_source:
        return f"{code}: {bound_source}"
    if logical_ref:
        return f"{code}: {logical_ref}"
    return code


def _bounded_trace_example(
    *,
    run_id: str,
    trace_count: int,
) -> NextActionPatchExample:
    """Return a safe read_run_trace request; never suggest full trace reads."""
    limit = max(1, min(25, trace_count))
    return NextActionPatchExample(
        description=(
            "Read a bounded debug trace slice. Increase start/limit only when needed."
        ),
        tool=NextActionTool.READ_RUN_TRACE,
        request={
            "run_id": run_id,
            "trace_range": {
                "start": 0,
                "limit": limit,
            },
        },
    )


__all__ = [
    "NextActionPatchExample",
    "NextActionTool",
    "NextActions",
]
