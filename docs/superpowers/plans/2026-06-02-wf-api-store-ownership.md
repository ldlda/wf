# wf_api Store Ownership Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make workflow artifact, draft workspace, and run store ownership explicit so `wf_api`, CLI, MCP, and future HTTP entrypoints can share stores without relying on `WfMcpService.__post_init__`.

**Architecture:** Add a protocol-neutral `WorkflowStores` bundle in `wf_api` that groups the three workflow stores. MCP config construction remains responsible for creating file-backed stores from `BrokerConfig.store_root`; `WfMcpService` receives stores but no longer manufactures them from its MCP `Store`. Existing process-local behavior stays intact through `build_service_from_config`.

**Tech Stack:** Python 3.14, dataclasses, `wf_api`, `wf_artifacts`, `wf_mcp`, pytest, ruff, basedpyright.

---

## Current Problem

`src/wf_mcp/broker/service/core.py` currently does this in `WfMcpService.__post_init__`:

```python
if self.artifact_store is None:
    self.artifact_store = FileWorkflowArtifactStore(_store_root(self.store))
if self.draft_workspace_store is None:
    self.draft_workspace_store = FileDraftWorkspaceStore(_store_root(self.store))
if self.run_store is None:
    self.run_store = FileRunStore(_store_root(self.store))
```

That makes a protocol-specific service decide protocol-neutral workflow persistence. It also hides missing-store tests because `WfMcpService(store=FileStore(...))` silently creates workflow stores.

`src/wf_mcp/broker/config.py::build_service_from_config` already does the right thing by passing all three stores explicitly. This slice preserves that behavior and removes the fallback.

## Target Ownership Rule

- `wf_artifacts` owns store protocols and file store implementations.
- `wf_api` may group protocol-neutral workflow stores into a small DTO.
- `wf_mcp` owns MCP config loading and calls the DTO factory for file-backed process-local stores.
- `WfMcpService` owns broker state, connections, adapters, source catalogs, events, and execution wiring.
- `WfMcpService` does not create workflow artifact/draft/run stores by guessing from the MCP catalog/auth store.

## Files

- Create: `src/wf_api/stores.py`
- Modify: `src/wf_api/__init__.py`
- Modify: `src/wf_mcp/broker/config.py`
- Modify: `src/wf_mcp/broker/service/core.py`
- Modify: direct `WfMcpService(...)` tests only where they rely on implicit workflow stores
- Test: `tests/wf_api/test_stores.py`
- Test: `tests/wf_mcp/service/test_catalog.py`
- Test: `tests/wf_mcp/test_broker_server.py`

---

### Task 1: Add Protocol-Neutral Store Bundle

**Files:**
- Create: `src/wf_api/stores.py`
- Modify: `src/wf_api/__init__.py`
- Test: `tests/wf_api/test_stores.py`

- [ ] **Step 1: Write failing store bundle tests**

Create `tests/wf_api/test_stores.py`:

```python
from __future__ import annotations

from wf_api.stores import WorkflowStores, file_workflow_stores
from wf_artifacts import (
    FileDraftWorkspaceStore,
    FileRunStore,
    FileWorkflowArtifactStore,
)

from tests.wf_mcp.test_support import local_temp_root


def test_file_workflow_stores_constructs_all_three_file_stores() -> None:
    root = local_temp_root() / "wf_api_file_workflow_stores"

    stores = file_workflow_stores(root)

    assert isinstance(stores, WorkflowStores)
    assert isinstance(stores.artifact_store, FileWorkflowArtifactStore)
    assert isinstance(stores.draft_workspace_store, FileDraftWorkspaceStore)
    assert isinstance(stores.run_store, FileRunStore)
    assert stores.artifact_store.root == root
    assert stores.draft_workspace_store.root == root
    assert stores.run_store.root == root


def test_wf_api_exports_workflow_stores() -> None:
    from wf_api import WorkflowStores as ExportedWorkflowStores
    from wf_api import file_workflow_stores as exported_file_workflow_stores

    assert ExportedWorkflowStores is WorkflowStores
    assert exported_file_workflow_stores is file_workflow_stores
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
uv run pytest tests\wf_api\test_stores.py -q
```

Expected: import failure for `wf_api.stores`.

- [ ] **Step 3: Implement `wf_api.stores`**

Create `src/wf_api/stores.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from wf_artifacts import (
    DraftWorkspaceStore,
    FileDraftWorkspaceStore,
    FileRunStore,
    FileWorkflowArtifactStore,
    RunStore,
    WorkflowArtifactStore,
)


@dataclass(frozen=True, slots=True)
class WorkflowStores:
    """Protocol-neutral persistence dependencies for workflow APIs."""

    artifact_store: WorkflowArtifactStore
    draft_workspace_store: DraftWorkspaceStore
    run_store: RunStore


def file_workflow_stores(root: str | Path) -> WorkflowStores:
    """Create process-local file-backed workflow stores under one root."""
    store_root = Path(root)
    return WorkflowStores(
        artifact_store=FileWorkflowArtifactStore(store_root),
        draft_workspace_store=FileDraftWorkspaceStore(store_root),
        run_store=FileRunStore(store_root),
    )


__all__ = ["WorkflowStores", "file_workflow_stores"]
```

- [ ] **Step 4: Export from `wf_api`**

Update `src/wf_api/__init__.py`:

```python
from .stores import WorkflowStores, file_workflow_stores
```

Add both names to `__all__`.

- [ ] **Step 5: Verify Task 1**

Run:

```bash
uv run pytest tests\wf_api\test_stores.py -q
uv run ruff check src\wf_api\stores.py tests\wf_api\test_stores.py
uv run ruff format --check src\wf_api\stores.py tests\wf_api\test_stores.py
```

Expected: tests pass, lint pass, format pass.

---

### Task 2: Move Config Store Construction Through the Bundle

**Files:**
- Modify: `src/wf_mcp/broker/config.py`
- Test: `tests/wf_mcp/test_broker_server.py`

- [ ] **Step 1: Strengthen config construction test**

Find `tests/wf_mcp/test_broker_server.py::test_build_service_from_config_uses_store_root_for_artifacts`.

Update it to assert all three stores use the configured root:

```python
def test_build_service_from_config_uses_store_root_for_workflow_stores() -> None:
    store_root = local_temp_root() / "broker_config_workflow_stores"
    config = BrokerConfig(store_root=store_root, connections=[])

    service = build_service_from_config(config)

    assert isinstance(service.artifact_store, FileWorkflowArtifactStore)
    assert isinstance(service.draft_workspace_store, FileDraftWorkspaceStore)
    assert isinstance(service.run_store, FileRunStore)
    assert service.artifact_store.root == store_root
    assert service.draft_workspace_store.root == store_root
    assert service.run_store.root == store_root
```

Ensure the test imports:

```python
from wf_artifacts import FileDraftWorkspaceStore, FileRunStore, FileWorkflowArtifactStore
```

- [ ] **Step 2: Run the focused test**

Run:

```bash
uv run pytest tests\wf_mcp\test_broker_server.py::test_build_service_from_config_uses_store_root_for_workflow_stores -q
```

Expected: pass before the config refactor, proving current behavior is covered.

- [ ] **Step 3: Update `build_service_from_config` to use `file_workflow_stores`**

In `src/wf_mcp/broker/config.py`, replace direct file store imports:

```python
from wf_api import file_workflow_stores
```

Remove:

```python
from wf_artifacts import (
    FileDraftWorkspaceStore,
    FileRunStore,
    FileWorkflowArtifactStore,
)
```

Then update `build_service_from_config`:

```python
def build_service_from_config(config: BrokerConfig) -> WfMcpService:
    """Create a broker service with SDK adapters for configured connections."""
    runtime_factory = PersistentSessionFactory()
    workflow_stores = file_workflow_stores(config.store_root)
    service = WfMcpService(
        store=FileStore(config.store_root),
        artifact_store=workflow_stores.artifact_store,
        draft_workspace_store=workflow_stores.draft_workspace_store,
        run_store=workflow_stores.run_store,
        # Discovery can use short-lived SDK sessions. Workflow execution needs
        # a persistent runtime so stateful MCP servers keep session/page state
        # across sequential workflow nodes.
        tool_executor=McpRuntimePool(runtime_factory.create),
    )
```

- [ ] **Step 4: Verify Task 2**

Run:

```bash
uv run pytest tests\wf_mcp\test_broker_server.py::test_build_service_from_config_uses_store_root_for_workflow_stores -q
uv run ruff check src\wf_mcp\broker\config.py tests\wf_mcp\test_broker_server.py
uv run ruff format --check src\wf_mcp\broker\config.py tests\wf_mcp\test_broker_server.py
```

Expected: tests pass, lint pass, format pass.

---

### Task 3: Remove Implicit Workflow Store Creation from WfMcpService

**Files:**
- Modify: `src/wf_mcp/broker/service/core.py`
- Modify: `tests/wf_mcp/service/test_catalog.py`

- [ ] **Step 1: Replace the old default-store test**

Find `tests/wf_mcp/service/test_catalog.py::test_service_installs_default_draft_workspace_store`.

Replace it with:

```python
def test_service_does_not_install_workflow_stores_implicitly() -> None:
    root = local_temp_root() / "service_no_implicit_workflow_stores"
    service = WfMcpService(store=FileStore(root))

    assert service.artifact_store is None
    assert service.draft_workspace_store is None
    assert service.run_store is None
```

- [ ] **Step 2: Run failing test**

Run:

```bash
uv run pytest tests\wf_mcp\service\test_catalog.py::test_service_does_not_install_workflow_stores_implicitly -q
```

Expected: fail because `WfMcpService.__post_init__` still creates stores.

- [ ] **Step 3: Remove implicit creation from `WfMcpService.__post_init__`**

In `src/wf_mcp/broker/service/core.py`, remove the imports:

```python
FileDraftWorkspaceStore,
FileRunStore,
FileWorkflowArtifactStore,
```

Remove the `_store_root` helper entirely:

```python
def _store_root(store: Store) -> Path:
    """Return the file root for stores that expose one, else use local default."""
    root = getattr(store, "root", None)
    return root if isinstance(root, Path) else Path(".wf_mcp_store")
```

Update `WfMcpService.__post_init__` to:

```python
def __post_init__(self) -> None:
    """Install broker-local system specs when enabled.

    Workflow stores are injected by entrypoint/config construction. This service
    must not guess workflow persistence from the MCP catalog/auth store because
    CLI, MCP, and future HTTP frontends may share or swap those stores.
    """
    if self.include_builtin_specs:
        for source in builtin_sources().values():
            self.register_capability_source(source)
    self.register_capability_source(admin_source())
```

If `Path` becomes unused in `core.py`, remove `from pathlib import Path`.

- [ ] **Step 4: Verify Task 3**

Run:

```bash
uv run pytest tests\wf_mcp\service\test_catalog.py::test_service_does_not_install_workflow_stores_implicitly -q
uv run ruff check src\wf_mcp\broker\service\core.py tests\wf_mcp\service\test_catalog.py
uv run ruff format --check src\wf_mcp\broker\service\core.py tests\wf_mcp\service\test_catalog.py
```

Expected: tests pass, lint pass, format pass.

---

### Task 4: Fix Direct Service Tests That Need Workflow Stores

**Files:**
- Modify only tests that fail after Task 3.

- [ ] **Step 1: Run targeted workflow API/service tests**

Run:

```bash
uv run pytest tests\wf_api tests\wf_mcp\workflow_surface tests\wf_mcp\test_broker_server.py tests\wf_mcp\service -q
```

Expected: if failures appear, they should be tests that constructed `WfMcpService(store=...)` but then used workflow artifact/draft/run operations.

- [ ] **Step 2: Patch only failing tests by injecting stores explicitly**

For any failing direct `WfMcpService(...)` test that needs workflow stores, use this pattern:

```python
from wf_api import file_workflow_stores


root = local_temp_root() / "test_specific_name"
workflow_stores = file_workflow_stores(root)
service = WfMcpService(
    store=FileStore(root / "mcp"),
    artifact_store=workflow_stores.artifact_store,
    draft_workspace_store=workflow_stores.draft_workspace_store,
    run_store=workflow_stores.run_store,
)
```

Do not add stores to tests that only exercise broker catalog/admin/source behavior.

- [ ] **Step 3: Keep no-store behavior tests intact**

Tests like these should keep `artifact_store=None` through `WorkflowOperationContext` or direct service construction because they prove graceful no-store behavior:

```python
assert result["nodes"] == []
assert result["deployments"] == []
```

Do not “fix” these by injecting stores unless the test is explicitly about stored workflow data.

- [ ] **Step 4: Verify targeted tests**

Run:

```bash
uv run pytest tests\wf_api tests\wf_mcp\workflow_surface tests\wf_mcp\test_broker_server.py tests\wf_mcp\service -q
uv run ruff check tests\wf_api tests\wf_mcp\workflow_surface tests\wf_mcp\test_broker_server.py tests\wf_mcp\service
uv run ruff format --check tests\wf_api tests\wf_mcp\workflow_surface tests\wf_mcp\test_broker_server.py tests\wf_mcp\service
```

Expected: targeted tests pass and no broad fixture churn.

---

### Task 5: Document the Store Ownership Rule

**Files:**
- Modify: `docs/superpowers/research/2026-06-01-wf-api-extraction-map.md`
- Modify: `docs/current_roadmap.md` if it already has a `wf_api` section

- [ ] **Step 1: Update the extraction map**

In `docs/superpowers/research/2026-06-01-wf-api-extraction-map.md`, under `### Store Ownership Ambiguity`, replace the section with:

```markdown
### Store Ownership

- `wf_artifacts` owns workflow store protocols and file-backed implementations.
- `wf_api.stores.WorkflowStores` groups the artifact, draft workspace, and run stores as protocol-neutral API dependencies.
- MCP config construction creates file-backed workflow stores from `BrokerConfig.store_root` and injects them into `WfMcpService`.
- `WfMcpService.__post_init__` no longer creates workflow stores from its MCP `Store`; direct service tests must inject stores when they exercise workflow persistence.
- Future HTTP/API entrypoints should construct or receive the same `WorkflowStores` bundle instead of importing `wf_mcp`.
```

- [ ] **Step 2: Update roadmap only if there is a matching section**

If `docs/current_roadmap.md` has a `wf_api` or API extraction section, add:

```markdown
- Workflow store ownership is explicit: entrypoints construct/inject `WorkflowStores`; `WfMcpService` no longer guesses stores from the MCP store root.
```

If there is no matching section, skip this file.

- [ ] **Step 3: Verify docs are not stale**

Run:

```bash
rg -n "_store_root\\(|creates default `FileWorkflowArtifactStore`|installs default.*store" src docs tests
```

Expected: no current docs/tests claim `WfMcpService` installs default workflow stores. Historical plans may still mention old implementation; leave historical plans alone unless they are current roadmap/research docs.

---

### Task 6: Final Verification

**Files:**
- All touched files.

- [ ] **Step 1: Run focused suite**

Run:

```bash
uv run pytest tests\wf_api tests\wf_mcp\workflow_surface tests\wf_mcp\test_broker_server.py tests\wf_mcp\service -q
```

Expected: all selected tests pass.

- [ ] **Step 2: Run full suite**

Run:

```bash
uv run pytest -q
```

Expected: full suite passes with the repo’s known skip/xfail counts.

- [ ] **Step 3: Run lint and format checks**

Run:

```bash
uv run ruff check src\wf_api src\wf_mcp tests\wf_api tests\wf_mcp
uv run ruff format --check src\wf_api src\wf_mcp tests\wf_api tests\wf_mcp
```

Expected: all checks pass.

- [ ] **Step 4: Run typecheck**

Run:

```bash
uv run basedpyright --level error
```

Expected: `0 errors, 0 warnings, 0 notes`. If the command exits nonzero only because of the known workspace enumeration warning, report that exactly.

---

## Self-Review

- Spec coverage: This plan covers explicit store creation, `WfMcpService.__post_init__` cleanup, config behavior preservation, test migration, and docs.
- Placeholder scan: No `TODO`/`TBD` placeholders remain. Historical-plan references are explicitly scoped.
- Type consistency: `WorkflowStores` uses protocol types from `wf_artifacts`; `file_workflow_stores()` returns file-backed implementations; `WfMcpService` field types do not change.
- Scope check: This does not implement FastAPI, persisted-run conflict handling, or store locking. Those are separate slices.
