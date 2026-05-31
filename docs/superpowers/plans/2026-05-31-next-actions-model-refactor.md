# Next Actions Model Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move MCP workflow guidance UX into reusable `NextActions` models so wrapper draft guidance stops living as ad-hoc dict helpers in `handlers.py`.

**Architecture:** Add `src/wf_mcp/workflow_surface/next_actions.py` as the single owner of next-action enums, response models, and the first constructor: `NextActions.from_wrapper_hints(...)`. Keep the existing `create_draft_workspace_from_capability` JSON stable, with `can_continue` as the only additive field. Do not add deployment/run guidance in this pass; this is the foundation for those later constructors.

**Tech Stack:** Python 3.14, Pydantic v2, FastMCP schema generation, pytest, ruff, basedpyright.

---

## File Structure

- Create `src/wf_mcp/workflow_surface/next_actions.py`
  - Owns `NextActionTool`, `NextActionPatchExample`, and `NextActions`.
  - Owns wrapper-hint guidance policy currently in `handlers.py`.
  - Contains docstrings explaining that `next_actions` is advisory, not authority.

- Modify `src/wf_mcp/workflow_surface/models.py`
  - Reuse the generic models for MCP response schemas.
  - Keep compatibility aliases for `WrapperDraftPatchExample` and `WrapperDraftNextActions` if local imports or generated schemas still reference the old names.

- Modify `src/wf_mcp/workflow_surface/handlers.py`
  - Remove `_wrapper_draft_next_actions(...)` and `_wrapper_draft_patch_examples(...)`.
  - Call `NextActions.from_wrapper_hints(...).model_dump(mode="json")`.

- Create `tests/wf_mcp/workflow_surface/test_next_actions.py`
  - Unit-test the generic model without the full draft store.

- Modify `tests/wf_mcp/workflow_surface/test_drafts.py`
  - Keep integration coverage through `create_draft_workspace_from_capability`.
  - Assert old fields still exist and `can_continue` is additive.

- Modify `tests/wf_mcp/server/test_config.py`
  - Assert the MCP output schema documents `can_continue` and still documents `can_save_now`.

- Modify `docs/workflow_capabilities.md`
  - Add one short note that `next_actions` is advisory guidance and not validation authority.

## Scope Boundaries

- Do not add `NextActions.from_deployment_validation(...)` in this pass.
- Do not add `NextActions.from_run_result(...)` in this pass.
- Do not change current wrapper patch example semantics.
- Do not infer MCP content block extraction or boolean routing.
- Do not make `can_save_now` authoritative.

---

### Task 1: Add Generic Next-Actions Unit Tests

**Files:**
- Create: `tests/wf_mcp/workflow_surface/test_next_actions.py`

- [ ] **Step 1: Write failing tests for high-confidence wrapper hints**

Create `tests/wf_mcp/workflow_surface/test_next_actions.py`:

```python
from __future__ import annotations

from wf_mcp.workflow_surface.next_actions import NextActionTool, NextActions


def test_next_actions_from_high_confidence_wrapper_hints_can_validate() -> None:
    actions = NextActions.from_wrapper_hints(
        workspace_id="echo_workspace",
        revision=3,
        hints={
            "confidence": "high",
            "missing_decisions": [],
            "notes": [],
        },
    )

    dumped = actions.model_dump(mode="json")
    assert dumped["can_continue"] is True
    assert dumped["can_save_now"] is True
    assert dumped["recommended_next_tool"] == (
        NextActionTool.VALIDATE_DRAFT_WORKSPACE.value
    )
    assert "high confidence" in dumped["reason"]
    assert dumped["patch_examples"] == []
    assert dumped["warnings"] == []
```

- [ ] **Step 2: Write failing tests for low-confidence wrapper hints**

Append to `tests/wf_mcp/workflow_surface/test_next_actions.py`:

```python
def test_next_actions_from_low_confidence_wrapper_hints_can_patch() -> None:
    actions = NextActions.from_wrapper_hints(
        workspace_id="echo_workspace",
        revision=4,
        hints={
            "confidence": "low",
            "missing_decisions": [
                {
                    "kind": "review_nested_output",
                    "message": "Review nested output fields before mapping.",
                },
                {
                    "kind": "confirm_boolean_outcomes",
                    "message": "Boolean fields may be data, not outcomes.",
                },
            ],
            "notes": ["Raw MCP tool output is not workflow-shaped."],
        },
    )

    dumped = actions.model_dump(mode="json")
    assert dumped["can_continue"] is True
    assert dumped["can_save_now"] is False
    assert dumped["recommended_next_tool"] == NextActionTool.PATCH_DRAFT_WORKSPACE.value
    assert "missing wrapper decisions" in dumped["reason"]
    assert dumped["warnings"][0] == "Raw MCP tool output is not workflow-shaped."
    assert dumped["patch_examples"][0]["tool"] == (
        NextActionTool.PATCH_DRAFT_WORKSPACE.value
    )
    assert dumped["patch_examples"][0]["request"]["workspace_id"] == "echo_workspace"
    assert dumped["patch_examples"][0]["request"]["revision"] == 4
    assert dumped["patch_examples"][0]["request"]["patch"][0]["path"] == (
        "/draft/steps/call/output"
    )
    assert dumped["patch_examples"][1]["request"]["patch"] == []
```

- [ ] **Step 3: Run the focused test to verify it fails**

Run:

```bash
uv run pytest tests/wf_mcp/workflow_surface/test_next_actions.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'wf_mcp.workflow_surface.next_actions'`.

---

### Task 2: Implement `next_actions.py`

**Files:**
- Create: `src/wf_mcp/workflow_surface/next_actions.py`

- [ ] **Step 1: Create the generic models and wrapper-hints constructor**

Create `src/wf_mcp/workflow_surface/next_actions.py`:

```python
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
            hints.model_dump(mode="json") if isinstance(hints, WrapperAuthoringHints)
            else hints
        )
        confidence = str(payload.get("confidence", "low"))
        missing_decisions = payload.get("missing_decisions")
        notes = [
            str(note) for note in payload.get("notes", []) if isinstance(note, str)
        ]
        has_missing = (
            isinstance(missing_decisions, list) and len(missing_decisions) > 0
        )
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
```

- [ ] **Step 2: Run the focused unit test**

Run:

```bash
uv run pytest tests/wf_mcp/workflow_surface/test_next_actions.py -q
```

Expected: PASS.

---

### Task 3: Replace Wrapper-Specific MCP Models with Generic Models

**Files:**
- Modify: `src/wf_mcp/workflow_surface/models.py`

- [ ] **Step 1: Import generic next-action models**

Near the other local imports in `src/wf_mcp/workflow_surface/models.py`, add:

```python
from .next_actions import NextActionPatchExample, NextActions
```

- [ ] **Step 2: Remove wrapper-specific model class bodies**

Delete the current `WrapperDraftPatchExample` and `WrapperDraftNextActions` class definitions.

Replace them with compatibility aliases immediately before `CreateDraftWorkspaceFromCapabilityResult`:

```python
# Compatibility aliases for older imports. The JSON fields are now generic
# workflow-surface guidance, not wrapper-only policy.
WrapperDraftPatchExample = NextActionPatchExample
WrapperDraftNextActions = NextActions
```

- [ ] **Step 3: Keep `CreateDraftWorkspaceFromCapabilityResult` typed with the alias**

Leave the field shape unchanged except that the alias now points at the generic type:

```python
class CreateDraftWorkspaceFromCapabilityResult(DraftWorkspaceResult):
    """Draft workspace result plus wrapper hints and advisory next actions."""

    wrapper_hints: dict[str, Any] = Field(
        description=(
            "The wrapper_hints payload used before applying request overrides. "
            "Use this to patch uncertain maps or schemas by revision."
        )
    )
    next_actions: WrapperDraftNextActions = Field(
        description=(
            "Advisory next step guidance derived from wrapper_hints. "
            "The server does not enforce can_save_now."
        )
    )
```

- [ ] **Step 4: Run model import check**

Run:

```bash
uv run python -c "from wf_mcp.workflow_surface.models import WrapperDraftNextActions, CreateDraftWorkspaceFromCapabilityResult; print(WrapperDraftNextActions.__name__)"
```

Expected output includes:

```text
NextActions
```

---

### Task 4: Replace Handler Dict Helpers with `NextActions`

**Files:**
- Modify: `src/wf_mcp/workflow_surface/handlers.py`

- [ ] **Step 1: Import `NextActions`**

Add to the local imports in `src/wf_mcp/workflow_surface/handlers.py`:

```python
from .next_actions import NextActions
```

- [ ] **Step 2: Update `create_draft_workspace_from_capability`**

Replace the `next_actions` part of the return value with:

```python
        return {
            **result,
            "wrapper_hints": hints,
            "next_actions": NextActions.from_wrapper_hints(
                workspace_id=workspace_id,
                revision=int(result["revision"]),
                hints=hints,
            ).model_dump(mode="json"),
        }
```

- [ ] **Step 3: Delete handler-local guidance helpers**

Delete these functions from `src/wf_mcp/workflow_surface/handlers.py`:

```python
def _wrapper_draft_next_actions(...)
def _wrapper_draft_patch_examples(...)
```

Do not delete `_source_id_for_capability(...)`, which follows those helpers.

- [ ] **Step 4: Run focused draft tests**

Run:

```bash
uv run pytest tests/wf_mcp/workflow_surface/test_next_actions.py tests/wf_mcp/workflow_surface/test_drafts.py -q
```

Expected: PASS except for assertions that still need additive `can_continue` checks in Task 5.

---

### Task 5: Update Integration and Schema Tests

**Files:**
- Modify: `tests/wf_mcp/workflow_surface/test_drafts.py`
- Modify: `tests/wf_mcp/server/test_config.py`

- [ ] **Step 1: Add `can_continue` assertions to draft integration tests**

In `tests/wf_mcp/workflow_surface/test_drafts.py`, find the test that asserts high-confidence `next_actions`.

Add this assertion near the other `next_actions` assertions:

```python
    assert next_actions["can_continue"] is True
```

Keep these existing assertions:

```python
    assert next_actions["can_save_now"] is True
    assert next_actions["recommended_next_tool"] == (
        "wf.workflow.validate_draft_workspace"
    )
    assert "high confidence" in next_actions["reason"]
    assert next_actions["patch_examples"] == []
    assert next_actions["warnings"] == []
```

- [ ] **Step 2: Add `can_continue` assertion to low-confidence integration test**

In the low-confidence/content-block test in `tests/wf_mcp/workflow_surface/test_drafts.py`, add:

```python
    assert next_actions["can_continue"] is True
```

Keep field-level assertions. Do not assert whole dict equality.

- [ ] **Step 3: Update MCP schema test**

In `tests/wf_mcp/server/test_config.py`, find the `create_draft_workspace_from_capability` output schema test.

Add:

```python
    next_actions_schema = result_schema["properties"]["next_actions"]
    next_action_properties = next_actions_schema["properties"]
    assert "can_continue" in next_action_properties
    assert "Advisory" in next_action_properties["can_continue"]["description"]
    assert "can_save_now" in next_action_properties
    assert "Advisory" in next_action_properties["can_save_now"]["description"]
```

If the existing test already has `next_actions_schema`, reuse it. Do not assert the entire generated schema.

- [ ] **Step 4: Run focused tests**

Run:

```bash
uv run pytest tests/wf_mcp/workflow_surface/test_next_actions.py tests/wf_mcp/workflow_surface/test_drafts.py tests/wf_mcp/server/test_config.py -q
```

Expected: PASS.

---

### Task 6: Add a Small Documentation Note

**Files:**
- Modify: `docs/workflow_capabilities.md`

- [ ] **Step 1: Add an advisory-guidance note**

Find the section that mentions `next_actions` or wrapper draft guidance. Add this paragraph:

```markdown
`next_actions` is advisory guidance, not validation authority. It gives MCP
clients a compact "what should I call next?" pointer, while diagnostics,
artifact validation, deployment validation, and runtime status remain the
source of truth.
```

- [ ] **Step 2: Verify docs reference still works**

Run:

```bash
uv run pytest tests/wf_mcp/server/test_docs.py -q
```

Expected: PASS.

---

### Task 7: Full Verification

**Files:**
- All touched files.

- [ ] **Step 1: Run focused tests**

Run:

```bash
uv run pytest tests/wf_mcp/workflow_surface/test_next_actions.py tests/wf_mcp/workflow_surface/test_drafts.py tests/wf_mcp/server/test_config.py tests/wf_mcp/server/test_docs.py -q
```

Expected: PASS.

- [ ] **Step 2: Run formatting check on touched files**

Run:

```bash
uv run ruff format --check src/wf_mcp/workflow_surface/next_actions.py src/wf_mcp/workflow_surface/models.py src/wf_mcp/workflow_surface/handlers.py tests/wf_mcp/workflow_surface/test_next_actions.py tests/wf_mcp/workflow_surface/test_drafts.py tests/wf_mcp/server/test_config.py
```

Expected: PASS.

- [ ] **Step 3: Run lint on touched files**

Run:

```bash
uv run ruff check src/wf_mcp/workflow_surface/next_actions.py src/wf_mcp/workflow_surface/models.py src/wf_mcp/workflow_surface/handlers.py tests/wf_mcp/workflow_surface/test_next_actions.py tests/wf_mcp/workflow_surface/test_drafts.py tests/wf_mcp/server/test_config.py
```

Expected: PASS.

- [ ] **Step 4: Run type check**

Run:

```bash
uv run basedpyright --level error
```

Expected: `0 errors`.

- [ ] **Step 5: Run the full test suite if time allows**

Run:

```bash
uv run pytest -q
```

Expected: current suite status should remain unchanged from the baseline, currently about `723 passed, 1 skipped, 1 xfailed`.

---

## Self-Review Checklist

- Spec coverage:
  - `next_actions.py` is created.
  - Generic models exist.
  - Wrapper-hint constructor exists.
  - Handler-local dict helpers are removed.
  - Existing JSON fields remain stable.
  - Deployment/run guidance is intentionally deferred.

- Placeholder scan:
  - No `TBD`.
  - No open-ended "add appropriate validation".
  - Each code step includes exact snippets.

- Type consistency:
  - `NextActionTool.PATCH_DRAFT_WORKSPACE.value` serializes to the existing string.
  - `WrapperDraftNextActions` remains importable as an alias.
  - `CreateDraftWorkspaceFromCapabilityResult.next_actions` keeps the same public response location.

## Handoff Notes

This plan is intentionally small. It should not change workflow behavior or draft semantics. If any test fails outside `next_actions` schema/serialization, stop and inspect before broadening the change.
