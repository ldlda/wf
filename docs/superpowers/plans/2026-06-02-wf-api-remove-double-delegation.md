# wf_api Remove Double Delegation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Collapse workflow calls from `WorkflowApi -> WfMcpWorkflowApiBackend -> WorkflowSurfaceHandlers -> domain services` to `WorkflowApi -> domain services`.

**Architecture:** `WorkflowApi` becomes the protocol-neutral application facade that composes `WorkflowCapabilityApi`, `WorkflowDraftApi`, `WorkflowArtifactApi`, `WorkflowDeploymentApi`, and `WorkflowRunApi` from a `WorkflowOperationContext`. MCP and CLI construct `WorkflowApi(context_from_service(service))` directly. `WorkflowSurfaceHandlers` remains only as a temporary compatibility shim for legacy imports/tests, and `WfMcpWorkflowApiBackend` / `WorkflowApiBackend` are removed.

**Tech Stack:** Python 3.14, `wf_api`, `wf_mcp`, dataclasses, pytest, ruff, basedpyright.

---

## Current Chain

```text
wf_mcp tools / wf_cli
  -> WorkflowApi
  -> WfMcpWorkflowApiBackend
  -> WorkflowSurfaceHandlers
  -> WorkflowCapabilityApi / WorkflowDraftApi / WorkflowArtifactApi / WorkflowDeploymentApi / WorkflowRunApi
```

This creates two mechanical delegation layers. Adding one workflow operation currently requires touching at least `WorkflowApi`, `WorkflowApiBackend`, `WfMcpWorkflowApiBackend`, and usually `WorkflowSurfaceHandlers`.

## Target Chain

```text
wf_mcp tools / wf_cli
  -> WorkflowApi
  -> WorkflowCapabilityApi / WorkflowDraftApi / WorkflowArtifactApi / WorkflowDeploymentApi / WorkflowRunApi
```

Legacy imports of `WorkflowSurfaceHandlers` may still work, but only as a thin wrapper around `WorkflowApi`.

## Files

- Modify: `src/wf_api/models.py`
- Modify: `src/wf_api/__init__.py`
- Modify: `src/wf_api/service.py`
- Delete: `src/wf_api/backend.py`
- Delete: `src/wf_mcp/broker/service/workflow_api_backend.py`
- Modify: `src/wf_cli/context.py`
- Modify: `src/wf_cli/commands/runs.py`
- Modify: `src/wf_mcp/workflow_surface/tools.py`
- Modify: `src/wf_mcp/workflow_surface/handlers.py`
- Modify: `tests/wf_cli/test_context.py`
- Modify: `tests/wf_api/test_cli_context_uses_api.py`
- Add: `tests/wf_api/test_direct_service.py`
- Add: `tests/wf_api/test_no_double_delegation.py`
- Modify docs: `docs/current_roadmap.md`, `docs/wf_mcp_architecture.md`, `docs/superpowers/plans/2026-06-01-wf-api-extraction-roadmap.md`

---

### Task 1: Move TraceRange Out of `backend.py`

**Files:**
- Modify: `src/wf_api/models.py`
- Modify: `src/wf_api/__init__.py`
- Modify: `src/wf_cli/commands/runs.py`
- Modify: `src/wf_mcp/workflow_surface/tools.py`

- [ ] **Step 1: Write import regression test**

Add to `tests/wf_api/test_raw_workflow_plan_extraction.py`:

```python
def test_trace_range_exports_from_wf_api_models() -> None:
    from wf_api import TraceRange
    from wf_api.models import TraceRange as CanonicalTraceRange

    assert TraceRange is CanonicalTraceRange
    assert TraceRange(start=1, limit=2).start == 1
    assert TraceRange(start=1, limit=2).limit == 2
```

- [ ] **Step 2: Run failing test**

Run:

```bash
uv run pytest tests\wf_api\test_raw_workflow_plan_extraction.py::test_trace_range_exports_from_wf_api_models -q
```

Expected: fail because `wf_api.models.TraceRange` does not exist yet.

- [ ] **Step 3: Add `TraceRange` to `wf_api.models`**

In `src/wf_api/models.py`, add imports:

```python
from dataclasses import dataclass
```

Then add before `RawWorkflowPlan`:

```python
@dataclass(frozen=True, slots=True)
class TraceRange:
    """Caller-bounded debug trace slice for durable deployment runs."""

    start: int = 0
    limit: int = 25
```

- [ ] **Step 4: Update `wf_api.__init__` export**

Change:

```python
from .backend import TraceRange, WorkflowApiBackend
```

to:

```python
from .models import RawWorkflowPlan, TraceRange
```

Remove `"WorkflowApiBackend"` from `__all__`. Keep `"TraceRange"`.

If `RawWorkflowPlan` was not exported before, include it only if already expected by tests; do not add new public API unless the existing file already imports it elsewhere.

- [ ] **Step 5: Update imports that referenced `wf_api.backend.TraceRange`**

In `src/wf_cli/commands/runs.py`, replace:

```python
from wf_api.backend import TraceRange
```

with:

```python
from wf_api import TraceRange
```

In `src/wf_mcp/workflow_surface/tools.py`, remove:

```python
from wf_api.backend import TraceRange as ApiTraceRange
```

Also remove `_to_api_trace_range()`. Later tasks pass MCP `TraceRange` directly because `WorkflowRunApi` validates trace ranges structurally through `TraceRangeLike`.

- [ ] **Step 6: Verify Task 1**

Run:

```bash
uv run pytest tests\wf_api\test_raw_workflow_plan_extraction.py::test_trace_range_exports_from_wf_api_models tests\wf_cli\test_run_deploy.py tests\wf_mcp\server\test_tools.py -q
uv run ruff check src\wf_api\models.py src\wf_api\__init__.py src\wf_cli\commands\runs.py src\wf_mcp\workflow_surface\tools.py tests\wf_api\test_raw_workflow_plan_extraction.py
uv run ruff format --check src\wf_api\models.py src\wf_api\__init__.py src\wf_cli\commands\runs.py src\wf_mcp\workflow_surface\tools.py tests\wf_api\test_raw_workflow_plan_extraction.py
```

Expected: tests pass, lint pass, format pass.

---

### Task 2: Make `WorkflowApi` Compose Domain Services Directly

**Files:**
- Modify: `src/wf_api/service.py`
- Add: `tests/wf_api/test_direct_service.py`

- [ ] **Step 1: Write direct-composition tests**

Create `tests/wf_api/test_direct_service.py`:

```python
from __future__ import annotations

import asyncio

from wf_artifacts import FileWorkflowArtifactStore
from wf_api import WorkflowApi
from wf_api.artifacts import WorkflowArtifactApi
from wf_api.capabilities import WorkflowCapabilityApi
from wf_api.deployments import WorkflowDeploymentApi
from wf_api.drafts import WorkflowDraftApi
from wf_api.runs import WorkflowRunApi
from wf_mcp.broker import WfMcpService
from wf_mcp.broker.service.workflow_operation_context import context_from_service
from wf_mcp.models import ConnectionConfig
from wf_mcp.storage import FileStore

from tests.wf_mcp.test_support import echo_tool, local_temp_root


def _api() -> WorkflowApi:
    root = local_temp_root() / "wf_api_direct_composition"
    service = WfMcpService(
        store=FileStore(root / "mcp"),
        artifact_store=FileWorkflowArtifactStore(root),
    )
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_specs("demo.personal", echo_tool)
    return WorkflowApi(context_from_service(service))


def test_workflow_api_composes_domain_services() -> None:
    api = _api()

    assert isinstance(api.capabilities, WorkflowCapabilityApi)
    assert isinstance(api.drafts, WorkflowDraftApi)
    assert isinstance(api.artifacts, WorkflowArtifactApi)
    assert isinstance(api.deployments, WorkflowDeploymentApi)
    assert isinstance(api.runs, WorkflowRunApi)
    assert not hasattr(api, "backend")


def test_workflow_api_direct_capability_call() -> None:
    api = _api()

    result = asyncio.run(
        api.call_capability(
            qualified_name="demo.personal.echo_tool",
            payload={"text": "hello"},
        )
    )

    assert result["kind"] == "node_spec"
    assert result["outcome"] == "ok"
    assert result["output"] == {"echoed": "hello"}
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
uv run pytest tests\wf_api\test_direct_service.py -q
```

Expected: fail because `WorkflowApi` still expects a `WorkflowApiBackend`.

- [ ] **Step 3: Rewrite `WorkflowApi.__init__`**

In `src/wf_api/service.py`, replace:

```python
from .backend import TraceRange, WorkflowApiBackend
```

with:

```python
from .artifacts import WorkflowArtifactApi
from .capabilities import WorkflowCapabilityApi
from .deployments import WorkflowDeploymentApi
from .drafts import WorkflowDraftApi
from .models import TraceRange
from .operation_context import WorkflowOperationContext
from .runs import TraceRangeLike, WorkflowRunApi
```

Replace the class docstring and constructor:

```python
class WorkflowApi:
    """Protocol-neutral workflow application facade.

    This facade owns the stable application entry point. It composes the
    domain APIs from a WorkflowOperationContext so MCP, CLI, and future HTTP
    callers share one operation surface without importing wf_mcp.
    """

    def __init__(self, context: WorkflowOperationContext) -> None:
        self.context = context
        self.capabilities = WorkflowCapabilityApi(context)
        self.drafts = WorkflowDraftApi(context)
        self.artifacts = WorkflowArtifactApi(context)
        self.deployments = WorkflowDeploymentApi(context)
        self.runs = WorkflowRunApi(context)
```

- [ ] **Step 4: Replace backend delegations with domain service delegations**

In `src/wf_api/service.py`, replace these groups:

Capabilities:

```python
self.backend.list_capabilities(...) -> self.capabilities.list_capabilities(...)
self.backend.inspect_capability(...) -> self.capabilities.inspect_capability(...)
self.backend.call_capability(...) -> self.capabilities.call_capability(...)
self.backend.create_draft_workspace_from_capability(...) -> self.capabilities.create_draft_workspace_from_capability(...)
```

Artifacts:

```python
self.backend.list_artifacts(...) -> self.artifacts.list_artifacts(...)
self.backend.inspect_artifact(...) -> self.artifacts.inspect_artifact(...)
self.backend.save_artifact(...) -> self.artifacts.save_artifact(...)
self.backend.create_artifact_from_plan(...) -> self.artifacts.create_artifact_from_plan(...)
self.backend.create_artifact_from_draft(...) -> self.artifacts.create_artifact_from_draft(...)
self.backend.create_artifact_from_workspace(...) -> self.artifacts.create_artifact_from_workspace(...)
self.backend.create_wrapper_from_workspace(...) -> self.artifacts.create_wrapper_from_workspace(...)
```

Drafts:

```python
self.backend.validate_draft(...) -> self.drafts.validate_draft(...)
self.backend.compile_draft(...) -> self.drafts.compile_draft(...)
self.backend.patch_draft(...) -> self.drafts.patch_draft(...)
self.backend.list_draft_workspaces() -> self.drafts.list_draft_workspaces()
self.backend.create_draft_workspace(...) -> self.drafts.create_draft_workspace(...)
self.backend.get_draft_workspace(...) -> self.drafts.get_draft_workspace(...)
self.backend.delete_draft_workspace(...) -> self.drafts.delete_draft_workspace(...)
self.backend.validate_draft_workspace(...) -> self.drafts.validate_draft_workspace(...)
self.backend.patch_draft_workspace(...) -> self.drafts.patch_draft_workspace(...)
self.backend.set_draft_name(...) -> self.drafts.set_draft_name(...)
self.backend.set_draft_route(...) -> self.drafts.set_draft_route(...)
self.backend.set_step_input_map(...) -> self.drafts.set_step_input_map(...)
self.backend.set_step_output_map(...) -> self.drafts.set_step_output_map(...)
self.backend.create_minimal_draft_workspace(...) -> self.drafts.create_minimal_draft_workspace(...)
```

Deployments:

```python
self.backend.list_deployments() -> self.deployments.list_deployments()
self.backend.inspect_deployment(...) -> self.deployments.inspect_deployment(...)
self.backend.save_deployment(...) -> self.deployments.save_deployment(...)
self.backend.delete_deployment(...) -> self.deployments.delete_deployment(...)
self.backend.validate_deployment(...) -> self.deployments.validate_deployment(...)
```

Runs:

```python
self.backend.run_deployment(...) -> self.runs.run_deployment(...)
self.backend.resume_run(...) -> self.runs.resume_run(...)
self.backend.inspect_run(...) -> self.runs.inspect_run(...)
self.backend.read_run_trace(...) -> self.runs.read_run_trace(...)
```

For run methods, change type hints from `TraceRange | None` to `TraceRangeLike | None` and `TraceRange` to `TraceRangeLike` so MCP Pydantic `TraceRange` and CLI dataclass `TraceRange` both remain accepted structurally.

- [ ] **Step 5: Verify Task 2**

Run:

```bash
uv run pytest tests\wf_api\test_direct_service.py tests\wf_api\test_capability_api.py tests\wf_api\test_drafts_service.py tests\wf_api\test_artifact_api.py tests\wf_api\test_deployment_api.py tests\wf_api\test_run_api.py -q
uv run ruff check src\wf_api\service.py tests\wf_api\test_direct_service.py
uv run ruff format --check src\wf_api\service.py tests\wf_api\test_direct_service.py
```

Expected: direct service tests and domain API tests pass.

---

### Task 3: Update CLI and MCP Tool Construction

**Files:**
- Modify: `src/wf_cli/context.py`
- Modify: `tests/wf_cli/test_context.py`
- Modify: `src/wf_mcp/workflow_surface/tools.py`
- Add: `tests/wf_api/test_no_double_delegation.py`

- [ ] **Step 1: Write no-backend-chain test**

Create `tests/wf_api/test_no_double_delegation.py`:

```python
from __future__ import annotations

import ast
from pathlib import Path


def _imports_module(path: Path, module_name: str) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == module_name:
            return True
        if isinstance(node, ast.Import):
            if any(alias.name == module_name for alias in node.names):
                return True
    return False


def test_cli_and_mcp_tools_do_not_import_backend_adapter() -> None:
    root = Path(__file__).resolve().parents[2]

    assert not _imports_module(
        root / "src" / "wf_cli" / "context.py",
        "wf_mcp.broker.service.workflow_api_backend",
    )
    assert not _imports_module(
        root / "src" / "wf_mcp" / "workflow_surface" / "tools.py",
        "wf_mcp.broker.service.workflow_api_backend",
    )
```

- [ ] **Step 2: Run failing no-backend-chain test**

Run:

```bash
uv run pytest tests\wf_api\test_no_double_delegation.py -q
```

Expected: fail because CLI context and MCP tools still import `WfMcpWorkflowApiBackend`.

- [ ] **Step 3: Update CLI context**

In `src/wf_cli/context.py`, remove:

```python
from wf_mcp.broker.service.workflow_api_backend import WfMcpWorkflowApiBackend
```

Add:

```python
from wf_mcp.broker.service.workflow_operation_context import context_from_service
```

Change `load_cli_context()`:

```python
handlers=WorkflowApi(context_from_service(service)),
```

- [ ] **Step 4: Update CLI context test**

In `tests/wf_cli/test_context.py`, replace the private backend-chain assertion:

```python
assert context.handlers.backend._handlers.service is context.service  # type: ignore[attr-defined]
```

with:

```python
assert context.handlers.context.artifact_store is context.service.artifact_store
assert context.handlers.context.draft_workspace_store is context.service.draft_workspace_store
assert context.handlers.context.run_store is context.service.run_store
```

This tests the public context seam instead of the deleted backend chain.

- [ ] **Step 5: Update MCP workflow tools**

In `src/wf_mcp/workflow_surface/tools.py`, remove:

```python
from wf_mcp.broker.service.workflow_api_backend import WfMcpWorkflowApiBackend
```

Add:

```python
from wf_mcp.broker.service.workflow_operation_context import context_from_service
```

Change:

```python
handlers = WorkflowApi(WfMcpWorkflowApiBackend(service))
```

to:

```python
handlers = WorkflowApi(context_from_service(service))
```

For run tools, pass `request.trace_range` or `trace_range` directly to `handlers.*`. Remove conversions through `ApiTraceRange`.

- [ ] **Step 6: Verify Task 3**

Run:

```bash
uv run pytest tests\wf_api\test_no_double_delegation.py tests\wf_cli\test_context.py tests\wf_cli tests\wf_mcp\server\test_tools.py tests\wf_mcp\workflow_surface -q
uv run ruff check src\wf_cli\context.py src\wf_mcp\workflow_surface\tools.py tests\wf_cli\test_context.py tests\wf_api\test_no_double_delegation.py
uv run ruff format --check src\wf_cli\context.py src\wf_mcp\workflow_surface\tools.py tests\wf_cli\test_context.py tests\wf_api\test_no_double_delegation.py
```

Expected: CLI and MCP workflow tool tests pass.

---

### Task 4: Shrink `WorkflowSurfaceHandlers` to Compatibility Shim

**Files:**
- Modify: `src/wf_mcp/workflow_surface/handlers.py`
- Modify: `tests/wf_api/test_direct_service.py` or add a small handler shim test

- [ ] **Step 1: Add compatibility shim test**

Add to `tests/wf_api/test_direct_service.py`:

```python
def test_workflow_surface_handlers_is_compatibility_shim() -> None:
    from wf_api import WorkflowApi
    from wf_mcp.workflow_surface import WorkflowSurfaceHandlers

    root = local_temp_root() / "workflow_surface_handler_shim"
    service = WfMcpService(
        store=FileStore(root / "mcp"),
        artifact_store=FileWorkflowArtifactStore(root),
    )

    handlers = WorkflowSurfaceHandlers(service)

    assert isinstance(handlers, WorkflowApi)
    assert handlers.service is service
    assert handlers.context.artifact_store is service.artifact_store
```

- [ ] **Step 2: Run failing compatibility test**

Run:

```bash
uv run pytest tests\wf_api\test_direct_service.py::test_workflow_surface_handlers_is_compatibility_shim -q
```

Expected: fail because `WorkflowSurfaceHandlers` is not a `WorkflowApi` subclass yet.

- [ ] **Step 3: Replace `WorkflowSurfaceHandlers` implementation**

Replace `src/wf_mcp/workflow_surface/handlers.py` with:

```python
from __future__ import annotations

from wf_api import WorkflowApi

from ..broker.service.workflow_operation_context import context_from_service

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..broker.service import WfMcpService


class WorkflowSurfaceHandlers(WorkflowApi):
    """Compatibility wrapper for old wf_mcp.workflow_surface imports.

    New code should construct `WorkflowApi(context_from_service(service))`
    directly. This shim keeps tests and legacy broker artifact tools working
    while the MCP surface is migrated.
    """

    def __init__(self, service: WfMcpService) -> None:
        self.service = service
        super().__init__(context_from_service(service))


__all__ = ["WorkflowSurfaceHandlers"]
```

This file should no longer import domain services directly.

- [ ] **Step 4: Verify handler compatibility**

Run:

```bash
uv run pytest tests\wf_api\test_direct_service.py::test_workflow_surface_handlers_is_compatibility_shim tests\wf_mcp\workflow_surface tests\wf_mcp\test_saved_subgraphs.py tests\wf_mcp\broker -q
uv run ruff check src\wf_mcp\workflow_surface\handlers.py tests\wf_api\test_direct_service.py
uv run ruff format --check src\wf_mcp\workflow_surface\handlers.py tests\wf_api\test_direct_service.py
```

Expected: old handler tests pass through the shim.

---

### Task 5: Delete Backend Protocol and Adapter

**Files:**
- Delete: `src/wf_api/backend.py`
- Delete: `src/wf_mcp/broker/service/workflow_api_backend.py`
- Modify: `src/wf_api/__init__.py`
- Modify docs that describe the old backend chain

- [ ] **Step 1: Delete backend files**

Delete:

```text
src/wf_api/backend.py
src/wf_mcp/broker/service/workflow_api_backend.py
```

- [ ] **Step 2: Remove public backend export**

In `src/wf_api/__init__.py`, ensure there is no import or `__all__` entry for `WorkflowApiBackend`.

- [ ] **Step 3: Search for live backend references**

Run:

```bash
rg -n "WorkflowApiBackend|WfMcpWorkflowApiBackend|workflow_api_backend|\\.backend" src tests
```

Expected: no live source/test references.

Historical docs under `docs/superpowers/plans/2026-06-01-*` may still mention the old slice. Do not rewrite historical plans except the active roadmap files named in Task 6.

- [ ] **Step 4: Verify deletion**

Run:

```bash
uv run pytest tests\wf_api\test_import_direction.py tests\wf_api\test_no_double_delegation.py tests\wf_api\test_cli_context_uses_api.py -q
uv run ruff check src\wf_api src\wf_cli\context.py src\wf_mcp\workflow_surface src\wf_mcp\broker\service tests\wf_api
uv run ruff format --check src\wf_api src\wf_cli\context.py src\wf_mcp\workflow_surface src\wf_mcp\broker\service tests\wf_api
```

Expected: tests pass, lint pass, format pass.

---

### Task 6: Update Active Docs

**Files:**
- Modify: `docs/current_roadmap.md`
- Modify: `docs/wf_mcp_architecture.md`
- Modify: `docs/superpowers/plans/2026-06-01-wf-api-extraction-roadmap.md`

- [ ] **Step 1: Update `docs/current_roadmap.md`**

Replace the bullet that says the next useful slice is removing double-delegation with:

```markdown
  - Double-delegation has been removed: CLI and MCP workflow tools construct
    `WorkflowApi(context_from_service(service))` directly. `WorkflowSurfaceHandlers`
    remains only as a temporary compatibility shim for older imports.
```

- [ ] **Step 2: Update `docs/wf_mcp_architecture.md`**

Find the architecture text that contains:

```text
wf_api.WorkflowApi ───> WorkflowApiBackend
```

Replace that diagram/text with:

```text
wf_mcp.workflow_surface.tools
  -> wf_api.WorkflowApi
  -> wf_api domain services
  -> WorkflowOperationContext
  -> WfMcpService adapters/stores/runtime
```

Add:

```markdown
`WorkflowSurfaceHandlers` is a compatibility shim only. New entrypoints should
construct `WorkflowApi(context_from_service(service))` directly.
```

- [ ] **Step 3: Update active extraction roadmap**

In `docs/superpowers/plans/2026-06-01-wf-api-extraction-roadmap.md`, add a current-state note near the top:

```markdown
> Current update: the original `WorkflowApiBackend` seam was useful for proving
> dependency direction, but has been collapsed. `WorkflowApi` now composes
> domain services directly from `WorkflowOperationContext`; MCP owns only
> context construction and tool schemas.
```

Do not rewrite the historical task bodies. They describe prior slices.

- [ ] **Step 4: Verify docs**

Run:

```bash
git diff --check -- docs\current_roadmap.md docs\wf_mcp_architecture.md docs\superpowers\plans\2026-06-01-wf-api-extraction-roadmap.md
```

Expected: no whitespace errors.

---

### Task 7: Final Verification

**Files:**
- All touched files.

- [ ] **Step 1: Run focused workflow API/MCP/CLI tests**

Run:

```bash
uv run pytest tests\wf_api tests\wf_cli tests\wf_mcp\workflow_surface tests\wf_mcp\server\test_tools.py tests\wf_mcp\test_saved_subgraphs.py -q
```

Expected: selected tests pass.

- [ ] **Step 2: Run full suite**

Run:

```bash
uv run pytest -q
```

Expected: full suite passes with known skip/xfail counts.

- [ ] **Step 3: Run lint and format checks**

Run:

```bash
uv run ruff check src\wf_api src\wf_cli src\wf_mcp tests\wf_api tests\wf_cli tests\wf_mcp
uv run ruff format --check src\wf_api src\wf_cli src\wf_mcp tests\wf_api tests\wf_cli tests\wf_mcp
```

Expected: all checks pass.

- [ ] **Step 4: Run typecheck**

Run:

```bash
uv run basedpyright --level error
```

Expected: `0 errors, 0 warnings, 0 notes`. If the command exits nonzero only because of the known workspace enumeration warning, report that exactly.

- [ ] **Step 5: Final reference check**

Run:

```bash
rg -n "WorkflowApiBackend|WfMcpWorkflowApiBackend|workflow_api_backend|\\.backend" src tests docs\current_roadmap.md docs\wf_mcp_architecture.md
```

Expected: no references in live source/tests/current docs.

---

## Self-Review

- Spec coverage: The plan removes `WorkflowApiBackend`, deletes `WfMcpWorkflowApiBackend`, updates CLI/MCP construction, keeps handler compatibility, moves `TraceRange`, and updates active docs.
- Placeholder scan: No `TODO`/`TBD` placeholders remain.
- Type consistency: `WorkflowApi` accepts `WorkflowOperationContext`; run trace methods accept `TraceRangeLike`; `TraceRange` is a convenience DTO exported from `wf_api.models`.
- Scope check: This does not remove all `WorkflowSurfaceHandlers` tests or legacy imports. It reduces handlers to a shim; deleting the shim is a later cleanup once `wf_mcp.broker.artifact_tools` and legacy tests stop importing it.
