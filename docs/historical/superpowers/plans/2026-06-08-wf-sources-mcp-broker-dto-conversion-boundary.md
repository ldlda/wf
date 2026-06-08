# MCP Broker DTO Conversion Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove `wf_mcp.ConnectionConfig` imports from `wf_sources_mcp` by making source-side conversion structural and moving broker DTO construction to `wf_mcp`.

**Architecture:** `wf_sources_mcp` owns source-provider DTOs and may adapt legacy connection-like inputs by structural protocol. It must not construct broker runtime DTOs. `wf_mcp.source_registry` becomes the compatibility/broker conversion module: it re-exports canonical source registry models and owns helpers that produce `ConnectionConfig`.

**Tech Stack:** Python 3.14, structural `Protocol`, dataclasses in tests, pytest, ruff, basedpyright, AST import guards.

---

## Why This Slice Exists

After the ID cleanup, the remaining real `wf_sources_mcp -> wf_mcp` dependencies are legacy broker DTO conversions:

- `wf_sources_mcp.connections` imports `wf_mcp.broker.models.ConnectionConfig` for type checking.
- `wf_sources_mcp.source_registry` imports `wf_mcp.models.ConnectionConfig` at runtime to construct broker configs.

Those conversions are compatibility edges. `wf_sources_mcp` should own MCP source objects, not broker runtime objects.

---

## Hard Boundaries

- Do not move `ConnectionConfig` itself in this slice.
- Do not change `ConnectionConfig` fields or behavior.
- Do not change source registry JSON shape.
- Do not change `McpSourceRegistryEntry` fields.
- Do not remove `wf_mcp.source_registry` compatibility imports.
- Do not import `wf_mcp` from any `src/wf_sources_mcp/*.py` file.
- Keep existing broker call sites working.
- Do not commit unless the caller explicitly asks for a commit.

## File Map

- Modify `src/wf_sources_mcp/connections.py`: replace `ConnectionConfig` type import with structural protocol.
- Modify `src/wf_sources_mcp/source_registry.py`: keep canonical models/store and input-only conversion; remove broker DTO construction helpers.
- Modify `src/wf_mcp/source_registry.py`: re-export canonical models/store and define broker DTO construction helpers.
- Modify `src/wf_mcp/broker/config.py`: import broker DTO construction helpers from `wf_mcp.source_registry`.
- Modify `src/wf_mcp/broker/service/connection_service.py`: import broker DTO construction helpers from `wf_mcp.source_registry`.
- Modify tests:
  - `tests/wf_sources_mcp/test_connections.py`
  - `tests/wf_sources_mcp/test_source_registry.py`
  - `tests/wf_mcp/test_source_registry.py`
  - `tests/wf_sources_mcp/test_import_direction_guard.py`
- Modify docs:
  - `docs/current_roadmap.md`
  - `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`
- Move this plan to `docs/historical/superpowers/plans/` after implementation is verified.

---

### Task 1: Make Legacy Connection Input Structural in `connections.py`

**Files:**
- Modify: `src/wf_sources_mcp/connections.py`
- Modify: `tests/wf_sources_mcp/test_connections.py`

- [ ] **Step 1: Replace `ConnectionConfig` type import with protocols**

In `src/wf_sources_mcp/connections.py`, remove:

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from wf_mcp.broker.models import ConnectionConfig
```

Add:

```python
from collections.abc import Mapping
from typing import Protocol


class LegacyConnectionConfigLike(Protocol):
    """Structural shape needed from legacy broker connection configs."""

    id: str
    server: str
    account: str
    enabled: bool
    metadata: Mapping[str, object]
```

Update signatures:

```python
def mcp_source_connection_from_connection_config(
    connection: LegacyConnectionConfigLike,
) -> McpSourceConnection:
    ...


def _transport_from_connection_metadata(
    connection: LegacyConnectionConfigLike,
) -> SourceTransport | None:
    ...
```

Add `LegacyConnectionConfigLike` to `__all__`.

- [ ] **Step 2: Preserve metadata handling**

Keep the exact current metadata logic:

- dict `metadata["transport"]` supports `{"kind": "stdio"}` and `{"kind": "http"}`;
- flat `"stdio"` metadata supports `command`, `args`, `env`, `cwd`;
- flat HTTP aliases support `url`, `headers`;
- missing transport returns `None`;
- unsupported transport raises `ValueError`.

- [ ] **Step 3: Add a no-`wf_mcp` fake test**

In `tests/wf_sources_mcp/test_connections.py`, add:

```python
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class _LegacyConnectionLike:
    id: str
    server: str
    account: str
    enabled: bool = True
    metadata: dict[str, object] = field(default_factory=dict)
```

Add a test using `_LegacyConnectionLike` with stdio metadata and assert conversion works. Existing tests that import `wf_mcp.broker.models.ConnectionConfig` may remain temporarily, but at least one canonical test must prove the converter does not need the concrete broker class.

- [ ] **Step 4: Run connection tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_connections.py -q
```

Expected: pass.

---

### Task 2: Move Broker DTO Construction Helpers to `wf_mcp.source_registry`

**Files:**
- Modify: `src/wf_sources_mcp/source_registry.py`
- Modify: `src/wf_mcp/source_registry.py`
- Modify: `tests/wf_sources_mcp/test_source_registry.py`
- Modify: `tests/wf_mcp/test_source_registry.py`

- [ ] **Step 1: Keep input-only seed conversion in `wf_sources_mcp.source_registry`**

In `src/wf_sources_mcp/source_registry.py`, remove all `wf_mcp.models.ConnectionConfig` imports.

Add a structural protocol:

```python
from collections.abc import Mapping
from typing import Protocol


class LegacyConnectionConfigLike(Protocol):
    id: str
    server: str
    account: str
    enabled: bool
    metadata: Mapping[str, object]
```

Keep `connection_config_to_registry_entry(connection: LegacyConnectionConfigLike) -> McpSourceRegistryEntry`.

This helper is allowed to stay in `wf_sources_mcp` because it converts legacy-shaped input into canonical source registry state and does not construct broker DTOs.

- [ ] **Step 2: Remove broker-output helpers from canonical `__all__`**

Remove these functions from `src/wf_sources_mcp/source_registry.py`:

- `registry_entry_to_connection_config`
- `workflow_mcp_source_to_connection_config`

Remove them from `__all__`.

- [ ] **Step 3: Define broker-output helpers in `src/wf_mcp/source_registry.py`**

Replace the pure shim with a mixed compatibility module:

```python
"""Compatibility and broker conversion helpers for MCP source registry state.

Canonical registry models and stores live in `wf_sources_mcp.source_registry`.
Helpers that construct `ConnectionConfig` stay here because `ConnectionConfig`
is a broker compatibility DTO.
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
)

from .models import ConnectionConfig


def registry_entry_to_connection_config(entry: McpSourceRegistryEntry) -> ConnectionConfig:
    ...


def workflow_mcp_source_to_connection_config(source: object) -> ConnectionConfig:
    ...
```

Move the current implementations of `registry_entry_to_connection_config` and `workflow_mcp_source_to_connection_config` from `wf_sources_mcp.source_registry` into this module unchanged except for imports.

Ensure `__all__` includes all re-exported canonical names plus the broker-output helpers.

- [ ] **Step 4: Move broker-output tests to `wf_mcp`**

In `tests/wf_sources_mcp/test_source_registry.py`:

- keep tests for `McpSourceRegistryEntry`;
- keep tests for `SourceRegistryFile`;
- keep tests for `FileSourceRegistryStore`;
- keep tests for `connection_config_to_registry_entry`, but use a local `_LegacyConnectionLike` dataclass instead of importing `wf_mcp.models.ConnectionConfig`;
- remove tests for `registry_entry_to_connection_config`;
- remove tests for `workflow_mcp_source_to_connection_config` if present.

In `tests/wf_mcp/test_source_registry.py`:

- keep or add tests for `registry_entry_to_connection_config`;
- keep or add tests for `workflow_mcp_source_to_connection_config`;
- assert these helpers return concrete `wf_mcp.models.ConnectionConfig`.

- [ ] **Step 5: Run source registry tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_source_registry.py tests/wf_mcp/test_source_registry.py -q
```

Expected: pass.

---

### Task 3: Update Broker Call Sites to Import Broker Conversions

**Files:**
- Modify: `src/wf_mcp/broker/config.py`
- Modify: `src/wf_mcp/broker/service/connection_service.py`

- [ ] **Step 1: Update imports in broker config**

In `src/wf_mcp/broker/config.py`, import canonical models/stores from `wf_sources_mcp.source_registry` only when they are pure source registry objects.

Import broker-output helper from `wf_mcp.source_registry`:

```python
from wf_mcp.source_registry import workflow_mcp_source_to_connection_config
```

Do not import `workflow_mcp_source_to_connection_config` from `wf_sources_mcp.source_registry`.

- [ ] **Step 2: Update imports in connection service**

In `src/wf_mcp/broker/service/connection_service.py`:

```python
from wf_mcp.source_registry import (
    connection_config_to_registry_entry,
    registry_entry_to_connection_config,
)
```

`connection_config_to_registry_entry` may be re-exported from `wf_mcp.source_registry` for consistency at broker call sites, even though canonical implementation remains in `wf_sources_mcp.source_registry`.

- [ ] **Step 3: Run broker source registry tests**

Run:

```bash
uv run pytest tests/wf_mcp/test_workflow_config_bridge.py tests/wf_mcp/service/test_connection_service.py tests/wf_mcp/test_source_registry.py -q
```

Expected: pass.

---

### Task 4: Add Import Guards for Broker DTO Dependencies

**Files:**
- Modify: `tests/wf_sources_mcp/test_import_direction_guard.py`

- [ ] **Step 1: Add forbidden broker DTO import test**

Append:

```python
def test_wf_sources_mcp_does_not_import_wf_mcp_broker_dtos() -> None:
    root = Path(__file__).resolve().parents[2] / "src" / "wf_sources_mcp"
    forbidden = {"wf_mcp.models", "wf_mcp.broker.models"}
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
        "wf_sources_mcp still imports wf_mcp broker DTO modules:\n"
        + "\n".join(f"  {violation}" for violation in violations)
    )
```

- [ ] **Step 2: Run import guards**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_import_direction_guard.py -q
```

Expected: pass.

---

### Task 5: Update Package Root Exports

**Files:**
- Modify: `src/wf_sources_mcp/__init__.py`

- [ ] **Step 1: Remove broker-output helper exports**

Remove these names from `wf_sources_mcp.__all__` and `__getattr__` routing:

- `registry_entry_to_connection_config`
- `workflow_mcp_source_to_connection_config`

Keep:

- `connection_config_to_registry_entry`
- `mcp_source_connection_from_connection_config`

Those remaining helpers must be structural/input-only and must not import `wf_mcp`.

- [ ] **Step 2: Run package export tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp tests/wf_mcp/test_compat_imports.py -q
```

Expected: pass.

If tests expect broker-output helpers at the `wf_sources_mcp` package root, update them to import from `wf_mcp.source_registry`. Do not keep broker-output helpers at the source-provider package root.

---

### Task 6: Update Docs and Archive Plan

**Files:**
- Modify: `docs/current_roadmap.md`
- Modify: `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`
- Move: `docs/superpowers/plans/2026-06-08-wf-sources-mcp-broker-dto-conversion-boundary.md` to `docs/historical/superpowers/plans/2026-06-08-wf-sources-mcp-broker-dto-conversion-boundary.md`

- [ ] **Step 1: Update roadmap**

Under the `wf_sources_mcp` cleanup section, add:

```markdown
      Broker DTO construction moved out of `wf_sources_mcp`: source-provider
      modules use structural legacy inputs only, while `wf_mcp.source_registry`
      owns helpers that construct `ConnectionConfig`.
```

- [ ] **Step 2: Update long-lived boundary spec**

In `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`, add a completed numbered item after the source ID item:

```markdown
23. Complete: broker DTO construction removed from `wf_sources_mcp`.
    `wf_sources_mcp` accepts legacy-shaped inputs structurally, while
    `wf_mcp.source_registry` owns helpers that construct `ConnectionConfig`.
```

Renumber the pending broad item if needed.

- [ ] **Step 3: Archive the plan**

Run:

```bash
git mv docs/superpowers/plans/2026-06-08-wf-sources-mcp-broker-dto-conversion-boundary.md docs/historical/superpowers/plans/2026-06-08-wf-sources-mcp-broker-dto-conversion-boundary.md
```

Expected: `git status --short` shows the plan under `docs/historical/...`.

---

### Task 7: Final Verification

**Files:**
- No code edits unless verification finds a real issue.

- [ ] **Step 1: Run focused tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp tests/wf_mcp/test_source_registry.py tests/wf_mcp/test_workflow_config_bridge.py tests/wf_mcp/service/test_connection_service.py tests/wf_mcp/test_compat_imports.py -q
```

Expected: all selected tests pass.

- [ ] **Step 2: Run import dependency check**

Run:

```bash
rg -n "^from wf_mcp|^import wf_mcp|wf_mcp\\." src/wf_sources_mcp
```

Expected: no production-code imports. A package docstring mention may remain only if it explains a compatibility concern, but prefer updating stale wording if it no longer applies.

- [ ] **Step 3: Run lint**

Run:

```bash
uv run ruff check src/wf_sources_mcp src/wf_mcp/source_registry.py src/wf_mcp/broker/config.py src/wf_mcp/broker/service/connection_service.py tests/wf_sources_mcp tests/wf_mcp/test_source_registry.py tests/wf_mcp/test_compat_imports.py
```

Expected: `All checks passed!`

- [ ] **Step 4: Run typecheck**

Run:

```bash
uv run basedpyright --level error src/wf_sources_mcp src/wf_mcp/source_registry.py src/wf_mcp/broker/config.py src/wf_mcp/broker/service/connection_service.py tests/wf_sources_mcp tests/wf_mcp/test_source_registry.py
```

Expected: `0 errors, 0 warnings, 0 notes`.

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
- Confirmation that `src/wf_sources_mcp` has no production imports from `wf_mcp`.
- Confirmation that broker DTO construction helpers live in `wf_mcp.source_registry`.
- Confirmation that source-provider conversion helpers use structural protocols.
- Any deviations from this plan.

Do not claim "full suite passed" unless the full suite was actually run.
