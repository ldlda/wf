# wf_api Slice 3B: Guidance Helpers Move Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move protocol-neutral wrapper guidance helpers from `wf_mcp.workflow_surface` into `wf_api`, while preserving old imports as compatibility shims.

**Architecture:** `wrapper_hints.py` and `next_actions.py` are coupled guidance helpers: `next_actions` imports `WrapperAuthoringHints`, and both describe workflow authoring UX rather than MCP transport behavior. This slice moves them together to avoid a half-moved dependency. The old `wf_mcp.workflow_surface` modules remain thin re-export shims so MCP schemas/tests and older imports keep working.

**Tech Stack:** Python 3.14+, Pydantic v2 models, pytest, ruff, basedpyright.

---

## Scope

### In Scope

- Create `src/wf_api/wrapper_hints.py`.
- Create `src/wf_api/next_actions.py`.
- Re-export selected public guidance types/functions from `src/wf_api/__init__.py`.
- Replace `wf_mcp.workflow_surface.wrapper_hints` with a compatibility shim.
- Replace `wf_mcp.workflow_surface.next_actions` with a compatibility shim.
- Update `src/wf_mcp/workflow_surface/handlers.py` to import canonical helpers from `wf_api`.
- Update `src/wf_mcp/workflow_surface/models.py` to import canonical next-action models from `wf_api`.
- Update direct tests to use canonical imports while preserving shim compatibility tests.
- Keep `wf_api` free of `wf_mcp` imports.

### Out Of Scope

- Do not move `models.py`.
- Do not move `run_lifecycle.py`.
- Do not move `runtime_dependencies.py`.
- Do not move `saved_subgraphs.py`.
- Do not rename `WorkflowSurfaceHandlers`.
- Do not change wrapper hint behavior.
- Do not change next action behavior.
- Do not change public payloads, MCP tool names, CLI command names, or JSON schema field names.

---

## File Structure

### New Canonical Files

| File | Responsibility |
| --- | --- |
| `src/wf_api/wrapper_hints.py` | Wrapper scaffolding hints, confidence, missing-decision models, and conservative schema mapping helper. |
| `src/wf_api/next_actions.py` | Advisory next-action models and factory helpers for wrapper/deployment/run responses. |

### Compatibility Shims

| File | Responsibility |
| --- | --- |
| `src/wf_mcp/workflow_surface/wrapper_hints.py` | Re-export wrapper hint helpers from `wf_api.wrapper_hints`. |
| `src/wf_mcp/workflow_surface/next_actions.py` | Re-export next action helpers from `wf_api.next_actions`. |

### Modified Consumers

| File | Change |
| --- | --- |
| `src/wf_api/__init__.py` | Re-export public guidance helpers. |
| `src/wf_mcp/workflow_surface/handlers.py` | Import `NextActions` and wrapper hint helpers from `wf_api`. |
| `src/wf_mcp/workflow_surface/models.py` | Import `NextActionPatchExample` and `NextActions` from `wf_api.next_actions`. |
| `tests/wf_mcp/test_workflow_wrapper_hints.py` | Use canonical `wf_api.wrapper_hints`; add shim identity test. |
| `tests/wf_mcp/workflow_surface/test_next_actions.py` | Use canonical `wf_api.next_actions`; add shim identity test. |

---

## Task 1: Create Canonical `wf_api.wrapper_hints`

**Files:**

- Create: `src/wf_api/wrapper_hints.py`

- [ ] **Step 1: Copy existing implementation**

Create `src/wf_api/wrapper_hints.py` by copying the complete current contents of:

```text
src/wf_mcp/workflow_surface/wrapper_hints.py
```

Do not change behavior. The copied module must not import `wf_mcp`.

- [ ] **Step 2: Add `__all__` at the end**

Append this block to the copied file:

```python
__all__ = [
    "MissingDecision",
    "MissingDecisionKind",
    "OutcomeCandidate",
    "OutcomeCandidateKind",
    "WrapperAuthoringHints",
    "WrapperHintConfidence",
    "WrapperOutcomePolicy",
    "workflow_output_schema_for_authoring",
    "wrapper_hints_for_capability",
]
```

- [ ] **Step 3: Run import smoke check**

Run:

```powershell
uv run python -c "from wf_api.wrapper_hints import WrapperAuthoringHints, wrapper_hints_for_capability; print(WrapperAuthoringHints.__name__, wrapper_hints_for_capability.__name__)"
```

Expected output:

```text
WrapperAuthoringHints wrapper_hints_for_capability
```

---

## Task 2: Create Canonical `wf_api.next_actions`

**Files:**

- Create: `src/wf_api/next_actions.py`

- [ ] **Step 1: Copy existing implementation**

Create `src/wf_api/next_actions.py` by copying the complete current contents of:

```text
src/wf_mcp/workflow_surface/next_actions.py
```

- [ ] **Step 2: Keep local wrapper hint import canonical**

Ensure the copied file imports wrapper hints from the new `wf_api` package via:

```python
from .wrapper_hints import WrapperAuthoringHints
```

The copied module must not import `wf_mcp`.

- [ ] **Step 3: Add `__all__` at the end**

Append this block to the copied file:

```python
__all__ = [
    "NextActionPatchExample",
    "NextActionTool",
    "NextActions",
]
```

- [ ] **Step 4: Run import smoke check**

Run:

```powershell
uv run python -c "from wf_api.next_actions import NextActionTool, NextActions; print(NextActionTool.RUN_DEPLOYMENT, NextActions.__name__)"
```

Expected output:

```text
wf.workflow.run_deployment NextActions
```

---

## Task 3: Re-export Guidance Helpers From `wf_api`

**Files:**

- Modify: `src/wf_api/__init__.py`

- [ ] **Step 1: Add imports**

Add these imports:

```python
from .next_actions import NextActionPatchExample, NextActionTool, NextActions
from .wrapper_hints import (
    MissingDecision,
    MissingDecisionKind,
    OutcomeCandidate,
    OutcomeCandidateKind,
    WrapperAuthoringHints,
    WrapperHintConfidence,
    WrapperOutcomePolicy,
    workflow_output_schema_for_authoring,
    wrapper_hints_for_capability,
)
```

- [ ] **Step 2: Add names to `__all__`**

Ensure `__all__` includes these names:

```python
"MissingDecision",
"MissingDecisionKind",
"NextActionPatchExample",
"NextActionTool",
"NextActions",
"OutcomeCandidate",
"OutcomeCandidateKind",
"WrapperAuthoringHints",
"WrapperHintConfidence",
"WrapperOutcomePolicy",
"workflow_output_schema_for_authoring",
"wrapper_hints_for_capability",
```

- [ ] **Step 3: Run top-level import smoke check**

Run:

```powershell
uv run python -c "from wf_api import NextActions, WrapperAuthoringHints; print(NextActions.__name__, WrapperAuthoringHints.__name__)"
```

Expected output:

```text
NextActions WrapperAuthoringHints
```

---

## Task 4: Convert Old Workflow-Surface Guidance Modules To Shims

**Files:**

- Modify: `src/wf_mcp/workflow_surface/wrapper_hints.py`
- Modify: `src/wf_mcp/workflow_surface/next_actions.py`

- [ ] **Step 1: Replace `src/wf_mcp/workflow_surface/wrapper_hints.py`**

Replace the file with this shim:

```python
"""Compatibility shim for workflow API wrapper authoring hints.

New code should import from `wf_api.wrapper_hints`. This module stays so older
MCP workflow-surface imports keep working during extraction.
"""

from wf_api.wrapper_hints import (
    MissingDecision,
    MissingDecisionKind,
    OutcomeCandidate,
    OutcomeCandidateKind,
    WrapperAuthoringHints,
    WrapperHintConfidence,
    WrapperOutcomePolicy,
    workflow_output_schema_for_authoring,
    wrapper_hints_for_capability,
)

__all__ = [
    "MissingDecision",
    "MissingDecisionKind",
    "OutcomeCandidate",
    "OutcomeCandidateKind",
    "WrapperAuthoringHints",
    "WrapperHintConfidence",
    "WrapperOutcomePolicy",
    "workflow_output_schema_for_authoring",
    "wrapper_hints_for_capability",
]
```

- [ ] **Step 2: Replace `src/wf_mcp/workflow_surface/next_actions.py`**

Replace the file with this shim:

```python
"""Compatibility shim for workflow API next-action guidance.

New code should import from `wf_api.next_actions`. This module stays so older
MCP workflow-surface imports keep working during extraction.
"""

from wf_api.next_actions import NextActionPatchExample, NextActionTool, NextActions

__all__ = [
    "NextActionPatchExample",
    "NextActionTool",
    "NextActions",
]
```

- [ ] **Step 3: Run shim import smoke check**

Run:

```powershell
uv run python -c "from wf_mcp.workflow_surface.wrapper_hints import WrapperAuthoringHints; from wf_mcp.workflow_surface.next_actions import NextActions; print(WrapperAuthoringHints.__name__, NextActions.__name__)"
```

Expected output:

```text
WrapperAuthoringHints NextActions
```

---

## Task 5: Update Production Imports To Canonical Paths

**Files:**

- Modify: `src/wf_mcp/workflow_surface/handlers.py`
- Modify: `src/wf_mcp/workflow_surface/models.py`

- [ ] **Step 1: Update `handlers.py` next action import**

Replace:

```python
from .next_actions import NextActions
```

with:

```python
from wf_api.next_actions import NextActions
```

- [ ] **Step 2: Update `handlers.py` wrapper hint import**

Replace:

```python
from .wrapper_hints import (
    workflow_output_schema_for_authoring,
    wrapper_hints_for_capability,
)
```

with:

```python
from wf_api.wrapper_hints import (
    workflow_output_schema_for_authoring,
    wrapper_hints_for_capability,
)
```

- [ ] **Step 3: Update `models.py` next action import**

Replace:

```python
from .next_actions import NextActionPatchExample, NextActions
```

with:

```python
from wf_api.next_actions import NextActionPatchExample, NextActions
```

- [ ] **Step 4: Run production import smoke check**

Run:

```powershell
uv run python -c "from wf_mcp.workflow_surface.handlers import WorkflowSurfaceHandlers; from wf_mcp.workflow_surface.models import WrapperDraftNextActions; print(WorkflowSurfaceHandlers.__name__, WrapperDraftNextActions.__name__)"
```

Expected output:

```text
WorkflowSurfaceHandlers NextActions
```

---

## Task 6: Update Direct Tests And Add Shim Compatibility Tests

**Files:**

- Modify: `tests/wf_mcp/test_workflow_wrapper_hints.py`
- Modify: `tests/wf_mcp/workflow_surface/test_next_actions.py`

- [ ] **Step 1: Update wrapper hints test imports**

In `tests/wf_mcp/test_workflow_wrapper_hints.py`, replace imports from:

```python
from wf_mcp.workflow_surface.wrapper_hints import (
```

with:

```python
from wf_api.wrapper_hints import (
```

- [ ] **Step 2: Add wrapper hints shim identity test**

Append this test to `tests/wf_mcp/test_workflow_wrapper_hints.py`:

```python
def test_workflow_surface_wrapper_hints_shim_reexports_canonical_helper() -> None:
    from wf_api.wrapper_hints import wrapper_hints_for_capability
    from wf_mcp.workflow_surface.wrapper_hints import (
        wrapper_hints_for_capability as wrapper_hints_for_capability_shim,
    )

    assert wrapper_hints_for_capability_shim is wrapper_hints_for_capability
```

- [ ] **Step 3: Update next actions test imports**

In `tests/wf_mcp/workflow_surface/test_next_actions.py`, replace:

```python
from wf_mcp.workflow_surface.next_actions import NextActionTool, NextActions
```

with:

```python
from wf_api.next_actions import NextActionTool, NextActions
```

- [ ] **Step 4: Add next actions shim identity test**

Append this test to `tests/wf_mcp/workflow_surface/test_next_actions.py`:

```python
def test_workflow_surface_next_actions_shim_reexports_canonical_model() -> None:
    from wf_api.next_actions import NextActions
    from wf_mcp.workflow_surface.next_actions import NextActions as NextActionsShim

    assert NextActionsShim is NextActions
```

- [ ] **Step 5: Run focused tests**

Run:

```powershell
uv run pytest tests/wf_mcp/test_workflow_wrapper_hints.py tests/wf_mcp/workflow_surface/test_next_actions.py tests/wf_api/test_import_direction.py -q
```

Expected: all pass.

---

## Task 7: Search For Remaining Canonical Import Opportunities

**Files:**

- Inspect only unless the search finds new low-risk direct consumers.

- [ ] **Step 1: Search old imports**

Run:

```powershell
rg -n "from \\.next_actions|from \\.wrapper_hints|from wf_mcp\\.workflow_surface\\.(next_actions|wrapper_hints)" src tests
```

Expected remaining matches:

```text
src/wf_mcp/workflow_surface/next_actions.py
src/wf_mcp/workflow_surface/wrapper_hints.py
tests/wf_mcp/test_workflow_wrapper_hints.py
tests/wf_mcp/workflow_surface/test_next_actions.py
```

If any other production module imports the old paths, update it to import from
`wf_api.next_actions` or `wf_api.wrapper_hints`.

- [ ] **Step 2: Search for accidental `wf_api -> wf_mcp` imports**

Run:

```powershell
rg -n "from wf_mcp|import wf_mcp|wf_mcp\\." src/wf_api
```

Expected: no matches.

---

## Task 8: Verification

- [ ] **Step 1: Run focused tests**

```powershell
uv run pytest tests/wf_api tests/wf_mcp/test_workflow_wrapper_hints.py tests/wf_mcp/workflow_surface/test_next_actions.py tests/wf_mcp/workflow_surface tests/wf_mcp/server/test_config.py -q
```

Expected: all pass.

- [ ] **Step 2: Run CLI tests that assert next_actions/wrapper_hints payloads**

```powershell
uv run pytest tests/wf_cli/test_discovery_lifecycle.py tests/wf_cli/test_run_deploy.py -q
```

Expected: all pass.

- [ ] **Step 3: Run ruff on touched files**

```powershell
uv run ruff check src/wf_api src/wf_mcp/workflow_surface/next_actions.py src/wf_mcp/workflow_surface/wrapper_hints.py src/wf_mcp/workflow_surface/handlers.py src/wf_mcp/workflow_surface/models.py tests/wf_mcp/test_workflow_wrapper_hints.py tests/wf_mcp/workflow_surface/test_next_actions.py tests/wf_api
```

Expected: all checks pass.

- [ ] **Step 4: Run basedpyright on touched files**

```powershell
uv run basedpyright --level error src/wf_api src/wf_mcp/workflow_surface/next_actions.py src/wf_mcp/workflow_surface/wrapper_hints.py src/wf_mcp/workflow_surface/handlers.py src/wf_mcp/workflow_surface/models.py tests/wf_mcp/test_workflow_wrapper_hints.py tests/wf_mcp/workflow_surface/test_next_actions.py tests/wf_api
```

Expected: `0 errors`.

- [ ] **Step 5: Optional full suite**

Run this if time allows:

```powershell
uv run pytest -q
```

Expected: full suite passes with the project’s existing skipped/xfailed counts.

---

## Self-Review Checklist

- `wf_api.wrapper_hints` imports no `wf_mcp`.
- `wf_api.next_actions` imports no `wf_mcp`.
- Old `wf_mcp.workflow_surface.wrapper_hints` import path still works.
- Old `wf_mcp.workflow_surface.next_actions` import path still works.
- `WorkflowSurfaceHandlers` imports canonical guidance helpers from `wf_api`.
- `wf_mcp.workflow_surface.models` imports canonical next-action models from `wf_api`.
- Wrapper hint behavior is unchanged.
- Next action behavior is unchanged.
- No public payload shape changed.
- No other workflow-surface helper moved in this slice.
