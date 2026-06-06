# wf_sources_mcp Source Registry Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move MCP-as-upstream-source registry models, file store, and conversion helpers from `wf_mcp.source_registry` into canonical `wf_sources_mcp.source_registry` while preserving compatibility imports.

**Architecture:** `wf_sources_mcp` owns MCP upstream source details. `wf_mcp` remains a compatibility facade and old entrypoint package. This slice is a pure move/refactor: no JSON shape changes, no config behavior changes, no live MCP session movement.

**Tech Stack:** Python 3.14, Pydantic v2, pytest, Ruff, basedpyright, `src/` package layout.

---

## Boundaries

Move only source registry code:

- `StdioSourceTransport`
- `HttpSourceTransport`
- `SourceTransport`
- `McpSourceRegistryEntry`
- `SourceRegistryFile`
- `SourceRegistryStore`
- `FileSourceRegistryStore`
- `registry_entry_to_connection_config`
- `connection_config_to_registry_entry`
- `workflow_mcp_source_to_connection_config`

Do not move:

- `wf_mcp.sdk.adapter`
- `wf_mcp.runtime.*`
- `wf_mcp.broker.service.upstream_transport`
- `wf_mcp.capabilities`
- `wf_mcp.catalog.models`
- generic `wf_api.source_registry`
- JSON-RPC or CLI source registry admin surfaces

Temporary dependencies are acceptable if documented:

- `wf_sources_mcp.source_registry` may import `wf_mcp.connections.parse_connection_id` and `wf_mcp.shared.names.RESERVED_CONNECTION_IDS`.
- `wf_sources_mcp.source_registry` may use lazy imports for `wf_mcp.models.ConnectionConfig` to avoid pulling broker runtime DTOs at module import time.

## File Map

Create:

- `src/wf_sources_mcp/source_registry.py` — canonical MCP upstream source registry models/store/conversions.
- `tests/wf_sources_mcp/test_source_registry.py` — canonical tests for moved behavior.

Modify:

- `src/wf_sources_mcp/__init__.py` — export the moved source registry symbols.
- `src/wf_mcp/source_registry.py` — replace with compatibility shim.
- `src/wf_mcp/broker/config.py` — canonical imports from `wf_sources_mcp.source_registry`.
- `src/wf_mcp/broker/server.py` — canonical imports from `wf_sources_mcp.source_registry`.
- `src/wf_mcp/broker/service/connection_service.py` — canonical imports.
- `src/wf_mcp/broker/service/core.py` — canonical imports.
- `src/wf_mcp/broker/service/source_registry_admin.py` — canonical imports.
- `src/wf_mcp/server/core.py` — canonical import for `FileSourceRegistryStore`.
- `tests/wf_mcp/test_compat_imports.py` — shim identity tests.
- Existing tests importing `wf_mcp.source_registry` may stay as compatibility tests unless they are production-facing import examples.
- `docs/current_roadmap.md` — mark source registry slice complete.
- `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md` — mark source registry slice complete.

After implementation, move this plan to:

- `docs/historical/superpowers/plans/2026-06-06-wf-sources-mcp-source-registry-slice.md`

---

### Task 1: Canonical Source Registry Module

**Files:**
- Create: `src/wf_sources_mcp/source_registry.py`
- Modify: `src/wf_sources_mcp/__init__.py`
- Test: `tests/wf_sources_mcp/test_source_registry.py`

- [ ] **Step 1: Create canonical source registry module**

Copy the current contents of `src/wf_mcp/source_registry.py` into `src/wf_sources_mcp/source_registry.py`, then apply these import edits exactly:

```python
from wf_mcp.connections import parse_connection_id
from wf_mcp.shared.names import RESERVED_CONNECTION_IDS
```

Keep this type-checking import:

```python
if TYPE_CHECKING:
    from wf_mcp.models import ConnectionConfig
```

Change lazy runtime imports inside conversion helpers to:

```python
from wf_mcp.models import ConnectionConfig
```

Add this module docstring at the top:

```python
"""MCP upstream-source registry models and conversion helpers.

This module is canonical for MCP-as-source desired registry state. The temporary
runtime dependency on `wf_mcp.models.ConnectionConfig` remains until broker
runtime DTOs move out of the compatibility MCP facade.
"""
```

- [ ] **Step 2: Export symbols from `wf_sources_mcp.__init__`**

Add imports and `__all__` entries for the source registry symbols:

```python
from .source_registry import (
    FileSourceRegistryStore,
    HttpSourceTransport,
    McpSourceRegistryEntry,
    SourceRegistryFile,
    SourceRegistryStore,
    SourceTransport,
    StdioSourceTransport,
    connection_config_to_registry_entry,
    registry_entry_to_connection_config,
    workflow_mcp_source_to_connection_config,
)
```

Ensure `__all__` includes the same symbol names.

- [ ] **Step 3: Add canonical tests**

Create `tests/wf_sources_mcp/test_source_registry.py` with tests copied from `tests/wf_mcp/test_source_registry.py`, but import from `wf_sources_mcp.source_registry`.

Use this import block:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from wf_mcp.models import ConnectionConfig
from wf_sources_mcp.source_registry import (
    FileSourceRegistryStore,
    HttpSourceTransport,
    McpSourceRegistryEntry,
    SourceRegistryFile,
    StdioSourceTransport,
    connection_config_to_registry_entry,
    registry_entry_to_connection_config,
)
```

Keep the existing test bodies unchanged except for import paths.

- [ ] **Step 4: Run canonical tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_source_registry.py -q
```

Expected: all copied canonical source registry tests pass.

---

### Task 2: Replace `wf_mcp.source_registry` With Compatibility Shim

**Files:**
- Modify: `src/wf_mcp/source_registry.py`
- Modify: `tests/wf_mcp/test_compat_imports.py`
- Test: `tests/wf_mcp/test_compat_imports.py`

- [ ] **Step 1: Replace old module with shim**

Replace `src/wf_mcp/source_registry.py` with:

```python
"""Compatibility shim for MCP source registry models.

Canonical implementation lives in `wf_sources_mcp.source_registry`.
"""

from __future__ import annotations

from wf_sources_mcp.source_registry import (
    FileSourceRegistryStore,
    HttpSourceTransport,
    McpSourceRegistryEntry,
    SourceRegistryFile,
    SourceRegistryStore,
    SourceTransport,
    StdioSourceTransport,
    connection_config_to_registry_entry,
    registry_entry_to_connection_config,
    workflow_mcp_source_to_connection_config,
)

__all__ = [
    "FileSourceRegistryStore",
    "HttpSourceTransport",
    "McpSourceRegistryEntry",
    "SourceRegistryFile",
    "SourceRegistryStore",
    "SourceTransport",
    "StdioSourceTransport",
    "connection_config_to_registry_entry",
    "registry_entry_to_connection_config",
    "workflow_mcp_source_to_connection_config",
]
```

- [ ] **Step 2: Add shim identity tests**

Append to `tests/wf_mcp/test_compat_imports.py`:

```python
def test_wf_mcp_source_registry_shim_reexports_wf_sources_mcp_registry() -> None:
    from wf_mcp.source_registry import FileSourceRegistryStore as CompatFileStore
    from wf_mcp.source_registry import McpSourceRegistryEntry as CompatEntry
    from wf_mcp.source_registry import SourceRegistryFile as CompatFile
    from wf_sources_mcp.source_registry import (
        FileSourceRegistryStore,
        McpSourceRegistryEntry,
        SourceRegistryFile,
    )

    assert CompatFileStore is FileSourceRegistryStore
    assert CompatEntry is McpSourceRegistryEntry
    assert CompatFile is SourceRegistryFile
```

- [ ] **Step 3: Run compatibility tests**

Run:

```bash
uv run pytest tests/wf_mcp/test_compat_imports.py tests/wf_mcp/test_source_registry.py -q
```

Expected: compatibility tests and old source registry tests pass.

---

### Task 3: Rewrite Production Imports to Canonical Package

**Files:**
- Modify: `src/wf_mcp/broker/config.py`
- Modify: `src/wf_mcp/broker/server.py`
- Modify: `src/wf_mcp/broker/service/connection_service.py`
- Modify: `src/wf_mcp/broker/service/core.py`
- Modify: `src/wf_mcp/broker/service/source_registry_admin.py`
- Modify: `src/wf_mcp/server/core.py`

- [ ] **Step 1: Rewrite imports**

Change production imports that currently point at `wf_mcp.source_registry` or relative `...source_registry` to `wf_sources_mcp.source_registry`.

Use these canonical import examples:

```python
from wf_sources_mcp.source_registry import (
    FileSourceRegistryStore,
    SourceRegistryStore,
)
```

```python
from wf_sources_mcp.source_registry import (
    SourceRegistryFile,
    connection_config_to_registry_entry,
    registry_entry_to_connection_config,
)
```

```python
from wf_sources_mcp.source_registry import (
    FileSourceRegistryStore,
    workflow_mcp_source_to_connection_config,
)
```

Do not rewrite `tests/` imports in this task except if a test is specifically asserting canonical production wiring.

- [ ] **Step 2: Confirm no production imports use the shim**

Run:

```bash
rg -n "from (\\.\\.|wf_mcp)\\.source_registry|import wf_mcp\\.source_registry|source_registry import" src
```

Expected: no `src/` production import uses `wf_mcp.source_registry` except the shim file itself. Imports from `wf_sources_mcp.source_registry` are expected.

- [ ] **Step 3: Run broker and server focused tests**

Run:

```bash
uv run pytest tests/wf_mcp/service/test_connection_service.py tests/wf_mcp/service/test_source_registry_admin.py tests/wf_mcp/test_broker_server.py tests/wf_mcp/test_mcp_workflow_server.py tests/wf_mcp/server/test_docs.py -q
```

Expected: all focused broker/server source registry tests pass.

---

### Task 4: Strengthen Import Direction Guard

**Files:**
- Modify: `tests/wf_sources_mcp/test_import_direction_guard.py`
- Test: `tests/wf_sources_mcp/test_import_direction_guard.py`

- [ ] **Step 1: Add allowed temporary dependency note**

Update the guard file to include this comment above `FORBIDDEN_WF_MCP_PREFIXES`:

```python
# Temporary low-level wf_mcp imports are allowed for connection id parsing,
# reserved names, and broker DTO conversion. Frontend/proxy/workflow-surface
# imports are forbidden because wf_sources_mcp is upstream-source code.
```

- [ ] **Step 2: Ensure frontend/proxy modules remain forbidden**

Keep these forbidden prefixes:

```python
FORBIDDEN_WF_MCP_PREFIXES = (
    "wf_mcp.admin_surface",
    "wf_mcp.workflow_surface",
    "wf_mcp.server",
    "wf_mcp.proxy",
    "wf_mcp.cli",
)
```

- [ ] **Step 3: Run guard test**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_import_direction_guard.py -q
```

Expected: guard passes.

---

### Task 5: Docs Status and Plan Archival

**Files:**
- Modify: `docs/current_roadmap.md`
- Modify: `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`
- Move: `docs/superpowers/plans/2026-06-06-wf-sources-mcp-source-registry-slice.md` to `docs/historical/superpowers/plans/2026-06-06-wf-sources-mcp-source-registry-slice.md`

- [ ] **Step 1: Update roadmap**

In `docs/current_roadmap.md`, under the MCP package split section, add a short completion note:

```markdown
     Second `wf_sources_mcp` slice complete: MCP desired source registry
     models, file store, and conversion helpers now live in
     `wf_sources_mcp.source_registry`, with `wf_mcp.source_registry` retained
     as a compatibility shim.
```

- [ ] **Step 2: Update long-lived API boundary spec**

In `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`, in the `wf_sources_mcp` status/list section, update the source registry line to mark it complete:

```markdown
2. Complete: MCP source registry models/conversion moved to `wf_sources_mcp.source_registry`, with `wf_mcp.source_registry` retained as a shim.
```

- [ ] **Step 3: Move completed plan to historical**

Run:

```bash
git mv docs/superpowers/plans/2026-06-06-wf-sources-mcp-source-registry-slice.md docs/historical/superpowers/plans/2026-06-06-wf-sources-mcp-source-registry-slice.md
```

Expected: `git status --short` shows an `R` rename for this plan.

---

### Task 6: Final Verification

**Files:**
- All changed files

- [ ] **Step 1: Run focused extraction tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp tests/wf_mcp/test_source_registry.py tests/wf_mcp/test_compat_imports.py tests/wf_mcp/service/test_connection_service.py tests/wf_mcp/service/test_source_registry_admin.py tests/wf_mcp/test_broker_server.py tests/wf_mcp/test_mcp_workflow_server.py -q
```

Expected: all focused tests pass.

- [ ] **Step 2: Run lint and type checks**

Run:

```bash
uv run ruff check src tests
uv run basedpyright --level error src
```

Expected: Ruff reports `All checks passed!`; basedpyright reports `0 errors`.

- [ ] **Step 3: Run full suite**

Run:

```bash
uv run pytest -q
```

Expected: full suite passes with the current expected skip/xfail counts.

- [ ] **Step 4: Review final import shape**

Run:

```bash
rg -n "from wf_mcp\\.source_registry|import wf_mcp\\.source_registry" src tests
```

Expected: only compatibility tests may import `wf_mcp.source_registry`; production code should import `wf_sources_mcp.source_registry`.

- [ ] **Step 5: Report**

Report:

- files created/modified
- focused/full verification output
- whether any temporary `wf_mcp` dependencies remain in `wf_sources_mcp.source_registry`
- whether compatibility shims remain
- deviations from this plan

Do not commit unless the user explicitly asks. If committing, use:

```bash
git add -A
git commit -m "refactor: move mcp source registry to wf_sources_mcp"
```

---

## Self-Review

- Spec coverage: covers the second listed `wf_sources_mcp` slice: source registry models/conversion. Does not move upstream sessions/adapters, by design.
- Placeholder scan: no `TODO`, `TBD`, or unspecified "add tests" steps.
- Type consistency: all moved symbols match the existing `wf_mcp.source_registry` names, preserving compatibility import names and production behavior.
