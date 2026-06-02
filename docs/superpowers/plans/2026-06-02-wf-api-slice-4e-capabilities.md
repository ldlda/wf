# wf_api Slice 4E: Capabilities Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move workflow capability discovery, inspection, direct capability calls, wrapper capability projection, and capability-backed draft bootstrap out of `WorkflowSurfaceHandlers` into `wf_api.capabilities.WorkflowCapabilityApi`.

**Architecture:** `WorkflowCapabilityApi` depends on `WorkflowOperationContext`, `WorkflowDraftApi`, and existing `wf_api` helper modules. It must not depend on `WfMcpService`, MCP events, MCP tools, or MCP request models. `WorkflowSurfaceHandlers` becomes a thin adapter/delegator for workflow operations.

**Tech Stack:** Python 3.14+, `wf_api.operation_context`, `wf_api.drafts`, `wf_api.runs`, `wf_api.wrapper_hints`, `wf_api.refs`, `wf_artifacts`, `wf_authoring`, `wf_core.RuntimeContext`, pytest, ruff, basedpyright.

---

## Scope

### Move In This Slice

Move these methods from `WorkflowSurfaceHandlers`:

```text
list_capabilities
inspect_capability
call_capability
create_draft_workspace_from_capability
```

Move these wrapper/capability private methods:

```text
_wrapper_artifact_for_capability_name
_wrapper_capability_summaries
_wrapper_capability_detail
_call_wrapper_artifact
```

Move or duplicate only the helpers needed by those methods:

```text
_schema_field_names
_source_id_for_capability
_artifact_capability_id
_raw_plan_from_artifact
_required_capability_payloads
_draft_name_from_capability
```

### Do Not Move In This Slice

Do not move MCP tool registration, MCP request/response Pydantic models, proxy/admin/broker runtime code, or CLI code.

### Invariants

- No public payload changes.
- No MCP tool schema changes.
- `WorkflowSurfaceHandlers` public capability method signatures stay unchanged.
- `wf_api` imports no `wf_mcp`.
- Direct raw NodeSpec calls still use `build_async_registry`.
- Direct wrapper calls still reject unsupported interrupting wrappers through `direct_wrapper_interrupt_diagnostic`.
- Full saved workflows still run through deployments, not direct capability calls.
- `create_draft_workspace_from_capability` keeps using inspect-capability wrapper hints.

---

## Design Notes

Capability extraction is the final domain split because it spans several concepts:

- live planner-visible source NodeSpecs
- saved wrapper artifacts projected as workflow-facing capabilities
- direct capability REPL calls
- wrapper calls through workflow execution
- wrapper-hint-driven draft bootstrap

Keep this in one `WorkflowCapabilityApi` for now. Do not create five tiny services unless tests prove the file is too large after extraction.

Temporary private helper duplication is allowed. A later cleanup can promote common helpers such as `artifact_capability_id`, `raw_plan_from_artifact`, and source snapshots into better shared modules. Do not widen this slice just to make helper names perfect.

---

## Task 1: Create `wf_api.capabilities`

**Files:**

- Create: `src/wf_api/capabilities.py`
- Modify: `src/wf_api/__init__.py`
- Test: `tests/wf_api/test_capability_api.py`

- [ ] **Step 1: Create service skeleton**

Create `src/wf_api/capabilities.py`:

```python
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from wf_artifacts import (
    DependencyDiagnostic,
    DiagnosticSeverity,
    WorkflowArtifact,
    WorkflowCapabilityRef,
)
from wf_authoring import build_async_registry
from wf_core import RuntimeContext
from wf_core.models.steps import InputBinding, OutputBinding
from wf_core.paths import GraphSourcePath
from wf_platform import CapabilitySource, page_items

from .drafts import WorkflowDraftApi
from .models import RawWorkflowPlan
from .operation_context import WorkflowOperationContext
from .refs import parse_workflow_surface_capability_id
from .saved_subgraphs import direct_wrapper_interrupt_diagnostic
from .wrapper_hints import (
    workflow_output_schema_for_authoring,
    wrapper_hints_for_capability,
)


class WorkflowCapabilityApi:
    """Workflow-facing capability discovery, inspection, and REPL calls.

    This service owns the source/wrapper projection, while adapter-specific MCP
    tool schemas stay outside wf_api.
    """

    def __init__(self, context: WorkflowOperationContext) -> None:
        self.context = context
        self.drafts = WorkflowDraftApi(context)
```

- [ ] **Step 2: Add local list helpers**

Add local helpers rather than importing `wf_mcp.shared`:

```python
def _matches_query(*values: object, query: str | None) -> bool:
    if query is None:
        return True
    needle = query.strip().casefold()
    if not needle:
        return True
    return any(needle in str(value).casefold() for value in values if value is not None)


def _paged_list_payload(
    key: str,
    items: Sequence[dict[str, Any]],
    *,
    cursor: str | None,
    limit: int,
) -> dict[str, Any]:
    page = page_items(items, cursor=cursor, limit=limit)
    return {key: list(page.items), "next_cursor": page.next_cursor, "total": page.total}
```

This duplicates current list behavior without importing MCP shared helpers into
`wf_api`.

- [ ] **Step 3: Export capability service**

In `src/wf_api/__init__.py`:

```python
from .capabilities import WorkflowCapabilityApi
```

Add `"WorkflowCapabilityApi"` to `__all__`.

---

## Task 2: Move Discovery And Inspection

**Files:**

- Modify: `src/wf_api/capabilities.py`

- [ ] **Step 1: Move `list_capabilities`**

Move the existing handler body into:

```python
async def list_capabilities(
    self,
    *,
    query: str | None = None,
    source_id: str | None = None,
    cursor: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    ...
```

Required replacements:

```python
self.service.capability_sources -> self.context.capability_sources
self._wrapper_capability_summaries(...) -> self._wrapper_capability_summaries(...)
matches_query(...) -> _matches_query(...)
paged_list_payload(...) -> _paged_list_payload(...)
```

Preserve sorting and response shape.

- [ ] **Step 2: Move `inspect_capability`**

Move the existing handler body into:

```python
async def inspect_capability(self, *, qualified_name: str) -> dict[str, Any]:
    ...
```

Required replacements:

```python
self.service.capability_sources -> self.context.capability_sources
self._wrapper_capability_detail(...) -> self._wrapper_capability_detail(...)
```

Preserve:

- enabled/planner visibility filtering
- wrapper detail fallback
- `KeyError(f"unknown workflow capability {qualified_name!r}")`
- `wrapper_hints` payload

- [ ] **Step 3: Add helper functions**

Move or duplicate:

```text
_schema_field_names
_artifact_capability_id
_required_capability_payloads
```

Do not import private helpers from `wf_api.artifacts` or `wf_api.runs` in this slice unless the import is already public. Private duplication is acceptable here.

---

## Task 3: Move Wrapper Capability Projection

**Files:**

- Modify: `src/wf_api/capabilities.py`

- [ ] **Step 1: Add artifact store helper**

Add:

```python
def _artifact_store(self):
    return self.context.artifact_store
```

Do not raise from this helper. Existing wrapper projection returns no wrapper
rows/details when artifact store is absent.

- [ ] **Step 2: Move `_wrapper_artifact_for_capability_name`**

Move the existing method, replacing:

```python
self.service.artifact_store -> self.context.artifact_store
```

Preserve current behavior:

- invalid capability ids return `None`
- non-wrapper artifacts return `None`
- missing artifact store returns `None`
- missing artifact id/version returns `None`

- [ ] **Step 3: Move `_wrapper_capability_summaries`**

Move the method and replace:

```python
matches_query(...) -> _matches_query(...)
```

Preserve `source_id not in {None, "workflow"}` filtering and the existing row shape.

- [ ] **Step 4: Move `_wrapper_capability_detail`**

Move the method unchanged except helper references now point to local functions.

Preserve:

- `kind == "wrapper_artifact"`
- `required_capabilities`
- `wrapper_hints`
- output/input schema fields

---

## Task 4: Move Direct Capability Calls

**Files:**

- Modify: `src/wf_api/capabilities.py`

- [ ] **Step 1: Move `call_capability`**

Move the existing handler body into:

```python
async def call_capability(
    self,
    *,
    qualified_name: str,
    payload: dict[str, Any],
    deployment_id: str | None = None,
) -> dict[str, Any]:
    ...
```

Required replacements:

```python
self.service._get_qualified_spec(qualified_name) -> self.context.specs.get_qualified_spec(qualified_name)
self.service.capability_sources -> self.context.capability_sources
self._call_wrapper_artifact(...) -> self._call_wrapper_artifact(...)
```

Preserve direct NodeSpec call behavior:

- build handler with `build_async_registry(spec)[spec.name]`
- pass `RuntimeContext(current_node_id=spec.name)`
- catch `Exception` and return `capability_call_failed` diagnostic payload
- successful response returns `kind: "node_spec"` and empty diagnostics

- [ ] **Step 2: Move `_call_wrapper_artifact`**

Move the wrapper call method into `WorkflowCapabilityApi`.

Required replacements:

```python
self.service.artifact_store -> self.context.artifact_store
self.service.run_workflow_from_plan(...) -> self.context.runtime.run_workflow_from_plan(...)
```

Call runtime with the same deployment/artifact arguments:

```python
run = await self.context.runtime.run_workflow_from_plan(
    plan,
    payload,
    deployment=deployment,
    artifact=artifact,
)
```

Preserve:

- `direct_wrapper_interrupt_diagnostic` rejection
- deployment target validation
- `kind: "wrapper_artifact"`
- `outcome: run.status.value`
- `output: run.output`

- [ ] **Step 3: Move raw plan helper**

Move or duplicate:

```text
_raw_plan_from_artifact
_plan_field
```

Do not import private `_raw_plan_from_artifact` from `wf_api.runs` unless you
first make it public. Keeping a local copy is acceptable for this slice.

---

## Task 5: Move Capability-Backed Draft Bootstrap

**Files:**

- Modify: `src/wf_api/capabilities.py`

- [ ] **Step 1: Move `create_draft_workspace_from_capability`**

Move the existing handler body into `WorkflowCapabilityApi`.

Required replacements:

```python
capability = await self.inspect_capability(...)
result = await self.drafts.create_minimal_draft_workspace(...)
```

Preserve:

- wrapper-hint defaults
- explicit `input` overrides `input_map`
- explicit `output` overrides `output_map`
- returned `wrapper_hints`
- returned `next_actions`

- [ ] **Step 2: Move `_draft_name_from_capability`**

Move or duplicate:

```python
def _draft_name_from_capability(capability_name: str) -> str:
    """Return a stable draft name when caller does not provide one."""
    return capability_name.replace(".", "_").replace("-", "_")
```

---

## Task 6: Wire `WorkflowSurfaceHandlers`

**Files:**

- Modify: `src/wf_mcp/workflow_surface/handlers.py`

- [ ] **Step 1: Add import and instance**

Add:

```python
from wf_api.capabilities import WorkflowCapabilityApi
```

In `WorkflowSurfaceHandlers.__init__`, reuse the existing operation context:

```python
context = context_from_service(service)
self._capabilities = WorkflowCapabilityApi(context)
self._drafts = WorkflowDraftApi(context)
self._artifacts = WorkflowArtifactApi(context)
self._deployments = WorkflowDeploymentApi(context)
self._runs = WorkflowRunApi(context)
```

- [ ] **Step 2: Delegate moved methods**

Replace method bodies for:

```text
list_capabilities
inspect_capability
call_capability
create_draft_workspace_from_capability
```

Example:

```python
async def inspect_capability(self, *, qualified_name: str) -> dict[str, Any]:
    """Return one planner-visible workflow capability contract."""
    return await self._capabilities.inspect_capability(qualified_name=qualified_name)
```

- [ ] **Step 3: Remove moved private methods**

Remove these from `handlers.py` after delegation:

```text
_wrapper_artifact_for_capability_name
_wrapper_capability_summaries
_wrapper_capability_detail
_call_wrapper_artifact
```

Then run:

```powershell
rg -n "_schema_field_names|_source_id_for_capability|_artifact_capability_id|_raw_plan_from_artifact|_plan_field|_draft_name_from_capability|_required_capability_payloads" src/wf_mcp/workflow_surface/handlers.py
```

Remove each helper only if it has no remaining handler caller. The target after
4E should be close to zero private workflow-domain helpers in `handlers.py`.

- [ ] **Step 4: Prune imports**

Use `ruff check` to remove unused imports. Likely candidates:

```text
DependencyDiagnostic
DiagnosticSeverity
WorkflowArtifact
WorkflowCapabilityRef
CapabilitySource
build_async_registry
RuntimeContext
direct_wrapper_interrupt_diagnostic
workflow_output_schema_for_authoring
wrapper_hints_for_capability
parse_workflow_surface_capability_id
matches_query
paged_list_payload
```

Do not remove imports still needed by method signatures such as `InputBinding`,
`OutputBinding`, `GraphSourcePath`, `TraceRange`, or `RawWorkflowPlan`.

---

## Task 7: Add Focused Capability API Tests

**Files:**

- Create: `tests/wf_api/test_capability_api.py`

- [ ] **Step 1: Cover live source capability listing and inspection**

Build a service with `echo_tool`, adapt with `context_from_service`, instantiate
`WorkflowCapabilityApi`, and assert:

```python
listed = asyncio.run(api.list_capabilities())
assert listed["total"] >= 1
assert any(item["name"] == "demo.personal.echo_tool" for item in listed["capabilities"])

detail = asyncio.run(api.inspect_capability(qualified_name="demo.personal.echo_tool"))
assert detail["name"] == "demo.personal.echo_tool"
assert "wrapper_hints" in detail
```

- [ ] **Step 2: Cover direct NodeSpec call**

Call:

```python
result = asyncio.run(
    api.call_capability(
        qualified_name="demo.personal.echo_tool",
        payload={"text": "hello"},
    )
)
```

Assert stable fields:

```python
assert result["kind"] == "node_spec"
assert result["outcome"] == "ok"
assert result["diagnostics"] == []
```

- [ ] **Step 3: Cover saved wrapper projection**

Save a wrapper artifact and assert:

- `list_capabilities(source_id="workflow")` includes `kind == "wrapper_artifact"`
- `inspect_capability(qualified_name="workflow.<id>.v<version>")` returns wrapper detail
- `call_capability(...)` executes the wrapper through runtime and returns `kind == "wrapper_artifact"`

Use existing artifact helpers where possible. Do not duplicate entire run tests.

- [ ] **Step 4: Cover capability-backed draft bootstrap**

Call `create_draft_workspace_from_capability(...)` and assert:

```python
assert result["workspace_id"] == "echo_ws"
assert result["revision"] == 1
assert "wrapper_hints" in result
assert "next_actions" in result
```

Fetch the workspace through `WorkflowDraftApi` and assert the draft uses the
expected capability name.

- [ ] **Step 5: Cover handler delegation smoke**

Compare stable fields from handler and direct API for one method:

```python
handler_result = asyncio.run(handlers.inspect_capability(qualified_name=name))
api_result = asyncio.run(api.inspect_capability(qualified_name=name))
assert handler_result["name"] == api_result["name"]
assert handler_result["kind"] == api_result["kind"]
```

Do not duplicate every capability behavior test in both layers.

---

## Task 8: Verification

- [ ] **Step 1: Run focused capability tests**

```powershell
uv run pytest tests/wf_api/test_capability_api.py tests/wf_mcp/workflow_surface/test_capabilities.py -q
```

If `tests/wf_mcp/workflow_surface/test_capabilities.py` does not exist, run the
closest existing workflow-surface capability tests discovered by `rg -n "call_capability|inspect_capability|list_capabilities" tests/wf_mcp`.

Expected: pass.

- [ ] **Step 2: Run adjacent API tests**

```powershell
uv run pytest tests/wf_api/test_drafts_service.py tests/wf_api/test_artifact_api.py tests/wf_api/test_deployment_api.py tests/wf_api/test_run_api.py -q
```

Expected: pass.

- [ ] **Step 3: Run import-direction test**

```powershell
uv run pytest tests/wf_api/test_import_direction.py -q
```

Expected: pass; `wf_api` has no `wf_mcp` imports.

- [ ] **Step 4: Run ruff on touched files**

```powershell
uv run ruff check src/wf_api/capabilities.py src/wf_api/__init__.py src/wf_mcp/workflow_surface/handlers.py tests/wf_api/test_capability_api.py
```

Expected: all checks pass.

- [ ] **Step 5: Run basedpyright on touched files**

```powershell
uv run basedpyright --level error src/wf_api/capabilities.py src/wf_mcp/workflow_surface/handlers.py tests/wf_api/test_capability_api.py
```

Expected: `0 errors`.

- [ ] **Step 6: Optional full suite**

```powershell
uv run pytest -q
```

Expected: full suite passes with the project’s existing skipped/xfailed counts.

---

## Self-Review Checklist

- `wf_api.capabilities` imports no `wf_mcp`.
- `WorkflowSurfaceHandlers` public capability signatures are unchanged.
- `create_draft_workspace_from_capability` moved with capability inspection.
- Direct NodeSpec calls still work.
- Saved wrapper discovery and direct wrapper calls still work.
- Full saved workflows still require deployments.
- No public payload shape changed.
- No MCP schema changed.
- Handler is now mostly a thin compatibility adapter over `wf_api` domain services.

## Follow-Up Cleanup After 4E

After this slice lands, consider a cleanup plan to promote shared helpers:

```text
wf_api.runs._raw_plan_from_artifact        -> wf_api.artifact_plans.raw_plan_from_artifact
wf_api.capabilities._artifact_capability_id -> wf_api.artifact_refs.artifact_capability_id
wf_api.deployments._available_sources      -> wf_api.source_snapshots.available_sources_from_capability_sources
```

Do not do that cleanup inside 4E unless it is required to remove circular imports
or duplicate behavior bugs.
