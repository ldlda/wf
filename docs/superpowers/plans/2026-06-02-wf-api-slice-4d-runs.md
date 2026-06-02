# wf_api Slice 4D: Run Lifecycle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move deployment run, resume, stopped-run inspection, and bounded trace reading out of `WorkflowSurfaceHandlers` into a protocol-neutral `wf_api.runs.WorkflowRunApi`.

**Architecture:** `WorkflowRunApi` depends on `WorkflowOperationContext` and `WorkflowDeploymentApi`, not `WfMcpService`. Runtime execution remains adapter-owned through `WorkflowRuntimeRunner`; run persistence and payload shaping move into `wf_api`. Keep MCP Pydantic request models at the MCP boundary and pass only a structural trace range into `wf_api`.

**Tech Stack:** Python 3.14+, `wf_api.operation_context`, `wf_api.deployments`, `wf_api.run_lifecycle`, `wf_api.saved_subgraphs`, `wf_artifacts` run store models, `wf_core.RunState`, pytest, ruff, basedpyright.

---

## Scope

### Move In This Slice

Move these methods from `WorkflowSurfaceHandlers` to `wf_api.runs.WorkflowRunApi`:

```text
run_deployment
resume_run
inspect_run
read_run_trace
```

Move or duplicate only the helpers needed by those methods:

```text
_run_store
_raw_plan_from_artifact
_plan_field
_run_payload
_interrupt_payload
```

### Do Not Move In This Slice

Do not move:

```text
list_capabilities
inspect_capability
call_capability
_wrapper_artifact_for_capability_name
_wrapper_capability_summaries
_wrapper_capability_detail
_call_wrapper_artifact
```

Reasons:

- Capability methods still own wrapper discovery and direct test calls.
- `_raw_plan_from_artifact` is still needed by wrapper direct calls in `handlers.py`; duplicate it temporarily in `wf_api.runs` or move it to a small shared `wf_api` helper only if that does not widen the slice.

### Invariants

- No public payload changes.
- No MCP tool schema changes.
- `WorkflowSurfaceHandlers` public run method signatures stay unchanged.
- `wf_api` imports no `wf_mcp`.
- Runtime event construction remains adapter-owned in `WfMcpService`.
- `run_deployment` still persists stopped runs.
- `resume_run` still revalidates pinned dependency environments before mutating state.
- Trace payloads remain opt-in and bounded by `trace_range`.

---

## Task 1: Align Runtime Protocol With Actual Runtime Calls

**Files:**

- Modify: `src/wf_api/operation_context.py`
- Modify: `src/wf_mcp/broker/service/workflow_operation_context.py`
- Test: `tests/wf_api/test_operation_context.py`

- [ ] **Step 1: Update `WorkflowRuntimeRunner` protocol**

In `src/wf_api/operation_context.py`, replace the older generic runtime kwargs with the current deployment-aware shape:

```python
from wf_api.saved_subgraphs import SavedSubgraphTree
```

```python
class WorkflowRuntimeRunner(Protocol):
    """Runs and resumes workflow plans using an adapter-owned runtime backend."""

    async def run_workflow_from_plan(
        self,
        plan: RawWorkflowPlan,
        workflow_input: dict[str, Any],
        deployment: WorkflowDeployment | None = None,
        artifact: WorkflowArtifact | None = None,
        saved_subgraph_tree: SavedSubgraphTree | None = None,
    ) -> RunState:
        """Execute one raw workflow plan and return its run state."""
        ...

    async def resume_workflow_from_plan(
        self,
        plan: RawWorkflowPlan,
        run: RunState,
        *,
        resume_payload: dict[str, Any],
        resume_outcome: str,
        deployment: WorkflowDeployment | None = None,
        artifact: WorkflowArtifact | None = None,
        saved_subgraph_tree: SavedSubgraphTree | None = None,
    ) -> RunState:
        """Resume one interrupted raw workflow plan and return its run state."""
        ...
```

Remove unused imports from the protocol file if `AsyncRegistryHandler` or
`ReducerDefinition` are no longer needed.

- [ ] **Step 2: Give adapter methods explicit signatures**

In `src/wf_mcp/broker/service/workflow_operation_context.py`, replace `**kwargs`
runtime adapter methods with explicit signatures matching the protocol:

```python
async def run_workflow_from_plan(
    self,
    plan,
    workflow_input,
    deployment=None,
    artifact=None,
    saved_subgraph_tree=None,
):
    return await self.service.run_workflow_from_plan(
        plan,
        workflow_input,
        deployment=deployment,
        artifact=artifact,
        saved_subgraph_tree=saved_subgraph_tree,
    )
```

Do the same for `resume_workflow_from_plan(...)`.

- [ ] **Step 3: Run operation-context tests**

```powershell
uv run pytest tests/wf_api/test_operation_context.py -q
```

Expected: pass.

---

## Task 2: Create `wf_api.runs`

**Files:**

- Create: `src/wf_api/runs.py`
- Modify: `src/wf_api/__init__.py`
- Test: `tests/wf_api/test_run_api.py`

- [ ] **Step 1: Create service skeleton and trace range protocol**

Create `src/wf_api/runs.py`:

```python
from __future__ import annotations

from dataclasses import asdict
from typing import Any, Protocol

from wf_artifacts import (
    DependencyDiagnostic,
    RunStore,
    WorkflowArtifact,
    WorkflowDeployment,
)
from wf_core import RunState

from .deployments import WorkflowDeploymentApi, _available_sources
from .models import RawWorkflowPlan
from .next_actions import NextActions
from .run_lifecycle import (
    create_pinned_environment,
    has_blocking_diagnostics,
    load_stored_run,
    mark_resume_blocked,
    persist_stopped_run,
    restore_interrupted_run,
    validate_pinned_resume_environment,
)
from .saved_subgraphs import saved_subgraph_tree_from_snapshots
from .operation_context import WorkflowOperationContext


class TraceRangeLike(Protocol):
    """Small structural trace range accepted from MCP, CLI, or HTTP adapters."""

    start: int
    limit: int


class WorkflowRunApi:
    """Deployment run lifecycle operations.

    Runtime execution stays behind WorkflowOperationContext.runtime so wf_api
    does not depend on MCP service internals.
    """

    def __init__(self, context: WorkflowOperationContext) -> None:
        self.context = context
        self.deployments = WorkflowDeploymentApi(context)

    def _run_store(self) -> RunStore:
        if self.context.run_store is None:
            raise KeyError("workflow run store is not configured")
        return self.context.run_store
```

Use `TraceRangeLike | None` for run methods. This lets handler methods pass
their MCP Pydantic `TraceRange` without importing it into `wf_api`.

- [ ] **Step 2: Export run service**

In `src/wf_api/__init__.py`:

```python
from .runs import WorkflowRunApi
```

Add `"WorkflowRunApi"` to `__all__`.

---

## Task 3: Move Run Methods

**Files:**

- Modify: `src/wf_api/runs.py`

- [ ] **Step 1: Move `run_deployment`**

Move the current handler body into `WorkflowRunApi.run_deployment(...)`.

Required replacements:

```python
self._deployments.deployment_validation(...) -> self.deployments.deployment_validation(...)
self.service.run_workflow_from_plan(...) -> self.context.runtime.run_workflow_from_plan(...)
self._run_store() -> self._run_store()
```

Call runtime with the same arguments:

```python
run = await self.context.runtime.run_workflow_from_plan(
    plan,
    workflow_input,
    deployment=deployment,
    artifact=artifact,
    saved_subgraph_tree=tree,
)
```

- [ ] **Step 2: Move `resume_run`**

Move the current handler body into `WorkflowRunApi.resume_run(...)`.

Required replacements:

```python
validate_pinned_resume_environment(..., sources=_available_sources(self.service))
```

becomes:

```python
validate_pinned_resume_environment(
    record=record,
    sources=_available_sources(self.context.capability_sources),
)
```

Call runtime with:

```python
run = await self.context.runtime.resume_workflow_from_plan(
    plan,
    stopped_run,
    resume_payload=resume_payload,
    resume_outcome=resume_outcome,
    deployment=environment.deployment,
    artifact=environment.root_artifact,
    saved_subgraph_tree=tree,
)
```

- [ ] **Step 3: Move stopped-run readers**

Move:

```text
inspect_run
read_run_trace
```

Preserve current payload shape:

- `inspect_run` returns no trace list.
- `read_run_trace` returns only `trace_range.start : start + limit`.
- both include `trace_count`.
- both include `next_actions` via `_run_payload`.

---

## Task 4: Move Run Helpers

**Files:**

- Modify: `src/wf_api/runs.py`
- Modify: `src/wf_mcp/workflow_surface/handlers.py`

- [ ] **Step 1: Add private helpers to `wf_api.runs`**

Move or duplicate these helpers into `src/wf_api/runs.py`:

```text
_raw_plan_from_artifact
_plan_field
_run_payload
_interrupt_payload
```

Keep the trace comment inside `_run_payload`:

```python
# Trace entries can grow quickly, so the public run tool only includes
# a bounded debug slice when the caller explicitly asks for a range.
```

This comment is important because trace bloat is a public UX boundary.

- [ ] **Step 2: Keep handler copies only if needed**

After handler delegation, run:

```powershell
rg -n "_raw_plan_from_artifact|_run_payload|_interrupt_payload|_plan_field" src/wf_mcp/workflow_surface/handlers.py
```

Expected:

- `_raw_plan_from_artifact` likely remains because `_call_wrapper_artifact` still uses it.
- `_plan_field` remains if `_raw_plan_from_artifact` remains.
- `_run_payload` and `_interrupt_payload` should be removable if no handler run methods remain.

Remove only helpers with no remaining handler callers.

---

## Task 5: Wire `WorkflowSurfaceHandlers`

**Files:**

- Modify: `src/wf_mcp/workflow_surface/handlers.py`

- [ ] **Step 1: Add import**

```python
from wf_api.runs import WorkflowRunApi
```

- [ ] **Step 2: Instantiate run service**

In `WorkflowSurfaceHandlers.__init__`, reuse the same context object:

```python
context = context_from_service(service)
self._drafts = WorkflowDraftApi(context)
self._artifacts = WorkflowArtifactApi(context)
self._deployments = WorkflowDeploymentApi(context)
self._runs = WorkflowRunApi(context)
```

Do not call `context_from_service(service)` separately for every domain service.

- [ ] **Step 3: Replace run method bodies with delegates**

Replace:

```text
run_deployment
resume_run
inspect_run
read_run_trace
```

Example:

```python
async def inspect_run(self, *, run_id: str) -> dict[str, Any]:
    """Return one durable stopped-run summary without debug trace entries."""
    return await self._runs.inspect_run(run_id=run_id)
```

For `trace_range`, pass the MCP model object through directly:

```python
return await self._runs.run_deployment(
    deployment_id=deployment_id,
    workflow_input=workflow_input,
    trace_range=trace_range,
)
```

`WorkflowRunApi` accepts it structurally through `TraceRangeLike`.

- [ ] **Step 4: Remove now-unused imports**

After replacing run methods, remove imports from `handlers.py` only if `ruff`
confirms they are unused. Likely candidates:

```text
dataclasses.asdict
RunStore
run_lifecycle helpers
saved_subgraph_tree_from_snapshots
```

Do not remove `SavedSubgraphTree`, `direct_wrapper_interrupt_diagnostic`,
`resolve_saved_subgraph_tree`, or `_raw_plan_from_artifact` if wrapper/capability
methods still need them.

---

## Task 6: Add Focused Run API Tests

**Files:**

- Create: `tests/wf_api/test_run_api.py`

- [ ] **Step 1: Cover unrunnable deployment path**

Create a test that saves a deployment with missing/unbound requirements and
asserts:

```python
result = asyncio.run(api.run_deployment(...))
assert result["status"] == "unrunnable"
assert result["run_id"] is None
assert result["trace_count"] == 0
assert result["diagnostics"][0]["code"]
```

- [ ] **Step 2: Cover completed run persistence**

Use existing test helpers (`echo_tool`, local temp store patterns) to register a
valid source, save an artifact/deployment, run it, and assert:

```python
assert result["status"] == "completed"
assert isinstance(result["run_id"], str)
assert result["resume_readiness"] == "not_applicable"
assert result["trace_count"] >= 1
```

Then load the run from the run store and assert it exists.

- [ ] **Step 3: Cover inspect and bounded trace**

After a completed run:

```python
summary = asyncio.run(api.inspect_run(run_id=run_id))
trace = asyncio.run(api.read_run_trace(run_id=run_id, trace_range=SimpleTraceRange(start=0, limit=1)))
```

Assert:

```python
assert "trace" not in summary
assert trace["trace_start"] == 0
assert trace["trace_limit"] == 1
assert len(trace["trace"]) <= 1
assert trace["trace_count"] == summary["trace_count"]
```

Define local helper:

```python
@dataclass(frozen=True)
class SimpleTraceRange:
    start: int
    limit: int
```

- [ ] **Step 4: Cover handler delegation**

Add one smoke test comparing stable fields from:

```python
handler_result = asyncio.run(WorkflowSurfaceHandlers(service).inspect_run(run_id=run_id))
api_result = asyncio.run(WorkflowRunApi(context_from_service(service)).inspect_run(run_id=run_id))
```

Compare `status`, `run_id`, `trace_count`, and `resume_readiness` individually.

Do not duplicate every old workflow-surface run test. `wf_api` should own run
behavior; `wf_mcp` should keep only adapter/schema/delegation coverage.

---

## Task 7: Verification

- [ ] **Step 1: Run focused run tests**

```powershell
uv run pytest tests/wf_api/test_run_api.py tests/wf_mcp/workflow_surface/test_runs.py -q
```

Expected: pass.

- [ ] **Step 2: Run deployment/artifact tests because runs reuse them**

```powershell
uv run pytest tests/wf_api/test_artifact_api.py tests/wf_api/test_deployment_api.py tests/wf_api/test_operation_context.py -q
```

Expected: pass.

- [ ] **Step 3: Run import-direction test**

```powershell
uv run pytest tests/wf_api/test_import_direction.py -q
```

Expected: pass; `wf_api` has no `wf_mcp` imports.

- [ ] **Step 4: Run ruff on touched files**

```powershell
uv run ruff check src/wf_api/runs.py src/wf_api/operation_context.py src/wf_api/__init__.py src/wf_mcp/broker/service/workflow_operation_context.py src/wf_mcp/workflow_surface/handlers.py tests/wf_api/test_run_api.py
```

Expected: all checks pass.

- [ ] **Step 5: Run basedpyright on touched files**

```powershell
uv run basedpyright --level error src/wf_api/runs.py src/wf_api/operation_context.py src/wf_mcp/broker/service/workflow_operation_context.py src/wf_mcp/workflow_surface/handlers.py tests/wf_api/test_run_api.py
```

Expected: `0 errors`.

- [ ] **Step 6: Optional full suite**

```powershell
uv run pytest -q
```

Expected: full suite passes with the project’s existing skipped/xfailed counts.

---

## Self-Review Checklist

- `wf_api.runs` imports no `wf_mcp`.
- Runtime execution goes through `WorkflowOperationContext.runtime`.
- Run persistence uses `WorkflowOperationContext.run_store`.
- `WorkflowSurfaceHandlers` public run signatures are unchanged.
- `TraceRange` stays structural at the `wf_api` layer.
- Trace list remains opt-in and bounded.
- `resume_run` still blocks when pinned dependency validation fails.
- Capability direct wrapper calls still work because handler keeps `_raw_plan_from_artifact` if needed.
- No public payload shape changed.
- No MCP schema changed.
