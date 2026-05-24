# Wrapper Authoring Hints Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add enum-backed wrapper authoring hints to workflow capability inspection so LLM and human MCP clients can scaffold wrapper drafts without guessing raw workflow plans.

**Architecture:** Keep MCP request/response names as plain JSON strings, but compute wrapper hints in a pure workflow-surface helper. The helper uses typed Pydantic models with enum fields for confidence, outcome policy, candidate kinds, and missing-decision kinds, then `inspect_capability` attaches the hint payload to live NodeSpec and saved wrapper details.

**Tech Stack:** Python 3.14, Pydantic v2, FastMCP-facing dict payloads, pytest, ruff, basedpyright.

---

## File Structure

- Create `src/wf_mcp/workflow_surface/wrapper_hints.py`
  - Owns enum-backed hint models.
  - Owns pure functions that derive hints from one capability contract.
  - Must not call MCP, stores, workflow runtime, or FastMCP.
- Modify `src/wf_mcp/workflow_surface/handlers.py`
  - Imports the pure hint helper.
  - Adds `wrapper_hints` to `inspect_capability` payloads.
- Modify `src/wf_mcp/workflow_surface/models.py`
  - Adds JSON-schema-visible response models if MCP tool schemas need stronger documentation.
  - Do this only after the helper shape stabilizes.
- Test `tests/wf_mcp/test_workflow_wrapper_hints.py`
  - Focused unit tests for hint derivation.
- Test `tests/wf_mcp/test_workflow_surface.py`
  - Integration tests proving `inspect_capability` includes hints.
- Docs `docs/workflow_capabilities.md`
  - Explain that hints are scaffolding, not semantic guarantees.

## Vocabulary

Use enums for all classification/type fields. Do not return magic strings for these fields from helper internals.

```python
from enum import StrEnum


class WrapperHintConfidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class WrapperOutcomePolicy(StrEnum):
    PRESERVE_DECLARED = "preserve_declared"
    MANUAL_MAPPING_REQUIRED = "manual_mapping_required"


class OutcomeCandidateKind(StrEnum):
    BOOLEAN_CONTROL_FIELD = "boolean_control_field"


class MissingDecisionKind(StrEnum):
    CHOOSE_OUTPUT_FIELDS = "choose_output_fields"
    REVIEW_NESTED_OUTPUT = "review_nested_output"
    CONFIRM_BOOLEAN_OUTCOMES = "confirm_boolean_outcomes"
    CHOOSE_ERROR_MAPPING = "choose_error_mapping"
```

MCP JSON still serializes those enum values as strings.

## Task 1: Add Enum-Backed Hint Models

**Files:**

- Create: `src/wf_mcp/workflow_surface/wrapper_hints.py`
- Test: `tests/wf_mcp/test_workflow_wrapper_hints.py`

- [ ] **Step 1: Write failing model serialization test**

Create `tests/wf_mcp/test_workflow_wrapper_hints.py`:

```python
from __future__ import annotations

from wf_mcp.workflow_surface.wrapper_hints import (
    MissingDecision,
    MissingDecisionKind,
    OutcomeCandidate,
    OutcomeCandidateKind,
    WrapperAuthoringHints,
    WrapperHintConfidence,
    WrapperOutcomePolicy,
)


def test_wrapper_hint_models_serialize_enum_fields_as_strings() -> None:
    hints = WrapperAuthoringHints(
        capability_name="demo.personal.echo_tool",
        confidence=WrapperHintConfidence.MEDIUM,
        declared_outcomes=["ok", "error"],
        suggested_wrapper_outcomes=["ok", "error"],
        outcome_policy=WrapperOutcomePolicy.PRESERVE_DECLARED,
        input_schema={"type": "object", "properties": {}},
        state_schema={"type": "object", "properties": {}},
        output_schema={"type": "object", "properties": {}},
        input_map={},
        output_map={},
        outcome_candidates=[
            OutcomeCandidate(
                kind=OutcomeCandidateKind.BOOLEAN_CONTROL_FIELD,
                source="output.success",
                candidate_outcomes=["success", "failure"],
                confidence=WrapperHintConfidence.MEDIUM,
                reason="top-level boolean field with control-like name",
                automatic=False,
            )
        ],
        missing_decisions=[
            MissingDecision(
                kind=MissingDecisionKind.CONFIRM_BOOLEAN_OUTCOMES,
                message="Confirm whether output.success should control routing.",
            )
        ],
        notes=["Hints are scaffolding, not semantic guarantees."],
    )

    dumped = hints.model_dump(mode="json")

    assert dumped["confidence"] == "medium"
    assert dumped["outcome_policy"] == "preserve_declared"
    assert dumped["outcome_candidates"][0]["kind"] == "boolean_control_field"
    assert dumped["missing_decisions"][0]["kind"] == "confirm_boolean_outcomes"
```

- [ ] **Step 2: Run model test to verify it fails**

Run:

```bash
uv run --with pytest pytest tests/wf_mcp/test_workflow_wrapper_hints.py::test_wrapper_hint_models_serialize_enum_fields_as_strings -q
```

Expected: import failure because `wf_mcp.workflow_surface.wrapper_hints` does not exist.

- [ ] **Step 3: Implement model definitions**

Create `src/wf_mcp/workflow_surface/wrapper_hints.py`:

```python
from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


JsonObject = dict[str, Any]


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
```

- [ ] **Step 4: Run model test to verify it passes**

Run:

```bash
uv run --with pytest pytest tests/wf_mcp/test_workflow_wrapper_hints.py::test_wrapper_hint_models_serialize_enum_fields_as_strings -q
```

Expected: pass.

## Task 2: Derive Simple Wrapper Hints From Capability Schemas

**Files:**

- Modify: `src/wf_mcp/workflow_surface/wrapper_hints.py`
- Test: `tests/wf_mcp/test_workflow_wrapper_hints.py`

- [ ] **Step 1: Add failing simple-schema hint test**

Append to `tests/wf_mcp/test_workflow_wrapper_hints.py`:

```python
from wf_mcp.workflow_surface.wrapper_hints import wrapper_hints_for_capability


def test_wrapper_hints_scaffold_simple_object_input_and_output() -> None:
    hints = wrapper_hints_for_capability(
        capability_name="demo.personal.echo_tool",
        input_schema={
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
        output_schema={
            "type": "object",
            "properties": {"echoed": {"type": "string"}},
            "required": ["echoed"],
        },
        outcomes=["ok"],
    )

    dumped = hints.model_dump(mode="json")

    assert dumped["confidence"] == "high"
    assert dumped["declared_outcomes"] == ["ok"]
    assert dumped["suggested_wrapper_outcomes"] == ["ok"]
    assert dumped["outcome_policy"] == "preserve_declared"
    assert dumped["input_map"] == {"input.text": "text"}
    assert dumped["output_map"] == {"echoed": "state.echoed"}
    assert dumped["state_schema"]["properties"]["echoed"]["type"] == "string"
    assert dumped["output_schema"]["properties"]["echoed"]["type"] == "string"
    assert dumped["missing_decisions"] == []
```

- [ ] **Step 2: Run simple-schema test to verify it fails**

Run:

```bash
uv run --with pytest pytest tests/wf_mcp/test_workflow_wrapper_hints.py::test_wrapper_hints_scaffold_simple_object_input_and_output -q
```

Expected: import failure or attribute error for `wrapper_hints_for_capability`.

- [ ] **Step 3: Implement `wrapper_hints_for_capability`**

Add to `src/wf_mcp/workflow_surface/wrapper_hints.py`:

```python
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


def wrapper_hints_for_capability(
    *,
    capability_name: str,
    input_schema: JsonObject,
    output_schema: JsonObject,
    outcomes: list[str] | tuple[str, ...],
) -> WrapperAuthoringHints:
    """Derive conservative wrapper scaffolding for one workflow capability."""
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
                message="Confirm whether boolean output fields should control wrapper routing.",
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
            "Declared outcomes are preserved; output-field outcome inference is not automatic.",
        ],
    )


def _object_properties(schema: JsonObject) -> dict[str, JsonObject]:
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return {}
    return {
        str(name): value
        for name, value in properties.items()
        if isinstance(value, dict)
    }
```

- [ ] **Step 4: Implement confidence and missing decision helpers**

Add below `_object_properties` in `src/wf_mcp/workflow_surface/wrapper_hints.py`:

```python
def _missing_decisions_for_output(output_schema: JsonObject) -> list[MissingDecision]:
    properties = _object_properties(output_schema)
    if not properties:
        return [
            MissingDecision(
                kind=MissingDecisionKind.CHOOSE_OUTPUT_FIELDS,
                message="Capability output schema has no top-level object properties to map.",
            )
        ]
    decisions: list[MissingDecision] = []
    for name, schema in sorted(properties.items()):
        schema_type = schema.get("type")
        if schema_type == "object" or schema_type == "array":
            decisions.append(
                MissingDecision(
                    kind=MissingDecisionKind.REVIEW_NESTED_OUTPUT,
                    message=f"Review output.{name}; nested or collection outputs may need explicit mapping.",
                )
            )
    return decisions


def _boolean_outcome_candidates(
    output_properties: dict[str, JsonObject],
) -> list[OutcomeCandidate]:
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
```

- [ ] **Step 5: Run wrapper hint tests**

Run:

```bash
uv run --with pytest pytest tests/wf_mcp/test_workflow_wrapper_hints.py -q
```

Expected: pass.

## Task 3: Add Boolean Outcome Candidate Tests

**Files:**

- Modify: `tests/wf_mcp/test_workflow_wrapper_hints.py`
- Modify: `src/wf_mcp/workflow_surface/wrapper_hints.py` only if tests reveal gaps.

- [ ] **Step 1: Add candidate and non-candidate tests**

Append:

```python
def test_wrapper_hints_offer_boolean_outcome_candidates_without_auto_mapping() -> None:
    hints = wrapper_hints_for_capability(
        capability_name="demo.personal.submit",
        input_schema={"type": "object", "properties": {"text": {"type": "string"}}},
        output_schema={
            "type": "object",
            "properties": {
                "success": {"type": "boolean"},
                "message": {"type": "string"},
            },
        },
        outcomes=["ok"],
    )

    dumped = hints.model_dump(mode="json")
    candidate = dumped["outcome_candidates"][0]

    assert dumped["confidence"] == "medium"
    assert candidate["kind"] == "boolean_control_field"
    assert candidate["source"] == "output.success"
    assert candidate["candidate_outcomes"] == ["success", "failure"]
    assert candidate["automatic"] is False
    assert dumped["outcome_policy"] == "preserve_declared"
    assert dumped["suggested_wrapper_outcomes"] == ["ok"]
    assert dumped["missing_decisions"][0]["kind"] == "confirm_boolean_outcomes"


def test_wrapper_hints_do_not_treat_arbitrary_booleans_as_outcomes() -> None:
    hints = wrapper_hints_for_capability(
        capability_name="demo.personal.profile",
        input_schema={"type": "object", "properties": {"user_id": {"type": "string"}}},
        output_schema={
            "type": "object",
            "properties": {
                "is_admin": {"type": "boolean"},
                "name": {"type": "string"},
            },
        },
        outcomes=["ok"],
    )

    dumped = hints.model_dump(mode="json")

    assert dumped["confidence"] == "high"
    assert dumped["outcome_candidates"] == []
    assert dumped["missing_decisions"] == []
```

- [ ] **Step 2: Run tests**

Run:

```bash
uv run --with pytest pytest tests/wf_mcp/test_workflow_wrapper_hints.py -q
```

Expected: pass. If arbitrary boolean fields produce candidates, fix `CONTROL_BOOLEAN_NAMES` filtering rather than deleting the test.

## Task 4: Add Complex Output Missing Decision Tests

**Files:**

- Modify: `tests/wf_mcp/test_workflow_wrapper_hints.py`
- Modify: `src/wf_mcp/workflow_surface/wrapper_hints.py` only if tests reveal gaps.

- [ ] **Step 1: Add nested-output and empty-output tests**

Append:

```python
def test_wrapper_hints_mark_nested_outputs_as_low_confidence() -> None:
    hints = wrapper_hints_for_capability(
        capability_name="demo.personal.search",
        input_schema={"type": "object", "properties": {"query": {"type": "string"}}},
        output_schema={
            "type": "object",
            "properties": {
                "results": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {"title": {"type": "string"}},
                    },
                }
            },
        },
        outcomes=["ok"],
    )

    dumped = hints.model_dump(mode="json")

    assert dumped["confidence"] == "low"
    assert dumped["missing_decisions"][0]["kind"] == "review_nested_output"
    assert dumped["output_map"] == {"results": "state.results"}


def test_wrapper_hints_mark_empty_output_schema_as_low_confidence() -> None:
    hints = wrapper_hints_for_capability(
        capability_name="demo.personal.no_output",
        input_schema={"type": "object", "properties": {"text": {"type": "string"}}},
        output_schema={"type": "object", "properties": {}},
        outcomes=["ok"],
    )

    dumped = hints.model_dump(mode="json")

    assert dumped["confidence"] == "low"
    assert dumped["input_map"] == {"input.text": "text"}
    assert dumped["output_map"] == {}
    assert dumped["missing_decisions"][0]["kind"] == "choose_output_fields"
```

- [ ] **Step 2: Run tests**

Run:

```bash
uv run --with pytest pytest tests/wf_mcp/test_workflow_wrapper_hints.py -q
```

Expected: pass.

## Task 5: Wire Hints Into `inspect_capability`

**Files:**

- Modify: `src/wf_mcp/workflow_surface/handlers.py`
- Test: `tests/wf_mcp/test_workflow_surface.py`

- [ ] **Step 1: Add failing live capability integration test**

In `tests/wf_mcp/test_workflow_surface.py`, after `test_workflow_surface_inspects_one_capability`, add:

```python
def test_workflow_surface_inspect_capability_includes_wrapper_hints() -> None:
    service = WfMcpService(
        store=FileStore(local_temp_root() / "surface_wrapper_hints_mcp"),
        artifact_store=FileWorkflowArtifactStore(
            local_temp_root() / "surface_wrapper_hints_artifacts"
        ),
    )
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_specs("demo.personal", echo_tool)
    handlers = WorkflowSurfaceHandlers(service)

    payload = asyncio.run(
        handlers.inspect_capability(qualified_name="demo.personal.echo_tool")
    )

    hints = payload["wrapper_hints"]
    assert hints["capability_name"] == "demo.personal.echo_tool"
    assert hints["declared_outcomes"] == ["ok"]
    assert hints["input_map"] == {"input.text": "text"}
    assert hints["output_map"] == {"echoed": "state.echoed"}
    assert hints["outcome_policy"] == "preserve_declared"
```

- [ ] **Step 2: Run integration test to verify it fails**

Run:

```bash
uv run --with pytest pytest tests/wf_mcp/test_workflow_surface.py::test_workflow_surface_inspect_capability_includes_wrapper_hints -q
```

Expected: failure because `wrapper_hints` is absent.

- [ ] **Step 3: Attach hints for live NodeSpecs**

In `src/wf_mcp/workflow_surface/handlers.py`, import:

```python
from .wrapper_hints import wrapper_hints_for_capability
```

Then in `inspect_capability`, replace the live-detail return with:

```python
detail_payload = detail.model_dump(mode="json")
detail_payload["wrapper_hints"] = wrapper_hints_for_capability(
    capability_name=detail.name,
    input_schema=detail.input_schema,
    output_schema=detail.output_schema,
    outcomes=detail.outcomes,
).model_dump(mode="json")
return detail_payload
```

- [ ] **Step 4: Run integration test**

Run:

```bash
uv run --with pytest pytest tests/wf_mcp/test_workflow_surface.py::test_workflow_surface_inspect_capability_includes_wrapper_hints -q
```

Expected: pass.

## Task 6: Add Hints For Saved Wrapper Artifact Inspection

**Files:**

- Modify: `src/wf_mcp/workflow_surface/handlers.py`
- Test: `tests/wf_mcp/test_workflow_surface.py`

- [ ] **Step 1: Add failing saved-wrapper hint assertion**

In existing `test_workflow_surface_inspects_saved_wrapper_capability`, add:

```python
    hints = payload["wrapper_hints"]
    assert hints["capability_name"] == "workflow.echo_wrapper.v1"
    assert hints["declared_outcomes"] == ["completed"]
    assert hints["suggested_wrapper_outcomes"] == ["completed"]
    assert hints["input_map"] == {"input.text": "text"}
    assert hints["output_map"] == {"echoed": "state.echoed"}
```

- [ ] **Step 2: Run saved-wrapper test to verify it fails**

Run:

```bash
uv run --with pytest pytest tests/wf_mcp/test_workflow_surface.py::test_workflow_surface_inspects_saved_wrapper_capability -q
```

Expected: failure because wrapper detail lacks `wrapper_hints`.

- [ ] **Step 3: Attach hints for wrapper artifacts**

In `_wrapper_capability_detail`, add `wrapper_hints` to the returned dict:

```python
"wrapper_hints": wrapper_hints_for_capability(
    capability_name=_artifact_capability_id(artifact),
    input_schema=artifact.input_schema,
    output_schema=artifact.output_schema,
    outcomes=list(artifact.outcomes),
).model_dump(mode="json"),
```

- [ ] **Step 4: Run saved-wrapper test**

Run:

```bash
uv run --with pytest pytest tests/wf_mcp/test_workflow_surface.py::test_workflow_surface_inspects_saved_wrapper_capability -q
```

Expected: pass.

## Task 7: Document Hint Semantics

**Files:**

- Modify: `docs/workflow_capabilities.md`

- [ ] **Step 1: Add documentation section**

Add a section titled `## Wrapper Authoring Hints`:

```markdown
## Wrapper Authoring Hints

`wf.workflow.inspect_capability` returns `wrapper_hints` for planner-visible
capabilities. These hints are scaffolding for draft creation, not semantic
guarantees.

Declared capability outcomes are authoritative and are preserved by default.
Boolean output fields may appear as `outcome_candidates` when they have
control-like names such as `success`, `error`, `approved`, or `has_more`, but
they are never wired automatically. A wrapper author must explicitly confirm
whether those fields should become routing conditions.

`confidence` is intentionally coarse:

- `high`: simple object input/output schemas and no missing decisions.
- `medium`: usable scaffold with candidate decisions, such as boolean outcome
  candidates.
- `low`: missing or nested output choices require explicit authoring.

`missing_decisions` is a typed list of decisions the author should resolve
before saving a wrapper. MCP clients should show these prominently rather than
treating the scaffold as complete.
```

- [ ] **Step 2: Run docs-adjacent tests**

Run:

```bash
uv run --with pytest pytest tests/wf_mcp/test_workflow_wrapper_hints.py tests/wf_mcp/test_workflow_surface.py -q
```

Expected: pass.

## Task 8: Final Verification

**Files:**

- All touched files.

- [ ] **Step 1: Run focused tests**

Run:

```bash
uv run --with pytest pytest tests/wf_mcp/test_workflow_wrapper_hints.py tests/wf_mcp/test_workflow_surface.py tests/wf_mcp/test_workflow_surface_refs.py -q
```

Expected: pass.

- [ ] **Step 2: Run full tests if the workspace is not mid-edit**

Run:

```bash
uv run --with pytest pytest -q
```

Expected: pass, allowing intentional environment-dependent skips. If the user is actively editing `tests/rewrite`, run focused tests only and state that full-suite verification was deferred.

- [ ] **Step 3: Run static checks**

Run:

```bash
uvx ruff check src/wf_mcp/workflow_surface tests/wf_mcp/test_workflow_wrapper_hints.py tests/wf_mcp/test_workflow_surface.py
uv run basedpyright --level error src/wf_mcp/workflow_surface tests/wf_mcp/test_workflow_wrapper_hints.py tests/wf_mcp/test_workflow_surface.py
uvx ruff format --check src/wf_mcp/workflow_surface tests/wf_mcp/test_workflow_wrapper_hints.py tests/wf_mcp/test_workflow_surface.py
```

Expected: ruff passes, basedpyright has 0 errors, and formatting is clean.

## Self-Review

- Spec coverage: The plan covers enum-backed type fields, conservative outcome suggestions, boolean candidates, confidence/missing-decision UX, inspect-capability integration, and docs.
- Placeholder scan: No `TBD`, `TODO`, or unspecified implementation steps remain.
- Type consistency: `WrapperHintConfidence`, `WrapperOutcomePolicy`, `OutcomeCandidateKind`, and `MissingDecisionKind` are defined before use and serialize through Pydantic models.
- Scope check: This plan does not create or save wrappers automatically; it only adds hint payloads for authoring.
