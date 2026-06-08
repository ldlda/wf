# MCP Source ID Ownership Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete ownership of MCP source ID validation in `wf_sources_mcp.ids` and remove remaining `wf_sources_mcp` imports from legacy `wf_mcp` ID modules.

**Architecture:** `wf_sources_mcp.ids` is the canonical home for MCP upstream source ID rules: accepted characters, provider/account splitting, and reserved source IDs. Legacy `wf_mcp` modules may import from it, but `wf_sources_mcp` must not import `wf_mcp.connections` or `wf_mcp.shared.names`. This slice is intentionally small: it does not move broker DTOs or `ConnectionConfig` conversions.

**Tech Stack:** Python 3.14, pytest, ruff, basedpyright, AST import guards.

---

## Why This Pattern Is Correct

Source IDs are used by upstream MCP source-provider code before the broker gets involved:

- registry entries use source IDs;
- catalog snapshots use source IDs;
- auth records are referenced by source IDs;
- filesystem stores must reject unsafe source IDs before building paths.

That makes ID parsing a low-level source-provider invariant. `wf_mcp` can keep compatibility imports, but it should not be the authority for these rules.

---

## Hard Boundaries

- Do not move `ConnectionConfig` or broker DTOs in this slice.
- Do not change accepted ID syntax.
- Do not change reserved ID values.
- Do not change on-disk file layout.
- Do not import `wf_mcp` from `src/wf_sources_mcp/ids.py`.
- Remove the `wf_sources_mcp.storage.store` lazy import from `wf_mcp.connections`.
- Keep `wf_mcp.connections.parse_connection_id` and `wf_mcp.shared.names.RESERVED_CONNECTION_IDS` import-compatible.
- Do not commit unless the caller explicitly asks for a commit.

## File Map

- Modify `src/wf_sources_mcp/ids.py`: add explicit `validate_connection_id()` helper and keep `parse_connection_id()`.
- Modify `src/wf_sources_mcp/storage/store.py`: import ID validation from `wf_sources_mcp.ids`, not `wf_mcp.connections`.
- Modify `src/wf_mcp/connections.py`: keep compatibility import from `wf_sources_mcp.ids`.
- Modify `src/wf_mcp/shared/names.py`: keep compatibility import from `wf_sources_mcp.ids`.
- Modify or create `tests/wf_sources_mcp/test_ids.py`: canonical ID tests.
- Modify `tests/wf_sources_mcp/test_import_direction_guard.py`: forbid old ID helper imports from `wf_sources_mcp`.
- Modify docs: `docs/current_roadmap.md` and `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`.
- Move this plan to `docs/historical/superpowers/plans/` after implementation is verified.

---

### Task 1: Add Canonical Source ID Tests

**Files:**
- Create: `tests/wf_sources_mcp/test_ids.py`
- Optionally modify: `tests/wf_sources_mcp/test_connections.py`

- [ ] **Step 1: Create focused ID tests**

Create `tests/wf_sources_mcp/test_ids.py`:

```python
from __future__ import annotations

import pytest

from wf_sources_mcp.ids import (
    CONNECTION_ID_PATTERN,
    RESERVED_CONNECTION_IDS,
    parse_connection_id,
    validate_connection_id,
)


def test_validate_connection_id_returns_valid_id() -> None:
    assert validate_connection_id("github.work") == "github.work"
    assert validate_connection_id("my_source.default") == "my_source.default"


def test_parse_connection_id_splits_provider_and_account() -> None:
    assert parse_connection_id("github.work") == ("github", "work")


@pytest.mark.parametrize(
    "source_id",
    ["", "github", ".github.work", "github.", "github/work", "github work", "../bad"],
)
def test_validate_connection_id_rejects_unsafe_or_unqualified_ids(source_id: str) -> None:
    with pytest.raises(ValueError):
        validate_connection_id(source_id)


def test_reserved_connection_ids_are_canonical_source_constants() -> None:
    assert "wf.admin" in RESERVED_CONNECTION_IDS
    assert "wf.mcp" in RESERVED_CONNECTION_IDS
    assert CONNECTION_ID_PATTERN.startswith("^")
```

- [ ] **Step 2: Remove duplicate assertions if needed**

If `tests/wf_sources_mcp/test_connections.py` now duplicates the exact `parse_connection_id` tests, either leave the overlap if it is small or reduce it to connection-conversion behavior. Do not remove coverage unless `test_ids.py` has equal or stronger assertions.

- [ ] **Step 3: Run the new tests and verify the expected failure**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_ids.py -q
```

Expected: fail because `validate_connection_id` does not exist yet.

---

### Task 2: Add `validate_connection_id()` to `wf_sources_mcp.ids`

**Files:**
- Modify: `src/wf_sources_mcp/ids.py`

- [ ] **Step 1: Implement the helper without changing parsing rules**

Update `src/wf_sources_mcp/ids.py`:

```python
def validate_connection_id(connection_id: str) -> str:
    """Validate one MCP source id and return it unchanged.

    Use this when callers need path-safety and shape validation but do not need
    provider/account pieces. `parse_connection_id()` remains the splitter.
    """

    parse_connection_id(connection_id)
    return connection_id
```

Add it to `__all__`.

- [ ] **Step 2: Run canonical ID tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_ids.py tests/wf_sources_mcp/test_connections.py -q
```

Expected: pass.

---

### Task 3: Remove Legacy ID Import From `wf_sources_mcp.storage`

**Files:**
- Modify: `src/wf_sources_mcp/storage/store.py`

- [ ] **Step 1: Replace lazy legacy import**

In `FileCatalogStore._connection_path`, replace:

```python
from wf_mcp.connections import parse_connection_id

parse_connection_id(connection_id)
```

with a canonical import:

```python
from wf_sources_mcp.ids import validate_connection_id

validate_connection_id(connection_id)
```

If import cycles allow it, prefer a top-level import near the other `wf_sources_mcp` imports. If a cycle appears, keep it as a local import and add a short comment explaining why.

- [ ] **Step 2: Run storage tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp tests/wf_mcp/test_store.py -q
```

Expected: pass.

---

### Task 4: Add Import Guard for Old ID Modules

**Files:**
- Modify: `tests/wf_sources_mcp/test_import_direction_guard.py`

- [ ] **Step 1: Add forbidden old ID helper import test**

Append:

```python
def test_wf_sources_mcp_does_not_import_old_wf_mcp_id_modules() -> None:
    root = Path(__file__).resolve().parents[2] / "src" / "wf_sources_mcp"
    forbidden = {"wf_mcp.connections", "wf_mcp.shared.names"}
    violations: list[str] = []

    for py_file in sorted(root.rglob("*.py")):
        rel = py_file.relative_to(root.parent)
        module = str(rel.with_suffix("")).replace("/", ".").replace("\\", ".")
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module in forbidden:
                violations.append(f"{module}:{node.lineno}: from {node.module} import ...")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in forbidden:
                        violations.append(f"{module}:{node.lineno}: import {alias.name}")

    assert violations == [], (
        "wf_sources_mcp still imports old wf_mcp source ID modules:\n"
        + "\n".join(f"  {violation}" for violation in violations)
    )
```

- [ ] **Step 2: Run import guard**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_import_direction_guard.py -q
```

Expected: pass.

---

### Task 5: Verify Legacy Compatibility Imports Still Work

**Files:**
- Modify: `tests/wf_mcp/test_compat_imports.py`

- [ ] **Step 1: Add identity tests for legacy paths**

Append:

```python
def test_wf_mcp_connection_id_helpers_reexport_wf_sources_mcp_ids() -> None:
    from wf_mcp.connections import parse_connection_id as compat_parse_connection_id
    from wf_mcp.shared.names import RESERVED_CONNECTION_IDS as compat_reserved_ids
    from wf_sources_mcp.ids import RESERVED_CONNECTION_IDS, parse_connection_id

    assert compat_parse_connection_id is parse_connection_id
    assert compat_reserved_ids is RESERVED_CONNECTION_IDS
```

- [ ] **Step 2: Run compatibility tests**

Run:

```bash
uv run pytest tests/wf_mcp/test_compat_imports.py tests/wf_mcp/test_store.py -q
```

Expected: pass.

---

### Task 6: Update Docs and Archive Plan

**Files:**
- Modify: `docs/current_roadmap.md`
- Modify: `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`
- Move: `docs/superpowers/plans/2026-06-08-wf-sources-mcp-source-id-ownership.md` to `docs/historical/superpowers/plans/2026-06-08-wf-sources-mcp-source-id-ownership.md`

- [ ] **Step 1: Update `docs/current_roadmap.md`**

Under the `wf_sources_mcp` cleanup section, add:

```markdown
      MCP source ID validation is canonical in `wf_sources_mcp.ids`.
      `wf_sources_mcp` no longer imports legacy `wf_mcp.connections` or
      `wf_mcp.shared.names` for source ID/path-safety checks.
```

- [ ] **Step 2: Update the long-lived boundary spec**

In `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`, add a completed numbered item after the adapter-helper item:

```markdown
22. Complete: MCP source ID validation and reserved source IDs are canonical in
    `wf_sources_mcp.ids`; legacy `wf_mcp.connections` / `wf_mcp.shared.names`
    remain compatibility consumers.
```

Renumber the pending broad item if needed.

- [ ] **Step 3: Archive the plan**

Run:

```bash
git mv docs/superpowers/plans/2026-06-08-wf-sources-mcp-source-id-ownership.md docs/historical/superpowers/plans/2026-06-08-wf-sources-mcp-source-id-ownership.md
```

Expected: `git status --short` shows the plan under `docs/historical/...`.

---

### Task 7: Final Verification

**Files:**
- No code edits unless verification finds a real issue.

- [ ] **Step 1: Run focused tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_ids.py tests/wf_sources_mcp/test_import_direction_guard.py tests/wf_sources_mcp tests/wf_mcp/test_compat_imports.py tests/wf_mcp/test_store.py -q
```

Expected: all selected tests pass.

- [ ] **Step 2: Run lint**

Run:

```bash
uv run ruff check src/wf_sources_mcp/ids.py src/wf_sources_mcp/storage/store.py src/wf_mcp/connections.py src/wf_mcp/shared/names.py tests/wf_sources_mcp/test_ids.py tests/wf_sources_mcp/test_import_direction_guard.py tests/wf_mcp/test_compat_imports.py
```

Expected: `All checks passed!`

- [ ] **Step 3: Run typecheck**

Run:

```bash
uv run basedpyright --level error src/wf_sources_mcp/ids.py src/wf_sources_mcp/storage/store.py src/wf_mcp/connections.py src/wf_mcp/shared/names.py tests/wf_sources_mcp/test_ids.py tests/wf_mcp/test_compat_imports.py
```

Expected: `0 errors, 0 warnings, 0 notes`.

- [ ] **Step 4: Check remaining old ID helper imports**

Run:

```bash
rg -n "wf_mcp\\.connections|wf_mcp\\.shared\\.names|parse_connection_id|RESERVED_CONNECTION_IDS|validate_connection_id" src/wf_sources_mcp src/wf_mcp tests/wf_sources_mcp tests/wf_mcp
```

Expected:

- `src/wf_sources_mcp` imports source ID helpers only from `wf_sources_mcp.ids`.
- `src/wf_mcp/connections.py` and `src/wf_mcp/shared/names.py` may import from `wf_sources_mcp.ids` for compatibility.
- Tests may reference legacy paths only for compatibility assertions.

- [ ] **Step 5: Check whitespace**

Run:

```bash
git diff --check
```

Expected: no whitespace errors. CRLF warnings on Windows are acceptable.

---

## Expected Final Report

The implementer should report:

- Files created, modified, and moved.
- Exact verification commands and pass/fail output.
- Confirmation that `wf_sources_mcp.ids` owns source ID validation.
- Confirmation that `wf_sources_mcp.storage.store` no longer imports `wf_mcp.connections`.
- Confirmation that legacy `wf_mcp` ID paths still work.
- Any deviations from this plan.

Do not claim "full suite passed" unless the full suite was actually run.
