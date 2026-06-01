# [INVALID] wf_api Slice 1: Dependency Direction — Implementation Plan

> **INVALID — replaced by `2026-06-01-wf-api-slice-1-dependency-direction.md`.**
>
> **Why this plan is wrong:** It moves 13 helper modules (`constants`, `refs`, `next_actions`, `wrapper_hints`, `saved_subgraphs`, `run_lifecycle`, `runtime_dependencies`, `events`, `listing`, `models`) into `wf_api` before the extraction seam is proven. That is a large, risky blast radius for a "dependency direction only" slice. It also defines `WorkflowApiBackend` as a low-level store/execution port rather than a high-level operation protocol, which means the facade does real work instead of delegating. The replacement plan keeps the existing `WorkflowSurfaceHandlers` implementation in `wf_mcp`, wraps it behind a high-level `WorkflowApiBackend` protocol, and introduces `wf_api` as a thin delegating facade — zero helper migration, zero response shape risk.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make both CLI and MCP call a protocol-neutral `WorkflowApi` while `wf_api` imports zero `wf_mcp` modules.

**Architecture:** `WorkflowApi` (renamed `WorkflowSurfaceHandlers`) takes a `WorkflowApiBackend` protocol instead of `WfMcpService`. `WfMcpWorkflowApiBackend` adapts `WfMcpService` into that protocol. Helper modules that `WorkflowApi` needs move from `wf_mcp.workflow_surface` to `wf_api` because they are protocol-neutral and their current location would create `wf_api -> wf_mcp` imports.

**Tech Stack:** Python 3.12+, pydantic, anyio, existing `wf_artifacts`/`wf_platform`/`wf_authoring`/`wf_core` packages.

---

## Import Direction Rules

After this plan is complete, the following rules hold:

```text
wf_api  ->  wf_artifacts, wf_platform, wf_authoring, wf_core   (OK)
wf_api  ->  wf_mcp                                              (FORBIDDEN)
wf_mcp  ->  wf_api                                              (OK — adapter direction)
wf_cli  ->  wf_api                                              (OK)
wf_cli  ->  wf_mcp                                              (OK — config/service construction only)
```

## File Structure

### New files to create

| File | Responsibility |
|------|---------------|
| `src/wf_api/__init__.py` | Package root; re-exports `WorkflowApi`, `WorkflowApiBackend` |
| `src/wf_api/backend.py` | `WorkflowApiBackend` protocol |
| `src/wf_api/service.py` | `WorkflowApi` class (body from `WorkflowSurfaceHandlers`) |
| `src/wf_api/events.py` | `McpEvent` dataclass + `make_event` factory (moved from `wf_mcp.events.models`) |
| `src/wf_api/listing.py` | `matches_query`, `paged_list_payload` (moved from `wf_mcp.shared.listing`) |
| `src/wf_api/models.py` | `RawWorkflowPlan`, `TraceRange` (moved from `wf_mcp.models` + `wf_mcp.workflow_surface.models`) |
| `src/wf_api/constants.py` | Draft helper constants (moved from `wf_mcp.workflow_surface.constants`) |
| `src/wf_api/refs.py` | `parse_workflow_surface_capability_id` (moved from `wf_mcp.workflow_surface.refs`) |
| `src/wf_api/next_actions.py` | `NextActions`, `NextActionTool` (moved from `wf_mcp.workflow_surface.next_actions`) |
| `src/wf_api/wrapper_hints.py` | `wrapper_hints_for_capability` etc. (moved from `wf_mcp.workflow_surface.wrapper_hints`) |
| `src/wf_api/runtime_dependencies.py` | `resolve_runtime_dependencies` (moved from `wf_mcp.workflow_surface.runtime_dependencies`) |
| `src/wf_api/saved_subgraphs.py` | `SavedSubgraphTree` etc. (moved from `wf_mcp.workflow_surface.saved_subgraphs`) |
| `src/wf_api/run_lifecycle.py` | `persist_stopped_run`, `create_pinned_environment` etc. (moved from `wf_mcp.workflow_surface.run_lifecycle`) |
| `src/wf_mcp/broker/service/workflow_api_backend.py` | `WfMcpWorkflowApiBackend` adapter |

### Files to modify

| File | Change |
|------|--------|
| `src/wf_mcp/workflow_surface/handlers.py` | Replace with thin shim: re-export from `wf_api.service` |
| `src/wf_mcp/workflow_surface/constants.py` | Replace with thin shim: re-export from `wf_api.constants` |
| `src/wf_mcp/workflow_surface/refs.py` | Replace with thin shim: re-export from `wf_api.refs` |
| `src/wf_mcp/workflow_surface/next_actions.py` | Replace with thin shim: re-export from `wf_api.next_actions` |
| `src/wf_mcp/workflow_surface/wrapper_hints.py` | Replace with thin shim: re-export from `wf_api.wrapper_hints` |
| `src/wf_mcp/workflow_surface/runtime_dependencies.py` | Replace with thin shim: re-export from `wf_api.runtime_dependencies` |
| `src/wf_mcp/workflow_surface/saved_subgraphs.py` | Replace with thin shim: re-export from `wf_api.saved_subgraphs` |
| `src/wf_mcp/workflow_surface/run_lifecycle.py` | Replace with thin shim: re-export from `wf_api.run_lifecycle` |
| `src/wf_mcp/workflow_surface/models.py` | Update `NextActions` import to `wf_api.next_actions` |
| `src/wf_mcp/workflow_surface/tools.py` | Import `TraceRange` from `wf_api.models`, `WorkflowApi` from `wf_api.service` |
| `src/wf_mcp/workflow_surface/__init__.py` | Keep re-exports (shims make them work) |
| `src/wf_mcp/events/models.py` | Replace with thin shim: re-export from `wf_api.events` |
| `src/wf_mcp/shared/listing.py` | Replace with thin shim: re-export from `wf_api.listing` |
| `src/wf_mcp/shared/__init__.py` | Update `matches_query`/`paged_list_payload` import path |
| `src/wf_cli/context.py` | Import `WorkflowApi` from `wf_api.service` |
| `src/wf_cli/commands/runs.py` | Import `TraceRange` from `wf_api.models` |
| `pyproject.toml` | Add `wf_api` to packages list |

### Files NOT to modify

- `tests/` — shim re-exports preserve all existing import paths; tests pass unchanged
- `examples/` — same; `from wf_mcp.workflow_surface import WorkflowSurfaceHandlers` still works via shim
- `src/wf_mcp/broker/service/core.py` — `WfMcpService` is unchanged
- `src/wf_mcp/workflow_surface/tools.py` internals — only import paths change; tool registration logic unchanged

---

## Risk: Where the Roadmap Might Be Wrong

1. **The roadmap says "keep helper modules in place."** That is not possible for Slice 1. `wf_api.service` imports `constants`, `refs`, `next_actions`, `wrapper_hints`, `saved_subgraphs`, `run_lifecycle`, `runtime_dependencies`, `matches_query`, `paged_list_payload`, `make_event`, and `RawWorkflowPlan` — all from `wf_mcp.*` today. To establish the `wf_api -/-> wf_mcp` rule, these must move. The extraction map confirms this. The roadmap's "not allowed: do not move every helper module yet" is aspirational for later slices but wrong for this one.

2. **The roadmap puts `WfMcpWorkflowApiBackend` in `src/wf_mcp/broker/service/workflow_api_backend.py`.** This is fine but the adapter needs access to `_live_source_diagnostics` (MCP connections/adapters/auth). The plan keeps that function inside the adapter rather than importing it from the old `handlers.py` shim, because the shim re-exports from `wf_api.service` which no longer contains MCP-specific code.

3. **`McpEvent` naming.** The roadmap defers renaming to Slice 2. This plan keeps the name `McpEvent` but moves it to `wf_api.events`. The rename to `DomainEvent` is a Slice 2 concern.

4. **`wf_mcp.workflow_surface.models` stays in `wf_mcp`.** It contains MCP tool request/response pydantic models (507 lines) that `tools.py` needs. Only the `NextActions` import path changes. `TraceRange` is re-exported via the `__init__.py` shim.

---

## Task 1: Create `wf_api` package root

**Files:**
- Create: `src/wf_api/__init__.py`

- [ ] **Step 1: Create the package directory**

```bash
mkdir -p src/wf_api
```

- [ ] **Step 2: Write `__init__.py`**

```python
from __future__ import annotations

from .backend import WorkflowApiBackend
from .service import WorkflowApi

__all__ = ["WorkflowApi", "WorkflowApiBackend"]
```

- [ ] **Step 3: Verify import**

```bash
uv run python -c "from wf_api import WorkflowApi, WorkflowApiBackend; print('OK')"
```

Expected: `OK` (will fail until later tasks populate the modules — that's fine; create the file now and revisit).

- [ ] **Step 4: Commit**

```bash
git add src/wf_api/__init__.py
git commit -m "feat(wf_api): create package root with re-exports"
```

---

## Task 2: Move protocol-neutral helper modules to `wf_api`

These modules have zero `wf_mcp` imports. Moving them is a prerequisite for `wf_api.service` to not import `wf_mcp`.

### Task 2a: Move `constants`

**Files:**
- Create: `src/wf_api/constants.py`
- Modify: `src/wf_mcp/workflow_surface/constants.py` → shim

- [ ] **Step 1: Create `src/wf_api/constants.py`**

```python
"""Shared workflow-surface literals used by generated draft helpers."""

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

- [ ] **Step 2: Replace `src/wf_mcp/workflow_surface/constants.py` with shim**

```python
"""Backward-compatibility shim — canonical location is wf_api.constants."""

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

- [ ] **Step 3: Verify existing tests still pass**

```bash
uv run pytest tests/wf_mcp/workflow_surface/test_drafts.py -q
```

Expected: all pass (imports route through shim).

- [ ] **Step 4: Commit**

```bash
git add src/wf_api/constants.py src/wf_mcp/workflow_surface/constants.py
git commit -m "refactor: move constants to wf_api, leave shim in wf_mcp"
```

### Task 2b: Move `wrapper_hints`

**Files:**
- Create: `src/wf_api/wrapper_hints.py`
- Modify: `src/wf_mcp/workflow_surface/wrapper_hints.py` → shim

- [ ] **Step 1: Copy `src/wf_mcp/workflow_surface/wrapper_hints.py` to `src/wf_api/wrapper_hints.py`**

Use `read` to get the full file content, then `write` it to the new location. Verify the file has no `wf_mcp` imports (it should only import from `pydantic`, `enum`, `typing`).

- [ ] **Step 2: Replace old file with shim**

```python
"""Backward-compatibility shim — canonical location is wf_api.wrapper_hints."""

from wf_api.wrapper_hints import *  # noqa: F401,F403
```

- [ ] **Step 3: Verify**

```bash
uv run pytest tests/wf_mcp/test_workflow_wrapper_hints.py -q
```

Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add src/wf_api/wrapper_hints.py src/wf_mcp/workflow_surface/wrapper_hints.py
git commit -m "refactor: move wrapper_hints to wf_api, leave shim"
```

### Task 2c: Move `refs`

**Files:**
- Create: `src/wf_api/refs.py`
- Modify: `src/wf_mcp/workflow_surface/refs.py` → shim

- [ ] **Step 1: Copy `src/wf_mcp/workflow_surface/refs.py` to `src/wf_api/refs.py`**

Verify: imports only from `wf_artifacts` and `wf_platform`.

- [ ] **Step 2: Replace old file with shim**

```python
"""Backward-compatibility shim — canonical location is wf_api.refs."""

from wf_api.refs import *  # noqa: F401,F403
```

- [ ] **Step 3: Verify**

```bash
uv run pytest tests/wf_mcp/test_workflow_surface_refs.py -q
```

Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add src/wf_api/refs.py src/wf_mcp/workflow_surface/refs.py
git commit -m "refactor: move refs to wf_api, leave shim"
```

### Task 2d: Move `next_actions`

**Files:**
- Create: `src/wf_api/next_actions.py`
- Modify: `src/wf_mcp/workflow_surface/next_actions.py` → shim

- [ ] **Step 1: Copy `src/wf_mcp/workflow_surface/next_actions.py` to `src/wf_api/next_actions.py`**

Update the internal import: change `from .wrapper_hints import WrapperAuthoringHints` to `from wf_api.wrapper_hints import WrapperAuthoringHints`.

- [ ] **Step 2: Replace old file with shim**

```python
"""Backward-compatibility shim — canonical location is wf_api.next_actions."""

from wf_api.next_actions import *  # noqa: F401,F403
```

- [ ] **Step 3: Verify**

```bash
uv run pytest tests/wf_mcp/workflow_surface/test_next_actions.py -q
```

Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add src/wf_api/next_actions.py src/wf_mcp/workflow_surface/next_actions.py
git commit -m "refactor: move next_actions to wf_api, leave shim"
```

### Task 2e: Move `runtime_dependencies`

**Files:**
- Create: `src/wf_api/runtime_dependencies.py`
- Modify: `src/wf_mcp/workflow_surface/runtime_dependencies.py` → shim

- [ ] **Step 1: Copy `src/wf_mcp/workflow_surface/runtime_dependencies.py` to `src/wf_api/runtime_dependencies.py`**

Verify: imports only from `wf_artifacts`, `wf_authoring`, `wf_core`, `wf_platform`. No changes needed.

- [ ] **Step 2: Replace old file with shim**

```python
"""Backward-compatibility shim — canonical location is wf_api.runtime_dependencies."""

from wf_api.runtime_dependencies import *  # noqa: F401,F403
```

- [ ] **Step 3: Commit**

```bash
git add src/wf_api/runtime_dependencies.py src/wf_mcp/workflow_surface/runtime_dependencies.py
git commit -m "refactor: move runtime_dependencies to wf_api, leave shim"
```

### Task 2f: Move `saved_subgraphs`

**Files:**
- Create: `src/wf_api/saved_subgraphs.py`
- Modify: `src/wf_mcp/workflow_surface/saved_subgraphs.py` → shim

- [ ] **Step 1: Copy `src/wf_mcp/workflow_surface/saved_subgraphs.py` to `src/wf_api/saved_subgraphs.py`**

Update internal imports:
- `from ..models import RawWorkflowPlan` → `from wf_api.models import RawWorkflowPlan`
- `from .runtime_dependencies import resolve_runtime_dependencies` → `from wf_api.runtime_dependencies import resolve_runtime_dependencies`

- [ ] **Step 2: Replace old file with shim**

```python
"""Backward-compatibility shim — canonical location is wf_api.saved_subgraphs."""

from wf_api.saved_subgraphs import *  # noqa: F401,F403
```

- [ ] **Step 3: Verify**

```bash
uv run pytest tests/wf_mcp/test_saved_subgraphs.py -q
```

Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add src/wf_api/saved_subgraphs.py src/wf_mcp/workflow_surface/saved_subgraphs.py
git commit -m "refactor: move saved_subgraphs to wf_api, leave shim"
```

### Task 2g: Move `run_lifecycle`

**Files:**
- Create: `src/wf_api/run_lifecycle.py`
- Modify: `src/wf_mcp/workflow_surface/run_lifecycle.py` → shim

- [ ] **Step 1: Copy `src/wf_mcp/workflow_surface/run_lifecycle.py` to `src/wf_api/run_lifecycle.py`**

Update internal import:
- `from .saved_subgraphs import SavedSubgraphTree` → `from wf_api.saved_subgraphs import SavedSubgraphTree`

- [ ] **Step 2: Replace old file with shim**

```python
"""Backward-compatibility shim — canonical location is wf_api.run_lifecycle."""

from wf_api.run_lifecycle import *  # noqa: F401,F403
```

- [ ] **Step 3: Commit**

```bash
git add src/wf_api/run_lifecycle.py src/wf_mcp/workflow_surface/run_lifecycle.py
git commit -m "refactor: move run_lifecycle to wf_api, leave shim"
```

---

## Task 3: Move `events` and `listing` primitives to `wf_api`

### Task 3a: Move `McpEvent` + `make_event` to `wf_api.events`

**Files:**
- Create: `src/wf_api/events.py`
- Modify: `src/wf_mcp/events/models.py` → shim

- [ ] **Step 1: Create `src/wf_api/events.py`**

Copy content from `src/wf_mcp/events/models.py`:

```python
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class McpEvent:
    """Broker-local event record before protocol-specific projection."""

    kind: str
    timestamp_epoch_ms: int
    connection_id: str | None = None
    capability_id: str | None = None
    workflow_name: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)


def make_event(
    kind: str,
    *,
    connection_id: str | None = None,
    capability_id: str | None = None,
    workflow_name: str | None = None,
    payload: dict[str, Any] | None = None,
) -> McpEvent:
    """Create a timestamped event with optional routing metadata."""
    return McpEvent(
        kind=kind,
        timestamp_epoch_ms=int(time.time() * 1000),
        connection_id=connection_id,
        capability_id=capability_id,
        workflow_name=workflow_name,
        payload=payload or {},
    )
```

- [ ] **Step 2: Replace `src/wf_mcp/events/models.py` with shim**

```python
"""Backward-compatibility shim — canonical location is wf_api.events."""

from wf_api.events import McpEvent, make_event

__all__ = ["McpEvent", "make_event"]
```

- [ ] **Step 3: Verify**

```bash
uv run pytest tests/wf_mcp/test_events.py -q
```

Expected: all pass. `wf_mcp.events.bus` imports `McpEvent` from `.models` which re-exports from `wf_api.events`.

- [ ] **Step 4: Commit**

```bash
git add src/wf_api/events.py src/wf_mcp/events/models.py
git commit -m "refactor: move McpEvent/make_event to wf_api.events, leave shim"
```

### Task 3b: Move `matches_query` + `paged_list_payload` to `wf_api.listing`

**Files:**
- Create: `src/wf_api/listing.py`
- Modify: `src/wf_mcp/shared/listing.py` → shim

- [ ] **Step 1: Create `src/wf_api/listing.py`**

Copy content from `src/wf_mcp/shared/listing.py`:

```python
from __future__ import annotations

from collections.abc import Sequence
from typing import Any, TypeVar

from wf_platform import page_items

T = TypeVar("T")


def matches_query(*values: object, query: str | None) -> bool:
    """Return whether a compact discovery row matches a human search query."""
    if query is None:
        return True
    needle = query.strip().casefold()
    if not needle:
        return True
    return any(needle in str(value).casefold() for value in values if value is not None)


def paged_list_payload(
    key: str,
    items: Sequence[T],
    *,
    cursor: str | None,
    limit: int,
) -> dict[str, Any]:
    """Build the common workflow-surface list response shape."""
    page = page_items(items, cursor=cursor, limit=limit)
    return {
        key: list(page.items),
        "next_cursor": page.next_cursor,
        "total": page.total,
    }
```

- [ ] **Step 2: Replace `src/wf_mcp/shared/listing.py` with shim**

```python
"""Backward-compatibility shim — canonical location is wf_api.listing."""

from wf_api.listing import matches_query, paged_list_payload

__all__ = ["matches_query", "paged_list_payload"]
```

- [ ] **Step 3: Update `src/wf_mcp/shared/__init__.py`**

Change the import source for `matches_query` and `paged_list_payload` from `.listing` to keep working (the shim handles it, but update for clarity):

```python
from .errors import error_payload, root_exception
from .listing import matches_query, paged_list_payload  # routes through shim to wf_api
from .names import (
    ADMIN_NAMESPACE,
    LdaNamespace,
    ProxyNamespace,
    ProxyToolName,
    connection_id_to_resource_path,
    is_admin_tool_name,
    namespaced_tool_name,
    parse_namespaced_tool_name,
)
from .pagination import clamp_limit, make_cursor, paginate_items, parse_cursor

__all__ = [
    "ADMIN_NAMESPACE",
    "LdaNamespace",
    "ProxyNamespace",
    "ProxyToolName",
    "connection_id_to_resource_path",
    "clamp_limit",
    "error_payload",
    "is_admin_tool_name",
    "make_cursor",
    "matches_query",
    "namespaced_tool_name",
    "paged_list_payload",
    "paginate_items",
    "parse_cursor",
    "parse_namespaced_tool_name",
    "root_exception",
]
```

No change needed — `from .listing import ...` still works because the shim re-exports.

- [ ] **Step 4: Commit**

```bash
git add src/wf_api/listing.py src/wf_mcp/shared/listing.py
git commit -m "refactor: move listing helpers to wf_api.listing, leave shim"
```

---

## Task 4: Move `RawWorkflowPlan` and `TraceRange` to `wf_api.models`

**Files:**
- Create: `src/wf_api/models.py`
- Modify: `src/wf_mcp/models.py` → add re-export shim for `RawWorkflowPlan`
- Modify: `src/wf_mcp/workflow_surface/models.py` → update `NextActions` import

- [ ] **Step 1: Create `src/wf_api/models.py`**

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field
from wf_core import Edge
from wf_core.models.steps import InputBinding, Step


class RawWorkflowPlan(BaseModel):
    """Raw authoring plan using the same graph step and edge models as core."""

    name: str
    input_schema: dict[str, Any]
    state_schema: dict[str, Any]
    output_schema: dict[str, Any]
    outcomes: list[str] = Field(
        default_factory=lambda: ["ok"],
        description=(
            "Declared public workflow outcomes. Legacy plans without this field "
            "default to ok."
        ),
    )
    output: list[InputBinding] = Field(
        default_factory=list,
        description=(
            "Optional root workflow output bindings. Sources read graph paths "
            "such as state.result and targets write the public output payload."
        ),
    )
    start: str
    nodes: list[Step]
    edges: list[Edge]


@dataclass(frozen=True, slots=True)
class TraceRange:
    """Caller-bounded debug trace slice for durable deployment runs."""

    start: int = 0
    limit: int = 20
```

Note: `RawWorkflowPlan` content comes from `src/wf_mcp/models.py:45-68`. `TraceRange` content comes from `src/wf_mcp/workflow_surface/models.py` — grep for `class TraceRange` to get the exact definition.

- [ ] **Step 2: Add re-export shim at bottom of `src/wf_mcp/models.py`**

Append to the end of `src/wf_mcp/models.py`:

```python
# Backward-compatibility re-export — canonical location is wf_api.models
from wf_api.models import RawWorkflowPlan as RawWorkflowPlan
```

This shadows the local `RawWorkflowPlan` class. Keep the local class definition for now so other `wf_mcp` code that imports `RawWorkflowPlan` from `wf_mcp.models` continues to work. The re-export ensures `from wf_mcp.models import RawWorkflowPlan` resolves to the `wf_api` version.

**Alternative (cleaner):** Remove the local `RawWorkflowPlan` class from `wf_mcp/models.py` entirely and keep only the re-export. This is preferred if no other `wf_mcp` code defines behavior on the local class.

- [ ] **Step 3: Update `src/wf_mcp/workflow_surface/models.py` imports**

Change line 7 from:
```python
from .next_actions import NextActionPatchExample, NextActions
```
to:
```python
from wf_api.next_actions import NextActionPatchExample, NextActions
```

Also add a re-export for `TraceRange` at the bottom of the file (for `wf_mcp.workflow_surface.__init__.py`):

```python
# Backward-compatibility re-export — canonical location is wf_api.models
from wf_api.models import TraceRange as TraceRange
```

- [ ] **Step 4: Verify**

```bash
uv run pytest tests/wf_mcp/workflow_surface/test_drafts.py tests/wf_mcp/workflow_surface/test_runs.py -q
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/wf_api/models.py src/wf_mcp/models.py src/wf_mcp/workflow_surface/models.py
git commit -m "refactor: move RawWorkflowPlan and TraceRange to wf_api.models"
```

---

## Task 5: Create `WorkflowApiBackend` protocol

**Files:**
- Create: `src/wf_api/backend.py`

- [ ] **Step 1: Write `src/wf_api/backend.py`**

```python
from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Protocol, runtime_checkable

from wf_artifacts import (
    DraftWorkspaceStore,
    RunStore,
    WorkflowArtifact,
    WorkflowArtifactCatalogEntry,
    WorkflowArtifactStore,
    WorkflowDeployment,
)
from wf_authoring import NodeSpec
from wf_platform import CapabilitySource

from .events import McpEvent


@runtime_checkable
class WorkflowApiBackend(Protocol):
    """Protocol that WorkflowApi requires from its host service.

    Implementations adapt a concrete service (e.g. WfMcpService) into this
    interface so that wf_api never imports wf_mcp.
    """

    @property
    def artifact_store(self) -> WorkflowArtifactStore | None: ...

    @property
    def draft_workspace_store(self) -> DraftWorkspaceStore | None: ...

    @property
    def run_store(self) -> RunStore | None: ...

    @property
    def capability_sources(self) -> dict[str, CapabilitySource]: ...

    def get_qualified_spec(self, qualified_name: str) -> NodeSpec[Any, Any]:
        """Return the executable NodeSpec for a fully-qualified capability name."""
        ...

    def record_event(self, event: McpEvent) -> None:
        """Publish one domain event."""
        ...

    async def run_workflow_from_plan(
        self,
        plan: Any,
        workflow_input: dict[str, Any],
        *,
        deployment: WorkflowDeployment | None = None,
        artifact: WorkflowArtifact | None = None,
        saved_subgraph_tree: Any | None = None,
    ) -> Any:
        """Execute a compiled workflow plan and return the run state."""
        ...

    async def resume_workflow_from_plan(
        self,
        plan: Any,
        run: Any,
        *,
        resume_payload: dict[str, Any],
        resume_outcome: str = "submitted",
        deployment: WorkflowDeployment | None = None,
        artifact: WorkflowArtifact | None = None,
        saved_subgraph_tree: Any | None = None,
    ) -> Any:
        """Resume a stopped workflow run."""
        ...

    def workflow_artifact_catalog_entry(
        self,
        artifact: WorkflowArtifact,
    ) -> WorkflowArtifactCatalogEntry:
        """Project a saved artifact as a planner catalog entry."""
        ...

    async def check_source_liveness(
        self,
        *,
        deployment: WorkflowDeployment,
        artifacts: Sequence[WorkflowArtifact],
    ) -> list[Any]:
        """Run opt-in live connectivity checks for bound upstream sources.

        Default implementation returns empty list. MCP adapter overrides
        with actual connection/adapter/auth probe.
        """
        ...
```

- [ ] **Step 2: Verify import**

```bash
uv run python -c "from wf_api.backend import WorkflowApiBackend; print('OK')"
```

Expected: `OK`.

- [ ] **Step 3: Commit**

```bash
git add src/wf_api/backend.py
git commit -m "feat(wf_api): add WorkflowApiBackend protocol"
```

---

## Task 6: Create `WorkflowApi` service

**Files:**
- Create: `src/wf_api/service.py`

- [ ] **Step 1: Write `src/wf_api/service.py`**

This is the largest step. The body is `WorkflowSurfaceHandlers` from `src/wf_mcp/workflow_surface/handlers.py` with these changes:

1. **Class name:** `WorkflowSurfaceHandlers` → `WorkflowApi`
2. **Constructor:** `self.service: WfMcpService` → `self.backend: WorkflowApiBackend`
3. **All `self.service.X`** → `self.backend.X` (property access)
4. **All `self.service._get_qualified_spec(...)`** → `self.backend.get_qualified_spec(...)`
5. **All `self.service._record_event(...)`** → `self.backend.record_event(...)`
6. **All `self.service.run_workflow_from_plan(...)`** → `self.backend.run_workflow_from_plan(...)`
7. **All `self.service.resume_workflow_from_plan(...)`** → `self.backend.resume_workflow_from_plan(...)`
8. **All `self.service.workflow_artifact_catalog_entry(...)`** → `self.backend.workflow_artifact_catalog_entry(...)`
9. **`_live_source_diagnostics(self.service, ...)`** → `self.backend.check_source_liveness(deployment=..., artifacts=...)`
10. **`_observed_node_specs(self.service)`** → `_observed_node_specs(self.backend)` (update function signature)
11. **`_available_sources(self.service)`** → `_available_sources(self.backend)` (update function signature)
12. **`_required_capabilities_for_plan(..., service=self.service)`** → `_required_capabilities_for_plan(..., backend=self.backend)`

**Import changes** (top of file):
- Remove: `from ..broker.service.adapters import require_adapter`
- Remove: `from ..events import make_event`
- Remove: `from ..models import RawWorkflowPlan`
- Remove: `from ..shared import matches_query, paged_list_payload`
- Remove: `if TYPE_CHECKING: from ..broker.service import WfMcpService`
- Remove: `import anyio`, `import httpx`, `from mcp.client.streamable_http import StreamableHTTPError`, `from mcp.shared.exceptions import McpError`
- Remove: `LIVE_SOURCE_CHECK_TIMEOUT_SECONDS`, `_LIVE_SOURCE_CHECK_FAILURES`
- Add: `from .backend import WorkflowApiBackend`
- Add: `from .events import make_event`
- Add: `from .listing import matches_query, paged_list_payload`
- Add: `from .models import RawWorkflowPlan`
- Update all `.constants`, `.models`, `.refs`, `.next_actions`, `.saved_subgraphs`, `.run_lifecycle`, `.wrapper_hints` to `wf_api.*`

**Module-level helpers to update:**
- `_available_sources(service: WfMcpService)` → `_available_sources(backend: WorkflowApiBackend)` — change `service.capability_sources` to `backend.capability_sources`
- `_observed_node_specs(service: WfMcpService)` → `_observed_node_specs(backend: WorkflowApiBackend)` — change `service.capability_sources` to `backend.capability_sources`
- `_required_capabilities_for_plan(..., service: WfMcpService)` → `_required_capabilities_for_plan(..., backend: WorkflowApiBackend)` — change `service` references to `backend`
- **Remove** `_live_source_diagnostics` function entirely (it moves into the adapter)
- **Remove** `_required_live_sources` function (it moves into the adapter)
- **Remove** `LIVE_SOURCE_CHECK_TIMEOUT_SECONDS` and `_LIVE_SOURCE_CHECK_FAILURES` constants

**`validate_deployment` method change:**
```python
async def validate_deployment(
    self,
    *,
    deployment_id: str,
    live_check: bool = False,
) -> dict[str, Any]:
    deployment, artifact, diagnostics, tree = self._deployment_validation(
        deployment_id
    )
    if live_check:
        diagnostics.extend(
            await self.backend.check_source_liveness(
                deployment=deployment,
                artifacts=[artifact, *tree.artifacts_by_ref.values()],
            )
        )
    # ... rest unchanged
```

- [ ] **Step 2: Verify import**

```bash
uv run python -c "from wf_api.service import WorkflowApi; print('OK')"
```

Expected: `OK`.

- [ ] **Step 3: Commit**

```bash
git add src/wf_api/service.py
git commit -m "feat(wf_api): add WorkflowApi service"
```

---

## Task 7: Replace `handlers.py` with shim

**Files:**
- Modify: `src/wf_mcp/workflow_surface/handlers.py`

- [ ] **Step 1: Replace entire file with shim**

```python
"""Backward-compatibility shim — canonical location is wf_api.service."""

from wf_api.service import WorkflowApi as WorkflowSurfaceHandlers

__all__ = ["WorkflowSurfaceHandlers"]
```

- [ ] **Step 2: Verify all workflow surface tests pass**

```bash
uv run pytest tests/wf_mcp/workflow_surface/ -q
```

Expected: all pass. Tests import `WorkflowSurfaceHandlers` from `wf_mcp.workflow_surface` which re-exports from `wf_api.service`.

- [ ] **Step 3: Commit**

```bash
git add src/wf_mcp/workflow_surface/handlers.py
git commit -m "refactor: replace handlers.py with shim to wf_api.service"
```

---

## Task 8: Create `WfMcpWorkflowApiBackend` adapter

**Files:**
- Create: `src/wf_mcp/broker/service/workflow_api_backend.py`

- [ ] **Step 1: Write `src/wf_mcp/broker/service/workflow_api_backend.py`**

```python
from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Any

import anyio
import httpx
from mcp.client.streamable_http import StreamableHTTPError
from mcp.shared.exceptions import McpError

from wf_api.backend import WorkflowApiBackend
from wf_api.events import McpEvent
from wf_artifacts import (
    DependencyDiagnostic,
    DiagnosticSeverity,
    DraftWorkspaceStore,
    RunStore,
    WorkflowArtifact,
    WorkflowArtifactCatalogEntry,
    WorkflowArtifactStore,
    WorkflowDeployment,
)
from wf_authoring import NodeSpec
from wf_platform import CapabilitySource

from .adapters import require_adapter
from .core import WfMcpService

LIVE_SOURCE_CHECK_TIMEOUT_SECONDS = 8.0
_LIVE_SOURCE_CHECK_FAILURES = (
    KeyError,
    TimeoutError,
    OSError,
    anyio.ClosedResourceError,
    anyio.EndOfStream,
    anyio.BrokenResourceError,
    httpx.HTTPError,
    McpError,
    StreamableHTTPError,
)


class WfMcpWorkflowApiBackend:
    """Adapt WfMcpService into the WorkflowApiBackend protocol."""

    def __init__(self, service: WfMcpService) -> None:
        self._service = service

    @property
    def artifact_store(self) -> WorkflowArtifactStore | None:
        return self._service.artifact_store

    @property
    def draft_workspace_store(self) -> DraftWorkspaceStore | None:
        return self._service.draft_workspace_store

    @property
    def run_store(self) -> RunStore | None:
        return self._service.run_store

    @property
    def capability_sources(self) -> dict[str, CapabilitySource]:
        return self._service.capability_sources

    def get_qualified_spec(self, qualified_name: str) -> NodeSpec[Any, Any]:
        return self._service._get_qualified_spec(qualified_name)

    def record_event(self, event: McpEvent) -> None:
        self._service._record_event(event)

    async def run_workflow_from_plan(
        self,
        plan: Any,
        workflow_input: dict[str, Any],
        *,
        deployment: WorkflowDeployment | None = None,
        artifact: WorkflowArtifact | None = None,
        saved_subgraph_tree: Any | None = None,
    ) -> Any:
        return await self._service.run_workflow_from_plan(
            plan,
            workflow_input,
            deployment=deployment,
            artifact=artifact,
            saved_subgraph_tree=saved_subgraph_tree,
        )

    async def resume_workflow_from_plan(
        self,
        plan: Any,
        run: Any,
        *,
        resume_payload: dict[str, Any],
        resume_outcome: str = "submitted",
        deployment: WorkflowDeployment | None = None,
        artifact: WorkflowArtifact | None = None,
        saved_subgraph_tree: Any | None = None,
    ) -> Any:
        return await self._service.resume_workflow_from_plan(
            plan,
            run,
            resume_payload=resume_payload,
            resume_outcome=resume_outcome,
            deployment=deployment,
            artifact=artifact,
            saved_subgraph_tree=saved_subgraph_tree,
        )

    def workflow_artifact_catalog_entry(
        self,
        artifact: WorkflowArtifact,
    ) -> WorkflowArtifactCatalogEntry:
        return self._service.workflow_artifact_catalog_entry(artifact)

    async def check_source_liveness(
        self,
        *,
        deployment: WorkflowDeployment,
        artifacts: Sequence[WorkflowArtifact],
    ) -> list[DependencyDiagnostic]:
        return await _live_source_diagnostics(
            self._service,
            deployment=deployment,
            artifacts=artifacts,
        )


async def _live_source_diagnostics(
    service: WfMcpService,
    *,
    deployment: WorkflowDeployment,
    artifacts: Sequence[WorkflowArtifact],
) -> list[DependencyDiagnostic]:
    """MCP-specific live connectivity probe for bound upstream sources."""
    diagnostics: list[DependencyDiagnostic] = []
    bindings = deployment.binding_map()
    required: dict[str, str] = {}
    for artifact in artifacts:
        for logical_ref, capability in artifact.required_capability_map().items():
            source_id = bindings.get(capability.logical_source)
            if source_id is not None:
                required.setdefault(source_id, logical_ref)

    for source_id, logical_ref in required.items():
        source = service.capability_sources.get(source_id)
        if (
            source is None
            or not source.enabled
            or not source.permissions.calls_upstream
        ):
            continue
        try:
            connection = service.connections.get(source_id)
            adapter = require_adapter(connection, service.adapters)
            auth = service.load_auth(source_id)
            await asyncio.wait_for(
                adapter.list_tools(connection, auth),
                timeout=LIVE_SOURCE_CHECK_TIMEOUT_SECONDS,
            )
        except _LIVE_SOURCE_CHECK_FAILURES as exc:
            diagnostics.append(
                DependencyDiagnostic(
                    severity=DiagnosticSeverity.ERROR,
                    code="source_unreachable",
                    logical_ref=logical_ref,
                    bound_source=source_id,
                    message=(
                        f"Live check for upstream source {source_id!r} failed: "
                        f"{type(exc).__name__}: {exc}"
                    ),
                    repair_hint=(
                        "Start or reconnect the source, fix its transport/auth "
                        "configuration, or bind this deployment to another source."
                    ),
                )
            )
    return diagnostics
```

- [ ] **Step 2: Verify import**

```bash
uv run python -c "from wf_mcp.broker.service.workflow_api_backend import WfMcpWorkflowApiBackend; print('OK')"
```

Expected: `OK`.

- [ ] **Step 3: Commit**

```bash
git add src/wf_mcp/broker/service/workflow_api_backend.py
git commit -m "feat(wf_mcp): add WfMcpWorkflowApiBackend adapter"
```

---

## Task 9: Update MCP tool registration to use `WorkflowApi`

**Files:**
- Modify: `src/wf_mcp/workflow_surface/tools.py`

- [ ] **Step 1: Update imports in `src/wf_mcp/workflow_surface/tools.py`**

Change:
```python
from wf_mcp.broker.service import WfMcpService
from .handlers import WorkflowSurfaceHandlers
from .models import (
    ...,
    TraceRange,
    ...
)
```

To:
```python
from wf_api.service import WorkflowApi
from wf_api.models import TraceRange
from wf_mcp.broker.service import WfMcpService
from wf_mcp.broker.service.workflow_api_backend import WfMcpWorkflowApiBackend
from .models import (
    ...,
    # Remove TraceRange from this import
    ...
)
```

- [ ] **Step 2: Update `register_workflow_tools` function body**

Change:
```python
def register_workflow_tools(server: FastMCP[Any], service: WfMcpService) -> None:
    """Register stable workflow tools on the public MCP server surface."""
    handlers = WorkflowSurfaceHandlers(service)
```

To:
```python
def register_workflow_tools(server: FastMCP[Any], service: WfMcpService) -> None:
    """Register stable workflow tools on the public MCP server surface."""
    handlers = WorkflowApi(WfMcpWorkflowApiBackend(service))
```

All references to `handlers.X(...)` remain unchanged — `WorkflowApi` has the same methods.

- [ ] **Step 3: Verify all workflow surface tests pass**

```bash
uv run pytest tests/wf_mcp/workflow_surface/ -q
```

Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add src/wf_mcp/workflow_surface/tools.py
git commit -m "refactor: use WorkflowApi in MCP tool registration"
```

---

## Task 10: Update `wf_cli.context` to use `WorkflowApi`

**Files:**
- Modify: `src/wf_cli/context.py`

- [ ] **Step 1: Update imports**

Change:
```python
from wf_mcp.workflow_surface import WorkflowSurfaceHandlers
```

To:
```python
from wf_api import WorkflowApi
from wf_mcp.broker.service.workflow_api_backend import WfMcpWorkflowApiBackend
```

- [ ] **Step 2: Update `CliContext` dataclass**

Change:
```python
@dataclass(frozen=True)
class CliContext:
    config_path: Path
    service: WfMcpService
    handlers: WorkflowSurfaceHandlers
```

To:
```python
@dataclass(frozen=True)
class CliContext:
    config_path: Path
    service: WfMcpService
    handlers: WorkflowApi
```

- [ ] **Step 3: Update `load_cli_context` function**

Change:
```python
def load_cli_context(config_path: str | Path) -> CliContext:
    resolved_config_path = Path(config_path)
    config = load_broker_config(resolved_config_path)
    service = build_service_from_config(config)
    return CliContext(
        config_path=resolved_config_path,
        service=service,
        handlers=WorkflowSurfaceHandlers(service),
    )
```

To:
```python
def load_cli_context(config_path: str | Path) -> CliContext:
    resolved_config_path = Path(config_path)
    config = load_broker_config(resolved_config_path)
    service = build_service_from_config(config)
    return CliContext(
        config_path=resolved_config_path,
        service=service,
        handlers=WorkflowApi(WfMcpWorkflowApiBackend(service)),
    )
```

- [ ] **Step 4: Update `src/wf_cli/commands/runs.py`**

Change:
```python
from wf_mcp.workflow_surface import TraceRange
```

To:
```python
from wf_api.models import TraceRange
```

- [ ] **Step 5: Verify CLI tests pass**

```bash
uv run pytest tests/wf_cli/ -q
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/wf_cli/context.py src/wf_cli/commands/runs.py
git commit -m "refactor: use WorkflowApi in CLI context"
```

---

## Task 11: Add `wf_api` to `pyproject.toml` packages

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Find the packages list in `pyproject.toml`**

Grep for `packages` or `find` in the `[tool.setuptools]` or `[tool.hatch]` section.

- [ ] **Step 2: Add `src/wf_api` to the packages list**

If using `find`:
```toml
[tool.setuptools.packages.find]
where = ["src"]
```

This should auto-discover `wf_api`. If packages are listed explicitly, add `"wf_api"`.

- [ ] **Step 3: Verify package is importable**

```bash
uv run python -c "from wf_api import WorkflowApi, WorkflowApiBackend; print('OK')"
```

Expected: `OK`.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "build: add wf_api to package discovery"
```

---

## Task 12: Full test suite verification

- [ ] **Step 1: Run all workflow surface tests**

```bash
uv run pytest tests/wf_mcp/workflow_surface/ -q
```

Expected: all pass.

- [ ] **Step 2: Run all CLI tests**

```bash
uv run pytest tests/wf_cli/ -q
```

Expected: all pass.

- [ ] **Step 3: Run all MCP tests**

```bash
uv run pytest tests/wf_mcp/ -q
```

Expected: all pass.

- [ ] **Step 4: Run full test suite**

```bash
uv run pytest -q
```

Expected: all pass.

- [ ] **Step 5: Verify import direction rule**

```bash
uv run python -c "
import ast, sys

violations = []
for mod in ['wf_api.service', 'wf_api.backend', 'wf_api.events', 'wf_api.listing',
            'wf_api.models', 'wf_api.constants', 'wf_api.refs', 'wf_api.next_actions',
            'wf_api.wrapper_hints', 'wf_api.runtime_dependencies', 'wf_api.saved_subgraphs',
            'wf_api.run_lifecycle']:
    try:
        file_path = mod.replace('.', '/') + '.py'
        with open(file_path) as f:
            tree = ast.parse(f.read())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith('wf_mcp'):
                violations.append(f'{mod}: from {node.module} import ...')
    except FileNotFoundError:
        pass

if violations:
    print('VIOLATIONS:')
    for v in violations:
        print(f'  {v}')
    sys.exit(1)
else:
    print('OK: wf_api has no wf_mcp imports')
"
```

Expected: `OK: wf_api has no wf_mcp imports`.

- [ ] **Step 6: Run lint/typecheck**

```bash
uv run ruff check src/wf_api/ src/wf_mcp/workflow_surface/ src/wf_cli/context.py src/wf_mcp/broker/service/workflow_api_backend.py
uv run basedpyright --level error
```

Expected: no new errors.

---

## Task 13: Final commit — all changes

- [ ] **Step 1: Verify clean working tree**

```bash
git status
```

Expected: no uncommitted changes (all tasks committed individually).

- [ ] **Step 2: Verify commit log**

```bash
git log --oneline -15
```

Expected: all task commits visible.

---

## Rollback / Compatibility Notes

1. **Shim-based rollback:** Every moved module has a shim in its original location. To rollback, replace each shim with the original file content and delete the `wf_api/` package.

2. **`CliContext.handlers` attribute name preserved:** All CLI command code uses `context.handlers.X()`. The attribute name `handlers` is unchanged; only the type changes from `WorkflowSurfaceHandlers` to `WorkflowApi`.

3. **`wf_mcp.workflow_surface.__init__.py` re-exports preserved:** `from wf_mcp.workflow_surface import WorkflowSurfaceHandlers` still works via the `handlers.py` shim. Same for `TraceRange`.

4. **Test monkeypatch paths preserved:** Tests that `patch("wf_cli.commands.runs.load_cli_context", ...)` still work because `load_cli_context` is still the function being patched. The patched function constructs `WorkflowApi` instead of `WorkflowSurfaceHandlers`, but the mock replaces the whole function.

5. **`WfMcpService` unchanged:** The `WfMcpService` class itself is not modified. The adapter wraps it without changing its behavior.

6. **`live_check` behavior preserved:** `validate_deployment(live_check=True)` calls `self.backend.check_source_liveness(...)`. The MCP adapter implements this with the same `_live_source_diagnostics` logic (connections, adapters, auth probe). Non-MCP backends can return an empty list or implement their own liveness checks.

7. **Event naming unchanged:** `McpEvent` keeps its name. Renaming to `DomainEvent` is a Slice 2 concern.

---

## Verification Commands Summary

```bash
# Per-task verification
uv run pytest tests/wf_mcp/workflow_surface/ -q
uv run pytest tests/wf_cli/ -q
uv run pytest tests/wf_mcp/ -q

# Full suite
uv run pytest -q

# Import direction check
uv run python -c "
import ast, sys
violations = []
for mod in ['wf_api.service', 'wf_api.backend', 'wf_api.events', 'wf_api.listing',
            'wf_api.models', 'wf_api.constants', 'wf_api.refs', 'wf_api.next_actions',
            'wf_api.wrapper_hints', 'wf_api.runtime_dependencies', 'wf_api.saved_subgraphs',
            'wf_api.run_lifecycle']:
    try:
        file_path = mod.replace('.', '/') + '.py'
        with open(file_path) as f:
            tree = ast.parse(f.read())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith('wf_mcp'):
                violations.append(f'{mod}: from {node.module} import ...')
    except FileNotFoundError:
        pass
if violations:
    print('VIOLATIONS:'); [print(f'  {v}') for v in violations]; sys.exit(1)
else:
    print('OK: wf_api has no wf_mcp imports')
"

# Lint
uv run ruff check src/wf_api/
uv run basedpyright --level error
```
