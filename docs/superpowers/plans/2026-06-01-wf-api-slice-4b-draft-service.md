# wf_api Slice 4B: Draft Service Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move draft validation, draft workspace editing, and minimal draft bootstrapping out of `WorkflowSurfaceHandlers` into a protocol-neutral `wf_api.drafts.WorkflowDraftApi`.

**Architecture:** `WorkflowDraftApi` depends on `WorkflowOperationContext`, not `WfMcpService`. `WorkflowSurfaceHandlers` keeps the public method names and delegates the draft subset to `WorkflowDraftApi`. This is the first real method-body extraction, so the slice intentionally excludes methods that save artifacts, record events, or call `inspect_capability`.

**Tech Stack:** Python 3.14+, `wf_api.operation_context`, `wf_artifacts` draft helpers, `wf_core` path/binding models, pytest, ruff, basedpyright.

---

## Scope

### Move In This Slice

Move these methods from `WorkflowSurfaceHandlers` to `wf_api.drafts.WorkflowDraftApi`:

```text
validate_draft
compile_draft
patch_draft
list_draft_workspaces
create_draft_workspace
get_draft_workspace
delete_draft_workspace
validate_draft_workspace
patch_draft_workspace
set_draft_name
set_draft_route
set_step_input_map
set_step_output_map
create_minimal_draft_workspace
```

Move these draft-only helper functions to `wf_api.drafts`:

```text
_required_capabilities_for_plan
_required_capability_payloads
_observed_node_specs
_draft_input_maps
_draft_output_map
_draft_input_bindings_payload
_draft_output_bindings_payload
_graph_path_payload
_local_path_payload
_state_path_payload
_escape_json_pointer
```

### Do Not Move In This Slice

Do not move:

```text
create_draft_workspace_from_capability
create_artifact_from_draft
create_artifact_from_workspace
create_wrapper_from_workspace
```

Reasons:

- `create_draft_workspace_from_capability` depends on `inspect_capability`, which belongs to the capability domain. Move it later after the capability-inspection seam is explicit.
- artifact-from-draft/workspace methods save artifacts and record events. Move them with artifacts/deployments in Slice 4C.

Temporary duplication is allowed for private helper functions used by both
draft preview and artifact creation. If a helper still has live callers in
`WorkflowSurfaceHandlers` after draft delegation, keep the old copy until Slice
4C moves the artifact/deployment methods. Do not make `wf_api` import
`wf_mcp` just to avoid duplication.

### Invariants

- No public payload changes.
- No MCP tool schema changes.
- `WorkflowSurfaceHandlers` still exposes the same methods.
- `wf_api` imports no `wf_mcp`.
- Draft methods delegate through `WorkflowDraftApi`.

---

## Task 1: Create `wf_api.drafts`

**Files:**
- Create: `src/wf_api/drafts.py`

- [ ] **Step 1: Create `WorkflowDraftApi` skeleton**

Create `src/wf_api/drafts.py` with imports and class skeleton:

```python
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from wf_artifacts import (
    DraftWorkspaceStore,
    RequiredCapability,
    build_workflow_artifact_from_plan,
    compile_workflow_draft,
    create_draft_workspace as create_draft_workspace_record,
    get_draft_workspace as get_draft_workspace_record,
    patch_draft_workspace as patch_draft_workspace_record,
    patch_workflow_draft,
    validate_workflow_draft,
)
from wf_core.models.steps import (
    InputBinding,
    InputPathBinding,
    InputValueBinding,
    OutputBinding,
)
from wf_core.paths import GraphSourcePath, LocalPath, StatePath
from wf_platform import CapabilityRef, NodeSpecInventory

from .constants import (
    DEFAULT_CALL_STEP_ID,
    DEFAULT_ERROR_OUTCOME,
    DEFAULT_ERROR_STEP_ID,
    DEFAULT_OK_OUTCOME,
    RUNTIME_ERROR_CAPABILITY,
)
from .operation_context import WorkflowOperationContext


class WorkflowDraftApi:
    """Draft validation and workspace editing operations.

    This service deliberately excludes artifact persistence and capability
    inspection. Those domains still live in the MCP-backed handler until later
    extraction slices.
    """

    def __init__(self, context: WorkflowOperationContext) -> None:
        self.context = context
```

- [ ] **Step 2: Export the draft service**

Add `WorkflowDraftApi` to `src/wf_api/__init__.py` so future adapters can use
the canonical import path:

```python
from .drafts import WorkflowDraftApi
```

Also add `"WorkflowDraftApi"` to `__all__`.

- [ ] **Step 3: Add store helper**

Add:

```python
    def _draft_store(self) -> DraftWorkspaceStore:
        if self.context.draft_workspace_store is None:
            raise KeyError("draft workspace store is not configured")
        return self.context.draft_workspace_store
```

- [ ] **Step 4: Add outcome lookup helper**

Add:

```python
    def _outcomes_for_capability(self, qualified_name: str) -> tuple[str, ...] | None:
        try:
            spec = self.context.specs.get_qualified_spec(qualified_name)
        except KeyError:
            return None
        outcomes = getattr(spec, "outcomes", None)
        return tuple(outcomes) if outcomes is not None else None
```

---

## Task 2: Move Stateless Draft Methods

**Files:**
- Modify: `src/wf_api/drafts.py`

- [ ] **Step 1: Add `validate_draft`**

```python
    async def validate_draft(self, *, draft: dict[str, Any]) -> dict[str, Any]:
        return validate_workflow_draft(
            draft,
            outcome_lookup=self._outcomes_for_capability,
        )
```

- [ ] **Step 2: Add `compile_draft`**

```python
    async def compile_draft(self, *, draft: dict[str, Any]) -> dict[str, Any]:
        plan = compile_workflow_draft(draft)
        return {
            "compiled_plan": plan,
            "required_capabilities": _required_capability_payloads(
                _required_capabilities_for_plan(
                    plan,
                    source_bindings=None,
                    context=self.context,
                )
            ),
        }
```

- [ ] **Step 3: Add `patch_draft`**

```python
    async def patch_draft(
        self,
        *,
        draft: dict[str, Any],
        patch: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return patch_workflow_draft(draft, patch)
```

---

## Task 3: Move Draft Workspace Methods

**Files:**
- Modify: `src/wf_api/drafts.py`

- [ ] **Step 1: Add workspace CRUD and validation methods**

Move these method bodies exactly from `WorkflowSurfaceHandlers`, replacing
`self._draft_store()` with the new `WorkflowDraftApi._draft_store()`:

```text
list_draft_workspaces
create_draft_workspace
get_draft_workspace
delete_draft_workspace
validate_draft_workspace
patch_draft_workspace
```

Keep behavior and return payloads identical.

- [ ] **Step 2: Add patch convenience methods**

Move these method bodies exactly:

```text
set_draft_name
set_draft_route
set_step_input_map
set_step_output_map
```

They should call `self.patch_draft_workspace(...)` inside `WorkflowDraftApi`.

---

## Task 4: Move Minimal Draft Bootstrap

**Files:**
- Modify: `src/wf_api/drafts.py`

- [ ] **Step 1: Add `create_minimal_draft_workspace`**

Move `WorkflowSurfaceHandlers.create_minimal_draft_workspace` into
`WorkflowDraftApi` unchanged except:

- use `self._outcomes_for_capability(...)`
- use `self.create_draft_workspace(...)`
- keep the existing comments about provider-specific error envelopes

- [ ] **Step 2: Add helper functions**

Move these helper functions from `handlers.py` to the bottom of `wf_api.drafts`:

```text
_draft_input_maps
_draft_output_map
_draft_input_bindings_payload
_draft_output_bindings_payload
_graph_path_payload
_local_path_payload
_state_path_payload
_escape_json_pointer
```

Do not change their behavior.

---

## Task 5: Move Required-Capability Draft Helpers

**Files:**
- Modify: `src/wf_api/drafts.py`

- [ ] **Step 1: Move `_required_capabilities_for_plan`**

Move the helper from `handlers.py` and change its signature from:

```python
def _required_capabilities_for_plan(
    plan: dict[str, Any],
    *,
    source_bindings: dict[str, str] | None,
    service: WfMcpService,
) -> dict[str, RequiredCapability]:
```

to:

```python
def _required_capabilities_for_plan(
    plan: dict[str, Any],
    *,
    source_bindings: dict[str, str] | None,
    context: WorkflowOperationContext,
) -> dict[str, RequiredCapability]:
```

Inside it, call `_observed_node_specs(context)` instead of
`_observed_node_specs(service)`.

- [ ] **Step 2: Move `_observed_node_specs`**

Change its signature from:

```python
def _observed_node_specs(service: WfMcpService) -> dict[str, NodeSpecInventory]:
```

to:

```python
def _observed_node_specs(
    context: WorkflowOperationContext,
) -> dict[str, NodeSpecInventory]:
```

Loop over `context.capability_sources.values()`.

- [ ] **Step 3: Move `_required_capability_payloads`**

Move it unchanged.

---

## Task 6: Wire `WorkflowSurfaceHandlers` To Delegate Draft Methods

**Files:**
- Modify: `src/wf_mcp/workflow_surface/handlers.py`

- [ ] **Step 1: Add imports**

Add:

```python
from wf_api.drafts import WorkflowDraftApi
from wf_mcp.broker.service.workflow_operation_context import context_from_service
```

- [ ] **Step 2: Instantiate draft service**

In `WorkflowSurfaceHandlers.__init__`, add:

```python
self._drafts = WorkflowDraftApi(context_from_service(service))
```

- [ ] **Step 3: Replace moved method bodies with delegates**

For each moved method, keep the same signature and replace the body with a call
to `self._drafts`.

Example:

```python
async def validate_draft(self, *, draft: dict[str, Any]) -> dict[str, Any]:
    return await self._drafts.validate_draft(draft=draft)
```

Apply this pattern to every method in the Slice 4B move list.

- [ ] **Step 4: Remove moved helper functions from `handlers.py`**

Delete only helper functions that are no longer used in `handlers.py`:

```text
_draft_input_maps
_draft_output_map
_draft_input_bindings_payload
_draft_output_bindings_payload
_graph_path_payload
_local_path_payload
_state_path_payload
```

Keep `_escape_json_pointer` if `set_draft_route` delegation still needs no local use. Remove it only if no remaining references exist.

Do not remove from `handlers.py` yet unless `rg` proves there are no remaining
callers:

```text
_required_capabilities_for_plan
_required_capability_payloads
_observed_node_specs
```

Artifact creation currently still uses these helpers. It is acceptable for
`wf_api.drafts` and `handlers.py` to each have a copy until Slice 4C moves the
artifact/deployment methods. If the implementor can safely share them from
`wf_api` without creating an MCP import or changing behavior, that is allowed,
but not required for this slice.

---

## Task 7: Add Focused Tests

**Files:**
- Create: `tests/wf_api/test_drafts_service.py`

- [ ] **Step 1: Write direct service tests**

Create tests that build a `WfMcpService` through existing test helpers or
`load_cli_context`, adapt it with `context_from_service`, then instantiate
`WorkflowDraftApi`.

Cover:

- `patch_draft` applies a JSON patch.
- `create_draft_workspace` creates a workspace.
- `patch_draft_workspace` updates revision.
- `validate_draft_workspace` refreshes status.
- `create_minimal_draft_workspace` returns the same shape as before for a simple `wf.std` capability or a registered test spec.

- [ ] **Step 2: Add delegation smoke test**

In an existing workflow-surface draft test file or a new focused test, assert
that `WorkflowSurfaceHandlers.validate_draft(...)` and
`WorkflowDraftApi.validate_draft(...)` return equivalent status/diagnostics for
the same draft.

Do not assert entire dict equality; compare stable fields individually.

---

## Task 8: Verification

- [ ] **Step 1: Run draft tests**

```powershell
uv run pytest tests/wf_api/test_drafts_service.py tests/wf_mcp/workflow_surface/test_drafts.py -q
```

Expected: all pass.

- [ ] **Step 2: Run MCP schema/config tests**

```powershell
uv run pytest tests/wf_mcp/server/test_config.py tests/wf_mcp/workflow_surface -q
```

Expected: all pass.

- [ ] **Step 3: Run ruff on touched files**

```powershell
uv run ruff check src/wf_api/drafts.py src/wf_mcp/workflow_surface/handlers.py tests/wf_api/test_drafts_service.py
```

Expected: all checks pass.

- [ ] **Step 4: Run basedpyright on touched files**

```powershell
uv run basedpyright --level error src/wf_api/drafts.py src/wf_mcp/workflow_surface/handlers.py tests/wf_api/test_drafts_service.py
```

Expected: `0 errors`.

- [ ] **Step 5: Optional full suite**

```powershell
uv run pytest -q
```

Expected: full suite passes with the project’s existing skipped/xfailed counts.

---

## Self-Review Checklist

- `wf_api.drafts` imports no `wf_mcp`.
- `WorkflowSurfaceHandlers` public draft method signatures are unchanged.
- Moved methods delegate through `WorkflowDraftApi`.
- `create_draft_workspace_from_capability` remains in handlers.
- artifact-saving methods remain in handlers.
- No public payload shape changed.
- No MCP schema changed.
- No new dependency on the whole `WfMcpService` inside `wf_api`.
