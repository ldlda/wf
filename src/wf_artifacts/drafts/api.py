from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from copy import deepcopy
from typing import Any

import jsonpatch
from pydantic import BaseModel, Field, ValidationError

from wf_core.models.schemas import NodeDef
from wf_core.models.steps import OutputBinding
from wf_core.models.workflow import Workflow
from wf_core.validation.issues import ValidationIssue, ValidationIssueCode

from .adapter import build_workflow_from_draft
from .models import WorkflowDraft

DRAFT_INVALID_CODE = "draft_invalid"
PATCH_INVALID_CODE = "patch_invalid"
DRAFT_NOT_OBJECT_CODE = "draft_not_object"
UNKNOWN_OUTCOME_CODE = "unknown_outcome"

JsonObject = dict[str, Any]
JsonPatch = list[dict[str, Any]]
OutcomeLookup = Callable[[str], tuple[str, ...] | None]
NodeDefsForDraft = Callable[[JsonObject], Sequence[NodeDef]]


class DraftDiagnostic(BaseModel):
    """Machine-readable reason a keyed draft could not be compiled."""

    code: str
    path: str
    step_id: str | None = None
    message: str
    repair_hint: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


def compile_workflow_draft(draft: JsonObject) -> JsonObject:
    """Compile a keyed draft through `WorkflowBuilder` into raw workflow JSON."""
    parsed = WorkflowDraft.model_validate(draft)
    workflow = build_workflow_from_draft(parsed)
    return workflow.model_dump(mode="json", by_alias=True, exclude={"node_defs"})


def validate_workflow_draft(
    draft: JsonObject,
    *,
    outcome_lookup: OutcomeLookup | None = None,
    node_defs: Sequence[NodeDef] | None = None,
) -> JsonObject:
    """Return structured diagnostics instead of raising on a bad keyed draft.

    When *node_defs* is supplied the structural validator can check
    input/output bindings against declared node schemas.  Without them
    only draft-level parse errors are reported.
    """
    try:
        parsed = WorkflowDraft.model_validate(draft)
        workflow = build_workflow_from_draft(parsed)
    except (ValidationError, KeyError, ValueError) as exc:
        return _invalid_result(_diagnostic_from_exception(exc))
    if node_defs is not None:
        workflow = workflow.model_copy(update={"node_defs": list(node_defs)})
        try:
            diagnostics = _diagnostics_from_workflow_issues(workflow)
        except (KeyError, ValueError) as exc:
            return _invalid_result(_diagnostic_from_exception(exc))
        if diagnostics:
            return _invalid_result(*diagnostics)
    if outcome_lookup is not None:
        diagnostic = _validate_known_outcomes(draft, outcome_lookup)
        if diagnostic is not None:
            return _invalid_result(diagnostic)
    compiled_plan = workflow.model_dump(
        mode="json", by_alias=True, exclude={"node_defs"}
    )
    return {
        "status": "valid",
        "diagnostics": [],
        "compiled_plan": compiled_plan,
    }


def patch_workflow_draft(
    draft: JsonObject,
    patch: JsonPatch,
    *,
    node_defs: Sequence[NodeDef] | None = None,
    node_defs_for_draft: NodeDefsForDraft | None = None,
) -> JsonObject:
    """Patch the draft source document, then validate the patched result."""
    try:
        patched = jsonpatch.JsonPatch(patch).apply(deepcopy(draft), in_place=False)
    except Exception as exc:
        return _invalid_result(
            DraftDiagnostic(
                code=PATCH_INVALID_CODE,
                path="patch",
                message=str(exc),
            )
        )
    if not isinstance(patched, dict):
        return _invalid_result(
            DraftDiagnostic(
                code=DRAFT_NOT_OBJECT_CODE,
                path="",
                message="patched draft must be a JSON object",
            )
        )
    effective_node_defs = (
        node_defs_for_draft(patched) if node_defs_for_draft is not None else node_defs
    )
    result = validate_workflow_draft(patched, node_defs=effective_node_defs)
    if result["status"] == "valid":
        patched = WorkflowDraft.model_validate(patched).model_dump(mode="json")
    # Forward-route references to steps added later must persist as invalid
    # so the next edit can resolve the missing edge.  Always return the
    # patched draft alongside diagnostics.  Malformed patches still hit the
    # early-return path above (no "draft" key), so this branch only fires
    # for structurally valid patches.
    return {"draft": patched, **result}


def _invalid_result(*diagnostics: DraftDiagnostic) -> JsonObject:
    return {
        "status": "invalid",
        "diagnostics": [
            item.model_dump(mode="json", exclude_none=True) for item in diagnostics
        ],
    }


def _diagnostic_from_exception(exc: Exception) -> DraftDiagnostic:
    if isinstance(exc, ValidationError):
        error = exc.errors()[0]
        return DraftDiagnostic(
            code=DRAFT_INVALID_CODE,
            path=_format_location(error["loc"]),
            message=error["msg"],
        )
    return DraftDiagnostic(
        code=DRAFT_INVALID_CODE,
        path="",
        message=str(exc),
    )


def _format_location(location: tuple[object, ...]) -> str:
    return ".".join(str(part) for part in location)


_NODE_OUTPUT_TARGET_RE = re.compile(
    r"^nodes\[(?P<node_index>\d+)\]\.output\[(?P<output_index>\d+)\]\.target$"
)


def _diagnostics_from_workflow_issues(workflow: Workflow) -> list[DraftDiagnostic]:
    report = workflow.validate_structure()
    return [_diagnostic_from_issue(workflow, issue) for issue in report.errors]


def _diagnostic_from_issue(
    workflow: Workflow,
    issue: ValidationIssue,
) -> DraftDiagnostic:
    step_id = _step_id_for_issue_path(workflow, issue.path)
    return DraftDiagnostic(
        code=str(issue.code),
        path=issue.path,
        step_id=step_id,
        message=issue.message,
        details=_details_for_issue(workflow, issue),
    )


def _step_id_for_issue_path(workflow: Workflow, path: str) -> str | None:
    match = re.match(r"^nodes\[(?P<node_index>\d+)\]", path)
    if match is None:
        return None
    node_index = int(match.group("node_index"))
    if node_index >= len(workflow.nodes):
        return None
    node_id = getattr(workflow.nodes[node_index], "id", None)
    return node_id if isinstance(node_id, str) else None


def _details_for_issue(
    workflow: Workflow,
    issue: ValidationIssue,
) -> dict[str, Any]:
    if issue.code is not ValidationIssueCode.INVALID_DESTINATION_PATH:
        return {}
    match = _NODE_OUTPUT_TARGET_RE.match(issue.path)
    if match is None:
        return {}
    node_index = int(match.group("node_index"))
    output_index = int(match.group("output_index"))
    if node_index >= len(workflow.nodes):
        return {}
    outputs = getattr(workflow.nodes[node_index], "output", None)
    if not isinstance(outputs, list) or output_index >= len(outputs):
        return {}
    binding = outputs[output_index]
    if not isinstance(binding, OutputBinding):
        return {}
    output_field = _single_local_field(binding)
    if output_field is None:
        return {}
    return {
        "output_field": output_field,
        "state_path": str(binding.target),
    }


def _single_local_field(binding: OutputBinding) -> str | None:
    from wf_core.local_paths import LocalPathError, split_local_path

    try:
        parts = split_local_path(binding.source)
    except LocalPathError:
        return None
    if len(parts) != 1:
        return None
    field = parts[0]
    return field if isinstance(field, str) else None


def _validate_known_outcomes(
    draft: JsonObject,
    outcome_lookup: OutcomeLookup,
) -> DraftDiagnostic | None:
    steps = draft.get("steps")
    routes = draft.get("routes")
    if not isinstance(steps, dict) or not isinstance(routes, dict):
        return None
    for step_id, route_map in routes.items():
        step = steps.get(step_id)
        if not isinstance(step, dict) or not isinstance(route_map, dict):
            continue
        capability = step.get("use")
        if not isinstance(capability, str):
            continue
        outcomes = outcome_lookup(capability)
        if outcomes is None:
            continue
        known_outcomes = set(outcomes)
        for outcome in route_map:
            if outcome not in known_outcomes:
                return DraftDiagnostic(
                    code=UNKNOWN_OUTCOME_CODE,
                    path=f"routes.{step_id}.{outcome}",
                    step_id=step_id,
                    message=(
                        f"step {step_id!r} routes unknown outcome {outcome!r}; "
                        f"expected one of {sorted(known_outcomes)!r}"
                    ),
                )
    return None
