# Explain Draft Diagnostics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `wf explain` with draft/workflow validation codes using real enum/constant sources instead of copied strings.

**Architecture:** Keep `wf explain` exact-match and docs-backed. Add enum-backed explain entries for `wf_core.validation.issues.ValidationIssueCode` values, introduce constants for draft/store-only codes, and update tests/docs so agents can explain draft failures without reading source/tests.

**Tech Stack:** Python 3.14, Typer CLI, Pydantic models, pytest, Ruff, basedpyright.

---

## File Structure

- Modify `src/wf_cli/explain/entries.py`: import enum/constants and add cards.
- Modify `src/wf_artifacts/drafts/api.py`: expose draft diagnostic code constants.
- Modify `src/wf_artifacts/draft_workspaces/api.py`: expose workspace diagnostic code constants.
- Modify `tests/wf_cli/test_explain.py`: cover new cards, enum-backed codes, and input-file extraction.
- Modify `docs/wf_cli.md`: expand common diagnostics.
- Modify `skills/wf-cli/SKILL.md` and `skills/wf-workflow/references/troubleshooting.md`: teach `wf explain` for draft codes.
- Modify `docs/current_roadmap.md`: mark completion when done.

### Task 1: Add Constants For Non-Enum Draft Codes

**Files:**
- Modify: `src/wf_artifacts/drafts/api.py`
- Modify: `src/wf_artifacts/draft_workspaces/api.py`
- Test: `tests/wf_cli/test_explain.py`

- [ ] **Step 1: Write the failing import test**

Add this test to `tests/wf_cli/test_explain.py`:

```python
def test_explain_registry_uses_exported_draft_codes() -> None:
    from wf_artifacts.draft_workspaces.api import REVISION_CONFLICT_CODE
    from wf_artifacts.drafts.api import (
        DRAFT_INVALID_CODE,
        PATCH_INVALID_CODE,
        UNKNOWN_OUTCOME_CODE,
    )

    registry_codes = {
        entry.code for entry in DEFAULT_EXPLAIN_REGISTRY.list_full_entries()
    }

    assert DRAFT_INVALID_CODE in registry_codes
    assert PATCH_INVALID_CODE in registry_codes
    assert UNKNOWN_OUTCOME_CODE in registry_codes
    assert REVISION_CONFLICT_CODE in registry_codes
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```powershell
uv run pytest tests/wf_cli/test_explain.py::test_explain_registry_uses_exported_draft_codes -q
```

Expected: import failure for the new constants.

- [ ] **Step 3: Add exported constants near producers**

In `src/wf_artifacts/drafts/api.py`, near the type aliases, add:

```python
DRAFT_INVALID_CODE = "draft_invalid"
PATCH_INVALID_CODE = "patch_invalid"
DRAFT_NOT_OBJECT_CODE = "draft_not_object"
UNKNOWN_OUTCOME_CODE = "unknown_outcome"
```

Replace the matching string literals in this file:

```python
code=PATCH_INVALID_CODE
code=DRAFT_NOT_OBJECT_CODE
code=DRAFT_INVALID_CODE
code=UNKNOWN_OUTCOME_CODE
```

In `src/wf_artifacts/draft_workspaces/api.py`, near the type aliases, add:

```python
WORKSPACE_EXISTS_CODE = "workspace_exists"
REVISION_CONFLICT_CODE = "revision_conflict"
```

Replace the matching string literals in this file:

```python
code=WORKSPACE_EXISTS_CODE
code=REVISION_CONFLICT_CODE
```

- [ ] **Step 4: Run the focused test and verify it now reaches registry failure**

Run:

```powershell
uv run pytest tests/wf_cli/test_explain.py::test_explain_registry_uses_exported_draft_codes -q
```

Expected: failure because the registry does not yet contain the new codes.

- [ ] **Step 5: Commit**

```powershell
git add src/wf_artifacts/drafts/api.py src/wf_artifacts/draft_workspaces/api.py tests/wf_cli/test_explain.py
git commit -m "refactor: name draft diagnostic codes"
```

### Task 2: Add Enum-Backed Explain Cards

**Files:**
- Modify: `src/wf_cli/explain/entries.py`
- Modify: `tests/wf_cli/test_explain.py`

- [ ] **Step 1: Write failing tests for workflow validation cards**

Add this test to `tests/wf_cli/test_explain.py`:

```python
def test_explain_registry_covers_core_validation_codes() -> None:
    from wf_core.validation.issues import ValidationIssueCode

    expected = {
        ValidationIssueCode.INVALID_SOURCE_PATH.value,
        ValidationIssueCode.INVALID_DESTINATION_PATH.value,
        ValidationIssueCode.UNKNOWN_EDGE_DESTINATION.value,
        ValidationIssueCode.UNDECLARED_EDGE_OUTCOME.value,
        ValidationIssueCode.MISSING_OUTCOME_EDGE.value,
    }
    registry_codes = {
        entry.code for entry in DEFAULT_EXPLAIN_REGISTRY.list_full_entries()
    }

    assert expected <= registry_codes
```

Add this behavior test:

```python
def test_explain_unknown_edge_destination_mentions_forward_route_repair() -> None:
    card = DEFAULT_EXPLAIN_REGISTRY.get("unknown_edge_destination")

    text = "\n".join(card.how_to_fix)

    assert "wf draft handle" in text
    assert "wf draft branch" in text
    assert "target step first" in text.lower()
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
uv run pytest tests/wf_cli/test_explain.py::test_explain_registry_covers_core_validation_codes tests/wf_cli/test_explain.py::test_explain_unknown_edge_destination_mentions_forward_route_repair -q
```

Expected: unknown code / missing registry entries.

- [ ] **Step 3: Import real code sources**

At the top of `src/wf_cli/explain/entries.py`, add:

```python
from wf_artifacts.draft_workspaces.api import REVISION_CONFLICT_CODE
from wf_artifacts.drafts.api import (
    DRAFT_INVALID_CODE,
    PATCH_INVALID_CODE,
    UNKNOWN_OUTCOME_CODE,
)
from wf_core.validation.issues import ValidationIssueCode
```

- [ ] **Step 4: Add the new cards**

Append these `ExplainCard` entries to `EXPLAIN_CARDS`:

```python
ExplainCard(
    code=ValidationIssueCode.INVALID_SOURCE_PATH.value,
    summary="A workflow step reads from a path that is not declared or available.",
    why_it_happens=[
        "A step input binding points at input/state/context data that the draft schema does not declare.",
        "A literal placeholder or guessed path was used in a binding.",
        "A wrapper bootstrap included a field that is not present in the actual run input.",
    ],
    how_to_fix=[
        "Run `wf schema InputPathBinding` to confirm binding shape.",
        "Inspect the draft input and state schemas.",
        "Use `wf draft set-input --merge` to repair step input bindings.",
        "Patch the draft input_schema/state_schema when the workflow genuinely needs a new path.",
        "Run `wf draft validate <workspace_id>` after the edit.",
    ],
    related_docs=[
        "docs/wf_cli.md#draft-workspaces",
        "docs/workflow_drafts.md",
    ],
),
ExplainCard(
    code=ValidationIssueCode.INVALID_DESTINATION_PATH.value,
    summary="A workflow step writes to a state or output path that is not declared.",
    why_it_happens=[
        "A capability output is bound to a missing state_schema field.",
        "A workflow output projection points at a missing output_schema field.",
        "A draft patch changed output bindings without changing the matching schema.",
    ],
    how_to_fix=[
        "For capability output to state, prefer `wf draft bind --from local.FIELD --to state.FIELD`.",
        "For multiple output bindings, use `wf draft set-output --merge` when preserving existing mappings.",
        "Read any `repair_hint` returned by `wf draft validate` before writing JSON Patch.",
        "Run `wf draft validate <workspace_id>` after the edit.",
    ],
    related_docs=[
        "docs/wf_cli.md#draft-workspaces",
        "docs/workflow_drafts.md",
    ],
),
ExplainCard(
    code=ValidationIssueCode.UNKNOWN_EDGE_DESTINATION.value,
    summary="A route or edge points at a step id that does not exist in the workflow.",
    why_it_happens=[
        "A draft route was added before the target step was created.",
        "A step id was misspelled in a route or edge.",
        "A raw plan edge references a node id that is absent from `nodes`.",
    ],
    how_to_fix=[
        "In draft authoring, create the target step first, then route to it.",
        "Use `wf draft handle <workspace_id> --step FROM --outcome OUTCOME --to TARGET` to repair one route.",
        "Use `wf draft branch <workspace_id> --step FROM --route OUTCOME=TARGET` for multiple route edits.",
        "For a complete graph authored at once, prefer `wf artifact create-from-plan` and validate the raw plan shape.",
    ],
    related_docs=[
        "docs/wf_cli.md#draft-workspaces",
        "docs/workflow_drafts.md",
    ],
),
ExplainCard(
    code=ValidationIssueCode.UNDECLARED_EDGE_OUTCOME.value,
    summary="A route uses an outcome that the source step does not declare.",
    why_it_happens=[
        "The route outcome was guessed instead of read from capability metadata.",
        "A multi-outcome capability was wired with an incomplete or misspelled outcome map.",
    ],
    how_to_fix=[
        "Run `wf cap inspect <capability>` and read the declared outcomes.",
        "Use `wf draft handle` or `wf draft branch` with the exact outcome names.",
        "Run `wf draft validate <workspace_id>` after route edits.",
    ],
    related_docs=[
        "docs/wf_cli.md#draft-workspaces",
        "docs/workflow_capabilities.md",
    ],
),
ExplainCard(
    code=ValidationIssueCode.MISSING_OUTCOME_EDGE.value,
    summary="A step outcome has no route and the workflow cannot prove where execution goes next.",
    why_it_happens=[
        "A multi-outcome step was added without complete route coverage.",
        "A draft patch replaced a route map and dropped an existing outcome.",
    ],
    how_to_fix=[
        "Run `wf cap inspect <capability>` to list declared outcomes.",
        "Use `wf draft branch --route OUTCOME=TARGET` for each missing outcome.",
        "Route terminal outcomes to `__end__` when the workflow should finish.",
    ],
    related_docs=[
        "docs/wf_cli.md#draft-workspaces",
        "docs/workflow_drafts.md",
    ],
),
```

Also append these draft/workspace cards:

```python
ExplainCard(
    code=UNKNOWN_OUTCOME_CODE,
    summary="A draft route uses an outcome that the source step cannot produce.",
    why_it_happens=[
        "The route outcome was guessed instead of read from the capability contract.",
        "A draft patch preserved an old outcome after the step capability changed.",
    ],
    how_to_fix=[
        "Run `wf cap inspect <capability>` and read the declared outcomes.",
        "Use `wf draft handle <workspace_id> --step STEP --outcome OUTCOME --to TARGET` with a declared outcome.",
        "Use `wf draft branch <workspace_id> --step STEP --route OUTCOME=TARGET` when repairing multiple outcomes.",
        "Run `wf draft validate <workspace_id>` after route edits.",
    ],
    related_docs=[
        "docs/wf_cli.md#draft-workspaces",
        "docs/workflow_drafts.md",
    ],
),
ExplainCard(
    code=DRAFT_INVALID_CODE,
    summary="A draft workspace contains an invalid draft shape or invalid workflow structure.",
    why_it_happens=[
        "The payload mixed draft-workspace shape with raw-plan shape.",
        "A JSON Patch produced a draft that does not satisfy the draft model.",
        "The draft model is syntactically valid but workflow validation found structural issues.",
    ],
    how_to_fix=[
        "Run `wf schema draft` for draft workspace payloads.",
        "Run `wf schema raw` for `wf artifact create-from-plan` payloads.",
        "Run `wf draft validate <workspace_id>` and follow each diagnostic code.",
        "Use `wf explain <code>` for the nested diagnostics before patching again.",
    ],
    related_docs=[
        "docs/wf_cli.md#draft-workspaces",
        "docs/workflow_drafts.md",
    ],
),
ExplainCard(
    code=PATCH_INVALID_CODE,
    summary="A draft patch is not a valid RFC 6902 JSON Patch or cannot be applied.",
    why_it_happens=[
        "The patch file used raw draft JSON instead of a JSON Patch operation list.",
        "A patch path points at a missing parent object.",
        "A patch operation is malformed or unsupported by the patch library.",
    ],
    how_to_fix=[
        "Use focused commands such as `wf draft set-input`, `wf draft set-output`, `wf draft bind`, `wf draft handle`, and `wf draft branch` when possible.",
        "If using `wf draft patch`, make the file a JSON array of RFC 6902 operations.",
        "Run `wf schema draft` to inspect the draft shape before choosing patch paths.",
        "Retry with the current workspace revision.",
    ],
    related_docs=[
        "docs/wf_cli.md#draft-workspaces",
        "docs/workflow_drafts.md",
    ],
),
ExplainCard(
    code=REVISION_CONFLICT_CODE,
    summary="A draft command used a stale workspace revision.",
    why_it_happens=[
        "Another edit advanced the draft workspace revision.",
        "The command was retried with an old `--revision` value.",
        "An agent copied a prior command transcript without fetching the current workspace.",
    ],
    how_to_fix=[
        "Run `wf draft inspect <workspace_id>` to get the current revision.",
        "Repeat the edit with the current `--revision` value.",
        "Do not skip revision checks; they prevent overwriting another edit.",
    ],
    related_docs=[
        "docs/wf_cli.md#draft-workspaces",
        "docs/workflow_drafts.md",
    ],
),
```

- [ ] **Step 5: Run explain tests**

Run:

```powershell
uv run pytest tests/wf_cli/test_explain.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add src/wf_cli/explain/entries.py tests/wf_cli/test_explain.py
git commit -m "feat: explain draft validation codes"
```

### Task 3: Update User-Facing Docs And Skills

**Files:**
- Modify: `docs/wf_cli.md`
- Modify: `skills/wf-cli/SKILL.md`
- Modify: `skills/wf-workflow/references/troubleshooting.md`
- Modify: `docs/current_roadmap.md`

- [ ] **Step 1: Update docs**

In `docs/wf_cli.md`, under `## Explain`, add a short list of draft examples:

```markdown
Draft authoring diagnostics commonly include:

- `invalid_source_path`
- `invalid_destination_path`
- `unknown_edge_destination`
- `unknown_outcome`
- `patch_invalid`
- `revision_conflict`
```

In `skills/wf-cli/SKILL.md`, add:

```markdown
For draft validation errors, run `wf explain <code>`. If routes point to a
missing step, create the target step first or repair routes with
`wf draft handle` / `wf draft branch`.
```

In `skills/wf-workflow/references/troubleshooting.md`, add:

```markdown
`unknown_edge_destination`: a route points to a missing step. Add the target
step or repair the route; do not guess `draft step add` or `draft export`.
```

- [ ] **Step 2: Update roadmap**

Add a completed bullet under Priority 1:

```markdown
- Completed: `wf explain` now covers draft/workflow validation codes such as
  `unknown_edge_destination`, `invalid_source_path`, and `patch_invalid`.
```

- [ ] **Step 3: Verify docs and skills**

Run:

```powershell
uv run pytest tests/docs tests/wf_cli/test_explain.py -q
uv run ruff check src/wf_cli/explain/entries.py tests/wf_cli/test_explain.py
uv run basedpyright --level error src/wf_cli/explain/entries.py tests/wf_cli/test_explain.py
```

Expected: all pass.

- [ ] **Step 4: Commit**

```powershell
git add docs/wf_cli.md skills/wf-cli/SKILL.md skills/wf-workflow/references/troubleshooting.md docs/current_roadmap.md
git commit -m "docs: teach draft explain codes"
```

### Task 4: Final Verification

**Files:**
- Move: `docs/superpowers/plans/2026-06-28-explain-draft-diagnostics.md`
- Modify: `docs/current_roadmap.md`

- [ ] **Step 1: Smoke the CLI**

Run:

```powershell
uv run wf explain unknown_edge_destination --format compact
uv run wf explain invalid_destination_path --format markdown
uv run wf explain --list --format compact
```

Expected: each command exits 0 and prints useful text.

- [ ] **Step 2: Archive the plan**

Move this plan to:

```text
docs/historical/superpowers/plans/2026-06-28-explain-draft-diagnostics.md
```

- [ ] **Step 3: Run final checks**

Run:

```powershell
uv run pytest tests/wf_cli/test_explain.py tests/docs -q
uv run ruff check src/wf_cli/explain/entries.py tests/wf_cli/test_explain.py
uv run ruff format --check src/wf_cli/explain/entries.py tests/wf_cli/test_explain.py
uv run basedpyright --level error src/wf_cli/explain/entries.py tests/wf_cli/test_explain.py
```

Expected: all pass.

- [ ] **Step 4: Commit**

```powershell
git add docs/current_roadmap.md docs/historical/superpowers/plans/2026-06-28-explain-draft-diagnostics.md
git commit -m "docs: archive draft explain plan"
```

## Self-Review

- Spec coverage: all acceptance criteria from `2026-06-28-explain-draft-diagnostics.md` map to Tasks 1-4.
- Placeholder scan: no placeholders remain.
- Type consistency: enum-backed codes come from `ValidationIssueCode`; draft-only codes come from exported constants.
