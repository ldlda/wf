# Draft Workspaces Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add mutable draft workspaces so LLM and human clients can create one workflow draft, patch it by id across calls, validate it repeatedly, and finally save an immutable workflow artifact.

**Architecture:** Keep the draft workspace domain in `wf_artifacts`, next to immutable artifacts but separate from them. `WorkflowDraftWorkspace` is mutable and revisioned; `WorkflowArtifact` remains immutable and versioned. `wf_mcp.workflow_surface` exposes workspace tools as a projection over the same draft APIs, not a second graph builder.

**Tech Stack:** Python 3.14, Pydantic v2, JSON file storage, `jsonpatch`, existing `wf_artifacts.drafts`, existing `WorkflowSurfaceHandlers`, pytest, ruff, basedpyright.

---

## Scope

This plan builds the promised stateful `wf_authoring over MCP` loop:

```text
list sources
list/inspect/call capability
create draft workspace
patch draft workspace by id
validate/get workspace by id
create artifact from workspace
save deployment
run deployment
```

This plan does **not** add:

- graph-as-node/subgraph runtime support
- rich JSON `match` / `when` / `choose` draft sugar
- UI
- auth/user ownership
- automatic clever field mapping
- per-outcome output schemas

The key design choice is explicit: the server owns the draft document after workspace creation, so clients send JSON Patch operations instead of resending the entire draft every turn.

## File Structure

- Create `src/wf_artifacts/draft_workspaces/models.py`
  - Pydantic models for mutable workspaces and summaries.
- Create `src/wf_artifacts/draft_workspaces/store.py`
  - Protocol-style store plus file-backed implementation.
- Create `src/wf_artifacts/draft_workspaces/api.py`
  - Pure functions for create/get/patch/validate summaries.
- Create `src/wf_artifacts/draft_workspaces/__init__.py`
  - Public package exports.
- Modify `src/wf_artifacts/__init__.py`
  - Re-export workspace models/store/api.
- Modify `src/wf_mcp/broker/service/core.py`
  - Add `draft_workspace_store` to `WfMcpService`.
- Modify `src/wf_mcp/broker/config.py`
  - Wire default file-backed workspace store beside the artifact store.
- Modify `src/wf_mcp/workflow_surface/handlers.py`
  - Add workspace operations and minimal-draft bootstrapping.
- Modify `src/wf_mcp/workflow_surface/tools.py`
  - Register MCP tools for workspace operations.
- Modify `src/wf_mcp/workflow_surface/models.py`
  - Add Inspector-visible response models for workspace tools where useful.
- Modify `src/wf_mcp/transparent_proxy/runtime.py`
  - Pin always-visible workflow workspace tools if this allowlist still gates search mode.
- Modify `docs/workflow_drafts.md`
  - Document stateless draft tools versus stateful draft workspace tools.
- Modify `docs/wf_mcp_operator_manual.md`
  - Add the authoring loop using workspace ids/revisions.
- Modify `docs/wf_mcp_end_to_end_runbook.md`
  - Add a short draft workspace path after the current full-draft path.
- Test `tests/artifacts/test_draft_workspaces.py`
  - Domain/store/API tests.
- Test `tests/wf_mcp/test_workflow_surface.py`
  - Handler tests for workspace tools.
- Test `tests/wf_mcp/test_server.py`
  - MCP tool registration/schema smoke tests.

## Public API Shape

### Domain Model

```python
class WorkflowDraftWorkspace(BaseModel):
    id: str
    revision: int = 1
    title: str | None = None
    draft: dict[str, Any]
    status: Literal["valid", "invalid"]
    diagnostics: list[dict[str, Any]] = []
    created_at_epoch_ms: int
    updated_at_epoch_ms: int
```

Rules:

- `id` is stable and caller-chosen or generated.
- `revision` starts at `1`.
- Each successful patch increments `revision`.
- A patch request must include the expected `revision`.
- Stale revision returns a structured `revision_conflict` result and does not mutate.
- Invalid drafts can be stored. The workspace exists so clients can repair them.
- Artifacts are only created from a workspace when the current draft validates.

### MCP Tools

New tools:

```text
wf.workflow.create_draft_workspace
wf.workflow.get_draft_workspace
wf.workflow.patch_draft_workspace
wf.workflow.create_minimal_draft_workspace
wf.workflow.create_artifact_from_workspace
```

Keep existing tools:

```text
wf.workflow.validate_draft
wf.workflow.compile_draft
wf.workflow.patch_draft
wf.workflow.create_artifact_from_draft
```

The existing stateless tools remain useful for one-shot clients and tests.
Workspace tools are the preferred LLM authoring surface.

## Response Shape

Workspace mutating tools should return:

```json
{
  "workspace_id": "echo_draft",
  "revision": 2,
  "status": "valid",
  "diagnostics": [],
  "summary": {
    "name": "echo",
    "start": "echo",
    "step_count": 2,
    "route_count": 2,
    "steps": ["echo", "tool_error"]
  }
}
```

`get_draft_workspace` should accept:

```python
include_draft: bool = False
```

Default response stays compact. If `include_draft=True`, include the full draft.

---

## Task 1: Add Draft Workspace Domain Models

**Files:**
- Create: `src/wf_artifacts/draft_workspaces/models.py`
- Create: `src/wf_artifacts/draft_workspaces/__init__.py`
- Modify: `src/wf_artifacts/__init__.py`
- Test: `tests/artifacts/test_draft_workspaces.py`

- [ ] **Step 1: Write failing model tests**

Create `tests/artifacts/test_draft_workspaces.py`:

```python
from __future__ import annotations

from wf_artifacts import WorkflowDraftWorkspace, summarize_draft_workspace


def test_draft_workspace_stores_mutable_draft_with_revision() -> None:
    workspace = WorkflowDraftWorkspace(
        id="echo_draft",
        revision=1,
        title="Echo Draft",
        draft=_draft(),
        status="valid",
        diagnostics=[],
        created_at_epoch_ms=100,
        updated_at_epoch_ms=100,
    )

    assert workspace.id == "echo_draft"
    assert workspace.revision == 1
    assert workspace.draft["steps"]["echo"]["use"] == "demo.echo"


def test_draft_workspace_summary_is_compact() -> None:
    workspace = WorkflowDraftWorkspace(
        id="echo_draft",
        revision=3,
        draft=_draft(),
        status="valid",
        diagnostics=[],
        created_at_epoch_ms=100,
        updated_at_epoch_ms=200,
    )

    summary = summarize_draft_workspace(workspace)

    assert summary["workspace_id"] == "echo_draft"
    assert summary["revision"] == 3
    assert summary["status"] == "valid"
    assert summary["summary"]["name"] == "echo"
    assert summary["summary"]["steps"] == ["echo"]
    assert "draft" not in summary


def _draft() -> dict[str, object]:
    return {
        "name": "echo",
        "input_schema": {"type": "object", "properties": {}},
        "state_schema": {"fields": {"echoed": {"type": "string"}}},
        "output_schema": {"type": "object", "properties": {}},
        "start": "echo",
        "steps": {
            "echo": {
                "use": "demo.echo",
                "in": {},
                "out": {"echoed": "state.echoed"},
            }
        },
        "routes": {"echo": {"ok": "__end__"}},
    }
```

- [ ] **Step 2: Run model tests and verify they fail**

Run:

```powershell
uv run --with pytest pytest tests\artifacts\test_draft_workspaces.py -q
```

Expected: import failure for `WorkflowDraftWorkspace`.

- [ ] **Step 3: Implement models**

Create `src/wf_artifacts/draft_workspaces/models.py`:

```python
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


JsonObject = dict[str, Any]


class WorkflowDraftWorkspace(BaseModel):
    """Mutable, revisioned authoring workspace for one workflow draft."""

    id: str
    revision: int = Field(default=1, ge=1)
    title: str | None = None
    draft: JsonObject
    status: Literal["valid", "invalid"]
    diagnostics: list[JsonObject] = Field(default_factory=list)
    created_at_epoch_ms: int
    updated_at_epoch_ms: int


def summarize_draft_workspace(
    workspace: WorkflowDraftWorkspace,
    *,
    include_draft: bool = False,
) -> JsonObject:
    """Return a compact workspace payload for MCP clients."""
    steps = workspace.draft.get("steps", {})
    routes = workspace.draft.get("routes", {})
    summary: JsonObject = {
        "workspace_id": workspace.id,
        "revision": workspace.revision,
        "title": workspace.title,
        "status": workspace.status,
        "diagnostics": workspace.diagnostics,
        "summary": {
            "name": workspace.draft.get("name"),
            "start": workspace.draft.get("start"),
            "step_count": len(steps) if isinstance(steps, dict) else 0,
            "route_count": len(routes) if isinstance(routes, dict) else 0,
            "steps": sorted(steps) if isinstance(steps, dict) else [],
        },
    }
    if include_draft:
        summary["draft"] = workspace.draft
    return summary
```

Create `src/wf_artifacts/draft_workspaces/__init__.py`:

```python
from .models import WorkflowDraftWorkspace, summarize_draft_workspace

__all__ = [
    "WorkflowDraftWorkspace",
    "summarize_draft_workspace",
]
```

Modify `src/wf_artifacts/__init__.py`:

```python
from .draft_workspaces import WorkflowDraftWorkspace, summarize_draft_workspace
```

Add both names to `__all__`.

- [ ] **Step 4: Run model tests**

Run:

```powershell
uv run --with pytest pytest tests\artifacts\test_draft_workspaces.py -q
```

Expected: `2 passed`.

- [ ] **Step 5: Commit**

```powershell
git add src\wf_artifacts tests\artifacts\test_draft_workspaces.py
git commit -m "feat: add draft workspace models"
```

---

## Task 2: Add File-Backed Draft Workspace Store

**Files:**
- Create: `src/wf_artifacts/draft_workspaces/store.py`
- Modify: `src/wf_artifacts/draft_workspaces/__init__.py`
- Modify: `src/wf_artifacts/__init__.py`
- Test: `tests/artifacts/test_draft_workspaces.py`

- [ ] **Step 1: Add failing store tests**

Append to `tests/artifacts/test_draft_workspaces.py`:

```python
from wf_artifacts import FileDraftWorkspaceStore


def test_file_draft_workspace_store_round_trips_workspace(tmp_path) -> None:
    store = FileDraftWorkspaceStore(tmp_path)
    workspace = WorkflowDraftWorkspace(
        id="echo_draft",
        revision=1,
        draft=_draft(),
        status="valid",
        diagnostics=[],
        created_at_epoch_ms=100,
        updated_at_epoch_ms=100,
    )

    store.save_workspace(workspace)
    loaded = store.get_workspace("echo_draft")

    assert loaded == workspace


def test_file_draft_workspace_store_lists_workspaces(tmp_path) -> None:
    store = FileDraftWorkspaceStore(tmp_path)
    store.save_workspace(
        WorkflowDraftWorkspace(
            id="b",
            revision=1,
            draft=_draft(),
            status="valid",
            diagnostics=[],
            created_at_epoch_ms=100,
            updated_at_epoch_ms=100,
        )
    )
    store.save_workspace(
        WorkflowDraftWorkspace(
            id="a",
            revision=1,
            draft=_draft(),
            status="valid",
            diagnostics=[],
            created_at_epoch_ms=100,
            updated_at_epoch_ms=100,
        )
    )

    assert [workspace.id for workspace in store.list_workspaces()] == ["a", "b"]
```

- [ ] **Step 2: Run store tests and verify they fail**

Run:

```powershell
uv run --with pytest pytest tests\artifacts\test_draft_workspaces.py -q
```

Expected: import failure for `FileDraftWorkspaceStore`.

- [ ] **Step 3: Implement store**

Create `src/wf_artifacts/draft_workspaces/store.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from .models import WorkflowDraftWorkspace


class DraftWorkspaceStore:
    """Storage boundary for mutable workflow draft workspaces."""

    def save_workspace(self, workspace: WorkflowDraftWorkspace) -> None:
        raise NotImplementedError

    def get_workspace(self, workspace_id: str) -> WorkflowDraftWorkspace:
        raise NotImplementedError

    def list_workspaces(self) -> list[WorkflowDraftWorkspace]:
        raise NotImplementedError


class FileDraftWorkspaceStore(DraftWorkspaceStore):
    """JSON file-backed draft workspace store for local development and tests."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.workspaces_dir.mkdir(parents=True, exist_ok=True)

    @property
    def workspaces_dir(self) -> Path:
        return self.root / "draft_workspaces"

    def save_workspace(self, workspace: WorkflowDraftWorkspace) -> None:
        path = self.workspaces_dir / f"{workspace.id}.json"
        path.write_text(
            json.dumps(workspace.model_dump(mode="json"), indent=2),
            encoding="utf-8",
        )

    def get_workspace(self, workspace_id: str) -> WorkflowDraftWorkspace:
        path = self.workspaces_dir / f"{workspace_id}.json"
        if not path.exists():
            raise KeyError(f"unknown draft workspace {workspace_id!r}")
        return WorkflowDraftWorkspace.model_validate_json(
            path.read_text(encoding="utf-8")
        )

    def list_workspaces(self) -> list[WorkflowDraftWorkspace]:
        return [
            WorkflowDraftWorkspace.model_validate_json(path.read_text(encoding="utf-8"))
            for path in sorted(self.workspaces_dir.glob("*.json"))
        ]
```

Update exports in `src/wf_artifacts/draft_workspaces/__init__.py`:

```python
from .models import WorkflowDraftWorkspace, summarize_draft_workspace
from .store import DraftWorkspaceStore, FileDraftWorkspaceStore

__all__ = [
    "DraftWorkspaceStore",
    "FileDraftWorkspaceStore",
    "WorkflowDraftWorkspace",
    "summarize_draft_workspace",
]
```

Update `src/wf_artifacts/__init__.py` to re-export `DraftWorkspaceStore` and `FileDraftWorkspaceStore`.

- [ ] **Step 4: Run store tests**

Run:

```powershell
uv run --with pytest pytest tests\artifacts\test_draft_workspaces.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add src\wf_artifacts tests\artifacts\test_draft_workspaces.py
git commit -m "feat: persist draft workspaces"
```

---

## Task 3: Add Draft Workspace API Functions

**Files:**
- Create: `src/wf_artifacts/draft_workspaces/api.py`
- Modify: `src/wf_artifacts/draft_workspaces/__init__.py`
- Modify: `src/wf_artifacts/__init__.py`
- Test: `tests/artifacts/test_draft_workspaces.py`

- [ ] **Step 1: Add failing API tests**

Append:

```python
from wf_artifacts import (
    create_draft_workspace,
    patch_draft_workspace,
)


def test_create_draft_workspace_validates_and_saves(tmp_path) -> None:
    store = FileDraftWorkspaceStore(tmp_path)

    result = create_draft_workspace(
        store,
        workspace_id="echo_draft",
        draft=_draft(),
        title="Echo Draft",
    )

    loaded = store.get_workspace("echo_draft")
    assert result["workspace_id"] == "echo_draft"
    assert result["status"] == "valid"
    assert loaded.revision == 1
    assert loaded.status == "valid"


def test_patch_draft_workspace_applies_patch_and_increments_revision(tmp_path) -> None:
    store = FileDraftWorkspaceStore(tmp_path)
    create_draft_workspace(store, workspace_id="echo_draft", draft=_draft())

    result = patch_draft_workspace(
        store,
        workspace_id="echo_draft",
        revision=1,
        patch=[
            {
                "op": "replace",
                "path": "/steps/echo/in/input.text",
                "value": "message",
            }
        ],
    )

    loaded = store.get_workspace("echo_draft")
    assert result["revision"] == 2
    assert result["status"] == "valid"
    assert loaded.revision == 2
    assert loaded.draft["steps"]["echo"]["in"]["input.text"] == "message"


def test_patch_draft_workspace_rejects_stale_revision(tmp_path) -> None:
    store = FileDraftWorkspaceStore(tmp_path)
    create_draft_workspace(store, workspace_id="echo_draft", draft=_draft())
    patch_draft_workspace(
        store,
        workspace_id="echo_draft",
        revision=1,
        patch=[],
    )

    result = patch_draft_workspace(
        store,
        workspace_id="echo_draft",
        revision=1,
        patch=[],
    )

    assert result["status"] == "conflict"
    assert result["diagnostics"][0]["code"] == "revision_conflict"
    assert store.get_workspace("echo_draft").revision == 2
```

- [ ] **Step 2: Run API tests and verify they fail**

Run:

```powershell
uv run --with pytest pytest tests\artifacts\test_draft_workspaces.py -q
```

Expected: import failure for API functions.

- [ ] **Step 3: Implement API**

Create `src/wf_artifacts/draft_workspaces/api.py`:

```python
from __future__ import annotations

import time
from typing import Any

from wf_artifacts.drafts import patch_workflow_draft, validate_workflow_draft

from .models import WorkflowDraftWorkspace, summarize_draft_workspace
from .store import DraftWorkspaceStore

JsonObject = dict[str, Any]
JsonPatch = list[dict[str, Any]]


def create_draft_workspace(
    store: DraftWorkspaceStore,
    *,
    workspace_id: str,
    draft: JsonObject,
    title: str | None = None,
) -> JsonObject:
    """Validate and save a new mutable draft workspace."""
    now = _now_ms()
    validation = validate_workflow_draft(draft)
    workspace = WorkflowDraftWorkspace(
        id=workspace_id,
        revision=1,
        title=title,
        draft=draft,
        status=validation["status"],
        diagnostics=validation["diagnostics"],
        created_at_epoch_ms=now,
        updated_at_epoch_ms=now,
    )
    store.save_workspace(workspace)
    return summarize_draft_workspace(workspace)


def patch_draft_workspace(
    store: DraftWorkspaceStore,
    *,
    workspace_id: str,
    revision: int,
    patch: JsonPatch,
) -> JsonObject:
    """Apply JSON Patch to a stored workspace when the revision matches."""
    workspace = store.get_workspace(workspace_id)
    if workspace.revision != revision:
        return {
            "workspace_id": workspace.id,
            "revision": workspace.revision,
            "status": "conflict",
            "diagnostics": [
                {
                    "code": "revision_conflict",
                    "path": "revision",
                    "message": (
                        f"workspace {workspace.id!r} is at revision "
                        f"{workspace.revision}, not {revision}"
                    ),
                }
            ],
            "summary": summarize_draft_workspace(workspace)["summary"],
        }
    patched = patch_workflow_draft(workspace.draft, patch)
    next_workspace = workspace.model_copy(
        update={
            "revision": workspace.revision + 1,
            "draft": patched.get("draft", workspace.draft),
            "status": patched["status"],
            "diagnostics": patched["diagnostics"],
            "updated_at_epoch_ms": _now_ms(),
        }
    )
    store.save_workspace(next_workspace)
    return summarize_draft_workspace(next_workspace)


def get_draft_workspace(
    store: DraftWorkspaceStore,
    *,
    workspace_id: str,
    include_draft: bool = False,
) -> JsonObject:
    """Return one stored workspace, compact by default."""
    return summarize_draft_workspace(
        store.get_workspace(workspace_id),
        include_draft=include_draft,
    )


def _now_ms() -> int:
    return int(time.time() * 1000)
```

Update exports in both `__init__.py` files.

- [ ] **Step 4: Run API tests**

Run:

```powershell
uv run --with pytest pytest tests\artifacts\test_draft_workspaces.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add src\wf_artifacts tests\artifacts\test_draft_workspaces.py
git commit -m "feat: patch draft workspaces by revision"
```

---

## Task 4: Wire Draft Workspace Store Into WfMcpService

**Files:**
- Modify: `src/wf_mcp/broker/service/core.py`
- Modify: `src/wf_mcp/broker/config.py`
- Test: `tests/wf_mcp/test_service.py`

- [ ] **Step 1: Add failing service test**

Append to `tests/wf_mcp/test_service.py`:

```python
from wf_artifacts import FileDraftWorkspaceStore


def test_service_installs_default_draft_workspace_store() -> None:
    root = local_temp_root() / "service_default_draft_workspace_store"
    service = WfMcpService(store=FileStore(root))

    assert isinstance(service.draft_workspace_store, FileDraftWorkspaceStore)
    assert service.draft_workspace_store.root == root
```

- [ ] **Step 2: Run service test and verify it fails**

Run:

```powershell
uv run --with pytest pytest tests\wf_mcp\test_service.py::test_service_installs_default_draft_workspace_store -q
```

Expected: attribute error for `draft_workspace_store`.

- [ ] **Step 3: Implement service field**

Modify imports in `src/wf_mcp/broker/service/core.py`:

```python
from wf_artifacts import (
    FileDraftWorkspaceStore,
    FileWorkflowArtifactStore,
    WorkflowArtifact,
    WorkflowArtifactCatalogEntry,
    WorkflowArtifactStore,
    WorkflowDeployment,
    DraftWorkspaceStore,
    artifact_catalog_entry,
)
```

Add field:

```python
draft_workspace_store: DraftWorkspaceStore | None = None
```

In `__post_init__` after artifact store setup:

```python
if self.draft_workspace_store is None:
    self.draft_workspace_store = FileDraftWorkspaceStore(_store_root(self.store))
```

Modify `src/wf_mcp/broker/config.py` if it constructs `WfMcpService` with explicit stores. Pass:

```python
draft_workspace_store=FileDraftWorkspaceStore(config.store_root)
```

- [ ] **Step 4: Run service test**

Run:

```powershell
uv run --with pytest pytest tests\wf_mcp\test_service.py::test_service_installs_default_draft_workspace_store -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```powershell
git add src\wf_mcp tests\wf_mcp\test_service.py
git commit -m "feat: attach draft workspace store to service"
```

---

## Task 5: Add Workflow Surface Workspace Handlers

**Files:**
- Modify: `src/wf_mcp/workflow_surface/handlers.py`
- Test: `tests/wf_mcp/test_workflow_surface.py`

- [ ] **Step 1: Add failing handler tests**

Append to `tests/wf_mcp/test_workflow_surface.py`:

```python
def test_workflow_surface_creates_and_gets_draft_workspace() -> None:
    artifact_store = FileWorkflowArtifactStore(local_temp_root() / "surface_workspace")
    handlers = _handlers(artifact_store)

    created = asyncio.run(
        handlers.create_draft_workspace(
            workspace_id="echo_draft",
            title="Echo Draft",
            draft=_echo_draft(),
        )
    )
    fetched = asyncio.run(
        handlers.get_draft_workspace(
            workspace_id="echo_draft",
            include_draft=True,
        )
    )

    assert created["workspace_id"] == "echo_draft"
    assert created["revision"] == 1
    assert fetched["draft"]["steps"]["echo"]["use"] == "demo.echo_tool"


def test_workflow_surface_patches_draft_workspace_by_revision() -> None:
    artifact_store = FileWorkflowArtifactStore(
        local_temp_root() / "surface_workspace_patch"
    )
    handlers = _handlers(artifact_store)
    asyncio.run(
        handlers.create_draft_workspace(
            workspace_id="echo_draft",
            draft=_echo_draft(),
        )
    )

    patched = asyncio.run(
        handlers.patch_draft_workspace(
            workspace_id="echo_draft",
            revision=1,
            patch=[
                {
                    "op": "replace",
                    "path": "/steps/echo/in/input.text",
                    "value": "message",
                }
            ],
        )
    )

    assert patched["revision"] == 2
    assert patched["status"] == "valid"
```

- [ ] **Step 2: Run handler tests and verify they fail**

Run:

```powershell
uv run --with pytest pytest tests\wf_mcp\test_workflow_surface.py::test_workflow_surface_creates_and_gets_draft_workspace tests\wf_mcp\test_workflow_surface.py::test_workflow_surface_patches_draft_workspace_by_revision -q
```

Expected: missing handler methods.

- [ ] **Step 3: Implement handler methods**

Modify imports:

```python
from wf_artifacts import (
    create_draft_workspace,
    get_draft_workspace,
    patch_draft_workspace,
)
```

Add helper:

```python
    def _draft_store(self):
        if self.service.draft_workspace_store is None:
            raise KeyError("draft workspace store is not configured")
        return self.service.draft_workspace_store
```

Add methods:

```python
    async def create_draft_workspace(
        self,
        *,
        workspace_id: str,
        draft: dict[str, Any],
        title: str | None = None,
    ) -> dict[str, Any]:
        return create_draft_workspace(
            self._draft_store(),
            workspace_id=workspace_id,
            draft=draft,
            title=title,
        )

    async def get_draft_workspace(
        self,
        *,
        workspace_id: str,
        include_draft: bool = False,
    ) -> dict[str, Any]:
        return get_draft_workspace(
            self._draft_store(),
            workspace_id=workspace_id,
            include_draft=include_draft,
        )

    async def patch_draft_workspace(
        self,
        *,
        workspace_id: str,
        revision: int,
        patch: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return patch_draft_workspace(
            self._draft_store(),
            workspace_id=workspace_id,
            revision=revision,
            patch=patch,
        )
```

Note: In implementation, avoid name shadowing by importing API functions with aliases:

```python
create_draft_workspace as create_draft_workspace_record
```

- [ ] **Step 4: Run handler tests**

Run:

```powershell
uv run --with pytest pytest tests\wf_mcp\test_workflow_surface.py::test_workflow_surface_creates_and_gets_draft_workspace tests\wf_mcp\test_workflow_surface.py::test_workflow_surface_patches_draft_workspace_by_revision -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```powershell
git add src\wf_mcp tests\wf_mcp\test_workflow_surface.py
git commit -m "feat: expose draft workspace handlers"
```

---

## Task 6: Add Minimal Draft Workspace Bootstrapper

**Files:**
- Modify: `src/wf_mcp/workflow_surface/handlers.py`
- Test: `tests/wf_mcp/test_workflow_surface.py`

- [ ] **Step 1: Add failing bootstrap test**

Append:

```python
def test_workflow_surface_creates_minimal_draft_workspace_with_error_route() -> None:
    artifact_store = FileWorkflowArtifactStore(
        local_temp_root() / "surface_minimal_workspace"
    )
    service = WfMcpService(
        store=FileStore(local_temp_root() / "surface_minimal_workspace_mcp"),
        artifact_store=artifact_store,
    )
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_specs("demo.personal", echo_tool)
    handlers = WorkflowSurfaceHandlers(service)

    result = asyncio.run(
        handlers.create_minimal_draft_workspace(
            workspace_id="echo_draft",
            name="echo",
            capability_name="demo.personal.echo_tool",
            input_schema={
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
            state_schema={"fields": {"echoed": {"type": "string"}}},
            output_schema={
                "type": "object",
                "properties": {"echoed": {"type": "string"}},
                "required": ["echoed"],
            },
            input_map={"input.text": "text"},
            output_map={"echoed": "state.echoed"},
        )
    )
    workspace = service.draft_workspace_store.get_workspace("echo_draft")

    assert result["workspace_id"] == "echo_draft"
    assert workspace.draft["routes"]["echo"]["ok"] == "__end__"
    assert workspace.draft["routes"]["echo"]["error"] == "tool_error"
    assert workspace.draft["steps"]["tool_error"]["use"] == "wf.std.runtime_error"
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```powershell
uv run --with pytest pytest tests\wf_mcp\test_workflow_surface.py::test_workflow_surface_creates_minimal_draft_workspace_with_error_route -q
```

Expected: missing handler method.

- [ ] **Step 3: Implement minimal draft builder**

Add method to `WorkflowSurfaceHandlers`:

```python
    async def create_minimal_draft_workspace(
        self,
        *,
        workspace_id: str,
        name: str,
        capability_name: str,
        input_schema: dict[str, Any],
        state_schema: dict[str, Any],
        output_schema: dict[str, Any],
        input_map: dict[str, str],
        output_map: dict[str, str],
        title: str | None = None,
    ) -> dict[str, Any]:
        outcomes = self._outcomes_for_capability(capability_name) or ("ok",)
        steps: dict[str, Any] = {
            "echo": {
                "use": capability_name,
                "in": input_map,
                "out": output_map,
            }
        }
        routes: dict[str, dict[str, str]] = {"echo": {"ok": "__end__"}}
        if "error" in outcomes:
            steps["tool_error"] = {
                "use": "wf.std.runtime_error",
                "in": {"state.echoed": "message"},
                "out": {},
            }
            routes["echo"]["error"] = "tool_error"
            routes["tool_error"] = {"ok": "__end__"}
        draft = {
            "name": name,
            "input_schema": input_schema,
            "state_schema": state_schema,
            "output_schema": output_schema,
            "start": "echo",
            "steps": steps,
            "routes": routes,
        }
        return await self.create_draft_workspace(
            workspace_id=workspace_id,
            title=title,
            draft=draft,
        )
```

Important: The error-route input map is intentionally simple and imperfect.
If the output map does not write a usable error message into state, validation may still pass but runtime may fail. Document this as an initial bootstrapper limitation. A later version can accept `error_message_path`.

- [ ] **Step 4: Run bootstrap test**

Run:

```powershell
uv run --with pytest pytest tests\wf_mcp\test_workflow_surface.py::test_workflow_surface_creates_minimal_draft_workspace_with_error_route -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```powershell
git add src\wf_mcp tests\wf_mcp\test_workflow_surface.py
git commit -m "feat: bootstrap minimal draft workspaces"
```

---

## Task 7: Add Artifact Creation From Workspace

**Files:**
- Modify: `src/wf_mcp/workflow_surface/handlers.py`
- Test: `tests/wf_mcp/test_workflow_surface.py`

- [ ] **Step 1: Add failing artifact-from-workspace test**

Append:

```python
def test_workflow_surface_creates_artifact_from_workspace() -> None:
    artifact_store = FileWorkflowArtifactStore(
        local_temp_root() / "surface_workspace_artifact"
    )
    service = WfMcpService(
        store=FileStore(local_temp_root() / "surface_workspace_artifact_mcp"),
        artifact_store=artifact_store,
    )
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_specs("demo.personal", echo_tool)
    handlers = WorkflowSurfaceHandlers(service)
    asyncio.run(
        handlers.create_draft_workspace(
            workspace_id="echo_draft",
            draft=_echo_draft(),
        )
    )

    result = asyncio.run(
        handlers.create_artifact_from_workspace(
            workspace_id="echo_draft",
            artifact_id="workspace_echo",
            version=1,
            title="Workspace Echo",
            outcomes=("completed",),
            source_bindings={"demo": "demo.personal"},
        )
    )

    artifact = artifact_store.get_artifact("workspace_echo", 1)
    assert result["saved"] is True
    assert artifact.id == "workspace_echo"
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```powershell
uv run --with pytest pytest tests\wf_mcp\test_workflow_surface.py::test_workflow_surface_creates_artifact_from_workspace -q
```

Expected: missing handler method.

- [ ] **Step 3: Implement artifact-from-workspace handler**

Add:

```python
    async def create_artifact_from_workspace(
        self,
        *,
        workspace_id: str,
        artifact_id: str,
        version: int,
        title: str,
        outcomes: Sequence[str],
        kind: ArtifactKind = "workflow",
        description: str | None = None,
        required_capabilities: dict[str, dict[str, Any]] | None = None,
        source_bindings: dict[str, str] | None = None,
        created_from_catalog_version: str | None = None,
    ) -> dict[str, Any]:
        workspace = self._draft_store().get_workspace(workspace_id)
        validation = await self.validate_draft(draft=workspace.draft)
        if validation["status"] != "valid":
            return {
                "saved": False,
                "workspace_id": workspace_id,
                "revision": workspace.revision,
                "status": validation["status"],
                "diagnostics": validation["diagnostics"],
            }
        return await self.create_artifact_from_draft(
            artifact_id=artifact_id,
            version=version,
            title=title,
            kind=kind,
            description=description,
            draft=workspace.draft,
            outcomes=outcomes,
            required_capabilities=required_capabilities,
            source_bindings=source_bindings,
            created_from_catalog_version=created_from_catalog_version,
        )
```

- [ ] **Step 4: Run test**

Run:

```powershell
uv run --with pytest pytest tests\wf_mcp\test_workflow_surface.py::test_workflow_surface_creates_artifact_from_workspace -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```powershell
git add src\wf_mcp tests\wf_mcp\test_workflow_surface.py
git commit -m "feat: save artifacts from draft workspaces"
```

---

## Task 8: Register MCP Workspace Tools

**Files:**
- Modify: `src/wf_mcp/workflow_surface/tools.py`
- Modify: `src/wf_mcp/workflow_surface/models.py`
- Modify: `src/wf_mcp/transparent_proxy/runtime.py`
- Test: `tests/wf_mcp/test_server.py`

- [ ] **Step 1: Add failing MCP tool registration test**

Modify `tests/wf_mcp/test_server.py::test_server_exposes_upstream_admin_and_workflow_tools`:

Add expected names:

```python
assert "wf.workflow.create_draft_workspace" in names
assert "wf.workflow.get_draft_workspace" in names
assert "wf.workflow.patch_draft_workspace" in names
assert "wf.workflow.create_minimal_draft_workspace" in names
assert "wf.workflow.create_artifact_from_workspace" in names
```

Add schema assertion:

```python
create_workspace_schema = tools_by_name[
    "wf.workflow.create_draft_workspace"
].outputSchema
assert create_workspace_schema is not None
assert "workspace_id" in create_workspace_schema["properties"]
assert "revision" in create_workspace_schema["properties"]
```

- [ ] **Step 2: Run server test and verify it fails**

Run:

```powershell
uv run --with pytest pytest tests\wf_mcp\test_server.py::test_server_exposes_upstream_admin_and_workflow_tools -q
```

Expected: missing tool names.

- [ ] **Step 3: Add response model**

Add to `src/wf_mcp/workflow_surface/models.py`:

```python
class DraftWorkspaceResult(BaseModel):
    """Inspector-visible response for draft workspace operations."""

    workspace_id: str
    revision: int
    title: str | None = None
    status: str
    diagnostics: list[dict[str, Any]] = Field(default_factory=list)
    summary: dict[str, Any]
    draft: dict[str, Any] | None = None
```

- [ ] **Step 4: Register tools**

Add to `src/wf_mcp/workflow_surface/tools.py`:

```python
    @server.tool(
        name="wf.workflow.create_draft_workspace",
        title="Create Draft Workspace",
        description="Store a mutable workflow draft workspace for iterative patching.",
    )
    async def create_draft_workspace(
        workspace_id: str,
        draft: dict[str, Any],
        title: str | None = None,
    ) -> DraftWorkspaceResult:
        return DraftWorkspaceResult.model_validate(
            await handlers.create_draft_workspace(
                workspace_id=workspace_id,
                draft=draft,
                title=title,
            )
        )
```

Register the other four tools similarly:

```python
get_draft_workspace(workspace_id: str, include_draft: bool = False)
patch_draft_workspace(workspace_id: str, revision: int, patch: list[dict[str, Any]])
create_minimal_draft_workspace(...)
create_artifact_from_workspace(...)
```

For `create_artifact_from_workspace`, returning `dict[str, Any]` is acceptable if the response already mirrors `create_artifact_from_draft`. If Inspector schema quality matters, add a response model in the same file.

Update `src/wf_mcp/transparent_proxy/runtime.py` allowlist if it has explicit always-visible workflow tools.

- [ ] **Step 5: Run server test**

Run:

```powershell
uv run --with pytest pytest tests\wf_mcp\test_server.py::test_server_exposes_upstream_admin_and_workflow_tools -q
```

Expected: pass.

- [ ] **Step 6: Commit**

```powershell
git add src\wf_mcp tests\wf_mcp\test_server.py
git commit -m "feat: expose draft workspace mcp tools"
```

---

## Task 9: Documentation

**Files:**
- Modify: `docs/workflow_drafts.md`
- Modify: `docs/wf_mcp_operator_manual.md`
- Modify: `docs/wf_mcp_end_to_end_runbook.md`
- Test: none beyond docs lint via ruff

- [ ] **Step 1: Update `docs/workflow_drafts.md`**

Add a section after "Draft Tools":

```markdown
## Draft Workspaces

Stateless draft tools require the caller to resend the whole draft. Draft
workspaces are the preferred LLM authoring flow when a client will patch a
workflow over several turns.

Workflow:

1. `wf.workflow.create_minimal_draft_workspace`
2. `wf.workflow.get_draft_workspace`
3. `wf.workflow.patch_draft_workspace`
4. repeat get/patch until valid
5. `wf.workflow.create_artifact_from_workspace`

Workspaces are mutable and revisioned. Artifacts are immutable and versioned.
Patch calls must include the current `revision`; stale revisions return
`revision_conflict` and do not mutate the workspace.
```

- [ ] **Step 2: Update `docs/wf_mcp_operator_manual.md`**

Add a concise tool family update:

```markdown
| Start a patchable authoring session | `wf.workflow.create_minimal_draft_workspace` |
| Fetch current draft workspace | `wf.workflow.get_draft_workspace` |
| Patch current draft workspace | `wf.workflow.patch_draft_workspace` |
| Save final workspace as artifact | `wf.workflow.create_artifact_from_workspace` |
```

- [ ] **Step 3: Update `docs/wf_mcp_end_to_end_runbook.md`**

Add a workspace-based variant:

```markdown
### Workspace Variant

If the client is iterating with an LLM, prefer a draft workspace:

1. Create a minimal workspace from the selected capability.
2. Patch it by id and revision.
3. Save an artifact from the workspace after validation is clean.

This avoids resending the whole draft object every turn.
```

- [ ] **Step 4: Run docs check**

Run:

```powershell
uvx ruff check docs\workflow_drafts.md docs\wf_mcp_operator_manual.md docs\wf_mcp_end_to_end_runbook.md
```

Expected: pass.

- [ ] **Step 5: Commit**

```powershell
git add docs\workflow_drafts.md docs\wf_mcp_operator_manual.md docs\wf_mcp_end_to_end_runbook.md
git commit -m "docs: describe draft workspace authoring loop"
```

---

## Task 10: Final Verification

**Files:**
- No code changes unless failures require fixes.

- [ ] **Step 1: Run focused test suite**

Run:

```powershell
uv run --with pytest pytest tests\artifacts\test_draft_workspaces.py tests\artifacts\test_draft_api.py tests\wf_mcp\test_workflow_surface.py tests\wf_mcp\test_server.py -q
```

Expected: pass.

- [ ] **Step 2: Run static checks**

Run:

```powershell
uvx ruff check src tests docs
uv run basedpyright --level error
```

Expected: both pass.

- [ ] **Step 3: Run full tests if time allows**

Run:

```powershell
uv run --with pytest pytest -q
```

Expected: all tests pass or known live-only skips.

- [ ] **Step 4: Commit final fixes**

Only if Step 1-3 required additional fixes:

```powershell
git add src tests docs
git commit -m "test: verify draft workspace authoring flow"
```

---

## Self-Review

Spec coverage:

- Mutable server-side draft state: Task 1-5.
- Revisioned JSON Patch loop: Task 3 and Task 5.
- Minimal draft bootstrapper: Task 6.
- Artifact creation from workspace: Task 7.
- MCP-visible tools and schemas: Task 8.
- Documentation: Task 9.
- Verification: Task 10.

No placeholders remain. The only intentionally deferred behavior is richer automatic mapping and richer JSON control flow; both are explicitly out of scope.

Potential implementation risks:

- Name collision between imported API functions and handler methods. Use alias imports in handlers.
- `create_minimal_draft_workspace` error mapping is intentionally simple. If the generated error route needs a better message path later, add `error_message_map` or `error_message_path`.
- Existing `patch_draft` validates without MCP outcome lookup. Workspace patching may initially share that limitation unless handler-level patching calls `validate_draft` after patch. Prefer handler validation with outcome lookup if practical.
