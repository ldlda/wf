from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

JsonObject = dict[str, Any]

CONTROL_BOOLEAN_NAMES = {
    "success",
    "ok",
    "failed",
    "error",
    "is_error",
    "needs_input",
    "requires_approval",
    "approved",
    "rejected",
    "has_more",
    "done",
    "complete",
}


class WrapperHintConfidence(StrEnum):
    """Coarse confidence for generated wrapper scaffolding hints."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class WrapperOutcomePolicy(StrEnum):
    """How wrapper outcomes were chosen."""

    PRESERVE_DECLARED = "preserve_declared"
    MANUAL_MAPPING_REQUIRED = "manual_mapping_required"


class OutcomeCandidateKind(StrEnum):
    """Reason a field was offered as a possible outcome source."""

    BOOLEAN_CONTROL_FIELD = "boolean_control_field"


class MissingDecisionKind(StrEnum):
    """Typed action item a human or LLM must decide before saving a wrapper."""

    CHOOSE_OUTPUT_FIELDS = "choose_output_fields"
    REVIEW_NESTED_OUTPUT = "review_nested_output"
    CONFIRM_BOOLEAN_OUTCOMES = "confirm_boolean_outcomes"
    CHOOSE_ERROR_MAPPING = "choose_error_mapping"


class OutcomeCandidate(BaseModel):
    """One possible outcome mapping that must not be applied automatically."""

    kind: OutcomeCandidateKind
    source: str = Field(description="Output path such as output.success.")
    candidate_outcomes: list[str]
    confidence: WrapperHintConfidence
    reason: str
    automatic: bool = False


class MissingDecision(BaseModel):
    """One explicit decision required before a wrapper should be saved."""

    kind: MissingDecisionKind
    message: str


class WrapperAuthoringHints(BaseModel):
    """Scaffold for creating a workflow wrapper around one capability."""

    capability_name: str
    confidence: WrapperHintConfidence
    declared_outcomes: list[str]
    suggested_wrapper_outcomes: list[str]
    outcome_policy: WrapperOutcomePolicy
    input_schema: JsonObject
    state_schema: JsonObject
    output_schema: JsonObject
    input_map: dict[str, str]
    output_map: dict[str, str]
    outcome_candidates: list[OutcomeCandidate] = Field(default_factory=list)
    missing_decisions: list[MissingDecision] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


def wrapper_hints_for_capability(
    *,
    capability_name: str,
    input_schema: JsonObject,
    output_schema: JsonObject,
    outcomes: list[str] | tuple[str, ...],
) -> WrapperAuthoringHints:
    """Derive conservative wrapper scaffolding for one workflow capability.

    The helper deliberately preserves declared outcomes and only proposes
    boolean output fields as candidates. It must not infer business semantics or
    create routes by itself.
    """
    input_properties = _object_properties(input_schema)
    output_properties = _object_properties(output_schema)
    input_map = {f"input.{name}": name for name in sorted(input_properties)}
    output_map = {name: f"state.{name}" for name in sorted(output_properties)}
    state_schema = {
        "type": "object",
        "properties": {
            name: schema for name, schema in sorted(output_properties.items())
        },
    }
    wrapper_output_schema = {
        "type": "object",
        "properties": {
            name: schema for name, schema in sorted(output_properties.items())
        },
    }
    missing_decisions = _missing_decisions_for_output(output_schema)
    outcome_candidates = _boolean_outcome_candidates(output_properties)
    if outcome_candidates:
        missing_decisions.append(
            MissingDecision(
                kind=MissingDecisionKind.CONFIRM_BOOLEAN_OUTCOMES,
                message=(
                    "Confirm whether boolean output fields should control "
                    "wrapper routing."
                ),
            )
        )
    confidence = _confidence_for_hint(
        input_schema=input_schema,
        output_schema=output_schema,
        missing_decisions=missing_decisions,
        outcome_candidates=outcome_candidates,
    )
    return WrapperAuthoringHints(
        capability_name=capability_name,
        confidence=confidence,
        declared_outcomes=list(outcomes),
        suggested_wrapper_outcomes=list(outcomes),
        outcome_policy=WrapperOutcomePolicy.PRESERVE_DECLARED,
        input_schema=input_schema,
        state_schema=state_schema,
        output_schema=wrapper_output_schema,
        input_map=input_map,
        output_map=output_map,
        outcome_candidates=outcome_candidates,
        missing_decisions=missing_decisions,
        notes=[
            "Hints are scaffolding, not semantic guarantees.",
            (
                "Declared outcomes are preserved; output-field outcome "
                "inference is not automatic."
            ),
        ],
    )


def _object_properties(schema: JsonObject) -> dict[str, JsonObject]:
    """Return object properties that are themselves JSON Schema objects."""
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return {}
    return {
        str(name): value
        for name, value in properties.items()
        if isinstance(value, dict)
    }


def _missing_decisions_for_output(output_schema: JsonObject) -> list[MissingDecision]:
    """Return explicit decisions required by output schema shape."""
    properties = _object_properties(output_schema)
    if not properties:
        return [
            MissingDecision(
                kind=MissingDecisionKind.CHOOSE_OUTPUT_FIELDS,
                message=(
                    "Capability output schema has no top-level object "
                    "properties to map."
                ),
            )
        ]
    decisions: list[MissingDecision] = []
    for name, schema in sorted(properties.items()):
        schema_type = schema.get("type")
        if schema_type == "object" or schema_type == "array":
            decisions.append(
                MissingDecision(
                    kind=MissingDecisionKind.REVIEW_NESTED_OUTPUT,
                    message=(
                        f"Review output.{name}; nested or collection outputs "
                        "may need explicit mapping."
                    ),
                )
            )
    return decisions


def _boolean_outcome_candidates(
    output_properties: dict[str, JsonObject],
) -> list[OutcomeCandidate]:
    """Return conservative candidate outcome mappings for control-like booleans."""
    candidates: list[OutcomeCandidate] = []
    for name, schema in sorted(output_properties.items()):
        if schema.get("type") != "boolean":
            continue
        if name.casefold() not in CONTROL_BOOLEAN_NAMES:
            continue
        candidates.append(
            OutcomeCandidate(
                kind=OutcomeCandidateKind.BOOLEAN_CONTROL_FIELD,
                source=f"output.{name}",
                candidate_outcomes=_candidate_outcomes_for_boolean_name(name),
                confidence=WrapperHintConfidence.MEDIUM,
                reason="top-level boolean field with control-like name",
                automatic=False,
            )
        )
    return candidates


def _candidate_outcomes_for_boolean_name(name: str) -> list[str]:
    """Map known control-like boolean names to possible outcome labels."""
    normalized = name.casefold()
    if normalized in {"success", "ok", "done", "complete"}:
        return ["success", "failure"]
    if normalized in {"failed", "error", "is_error"}:
        return ["error", "ok"]
    if normalized in {"approved", "rejected"}:
        return ["approved", "rejected"]
    if normalized in {"needs_input", "requires_approval"}:
        return [normalized, "done"]
    if normalized == "has_more":
        return ["has_more", "done"]
    return ["true", "false"]


def _confidence_for_hint(
    *,
    input_schema: JsonObject,
    output_schema: JsonObject,
    missing_decisions: list[MissingDecision],
    outcome_candidates: list[OutcomeCandidate],
) -> WrapperHintConfidence:
    """Assign coarse confidence from schema shape and pending decisions."""
    if not _object_properties(input_schema) or not _object_properties(output_schema):
        return WrapperHintConfidence.LOW
    if any(
        decision.kind == MissingDecisionKind.REVIEW_NESTED_OUTPUT
        for decision in missing_decisions
    ):
        return WrapperHintConfidence.LOW
    if missing_decisions or outcome_candidates:
        return WrapperHintConfidence.MEDIUM
    return WrapperHintConfidence.HIGH
