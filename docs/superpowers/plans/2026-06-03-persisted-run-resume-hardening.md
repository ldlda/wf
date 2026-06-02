# Persisted Run/Resume Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Lock down the persisted run/resume contract with missing regression tests and add a fail-fast required-store factory for durable API frontends.

**Architecture:** The current V1 run/resume behavior mostly exists in `wf_api.runs` and `wf_api.run_lifecycle`. This plan avoids redesigning `RunState`, retry, checkpoint cadence, or transactional storage. It adds tests for weakly covered contract rules, then introduces a protocol-neutral durable-context helper that future HTTP/API frontends can use before constructing `WorkflowApi`.

**Tech Stack:** Python 3.14, pytest, Pydantic v2, `wf_api`, `wf_artifacts`, `wf_core`, existing MCP-backed test fixtures.

---

## File Map

- Modify `tests/wf_api/test_run_api.py`
  - Add contract tests for rejected resume of non-interrupted stored runs.
  - Add contract test proving deleted deployments do not break stored run inspection.
  - Strengthen trace-range validation test to prove store lookup is not touched.
- Create `src/wf_api/durable_context.py`
  - Add required-store validation for durable frontends.
  - Add `durable_workflow_api(context)` helper returning `WorkflowApi`.
- Modify `src/wf_api/__init__.py`
  - Export the durable-context helpers.
- Create `tests/wf_api/test_durable_context.py`
  - Cover success and missing-store failures.
- Modify `docs/superpowers/specs/2026-06-03-persisted-run-resume-contract.md`
  - Mark these V1 hardening items as implemented after tests/helper land.
- Modify `docs/current_roadmap.md`
  - Add a short note that durable required-store factory exists; transactional backend remains future work.

Out of scope:

- No transactional run store.
- No concurrent resume compare-and-swap.
- No paged run listing/checkpoint listing.
- No automatic retry/timeout policy.
- No HTTP server routes.

---

## Task 1: Add Missing Run Contract Tests

**Files:**

- Modify: `tests/wf_api/test_run_api.py`

- [ ] **Step 1: Add imports for stored-run helpers**

At the top of `tests/wf_api/test_run_api.py`, extend imports:

```python
from wf_artifacts import (
    FileWorkflowArtifactStore,
    FileRunStore,
    ResumeReadiness,
    WorkflowDeployment,
)
```

If `ResumeReadiness` is already imported later by another task, keep one import only.

- [ ] **Step 2: Add test for non-interrupted resume rejection**

Append this test after `test_run_api_completed_run_persists`:

```python
def test_run_api_rejects_resume_for_completed_run() -> None:
    root = local_temp_root() / "run_api_resume_completed_rejected"
    service, _ = _service_with_echo(root)
    context = context_from_service(service)
    api = WorkflowRunApi(context)

    result = asyncio.run(
        api.run_deployment(
            deployment_id="echo.personal",
            workflow_input={"text": "hello"},
        )
    )

    with pytest.raises(ValueError, match="is not interrupted"):
        asyncio.run(
            api.resume_run(
                run_id=result["run_id"],
                resume_payload={"answer": "ignored"},
            )
        )
```

This locks down: `resume_run` only resumes stored runs whose latest status is `interrupted`.

- [ ] **Step 3: Add test that deleting deployment does not erase stored inspection**

Append this test after the non-interrupted resume test:

```python
def test_run_api_inspect_uses_pinned_environment_after_deployment_deleted() -> None:
    root = local_temp_root() / "run_api_inspect_after_deployment_deleted"
    service, artifact_store = _service_with_echo(root)
    context = context_from_service(service)
    api = WorkflowRunApi(context)

    result = asyncio.run(
        api.run_deployment(
            deployment_id="echo.personal",
            workflow_input={"text": "hello"},
        )
    )
    artifact_store.delete_deployment("echo.personal")

    summary = asyncio.run(api.inspect_run(run_id=result["run_id"]))

    assert summary["status"] == "completed"
    assert summary["run_id"] == result["run_id"]
    assert summary["deployment_id"] == "echo.personal"
    assert summary["artifact_id"] == "echo"
    assert summary["output"]["echoed"] == "hello"
```

This locks down: stored run inspection reads pinned environment from `WorkflowRunRecord`, not mutable deployment storage.

- [ ] **Step 4: Strengthen trace-range-before-store validation**

In `test_run_api_rejects_invalid_trace_range_before_store_lookup`, replace the setup with a service whose run store raises if accessed:

```python
class ExplodingRunStore(FileRunStore):
    def get_run(self, run_id: str):
        raise AssertionError("run store must not be read before trace_range validation")
```

Then build the service explicitly:

```python
root = local_temp_root() / "run_api_invalid_trace_range"
service, _ = _service_with_echo(root)
service.run_store = ExplodingRunStore(root / "exploding_runs")
context = context_from_service(service)
api = WorkflowRunApi(context)
```

Keep the two existing `pytest.raises(ValueError, ...)` assertions unchanged. The test must still pass, proving invalid trace ranges fail before store lookup.

- [ ] **Step 5: Run focused run API tests**

Run:

```bash
uv run pytest tests/wf_api/test_run_api.py -q
```

Expected:

```text
all tests in tests/wf_api/test_run_api.py pass
```

- [ ] **Step 6: Commit Task 1**

```bash
git add tests/wf_api/test_run_api.py
git commit -m "test: lock down durable run resume contract"
```

---

## Task 2: Add Required-Store Durable Context Helper

**Files:**

- Create: `src/wf_api/durable_context.py`
- Modify: `src/wf_api/__init__.py`
- Test: `tests/wf_api/test_durable_context.py`

- [ ] **Step 1: Write failing durable-context tests**

Create `tests/wf_api/test_durable_context.py`:

```python
from __future__ import annotations

import pytest

from wf_api import WorkflowApi
from wf_api.durable_context import durable_workflow_api, require_workflow_stores
from wf_api.operation_context import WorkflowOperationContext
from wf_api.stores import file_workflow_stores
from wf_mcp.broker import WfMcpService
from wf_mcp.broker.service.workflow_operation_context import context_from_service
from wf_mcp.storage import FileStore


def test_require_workflow_stores_returns_existing_store_bundle(tmp_path) -> None:
    stores = file_workflow_stores(tmp_path / "workflow_stores")
    service = WfMcpService(
        store=FileStore(tmp_path / "mcp"),
        artifact_store=stores.artifact_store,
        draft_workspace_store=stores.draft_workspace_store,
        run_store=stores.run_store,
    )
    context = context_from_service(service)

    required = require_workflow_stores(context)

    assert required.artifact_store is stores.artifact_store
    assert required.draft_workspace_store is stores.draft_workspace_store
    assert required.run_store is stores.run_store


def test_require_workflow_stores_rejects_missing_store(tmp_path) -> None:
    service = WfMcpService(
        store=FileStore(tmp_path / "mcp"),
        artifact_store=None,
        draft_workspace_store=None,
        run_store=None,
    )
    context = context_from_service(service)

    with pytest.raises(ValueError, match="durable workflow API requires stores"):
        require_workflow_stores(context)


def test_durable_workflow_api_returns_workflow_api_with_same_context(tmp_path) -> None:
    stores = file_workflow_stores(tmp_path / "workflow_stores")
    service = WfMcpService(
        store=FileStore(tmp_path / "mcp"),
        artifact_store=stores.artifact_store,
        draft_workspace_store=stores.draft_workspace_store,
        run_store=stores.run_store,
    )
    context = context_from_service(service)

    api = durable_workflow_api(context)

    assert isinstance(api, WorkflowApi)
    assert api.context is context
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
uv run pytest tests/wf_api/test_durable_context.py -q
```

Expected:

```text
FAIL with ModuleNotFoundError: No module named 'wf_api.durable_context'
```

- [ ] **Step 3: Implement durable context helper**

Create `src/wf_api/durable_context.py`:

```python
from __future__ import annotations

from .operation_context import WorkflowOperationContext
from .service import WorkflowApi
from .stores import WorkflowStores


def require_workflow_stores(context: WorkflowOperationContext) -> WorkflowStores:
    """Return required stores or fail before constructing durable frontends.

    `WorkflowOperationContext` keeps stores optional for compatibility tests and
    lightweight MCP surfaces. Durable API surfaces need all stores up front so a
    run cannot start without somewhere to persist artifacts, drafts, and stopped
    execution state.
    """
    missing = []
    if context.artifact_store is None:
        missing.append("artifact_store")
    if context.draft_workspace_store is None:
        missing.append("draft_workspace_store")
    if context.run_store is None:
        missing.append("run_store")
    if missing:
        raise ValueError(
            "durable workflow API requires stores: " + ", ".join(missing)
        )
    return WorkflowStores(
        artifact_store=context.artifact_store,
        draft_workspace_store=context.draft_workspace_store,
        run_store=context.run_store,
    )


def durable_workflow_api(context: WorkflowOperationContext) -> WorkflowApi:
    """Construct a WorkflowApi only after durable store dependencies exist."""
    require_workflow_stores(context)
    return WorkflowApi(context)


__all__ = ["durable_workflow_api", "require_workflow_stores"]
```

- [ ] **Step 4: Export helpers from wf_api**

Modify `src/wf_api/__init__.py` to import and export:

```python
from .durable_context import durable_workflow_api, require_workflow_stores
```

Add these names to `__all__`:

```python
"durable_workflow_api",
"require_workflow_stores",
```

- [ ] **Step 5: Run durable-context tests**

Run:

```bash
uv run pytest tests/wf_api/test_durable_context.py -q
```

Expected:

```text
3 passed
```

- [ ] **Step 6: Run wf_api import-direction test**

Run:

```bash
uv run pytest tests/wf_api/test_import_direction.py -q
```

Expected:

```text
1 passed
```

- [ ] **Step 7: Commit Task 2**

```bash
git add src/wf_api/durable_context.py src/wf_api/__init__.py tests/wf_api/test_durable_context.py
git commit -m "feat: add durable workflow API store guard"
```

---

## Task 3: Document Implemented Hardening

**Files:**

- Modify: `docs/superpowers/specs/2026-06-03-persisted-run-resume-contract.md`
- Modify: `docs/current_roadmap.md`

- [ ] **Step 1: Update spec current gaps**

In `docs/superpowers/specs/2026-06-03-persisted-run-resume-contract.md`, under `## Current Gaps / Next Implementation Work`, replace item 1 with:

```markdown
1. **Required stores for durable API**
   - Implemented for process-local frontends through
     `wf_api.durable_context.require_workflow_stores()` and
     `wf_api.durable_context.durable_workflow_api()`.
   - `WorkflowOperationContext` still allows optional stores for MCP test and
     compatibility paths.
```

Under `## Implementation Order`, replace item 1 with:

```markdown
1. Contract regression tests now cover:
   - non-interrupted `resume_run` rejection
   - deleted deployment does not erase existing run inspection
   - trace range validates before store lookup
   - blocked resume writes no checkpoint (`tests/wf_mcp/test_saved_subgraphs.py`)
```

- [ ] **Step 2: Update current roadmap**

In `docs/current_roadmap.md`, find the durable/persisted run section and add:

```markdown
- `wf_api.durable_context` now provides a required-store guard for future
  durable HTTP/API frontends. It preserves the current process-local behavior
  while failing fast if artifact, draft, or run stores are missing.
```

If no durable/persisted run section exists, add it under the current `wf_api` or runtime roadmap notes.

- [ ] **Step 3: Run docs grep sanity check**

Run:

```bash
rg -n "durable_workflow_api|require_workflow_stores|non-interrupted|blocked resume writes no checkpoint" docs
```

Expected:

```text
matches in persisted-run spec and/or current roadmap
```

- [ ] **Step 4: Commit Task 3**

```bash
git add docs/superpowers/specs/2026-06-03-persisted-run-resume-contract.md docs/current_roadmap.md
git commit -m "docs: record durable run hardening status"
```

---

## Task 4: Final Verification

**Files:**

- Verify all touched code/tests/docs.

- [ ] **Step 1: Run focused tests**

Run:

```bash
uv run pytest tests/wf_api/test_run_api.py tests/wf_api/test_durable_context.py tests/wf_api/test_import_direction.py tests/wf_mcp/test_saved_subgraphs.py -q
```

Expected:

```text
all selected tests pass
```

- [ ] **Step 2: Run broader wf_api suite**

Run:

```bash
uv run pytest tests/wf_api -q
```

Expected:

```text
all wf_api tests pass
```

- [ ] **Step 3: Run ruff**

Run:

```bash
uv run ruff check src/wf_api tests/wf_api tests/wf_mcp/test_saved_subgraphs.py
uv run ruff format --check src/wf_api tests/wf_api tests/wf_mcp/test_saved_subgraphs.py
```

Expected:

```text
All checks passed
```

- [ ] **Step 4: Run basedpyright**

Run:

```bash
uv run basedpyright --level error
```

Expected:

```text
0 errors, 0 warnings, 0 notes
```

Known caveat: this repo may still exit nonzero with the workspace enumeration warning even when it reports `0 errors`.

- [ ] **Step 5: Final report**

Report:

```text
Implemented persisted run/resume hardening:
- added missing contract regression tests
- added wf_api durable required-store guard
- updated persisted-run spec and roadmap

Verification:
- focused tests: ...
- wf_api tests: ...
- ruff: ...
- basedpyright: ...
```

---

## Self-Review

Spec coverage:

- `resume_run` only resumes interrupted runs: Task 1.
- Pinned environment survives deployment deletion: Task 1.
- Trace range validates before store lookup: Task 1.
- Blocked resume writes no checkpoint: already covered by `tests/wf_mcp/test_saved_subgraphs.py`; referenced in Task 3 and final focused verification.
- Required-store context/factory for durable API surfaces: Task 2.
- Transactional backend, CAS resume guard, run listing, progress, retry/timeout: explicitly out of scope.

Placeholder scan:

- No placeholder implementation steps.
- Code snippets include exact functions and expected assertions.

Type consistency:

- `WorkflowStores`, `WorkflowOperationContext`, and `WorkflowApi` names match current `src/wf_api`.
- `TraceRangeLike` remains unchanged; this plan does not alter MCP/CLI schemas.
