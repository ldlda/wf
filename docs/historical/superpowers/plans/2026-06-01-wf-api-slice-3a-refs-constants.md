# wf_api Slice 3A: Refs And Constants Move Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the protocol-neutral workflow API refs and constants helpers from `wf_mcp.workflow_surface` into `wf_api`, while preserving old imports as compatibility shims.

**Architecture:** `wf_api` is now the canonical home for process-local workflow API helpers that are not MCP-specific. This slice moves only `constants.py` and `refs.py` because both are small and import only `wf_artifacts` / `wf_platform`. `wf_mcp.workflow_surface.constants` and `wf_mcp.workflow_surface.refs` remain thin re-export shims so existing imports keep working.

**Tech Stack:** Python 3.14+, Pydantic-backed refs from `wf_artifacts` and `wf_platform`, pytest, ruff, basedpyright.

---

## Scope

### In Scope

- Create `src/wf_api/constants.py`.
- Create `src/wf_api/refs.py`.
- Re-export the new helpers from `src/wf_api/__init__.py`.
- Replace `wf_mcp.workflow_surface.constants` with a compatibility shim.
- Replace `wf_mcp.workflow_surface.refs` with a compatibility shim.
- Update `src/wf_mcp/workflow_surface/handlers.py` to import canonical helpers from `wf_api`.
- Add/adjust tests for canonical imports and shim compatibility.
- Keep `wf_api` free of `wf_mcp` imports.

### Out Of Scope

- Do not move `models.py`.
- Do not move `next_actions.py`.
- Do not move `wrapper_hints.py`.
- Do not move `run_lifecycle.py`.
- Do not move `runtime_dependencies.py`.
- Do not move `saved_subgraphs.py`.
- Do not rename `WorkflowSurfaceHandlers`.
- Do not change public payloads, tool names, command names, or parsing behavior.

---

## File Structure

### New Canonical Files

| File | Responsibility |
| --- | --- |
| `src/wf_api/constants.py` | Canonical workflow API literals used by draft/helper code. |
| `src/wf_api/refs.py` | Canonical parser for workflow-surface capability IDs. |

### Compatibility Shims

| File | Responsibility |
| --- | --- |
| `src/wf_mcp/workflow_surface/constants.py` | Re-export constants from `wf_api.constants`; no local logic. |
| `src/wf_mcp/workflow_surface/refs.py` | Re-export refs from `wf_api.refs`; no local logic. |

### Modified Consumers

| File | Change |
| --- | --- |
| `src/wf_api/__init__.py` | Re-export moved helpers. |
| `src/wf_mcp/workflow_surface/handlers.py` | Import constants and parser from `wf_api`. |
| `tests/wf_mcp/test_workflow_surface_refs.py` | Keep shim compatibility tests and add canonical import tests. |
| `tests/wf_api/test_import_direction.py` | Existing guard should continue to pass. |

---

## Task 1: Add Canonical `wf_api.constants`

**Files:**

- Create: `src/wf_api/constants.py`

- [ ] **Step 1: Create `src/wf_api/constants.py`**

Write this exact file:

```python
"""Protocol-neutral workflow API literals used by draft/helper code."""

DEFAULT_CALL_STEP_ID = "call"
DEFAULT_ERROR_STEP_ID = "tool_error"
DEFAULT_OK_OUTCOME = "ok"
DEFAULT_ERROR_OUTCOME = "error"
RUNTIME_ERROR_CAPABILITY = "wf.std.runtime_error"

__all__ = [
    "DEFAULT_CALL_STEP_ID",
    "DEFAULT_ERROR_OUTCOME",
    "DEFAULT_ERROR_STEP_ID",
    "DEFAULT_OK_OUTCOME",
    "RUNTIME_ERROR_CAPABILITY",
]
```

- [ ] **Step 2: Run import smoke check**

Run:

```powershell
uv run python -c "from wf_api.constants import DEFAULT_CALL_STEP_ID, RUNTIME_ERROR_CAPABILITY; print(DEFAULT_CALL_STEP_ID, RUNTIME_ERROR_CAPABILITY)"
```

Expected output:

```text
call wf.std.runtime_error
```

---

## Task 2: Add Canonical `wf_api.refs`

**Files:**

- Create: `src/wf_api/refs.py`

- [ ] **Step 1: Create `src/wf_api/refs.py`**

Write this exact file:

```python
from __future__ import annotations

from typing import Any, TypeAlias

from wf_artifacts import WorkflowCapabilityRef
from wf_platform import CapabilityRef

WorkflowSurfaceCapabilityId: TypeAlias = CapabilityRef | WorkflowCapabilityRef


def parse_workflow_surface_capability_id(
    value: str | dict[str, Any],
) -> WorkflowSurfaceCapabilityId:
    """Parse a workflow API capability id into its real domain ref.

    API callers still pass strings at protocol boundaries. Internally,
    workflow-facing capability ids are either live source capabilities or saved
    wrapper artifacts, so this parser avoids inventing a third identifier model.
    """
    if isinstance(value, dict):
        if "artifact_id" in value and "version" in value:
            return WorkflowCapabilityRef._validate(value)
        return CapabilityRef._validate(value)

    try:
        return WorkflowCapabilityRef.parse(value)
    except ValueError:
        return CapabilityRef.parse(value)
```

- [ ] **Step 2: Run import smoke check**

Run:

```powershell
uv run python -c "from wf_api.refs import parse_workflow_surface_capability_id; print(parse_workflow_surface_capability_id('workflow.echo_wrapper.v2'))"
```

Expected output:

```text
workflow.echo_wrapper.v2
```

---

## Task 3: Re-export Helpers From `wf_api`

**Files:**

- Modify: `src/wf_api/__init__.py`

- [ ] **Step 1: Update imports and `__all__`**

Change `src/wf_api/__init__.py` to include these imports:

```python
from .constants import (
    DEFAULT_CALL_STEP_ID,
    DEFAULT_ERROR_OUTCOME,
    DEFAULT_ERROR_STEP_ID,
    DEFAULT_OK_OUTCOME,
    RUNTIME_ERROR_CAPABILITY,
)
from .refs import WorkflowSurfaceCapabilityId, parse_workflow_surface_capability_id
```

Ensure `__all__` includes:

```python
__all__ = [
    "DEFAULT_CALL_STEP_ID",
    "DEFAULT_ERROR_OUTCOME",
    "DEFAULT_ERROR_STEP_ID",
    "DEFAULT_OK_OUTCOME",
    "RUNTIME_ERROR_CAPABILITY",
    "TraceRange",
    "WorkflowApi",
    "WorkflowApiBackend",
    "WorkflowSurfaceCapabilityId",
    "parse_workflow_surface_capability_id",
]
```

- [ ] **Step 2: Run import smoke check**

Run:

```powershell
uv run python -c "from wf_api import DEFAULT_OK_OUTCOME, parse_workflow_surface_capability_id; print(DEFAULT_OK_OUTCOME, parse_workflow_surface_capability_id('demo.personal.echo_tool'))"
```

Expected output:

```text
ok demo.personal.echo_tool
```

---

## Task 4: Convert Old Workflow-Surface Modules To Shims

**Files:**

- Modify: `src/wf_mcp/workflow_surface/constants.py`
- Modify: `src/wf_mcp/workflow_surface/refs.py`

- [ ] **Step 1: Replace `src/wf_mcp/workflow_surface/constants.py`**

Replace the file with this shim:

```python
"""Compatibility shim for workflow API constants.

New code should import these literals from `wf_api.constants`. This module stays
so older MCP workflow-surface imports keep working during extraction.
"""

from wf_api.constants import (
    DEFAULT_CALL_STEP_ID,
    DEFAULT_ERROR_OUTCOME,
    DEFAULT_ERROR_STEP_ID,
    DEFAULT_OK_OUTCOME,
    RUNTIME_ERROR_CAPABILITY,
)

__all__ = [
    "DEFAULT_CALL_STEP_ID",
    "DEFAULT_ERROR_OUTCOME",
    "DEFAULT_ERROR_STEP_ID",
    "DEFAULT_OK_OUTCOME",
    "RUNTIME_ERROR_CAPABILITY",
]
```

- [ ] **Step 2: Replace `src/wf_mcp/workflow_surface/refs.py`**

Replace the file with this shim:

```python
"""Compatibility shim for workflow API capability refs.

New code should import from `wf_api.refs`. This module stays so older MCP
workflow-surface imports keep working during extraction.
"""

from wf_api.refs import (
    WorkflowSurfaceCapabilityId,
    parse_workflow_surface_capability_id,
)

__all__ = [
    "WorkflowSurfaceCapabilityId",
    "parse_workflow_surface_capability_id",
]
```

- [ ] **Step 3: Run shim import smoke check**

Run:

```powershell
uv run python -c "from wf_mcp.workflow_surface.constants import DEFAULT_CALL_STEP_ID; from wf_mcp.workflow_surface.refs import parse_workflow_surface_capability_id; print(DEFAULT_CALL_STEP_ID, parse_workflow_surface_capability_id('workflow.echo_wrapper.v2'))"
```

Expected output:

```text
call workflow.echo_wrapper.v2
```

---

## Task 5: Update Canonical Imports In `WorkflowSurfaceHandlers`

**Files:**

- Modify: `src/wf_mcp/workflow_surface/handlers.py`

- [ ] **Step 1: Change constants import**

Replace:

```python
from .constants import (
    DEFAULT_CALL_STEP_ID,
    DEFAULT_ERROR_OUTCOME,
    DEFAULT_ERROR_STEP_ID,
    DEFAULT_OK_OUTCOME,
    RUNTIME_ERROR_CAPABILITY,
)
```

with:

```python
from wf_api.constants import (
    DEFAULT_CALL_STEP_ID,
    DEFAULT_ERROR_OUTCOME,
    DEFAULT_ERROR_STEP_ID,
    DEFAULT_OK_OUTCOME,
    RUNTIME_ERROR_CAPABILITY,
)
```

- [ ] **Step 2: Change refs import**

Replace:

```python
from .refs import parse_workflow_surface_capability_id
```

with:

```python
from wf_api.refs import parse_workflow_surface_capability_id
```

- [ ] **Step 3: Run import smoke check**

Run:

```powershell
uv run python -c "from wf_mcp.workflow_surface.handlers import WorkflowSurfaceHandlers; print(WorkflowSurfaceHandlers.__name__)"
```

Expected output:

```text
WorkflowSurfaceHandlers
```

---

## Task 6: Update Ref Tests For Canonical And Shim Imports

**Files:**

- Modify: `tests/wf_mcp/test_workflow_surface_refs.py`

- [ ] **Step 1: Update imports**

Change the top imports to:

```python
from wf_api.refs import parse_workflow_surface_capability_id
from wf_artifacts import WorkflowCapabilityRef
from wf_mcp.workflow_surface.refs import (
    parse_workflow_surface_capability_id as parse_workflow_surface_capability_id_shim,
)
from wf_platform import CapabilityRef
```

- [ ] **Step 2: Add shim compatibility test**

Append this test to the file:

```python
def test_workflow_surface_refs_shim_reexports_canonical_parser() -> None:
    assert parse_workflow_surface_capability_id_shim is parse_workflow_surface_capability_id
```

- [ ] **Step 3: Add constants shim compatibility test**

Append this test to the file:

```python
def test_workflow_surface_constants_shim_reexports_canonical_literals() -> None:
    from wf_api.constants import DEFAULT_CALL_STEP_ID
    from wf_mcp.workflow_surface.constants import (
        DEFAULT_CALL_STEP_ID as DEFAULT_CALL_STEP_ID_SHIM,
    )

    assert DEFAULT_CALL_STEP_ID_SHIM == DEFAULT_CALL_STEP_ID
```

- [ ] **Step 4: Run focused tests**

Run:

```powershell
uv run pytest tests/wf_mcp/test_workflow_surface_refs.py tests/wf_api/test_import_direction.py -q
```

Expected: all tests pass.

---

## Task 7: Search For Remaining Canonical Import Opportunities

**Files:**

- Inspect only unless the search finds new low-risk direct consumers.

- [ ] **Step 1: Search old imports**

Run:

```powershell
rg -n "from \\.constants|from \\.refs|from wf_mcp\\.workflow_surface\\.(constants|refs)" src tests
```

Expected remaining matches:

```text
src/wf_mcp/workflow_surface/constants.py
src/wf_mcp/workflow_surface/refs.py
tests/wf_mcp/test_workflow_surface_refs.py
```

If any other production module imports the old paths, update it to import from
`wf_api.constants` or `wf_api.refs`.

- [ ] **Step 2: Search for accidental `wf_api -> wf_mcp` imports**

Run:

```powershell
rg -n "wf_mcp" src/wf_api tests/wf_api
```

Expected matches only in test text/docstrings for the import-direction guard,
not in `src/wf_api/*.py`.

---

## Task 8: Verification

- [ ] **Step 1: Run focused tests**

```powershell
uv run pytest tests/wf_api tests/wf_mcp/test_workflow_surface_refs.py tests/wf_mcp/workflow_surface -q
```

Expected: all pass.

- [ ] **Step 2: Run CLI context smoke tests**

```powershell
uv run pytest tests/wf_cli/test_context.py -q
```

Expected: pass.

- [ ] **Step 3: Run ruff on touched files**

```powershell
uv run ruff check src/wf_api src/wf_mcp/workflow_surface/constants.py src/wf_mcp/workflow_surface/refs.py src/wf_mcp/workflow_surface/handlers.py tests/wf_mcp/test_workflow_surface_refs.py tests/wf_api
```

Expected: all checks pass.

- [ ] **Step 4: Run basedpyright on touched files**

```powershell
uv run basedpyright --level error src/wf_api src/wf_mcp/workflow_surface/constants.py src/wf_mcp/workflow_surface/refs.py src/wf_mcp/workflow_surface/handlers.py tests/wf_mcp/test_workflow_surface_refs.py tests/wf_api
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

- `wf_api.constants` imports no `wf_mcp`.
- `wf_api.refs` imports no `wf_mcp`.
- Old `wf_mcp.workflow_surface.constants` import path still works.
- Old `wf_mcp.workflow_surface.refs` import path still works.
- `WorkflowSurfaceHandlers` imports the canonical `wf_api` helpers.
- No public payload shape changed.
- No behavior changed.
- No other workflow-surface helper moved in this slice.
