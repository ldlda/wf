# wf_api Slice 4C: Artifacts And Deployments Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move saved artifact and deployment operations out of `WorkflowSurfaceHandlers` into protocol-neutral `wf_api` domain services.

**Architecture:** Add `WorkflowArtifactApi` and `WorkflowDeploymentApi` that depend on `WorkflowOperationContext`, not `WfMcpService`. Keep `WorkflowSurfaceHandlers` public method signatures unchanged and delegate artifact/deployment methods to the new services. Extend operation-context protocols for event emission and live source checks so `wf_api` does not import MCP event factories, adapters, auth, or connections.

**Tech Stack:** Python 3.14+, `wf_api.operation_context`, `wf_api.drafts`, `wf_artifacts`, `wf_platform`, `wf_core`, pytest, ruff, basedpyright.

---

## Scope

### Move In This Slice

Move these methods from `WorkflowSurfaceHandlers`:

```text
list_artifacts
save_artifact
create_artifact_from_plan
create_artifact_from_draft
create_artifact_from_workspace
create_wrapper_from_workspace
inspect_artifact
list_deployments
inspect_deployment
save_deployment
delete_deployment
validate_deployment
```

Move or duplicate only the helpers required by those methods:

```text
_available_sources
_suggested_self_bindings
_observed_node_specs
_capability_name
_artifact_capability_id
_deployment_summary
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
run_deployment
resume_run
inspect_run
read_run_trace
_raw_plan_from_artifact
_run_payload
_interrupt_payload
```

Reasons:

- Capability methods still combine live source specs, saved wrappers, and direct test calls. Move them in Slice 4E.
- Run methods depend on durable run checkpoints, runtime preparation, trace slicing, and saved subgraph execution. Move them in Slice 4D.
- `_raw_plan_from_artifact` is still needed by wrapper capability calls and run methods. Leave it in `handlers.py` until those domains move or extract it separately.

### Invariants

- No public payload changes.
- No MCP tool schema changes.
- `WorkflowSurfaceHandlers` still exposes the same methods.
- `wf_api` imports no `wf_mcp`.
- Event construction stays adapter-owned.
- Live upstream checks stay adapter-owned.
- Temporary private helper duplication is allowed when capability/run methods still need a helper in `handlers.py`.

---

## Task 1: Extend Operation Context For Events And Live Checks

**Files:**

- Modify: `src/wf_api/operation_context.py`
- Create: `src/wf_mcp/broker/service/workflow_live_checks.py`
- Modify: `src/wf_mcp/broker/service/workflow_operation_context.py`
- Modify: `src/wf_mcp/workflow_surface/handlers.py`
- Test: `tests/wf_api/test_operation_context.py`

- [ ] **Step 1: Add protocol methods**

In `src/wf_api/operation_context.py`, update `WorkflowEventRecorder`:

```python
class WorkflowEventRecorder(Protocol):
    """Records workflow lifecycle events without exposing MCP event types."""

    def record_event(self, event: object) -> None:
        """Record one adapter-native event object."""
        ...

    def record_workflow_event(
        self,
        event_type: str,
        *,
        capability_id: str,
        payload: dict[str, Any],
    ) -> None:
        """Record one workflow lifecycle event by protocol-neutral fields."""
        ...
```

Update `WorkflowLiveSourceChecker`:

```python
class WorkflowLiveSourceChecker(Protocol):
    """Optional hook for validating live external source availability."""

    async def deployment_diagnostics(
        self,
        *,
        deployment: WorkflowDeployment,
        artifacts: Sequence[WorkflowArtifact],
    ) -> list[DependencyDiagnostic]:
        """Return opt-in live-source diagnostics for a deployment tree."""
        ...
```

Add imports:

```python
from collections.abc import Mapping, Sequence
from wf_artifacts import DependencyDiagnostic, WorkflowDeployment
```

Remove or keep `available_sources()` only if still used by tests. New moved code should use `deployment_diagnostics(...)`.

- [ ] **Step 2: Move MCP live-check helper out of handlers**

Create `src/wf_mcp/broker/service/workflow_live_checks.py` and move these
handler-level live-check pieces into it:

```text
LIVE_SOURCE_CHECK_TIMEOUT_SECONDS
_LIVE_SOURCE_CHECK_FAILURES
live_source_diagnostics
_required_live_sources
```

Rename `_live_source_diagnostics(...)` to public module-private-adapter helper
`live_source_diagnostics(...)`.

The new module should own the MCP-only imports:

```python
import asyncio

import anyio
import httpx
from mcp.client.streamable_http import StreamableHTTPError
from mcp.shared.exceptions import McpError

from wf_artifacts import DependencyDiagnostic, DiagnosticSeverity, WorkflowArtifact, WorkflowDeployment
from wf_mcp.broker.service.adapters import require_adapter
from wf_mcp.broker.service.core import WfMcpService
```

Keep the existing docstring explaining that live checks perform opt-in upstream
I/O. This split is required to avoid a circular import:

```text
handlers.py -> workflow_operation_context.py -> handlers.py
```

After the move, update `handlers.py` to import `live_source_diagnostics` from
the new module for as long as `validate_deployment` still lives in handlers.
When Task 4 delegates `validate_deployment`, remove that handler import if it
is unused.

- [ ] **Step 3: Implement MCP adapter methods**

In `src/wf_mcp/broker/service/workflow_operation_context.py`, import:

```python
from collections.abc import Sequence

from wf_artifacts import DependencyDiagnostic, WorkflowArtifact, WorkflowDeployment
from wf_mcp.events import make_event
from wf_mcp.broker.service.workflow_live_checks import live_source_diagnostics
```

Then update event recorder:

```python
def record_workflow_event(
    self,
    event_type: str,
    *,
    capability_id: str,
    payload: dict[str, Any],
) -> None:
    self.service._record_event(  # noqa: SLF001
        make_event(event_type, capability_id=capability_id, payload=payload)
    )
```

Update live source checker:

```python
async def deployment_diagnostics(
    self,
    *,
    deployment: WorkflowDeployment,
    artifacts: Sequence[WorkflowArtifact],
) -> list[DependencyDiagnostic]:
    return await live_source_diagnostics(
        self.service,
        deployment=deployment,
        artifacts=artifacts,
    )
```

Do not import handler modules from `workflow_operation_context.py`.

- [ ] **Step 4: Update operation context tests**

In `tests/wf_api/test_operation_context.py`, add a test that calls:

```python
operation_context.events.record_workflow_event(
    "workflow_artifact_saved",
    capability_id="workflow.demo.v1",
    payload={"artifact_id": "demo", "version": 1},
)
```

Then assert the service recorded an event with stable fields individually. Do not assert full dict equality.

- [ ] **Step 5: Run focused tests**

```powershell
uv run pytest tests/wf_api/test_operation_context.py -q
```

Expected: pass.

---

## Task 2: Create `wf_api.artifacts`

**Files:**

- Create: `src/wf_api/artifacts.py`
- Modify: `src/wf_api/__init__.py`
- Test: `tests/wf_api/test_artifact_api.py`

- [ ] **Step 1: Create service skeleton**

Create `src/wf_api/artifacts.py`:

```python
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from wf_artifacts import (
    ArtifactKind,
    RequiredCapability,
    WorkflowArtifact,
    create_workflow_artifact_from_plan as build_workflow_artifact_from_plan,
)
from wf_platform import CapabilityRef, NodeSpecInventory

from .drafts import WorkflowDraftApi
from .models import RawWorkflowPlan
from .operation_context import WorkflowOperationContext


class WorkflowArtifactApi:
    """Saved workflow artifact operations.

    Event construction is intentionally delegated through
    WorkflowOperationContext so this module stays protocol-neutral.
    """

    def __init__(self, context: WorkflowOperationContext) -> None:
        self.context = context
        self.drafts = WorkflowDraftApi(context)

    def _artifact_store(self):
        if self.context.artifact_store is None:
            raise KeyError("workflow artifact store is not configured")
        return self.context.artifact_store
```

- [ ] **Step 2: Move artifact methods**

Move these bodies from `WorkflowSurfaceHandlers`, replacing `self.service` access:

```text
list_artifacts
save_artifact
create_artifact_from_plan
create_artifact_from_draft
inspect_artifact
```

Required replacements:

```python
self.service.artifact_store -> self._artifact_store()
self.service.workflow_artifact_catalog_entry(artifact) -> self.context.artifacts.workflow_artifact_catalog_entry(artifact)
self.service._record_event(make_event(...)) -> self.context.events.record_workflow_event(...)
_observed_node_specs(self.service) -> _observed_node_specs(self.context)
```

Keep return payloads byte-for-byte equivalent except for dictionary ordering.

- [ ] **Step 3: Move workspace artifact methods**

Move:

```text
create_artifact_from_workspace
create_wrapper_from_workspace
```

Use `self.context.draft_workspace_store` through `self.drafts` or a local store helper. Preserve current behavior:

- validate workspace draft first
- return `saved: False` with diagnostics when invalid
- call `create_artifact_from_draft(...)` when valid
- wrapper path passes `kind="wrapper"`

- [ ] **Step 4: Add helpers**

Add private helpers to `wf_api.artifacts`:

```text
_required_capability_payloads
_suggested_self_bindings
_observed_node_specs
_plan_nodes
_artifact_capability_id
```

Duplicate `_required_capability_payloads`, `_observed_node_specs`, and `_plan_nodes` from `wf_api.drafts` for now instead of importing private draft helpers. We can consolidate after Slice 4C if duplication becomes annoying.

Do not remove `_artifact_capability_id` from `handlers.py`; wrapper capability methods still need it until Slice 4E.

- [ ] **Step 5: Export artifact service**

In `src/wf_api/__init__.py`:

```python
from .artifacts import WorkflowArtifactApi
```

Add `"WorkflowArtifactApi"` to `__all__`.

- [ ] **Step 6: Add focused tests**

Create `tests/wf_api/test_artifact_api.py` with tests that instantiate `WorkflowArtifactApi(context_from_service(service))`:

- `save_artifact` stores a `WorkflowArtifact` and returns `saved: True`.
- `create_artifact_from_plan` saves an artifact and includes observed node specs.
- `create_artifact_from_workspace` returns `saved: False` when workspace validation fails.
- `create_wrapper_from_workspace` saves `kind == "wrapper"`.
- Handler delegation for `inspect_artifact` returns the same stable fields as direct `WorkflowArtifactApi.inspect_artifact`.

Use field-by-field assertions unless asserting a known closed model shape.

- [ ] **Step 7: Run artifact tests**

```powershell
uv run pytest tests/wf_api/test_artifact_api.py tests/wf_api/test_drafts_service.py -q
```

Expected: pass.

---

## Task 3: Create `wf_api.deployments`

**Files:**

- Create: `src/wf_api/deployments.py`
- Modify: `src/wf_api/__init__.py`
- Test: `tests/wf_api/test_deployment_api.py`

- [ ] **Step 1: Create service skeleton**

Create `src/wf_api/deployments.py`:

```python
from __future__ import annotations

from typing import Any

from wf_artifacts import (
    AvailableCapability,
    AvailableSource,
    DependencyDiagnostic,
    WorkflowArtifact,
    WorkflowDeployment,
    hash_json_schema,
    validate_deployment_dependencies,
)
from wf_platform import CapabilitySource

from .next_actions import NextActions
from .operation_context import WorkflowOperationContext
from .saved_subgraphs import resolve_saved_subgraph_tree, validate_saved_subgraph_tree


class WorkflowDeploymentApi:
    """Saved deployment operations and dependency validation."""

    def __init__(self, context: WorkflowOperationContext) -> None:
        self.context = context

    def _artifact_store(self):
        if self.context.artifact_store is None:
            raise KeyError("workflow artifact store is not configured")
        return self.context.artifact_store
```

- [ ] **Step 2: Move deployment methods**

Move these bodies from `WorkflowSurfaceHandlers`:

```text
list_deployments
inspect_deployment
save_deployment
delete_deployment
validate_deployment
```

Required replacements:

```python
self.service.artifact_store -> self._artifact_store()
self.service._record_event(make_event(...)) -> self.context.events.record_workflow_event(...)
_available_sources(self.service) -> _available_sources(self.context.capability_sources)
```

For `validate_deployment(live_check=True)`, use:

```python
if live_check and self.context.live_sources is not None:
    diagnostics.extend(
        await self.context.live_sources.deployment_diagnostics(
            deployment=deployment,
            artifacts=[artifact, *tree.artifacts_by_ref.values()],
        )
    )
```

If `live_check=True` and `live_sources is None`, preserve static validation only. Do not invent a new warning payload in this slice.

- [ ] **Step 3: Move deployment validation helper**

Move `_deployment_validation` logic into `WorkflowDeploymentApi` as a private method:

```python
def _deployment_validation(
    self,
    deployment_id: str,
) -> tuple[WorkflowDeployment, WorkflowArtifact, list[DependencyDiagnostic], SavedSubgraphTree]:
    ...
```

Use `self._artifact_store()` and `_available_sources(self.context.capability_sources)`.

- [ ] **Step 4: Add helper functions**

Add private helpers:

```text
_available_sources
_capability_name
_deployment_summary
```

Adapt `_available_sources` to accept `Mapping[str, CapabilitySource]` instead of `WfMcpService`.

Do not remove `_available_sources` or `_capability_name` from `handlers.py` if run/capability methods still use them.

- [ ] **Step 5: Export deployment service**

In `src/wf_api/__init__.py`:

```python
from .deployments import WorkflowDeploymentApi
```

Add `"WorkflowDeploymentApi"` to `__all__`.

- [ ] **Step 6: Add focused tests**

Create `tests/wf_api/test_deployment_api.py` with tests that instantiate `WorkflowDeploymentApi(context_from_service(service))`:

- `save_deployment` stores and returns stable deployment fields.
- `list_deployments` returns compact summaries.
- `delete_deployment` removes one deployment.
- `validate_deployment(live_check=False)` returns `runnable` for a valid binding.
- `validate_deployment(live_check=True)` calls the operation-context live checker. A simple fake context may be easier than MCP service setup for this test.
- Handler delegation for `validate_deployment` returns the same stable status/diagnostic fields as direct `WorkflowDeploymentApi.validate_deployment`.

- [ ] **Step 7: Run deployment tests**

```powershell
uv run pytest tests/wf_api/test_deployment_api.py tests/wf_mcp/workflow_surface/test_deployments.py -q
```

Expected: pass.

---

## Task 4: Wire `WorkflowSurfaceHandlers`

**Files:**

- Modify: `src/wf_mcp/workflow_surface/handlers.py`

- [ ] **Step 1: Add imports**

```python
from wf_api.artifacts import WorkflowArtifactApi
from wf_api.deployments import WorkflowDeploymentApi
```

- [ ] **Step 2: Instantiate services**

In `WorkflowSurfaceHandlers.__init__`, avoid building multiple independent contexts:

```python
context = context_from_service(service)
self._drafts = WorkflowDraftApi(context)
self._artifacts = WorkflowArtifactApi(context)
self._deployments = WorkflowDeploymentApi(context)
```

- [ ] **Step 3: Replace moved artifact methods with delegates**

Replace bodies for:

```text
list_artifacts
save_artifact
create_artifact_from_plan
create_artifact_from_draft
create_artifact_from_workspace
create_wrapper_from_workspace
inspect_artifact
```

Example:

```python
async def inspect_artifact(self, *, artifact_id: str, version: int) -> dict[str, Any]:
    return await self._artifacts.inspect_artifact(
        artifact_id=artifact_id,
        version=version,
    )
```

- [ ] **Step 4: Replace moved deployment methods with delegates**

Replace bodies for:

```text
list_deployments
inspect_deployment
save_deployment
delete_deployment
validate_deployment
```

Example:

```python
async def validate_deployment(
    self,
    *,
    deployment_id: str,
    live_check: bool = False,
) -> dict[str, Any]:
    return await self._deployments.validate_deployment(
        deployment_id=deployment_id,
        live_check=live_check,
    )
```

- [ ] **Step 5: Remove only unused imports/helpers**

After delegation, run:

```powershell
rg -n "_available_sources|_suggested_self_bindings|_observed_node_specs|_deployment_summary|_artifact_capability_id|_capability_name" src/wf_mcp/workflow_surface/handlers.py
```

Remove a helper from `handlers.py` only if it has no remaining caller there.

Expected likely result:

- `_suggested_self_bindings`, `_observed_node_specs`, `_deployment_summary` can probably be removed.
- `_artifact_capability_id`, `_capability_name`, `_available_sources` may still be needed by capability/run methods. Keep them if referenced.

---

## Task 5: Verification

- [ ] **Step 1: Run focused wf_api tests**

```powershell
uv run pytest tests/wf_api/test_artifact_api.py tests/wf_api/test_deployment_api.py tests/wf_api/test_drafts_service.py -q
```

Expected: pass.

- [ ] **Step 2: Run workflow surface tests**

```powershell
uv run pytest tests/wf_mcp/workflow_surface -q
```

Expected: pass.

- [ ] **Step 3: Run import-direction test**

```powershell
uv run pytest tests/wf_api/test_import_direction.py -q
```

Expected: pass; `wf_api` has no `wf_mcp` imports.

- [ ] **Step 4: Run ruff on touched files**

```powershell
uv run ruff check src/wf_api/artifacts.py src/wf_api/deployments.py src/wf_api/operation_context.py src/wf_api/__init__.py src/wf_mcp/broker/service/workflow_operation_context.py src/wf_mcp/workflow_surface/handlers.py tests/wf_api/test_artifact_api.py tests/wf_api/test_deployment_api.py
```

Expected: all checks pass.

- [ ] **Step 5: Run basedpyright on touched files**

```powershell
uv run basedpyright --level error src/wf_api/artifacts.py src/wf_api/deployments.py src/wf_api/operation_context.py src/wf_mcp/broker/service/workflow_operation_context.py src/wf_mcp/workflow_surface/handlers.py tests/wf_api/test_artifact_api.py tests/wf_api/test_deployment_api.py
```

Expected: `0 errors`.

- [ ] **Step 6: Optional full suite**

```powershell
uv run pytest -q
```

Expected: full suite passes with the project’s existing skipped/xfailed counts.

---

## Self-Review Checklist

- `wf_api.artifacts` imports no `wf_mcp`.
- `wf_api.deployments` imports no `wf_mcp`.
- Event construction remains in `wf_mcp.broker.service.workflow_operation_context`.
- Live upstream adapter/auth probing remains in `wf_mcp`.
- `WorkflowSurfaceHandlers` public artifact/deployment method signatures are unchanged.
- `create_draft_workspace_from_capability` still lives in `WorkflowSurfaceHandlers`.
- Capability methods still live in `WorkflowSurfaceHandlers`.
- Run methods still live in `WorkflowSurfaceHandlers`.
- No public payload shape changed.
- No MCP schema changed.
- Temporary helper duplication is documented and deliberate.
