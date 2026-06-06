# wf_sources_mcp Auth And Storage Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create the first `wf_sources_mcp` package slice by moving MCP upstream-source auth helpers and focused auth/catalog stores out of the combined `wf_mcp` facade.

**Architecture:** `wf_sources_mcp` becomes the package for MCP-as-upstream-source behavior. This first slice moves leaf modules only: auth DTO/helpers and auth/catalog file stores. `wf_mcp.auth` and `wf_mcp.storage` remain compatibility shims so existing imports keep working.

**Tech Stack:** Python package shims, dataclasses, existing file stores, pytest import-identity tests, AST import-direction guard, ruff, basedpyright.

---

## File Map

- Create: `src/wf_sources_mcp/__init__.py`
- Create: `src/wf_sources_mcp/auth.py`
- Create: `src/wf_sources_mcp/storage/__init__.py`
- Create: `src/wf_sources_mcp/storage/store.py`
- Modify: `src/wf_mcp/auth.py` into a re-export shim.
- Modify: `src/wf_mcp/storage/__init__.py` into a re-export shim.
- Modify: `src/wf_mcp/storage/store.py` into a re-export shim.
- Modify production imports in MCP upstream-source code to use canonical `wf_sources_mcp` paths where low-risk.
- Add: `tests/wf_sources_mcp/test_import_direction.py`
- Add: `tests/wf_sources_mcp/test_auth_storage_exports.py`
- Modify: existing `tests/wf_mcp/test_auth.py`, `tests/wf_mcp/test_store.py`, and compatibility import tests only as needed.
- Modify docs: `docs/current_roadmap.md`, `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`.

---

## Hard Boundaries

- Do not move upstream transport/session/runtime services in this slice.
- Do not move source registry models in this slice.
- Do not change on-disk JSON shapes.
- Do not remove `wf_mcp.auth`, `wf_mcp.storage`, or `wf_mcp.storage.store`; they become compatibility shims.
- `wf_sources_mcp` must not import:
  - `wf_mcp.workflow_surface`
  - `wf_mcp.admin_surface`
  - `wf_mcp.server`
  - `wf_mcp.proxy`
  - `wf_mcp.cli`
- Temporary imports from neutral/core packages are fine: `wf_api`, `wf_artifacts`, `wf_mcp.capabilities`, `wf_mcp.connections`, and `wf_mcp.catalog.models`. If a temporary `wf_mcp.*` import is needed for catalog entry/connection types, document it in the file docstring or test comment.

---

## Task 1: Create Package And Move Auth Module

**Files:**
- Create: `src/wf_sources_mcp/__init__.py`
- Create: `src/wf_sources_mcp/auth.py`
- Modify: `src/wf_mcp/auth.py`
- Test: `tests/wf_sources_mcp/test_auth_storage_exports.py`

- [ ] **Step 1: Add failing canonical auth export test**

Create `tests/wf_sources_mcp/test_auth_storage_exports.py` with:

```python
from __future__ import annotations

from wf_api.auth import AuthRecord as NeutralAuthRecord
from wf_sources_mcp.auth import (
    AuthRecord,
    mcp_auth_env,
    mcp_auth_from_neutral,
    mcp_auth_headers,
    neutral_auth_from_mcp,
)


def test_wf_sources_mcp_auth_round_trips_neutral_record() -> None:
    neutral = NeutralAuthRecord(
        id="github.work",
        scheme="bearer",
        payload={"token": "secret", "env": {"GITHUB_TOKEN": "secret"}},
    )

    mcp = mcp_auth_from_neutral(neutral)
    round_trip = neutral_auth_from_mcp(mcp)

    assert isinstance(mcp, AuthRecord)
    assert mcp.connection_id == "github.work"
    assert round_trip.id == "github.work"
    assert round_trip.scheme == "bearer"
    assert round_trip.payload["token"] == "secret"


def test_wf_sources_mcp_auth_adapters_interpret_mcp_payload() -> None:
    auth = AuthRecord(
        connection_id="github.work",
        scheme="bearer",
        payload={
            "token": "secret",
            "headers": {"X-Test": "yes"},
            "env": {"GITHUB_TOKEN": "secret"},
        },
    )

    assert mcp_auth_headers(auth) == {
        "X-Test": "yes",
        "Authorization": "Bearer secret",
    }
    assert mcp_auth_env(auth) == {"GITHUB_TOKEN": "secret"}
```

- [ ] **Step 2: Run failing test**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_auth_storage_exports.py -q
```

Expected: fail because `wf_sources_mcp` does not exist.

- [ ] **Step 3: Create canonical auth module**

Create `src/wf_sources_mcp/__init__.py`:

```python
from __future__ import annotations

from .auth import (
    AuthRecord,
    auth_missing_diagnostic,
    auth_ref_for_connection,
    connection_auth_diagnostic,
    mcp_auth_env,
    mcp_auth_from_neutral,
    mcp_auth_headers,
    neutral_auth_from_mcp,
)

__all__ = [
    "AuthRecord",
    "auth_missing_diagnostic",
    "auth_ref_for_connection",
    "connection_auth_diagnostic",
    "mcp_auth_env",
    "mcp_auth_from_neutral",
    "mcp_auth_headers",
    "neutral_auth_from_mcp",
]
```

Create `src/wf_sources_mcp/auth.py` by moving the current contents of `src/wf_mcp/auth.py`.

Change the `TYPE_CHECKING` import in the moved file from:

```python
from .broker.models import ConnectionConfig
```

to:

```python
from wf_mcp.broker.models import ConnectionConfig
```

Add this module docstring after imports:

```python
"""MCP upstream-source auth helpers.

This module is canonical for MCP-as-source auth interpretation. The temporary
TYPE_CHECKING dependency on `wf_mcp.broker.models.ConnectionConfig` exists until
connection runtime DTOs move out of the compatibility MCP facade.
"""
```

- [ ] **Step 4: Replace `wf_mcp.auth` with shim**

Replace `src/wf_mcp/auth.py` with:

```python
"""Compatibility shim for MCP source auth helpers.

Canonical implementation lives in `wf_sources_mcp.auth`.
"""

from __future__ import annotations

from wf_sources_mcp.auth import (
    AuthRecord,
    auth_missing_diagnostic,
    auth_ref_for_connection,
    connection_auth_diagnostic,
    mcp_auth_env,
    mcp_auth_from_neutral,
    mcp_auth_headers,
    neutral_auth_from_mcp,
)

__all__ = [
    "AuthRecord",
    "auth_missing_diagnostic",
    "auth_ref_for_connection",
    "connection_auth_diagnostic",
    "mcp_auth_env",
    "mcp_auth_from_neutral",
    "mcp_auth_headers",
    "neutral_auth_from_mcp",
]
```

- [ ] **Step 5: Verify auth tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_auth_storage_exports.py tests/wf_mcp/test_auth.py -q
```

Expected: pass.

---

## Task 2: Move Focused Storage Module

**Files:**
- Create: `src/wf_sources_mcp/storage/__init__.py`
- Create: `src/wf_sources_mcp/storage/store.py`
- Modify: `src/wf_mcp/storage/__init__.py`
- Modify: `src/wf_mcp/storage/store.py`
- Test: `tests/wf_sources_mcp/test_auth_storage_exports.py`
- Test: `tests/wf_mcp/test_store.py`

- [ ] **Step 1: Add failing canonical storage test**

Append to `tests/wf_sources_mcp/test_auth_storage_exports.py`:

```python
from wf_sources_mcp.storage import FileAuthStore, FileCatalogStore, FileStore
from wf_mcp.models import CatalogSnapshot


def test_wf_sources_mcp_file_stores_keep_existing_disk_shape(tmp_path) -> None:
    auth_store = FileAuthStore(tmp_path / "auth-root")
    catalog_store = FileCatalogStore(tmp_path / "catalog-root")
    combined_store = FileStore(tmp_path / "combined-root")
    auth = AuthRecord(connection_id="demo.personal", scheme="bearer")
    snapshot = CatalogSnapshot(
        connection_id="demo.personal",
        fetched_at_epoch_ms=1,
        max_age_seconds=300,
        nodes=[],
        resources=[],
        prompts=[],
        metadata={},
    )

    auth_store.save_auth(auth)
    catalog_store.save_catalog(snapshot)
    combined_store.save_auth(auth)
    combined_store.save_catalog(snapshot)

    assert (tmp_path / "auth-root" / "auth" / "demo.personal.json").exists()
    assert (
        tmp_path / "catalog-root" / "catalog" / "demo.personal.json"
    ).exists()
    assert (tmp_path / "combined-root" / "auth" / "demo.personal.json").exists()
    assert (
        tmp_path / "combined-root" / "catalog" / "demo.personal.json"
    ).exists()
```

- [ ] **Step 2: Run failing storage test**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_auth_storage_exports.py::test_wf_sources_mcp_file_stores_keep_existing_disk_shape -q
```

Expected: fail because `wf_sources_mcp.storage` does not exist.

- [ ] **Step 3: Create canonical storage module**

Create `src/wf_sources_mcp/storage/store.py` by moving the current contents of `src/wf_mcp/storage/store.py`.

Change imports in the moved file:

```python
from wf_sources_mcp.auth import AuthRecord, mcp_auth_from_neutral, neutral_auth_from_mcp
```

Keep these temporary imports if needed:

```python
from wf_mcp.capabilities import CatalogNodeEntry, CatalogPromptEntry, CatalogResourceEntry
from wf_mcp.connections import parse_connection_id
from wf_mcp.models import CatalogSnapshot, dump_catalog_snapshot
```

Add this module docstring after imports:

```python
"""MCP upstream-source auth and catalog file stores.

These stores preserve the current MCP compatibility JSON shapes. Catalog entry
types still come from `wf_mcp` until catalog DTOs finish moving to a neutral or
source-provider package.
"""
```

Create `src/wf_sources_mcp/storage/__init__.py`:

```python
from __future__ import annotations

from .store import (
    AuthStore,
    CatalogStore,
    FileAuthStore,
    FileCatalogStore,
    FileStore,
    Store,
)

__all__ = [
    "AuthStore",
    "CatalogStore",
    "FileAuthStore",
    "FileCatalogStore",
    "FileStore",
    "Store",
]
```

- [ ] **Step 4: Replace `wf_mcp.storage` with shims**

Replace `src/wf_mcp/storage/store.py` with:

```python
"""Compatibility shim for MCP source auth/catalog stores.

Canonical implementation lives in `wf_sources_mcp.storage.store`.
"""

from __future__ import annotations

from wf_sources_mcp.storage.store import (
    AuthStore,
    CatalogStore,
    FileAuthStore,
    FileCatalogStore,
    FileStore,
    Store,
)

__all__ = [
    "AuthStore",
    "CatalogStore",
    "FileAuthStore",
    "FileCatalogStore",
    "FileStore",
    "Store",
]
```

Replace `src/wf_mcp/storage/__init__.py` with the same imports from `wf_sources_mcp.storage`.

- [ ] **Step 5: Verify storage tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_auth_storage_exports.py tests/wf_mcp/test_store.py -q
```

Expected: pass.

---

## Task 3: Switch Low-Risk Production Imports To Canonical Package

**Files:**
- Modify: `src/wf_mcp/broker/config.py`
- Modify: `src/wf_mcp/broker/service/auth_admin.py`
- Modify: `src/wf_mcp/broker/service/core.py`
- Modify: `src/wf_mcp/broker/service/source_catalog.py`
- Modify: `src/wf_mcp/broker/service/upstream_transport.py`
- Modify: `src/wf_mcp/broker/server.py`
- Modify: `src/wf_mcp/runtime/factory.py`
- Modify: `src/wf_mcp/sdk/adapter.py`

- [ ] **Step 1: Update canonical imports**

Replace imports of `wf_mcp.auth` / relative `...auth` for moved symbols with `wf_sources_mcp.auth`.

Examples:

```python
from wf_sources_mcp.auth import AuthRecord
from wf_sources_mcp.auth import connection_auth_diagnostic
from wf_sources_mcp.auth import mcp_auth_env, mcp_auth_headers
```

Replace imports of `wf_mcp.storage` / relative `...storage` for moved symbols with `wf_sources_mcp.storage`.

Examples:

```python
from wf_sources_mcp.storage import AuthStore, CatalogStore, FileAuthStore, FileCatalogStore, FileStore, Store
```

Leave tests and compatibility modules alone unless ruff/type checks require updates. The point is to start production code using canonical paths while keeping old imports valid.

- [ ] **Step 2: Run focused import smoke**

Run:

```bash
uv run pytest tests/wf_mcp/test_auth.py tests/wf_mcp/test_store.py tests/wf_mcp/service/test_upstream_transport.py tests/wf_mcp/service/test_catalog.py tests/wf_mcp/test_mcp_workflow_server.py -q
```

Expected: pass.

---

## Task 4: Add Import Direction Guard

**Files:**
- Create: `tests/wf_sources_mcp/test_import_direction.py`

- [ ] **Step 1: Add AST guard**

Create `tests/wf_sources_mcp/test_import_direction.py`:

```python
from __future__ import annotations

import ast
from pathlib import Path

FORBIDDEN_WF_MCP_PREFIXES = (
    "wf_mcp.admin_surface",
    "wf_mcp.workflow_surface",
    "wf_mcp.server",
    "wf_mcp.proxy",
    "wf_mcp.cli",
)


def test_wf_sources_mcp_does_not_import_frontend_mcp_modules() -> None:
    root = Path(__file__).resolve().parents[2] / "src" / "wf_sources_mcp"
    violations: list[str] = []

    for py_file in sorted(root.rglob("*.py")):
        rel = py_file.relative_to(root.parent)
        module = str(rel.with_suffix("")).replace("/", ".").replace("\\", ".")
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module is not None:
                if node.module.startswith(FORBIDDEN_WF_MCP_PREFIXES):
                    violations.append(
                        f"{module}:{node.lineno}: from {node.module} import ..."
                    )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith(FORBIDDEN_WF_MCP_PREFIXES):
                        violations.append(
                            f"{module}:{node.lineno}: import {alias.name}"
                        )

    assert violations == [], (
        "wf_sources_mcp imports frontend/proxy MCP modules:\n"
        + "\n".join(f"  {violation}" for violation in violations)
    )
```

- [ ] **Step 2: Run import guard**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_import_direction.py -q
```

Expected: pass.

---

## Task 5: Compatibility Identity Tests

**Files:**
- Modify: `tests/wf_mcp/test_compat_imports.py`

- [ ] **Step 1: Add shim identity assertions**

Append tests:

```python
def test_wf_mcp_auth_shim_reexports_wf_sources_mcp_auth() -> None:
    from wf_mcp.auth import AuthRecord as CompatAuthRecord
    from wf_sources_mcp.auth import AuthRecord

    assert CompatAuthRecord is AuthRecord


def test_wf_mcp_storage_shim_reexports_wf_sources_mcp_storage() -> None:
    from wf_mcp.storage import FileAuthStore as CompatFileAuthStore
    from wf_mcp.storage import FileCatalogStore as CompatFileCatalogStore
    from wf_mcp.storage import FileStore as CompatFileStore
    from wf_sources_mcp.storage import FileAuthStore, FileCatalogStore, FileStore

    assert CompatFileAuthStore is FileAuthStore
    assert CompatFileCatalogStore is FileCatalogStore
    assert CompatFileStore is FileStore
```

- [ ] **Step 2: Verify compatibility tests**

Run:

```bash
uv run pytest tests/wf_mcp/test_compat_imports.py tests/wf_sources_mcp -q
```

Expected: pass.

---

## Task 6: Docs And Final Verification

**Files:**
- Modify: `docs/current_roadmap.md`
- Modify: `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`

- [ ] **Step 1: Update docs status**

In `docs/current_roadmap.md`, update the MCP package split bullet:

```markdown
    First `wf_sources_mcp` slice complete: MCP auth helpers and focused
    auth/catalog stores now live in `wf_sources_mcp`, with `wf_mcp` compatibility
    shims preserved. Runtime/session/source-registry moves remain future slices.
```

In `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`, update the first-slices list under `MCP Source Provider Package Direction` to mark slice 1 complete:

```markdown
1. Complete: MCP auth helpers and focused auth/catalog stores moved to
   `wf_sources_mcp`, with `wf_mcp` shims preserved.
```

- [ ] **Step 2: Run focused tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp tests/wf_mcp/test_auth.py tests/wf_mcp/test_store.py tests/wf_mcp/test_compat_imports.py tests/wf_mcp/service/test_upstream_transport.py tests/wf_mcp/service/test_catalog.py -q
```

Expected: pass.

- [ ] **Step 3: Run lint/type checks**

Run:

```bash
uv run ruff check src tests
uv run basedpyright --level error src
```

Expected: ruff passes and basedpyright reports `0 errors`.

- [ ] **Step 4: Optional full suite**

Run if time allows:

```bash
uv run pytest -q
```

Expected: current suite shape, around `1207 passed, 1 skipped, 1 xfailed`.

- [ ] **Step 5: Final report**

Report:

- files changed
- tests/lint/type output
- whether full suite was run
- compatibility shims retained
- remaining future moves: source registry, upstream transport/discovery/session services

---

## Self-Review Notes

- This is a package-boundary slice, not a behavior slice.
- On-disk JSON shapes do not change.
- `wf_mcp` compatibility imports stay valid.
- `wf_sources_mcp` starts with limited, documented temporary dependencies on MCP catalog/connection DTOs.
- The next package split slice should move MCP source registry models/conversion after this lands.
