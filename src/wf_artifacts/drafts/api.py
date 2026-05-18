from __future__ import annotations

from copy import deepcopy
from collections.abc import Callable
from typing import Any

import jsonpatch
from pydantic import BaseModel, ValidationError

from .adapter import build_workflow_from_draft
from .models import WorkflowDraft

JsonObject = dict[str, Any]
JsonPatch = list[dict[str, Any]]
OutcomeLookup = Callable[[str], tuple[str, ...] | None]


class DraftDiagnostic(BaseModel):
    """Machine-readable reason a keyed draft could not be compiled."""

    code: str
    path: str
    step_id: str | None = None
    message: str


def compile_workflow_draft(draft: JsonObject) -> JsonObject:
    """Compile a keyed draft through `WorkflowBuilder` into raw workflow JSON."""
    parsed = WorkflowDraft.model_validate(draft)
    workflow = build_workflow_from_draft(parsed)
    return workflow.model_dump(mode="json", by_alias=True, exclude={"node_defs"})


def validate_workflow_draft(
    draft: JsonObject,
    *,
    outcome_lookup: OutcomeLookup | None = None,
) -> JsonObject:
    """Return structured diagnostics instead of raising on a bad keyed draft."""
    try:
        compiled_plan = compile_workflow_draft(draft)
    except (ValidationError, KeyError, ValueError) as exc:
        return _invalid_result(_diagnostic_from_exception(exc))
    if outcome_lookup is not None:
        diagnostic = _validate_known_outcomes(draft, outcome_lookup)
        if diagnostic is not None:
            return _invalid_result(diagnostic)
    return {
        "status": "valid",
        "diagnostics": [],
        "compiled_plan": compiled_plan,
    }


def patch_workflow_draft(draft: JsonObject, patch: JsonPatch) -> JsonObject:
    """Patch the draft source document, then validate the patched result."""
    try:
        patched = jsonpatch.JsonPatch(patch).apply(deepcopy(draft), in_place=False)
    except Exception as exc:
        return _invalid_result(
            DraftDiagnostic(
                code="patch_invalid",
                path="patch",
                message=str(exc),
            )
        )
    if not isinstance(patched, dict):
        return _invalid_result(
            DraftDiagnostic(
                code="draft_not_object",
                path="",
                message="patched draft must be a JSON object",
            )
        )
    result = validate_workflow_draft(patched)
    return {"draft": patched, **result}


def _invalid_result(diagnostic: DraftDiagnostic) -> JsonObject:
    return {
        "status": "invalid",
        "diagnostics": [diagnostic.model_dump(mode="json")],
    }


def _diagnostic_from_exception(exc: Exception) -> DraftDiagnostic:
    if isinstance(exc, ValidationError):
        error = exc.errors()[0]
        return DraftDiagnostic(
            code="draft_invalid",
            path=_format_location(error["loc"]),
            message=error["msg"],
        )
    return DraftDiagnostic(
        code="draft_invalid",
        path="",
        message=str(exc),
    )


def _format_location(location: tuple[object, ...]) -> str:
    return ".".join(str(part) for part in location)


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
                    code="unknown_outcome",
                    path=f"routes.{step_id}.{outcome}",
                    step_id=step_id,
                    message=(
                        f"step {step_id!r} routes unknown outcome {outcome!r}; "
                        f"expected one of {sorted(known_outcomes)!r}"
                    ),
                )
    return None
