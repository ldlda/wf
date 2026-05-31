# Next Actions Model Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move wrapper-draft `next_actions` from handler-local dict helpers into reusable typed workflow-surface models and constructors.

**Architecture:** Create `src/wf_mcp/workflow_surface/next_actions.py` as the single home for advisory guidance models. Keep the current `create_draft_workspace_from_capability` JSON output stable while adding generic `NextActions` / `NextActionPatchExample` types and `NextActions.from_wrapper_hints(...)`. Do not add deployment/run guidance in this pass.

**Tech Stack:** Python 3.14, Pydantic v2, pytest, ruff, basedpyright.

---

## Scope

Do:

- Create `workflow_surface/next_actions.py`.
- Move `WrapperDraftPatchExample` and `WrapperDraftNextActions` into generic models.
- Replace handler-local `_wrapper_draft_next_actions` and `_wrapper_draft_patch_examples` with `NextActions.from_wrapper_hints(...)`.
- Keep existing output fields stable:
  - `can_save_now`
  - `recommended_next_tool`
  - `reason`
  - `patch_examples`
  - `warnings`
- Add `can_continue` as an additive field.
- Preserve all existing tests and add targeted serialization/model tests.

Do not:

- Add `next_actions` to `validate_deployment`, `run_deployment`, or `resume_run`.
- Enforce `can_save_now`.
- Change MCP tool names.
- Add automatic semantic mapping or MCP content extraction.

## Files

- Create: `src/wf_mcp/workflow_surface/next_actions.py`
  - Generic guidance models and wrapper-hints constructor.
- Modify: `src/wf_mcp/workflow_surface/models.py`
  - Import/reuse `NextActions` for `CreateDraftWorkspaceFromCapabilityResult`.
  - Remove local wrapper-specific next-action models.
- Modify: `src/wf_mcp/workflow_surface/handlers.py`
  - Import `NextActions`.
  - Replace private dict helpers with `NextActions.from_wrapper_hints(...).model_dump(mode="json")`.
- Test: `tests/wf_mcp/workflow_surface/test_next_actions.py`
  - Direct model/constructor tests.
- Modify: `tests/wf_mcp/workflow_surface/test_drafts.py`
  - Add assertions for `can_continue`.
- Modify if needed: `tests/wf_mcp/server/test_config.py`
  - Keep schema assertions passing with generic model names.

## Task 1: Add Direct NextActions Model Tests

**Files:**

- Create: `tests/wf_mcp/workflow_surface/test_next_actions.py`

- [ ] **Step 1: Create failing tests**

Create `tests/wf_mcp/workflow_surface/test_next_actions.py`:

```python
from __future__ import annotations

from wf_mcp.workflow_surface.next_actions import NextActions, NextActionTool


def test_next_actions_from_high_confidence_wrapper_hints() -> None:
    hints = {
        "confidence": "high",
        "missing_decisions": [],
        "notes": ["Hints are scaffolding, not semantic guarantees."],
    }

    actions = NextActions.from_wrapper_hints(
        workspace_id="echo_wrapper",
        revision=3,
        hints=hints,
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


def test_next_actions_from_low_confidence_wrapper_hints() -> None:
    hints = {
        "confidence": "low",
        "missing_decisions": [{"kind": "review_nested_output"}],
        "notes": ["Raw MCP content blocks are not workflow-shaped."],
    }

    actions = NextActions.from_wrapper_hints(
        workspace_id="content_wrapper",
        revision=5,
        hints=hints,
    )
    dumped = actions.model_dump(mode="json")

    assert dumped["can_continue"] is True
    assert dumped["can_save_now"] is False
    assert dumped["recommended_next_tool"] == (
        NextActionTool.PATCH_DRAFT_WORKSPACE.value
    )
    assert "missing wrapper decisions" in dumped["reason"]
    assert dumped["patch_examples"][0]["request"]["workspace_id"] == "content_wrapper"
    assert dumped["patch_examples"][0]["request"]["revision"] == 5
    assert dumped["warnings"] == ["Raw MCP content blocks are not workflow-shaped."]
```

Run:

```powershell
uv run pytest tests/wf_mcp/workflow_surface/test_next_actions.py -q
```

Expected: fail because `wf_mcp.workflow_surface.next_actions` does not exist.

## Task 2: Create `next_actions.py`

**Files:**

- Create: `src/wf_mcp/workflow_surface/next_actions.py`

- [ ] **Step 1: Add generic models and constructor**

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
    """Concrete example request for a recommended workflow tool."""

    description: str = Field(description="Human-readable reason for this example.")
    tool: NextActionTool = Field(description="MCP workflow tool to call.")
    request: dict[str, Any] = Field(
        description="JSON request payload to pass to the tool."
    )


class NextActions(BaseModel):
    """Advisory continuation hints for MCP workflow clients."""

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
            "recommended before saving; the server does not enforce it."
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
        """Create guidance after create_draft_workspace_from_capability."""
        hint_payload = _hint_payload(hints)
        confidence = str(hint_payload.get("confidence", "low"))
        missing_decisions = hint_payload.get("missing_decisions")
        notes = [
            str(note) for note in hint_payload.get("notes", []) if isinstance(note, str)
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
                reason=(
                    "Wrapper hints are high confidence and have no missing decisions."
                ),
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
                hints=hint_payload,
            ),
            warnings=notes,
        )
```

Then add below:

```python
def _hint_payload(hints: WrapperAuthoringHints | dict[str, Any]) -> dict[str, Any]:
    """Return a JSON-compatible wrapper hint payload."""
    if isinstance(hints, WrapperAuthoringHints):
        return hints.model_dump(mode="json")
    return dict(hints)


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

- [ ] **Step 2: Run direct tests**

Run:

```powershell
uv run pytest tests/wf_mcp/workflow_surface/test_next_actions.py -q
```

Expected: pass.

## Task 3: Use Generic Models In MCP Result Schema

**Files:**

- Modify: `src/wf_mcp/workflow_surface/models.py`
- Modify: `tests/wf_mcp/server/test_config.py`

- [ ] **Step 1: Replace local models**

In `src/wf_mcp/workflow_surface/models.py`:

1. Import:

```python
from .next_actions import NextActions
```

2. Delete local classes:

```python
class WrapperDraftPatchExample(...)
class WrapperDraftNextActions(...)
```

3. Change:

```python
next_actions: WrapperDraftNextActions = Field(...)
```

to:

```python
next_actions: NextActions = Field(
    description=(
        "Advisory next step guidance derived from wrapper_hints. "
        "The server does not enforce can_save_now."
    )
)
```

- [ ] **Step 2: Update schema test for additive field**

In `tests/wf_mcp/server/test_config.py`, keep existing assertions and add:

```python
assert "can_continue" in next_actions_schema["properties"]
```

Run:

```powershell
uv run pytest tests/wf_mcp/server/test_config.py -q
```

Expected: pass after handler is updated in Task 4. If this fails only because handler runtime does not return `can_continue`, proceed to Task 4.

## Task 4: Replace Handler Helpers

**Files:**

- Modify: `src/wf_mcp/workflow_surface/handlers.py`
- Modify: `tests/wf_mcp/workflow_surface/test_drafts.py`

- [ ] **Step 1: Add output assertions for additive field**

In `tests/wf_mcp/workflow_surface/test_drafts.py`, in both next action assertions, add:

```python
assert next_actions["can_continue"] is True
```

Run:

```powershell
uv run pytest tests/wf_mcp/workflow_surface/test_drafts.py::test_workflow_surface_creates_draft_workspace_from_capability_hints tests/wf_mcp/workflow_surface/test_drafts.py::test_workflow_surface_low_confidence_draft_returns_patch_guidance -q
```

Expected: fail because current dict helper does not emit `can_continue`.

- [ ] **Step 2: Import and use `NextActions`**

In `src/wf_mcp/workflow_surface/handlers.py`, add:

```python
from .next_actions import NextActions
```

Change the return in `create_draft_workspace_from_capability` to:

```python
"next_actions": NextActions.from_wrapper_hints(
    workspace_id=workspace_id,
    revision=int(result["revision"]),
    hints=hints,
).model_dump(mode="json"),
```

- [ ] **Step 3: Delete private helpers**

Remove from `handlers.py`:

```python
_wrapper_draft_next_actions
_wrapper_draft_patch_examples
```

Run:

```powershell
rg -n "_wrapper_draft_next_actions|_wrapper_draft_patch_examples" src/wf_mcp/workflow_surface/handlers.py
```

Expected: no matches.

- [ ] **Step 4: Run focused behavior tests**

Run:

```powershell
uv run pytest tests/wf_mcp/workflow_surface/test_drafts.py tests/wf_mcp/workflow_surface/test_next_actions.py tests/wf_mcp/server/test_config.py -q
```

Expected: pass.

## Task 5: Update Docs If Needed

**Files:**

- Modify if needed: `docs/workflow_capabilities.md`
- Modify if needed: `docs/superpowers/specs/2026-05-31-workflow-surface-next-actions-design.md`

- [ ] **Step 1: Check docs already match implementation**

Run:

```powershell
rg -n "can_continue|NextActions|next_actions" docs/workflow_capabilities.md docs/superpowers/specs/2026-05-31-workflow-surface-next-actions-design.md
```

If `workflow_capabilities.md` does not mention `can_continue`, add:

```markdown
`next_actions.can_continue` is advisory. It says whether the response has an
obvious workflow-surface tool to call next.
```

## Task 6: Final Verification

**Files:**

- All touched files.

- [ ] **Step 1: Run focused tests**

Run:

```powershell
uv run pytest tests/wf_mcp/workflow_surface/test_next_actions.py tests/wf_mcp/workflow_surface/test_drafts.py tests/wf_mcp/server/test_config.py -q
```

Expected: pass.

- [ ] **Step 2: Run lint/format checks**

Run:

```powershell
uv run ruff check src/wf_mcp/workflow_surface/next_actions.py src/wf_mcp/workflow_surface/models.py src/wf_mcp/workflow_surface/handlers.py tests/wf_mcp/workflow_surface/test_next_actions.py tests/wf_mcp/workflow_surface/test_drafts.py tests/wf_mcp/server/test_config.py
uv run ruff format --check src/wf_mcp/workflow_surface/next_actions.py src/wf_mcp/workflow_surface/models.py src/wf_mcp/workflow_surface/handlers.py tests/wf_mcp/workflow_surface/test_next_actions.py tests/wf_mcp/workflow_surface/test_drafts.py tests/wf_mcp/server/test_config.py
```

Expected: pass.

- [ ] **Step 3: Run touched-file type check**

Run:

```powershell
uv run basedpyright --level error src/wf_mcp/workflow_surface/next_actions.py src/wf_mcp/workflow_surface/models.py src/wf_mcp/workflow_surface/handlers.py tests/wf_mcp/workflow_surface/test_next_actions.py tests/wf_mcp/workflow_surface/test_drafts.py tests/wf_mcp/server/test_config.py
```

Expected: `0 errors`.

- [ ] **Step 4: Optional full suite**

Run when time allows:

```powershell
uv run pytest -q
```

Expected current baseline: full suite passes with the existing skip/xfail count.

## Notes For Opencode

- Keep this as a refactor plus additive `can_continue`.
- Do not add deployment/run guidance yet.
- Do not enforce `can_save_now`.
- Keep JSON output stable for existing fields.
- `next_actions` is UX guidance. Diagnostics and validation remain source of truth.
