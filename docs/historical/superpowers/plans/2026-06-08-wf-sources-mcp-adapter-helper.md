# MCP Adapter Helper Move Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the upstream MCP adapter lookup helper from `wf_mcp.broker.service.adapters` into canonical `wf_sources_mcp.adapters`.

**Architecture:** `wf_sources_mcp.adapters.require_adapter` will accept a structural source reference so both legacy `ConnectionConfig(server=...)` and typed `McpSourceConnection(provider=...)` can resolve adapters. The type seam should model "either server or provider", not "both". The old `wf_mcp.broker.service.adapters` module remains a compatibility shim. `UpstreamTransportService` imports the canonical helper.

**Tech Stack:** Python 3.14, structural `Protocol`, `Mapping`, `wf_sources_mcp.sdk.BackendAdapter`, pytest, ruff, basedpyright.

---

## Hard Boundaries

- Do not move `UpstreamTransportService` in this slice.
- Do not change adapter registry shape: it remains `dict[str, BackendAdapter]`.
- Do not change error type: missing adapter should still raise `KeyError`.
- Do not import `wf_mcp` from `src/wf_sources_mcp/adapters.py`.
- Keep `wf_mcp.broker.service.adapters.require_adapter` import-compatible via a shim.
- Do not commit unless the caller explicitly asks for a commit.

## File Map

- Create `src/wf_sources_mcp/adapters.py`: canonical adapter-ref protocols and `require_adapter`.
- Modify `src/wf_sources_mcp/__init__.py`: export adapter-ref protocols and `require_adapter`.
- Replace `src/wf_mcp/broker/service/adapters.py`: compatibility shim.
- Modify `src/wf_mcp/broker/service/upstream_transport.py`: import `require_adapter` from `wf_sources_mcp.adapters`.
- Create `tests/wf_sources_mcp/test_adapters.py`: canonical helper tests.
- Modify `tests/wf_mcp/test_compat_imports.py`: shim identity test.
- Modify `tests/wf_sources_mcp/test_import_direction_guard.py`: forbid old broker service adapter imports.
- Modify docs: `docs/current_roadmap.md` and `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`.
- Move this plan to `docs/historical/superpowers/plans/` after implementation is verified.

---

### Task 1: Add Canonical Adapter Helper Tests

**Files:**
- Create: `tests/wf_sources_mcp/test_adapters.py`

- [ ] **Step 1: Write tests for legacy and typed source refs**

Create `tests/wf_sources_mcp/test_adapters.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from wf_sources_mcp.adapters import require_adapter
from wf_sources_mcp.auth import AuthRecord
from wf_sources_mcp.catalog import DiscoveredPrompt, DiscoveredResource, DiscoveredTool
from wf_sources_mcp.connections import McpSourceConnection
from wf_sources_mcp.sdk import BackendAdapter, ToolCallResult
from wf_sources_mcp.transports import StdioSourceTransport


class _Adapter:
    async def list_tools(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
    ) -> list[DiscoveredTool]:
        return []

    async def list_resources(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
    ) -> list[DiscoveredResource]:
        return []

    async def list_prompts(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
    ) -> list[DiscoveredPrompt]:
        return []

    async def get_connection_metadata(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
    ) -> dict[str, Any]:
        return {}

    async def read_resource(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
        uri: str,
    ) -> dict[str, Any]:
        raise NotImplementedError

    async def get_prompt(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
        prompt_name: str,
        arguments: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError

    async def invoke_method(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError

    async def send_notification(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> None:
        raise NotImplementedError

    async def call_tool(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
        tool_name: str,
        payload: dict[str, Any],
    ) -> ToolCallResult:
        raise NotImplementedError


@dataclass(slots=True)
class _LegacyConnection:
    server: str


def test_require_adapter_uses_legacy_server_field() -> None:
    adapter = _Adapter()

    result = require_adapter(
        _LegacyConnection(server="demo"),
        {"demo": adapter},
    )

    assert result is adapter


def test_require_adapter_uses_typed_source_provider_field() -> None:
    adapter = _Adapter()
    connection = McpSourceConnection(
        id="demo.default",
        provider="demo",
        account="default",
        transport=StdioSourceTransport(command="demo-mcp"),
    )

    result = require_adapter(connection, {"demo": adapter})

    assert result is adapter


def test_require_adapter_raises_useful_key_error() -> None:
    with pytest.raises(KeyError, match="no adapter registered for source 'missing'"):
        require_adapter(_LegacyConnection(server="missing"), {})


def test_require_adapter_has_backend_adapter_static_shape() -> None:
    adapter: BackendAdapter = _Adapter()

    assert adapter is not None
```

- [ ] **Step 2: Run tests and verify failure before implementation**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_adapters.py -q
```

Expected: fail with `ModuleNotFoundError` or import error for `wf_sources_mcp.adapters`.

---

### Task 2: Create Canonical `wf_sources_mcp.adapters`

**Files:**
- Create: `src/wf_sources_mcp/adapters.py`

- [ ] **Step 1: Add structural helper implementation**

Create `src/wf_sources_mcp/adapters.py`:

```python
from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

from wf_sources_mcp.sdk import BackendAdapter


class SourceAdapterRef(Protocol):
    """Typed source identity used by `McpSourceConnection`."""

    provider: str


class LegacyAdapterRef(Protocol):
    """Legacy broker source identity used by `ConnectionConfig`."""

    server: str


type AdapterLookupRef = SourceAdapterRef | LegacyAdapterRef


def _adapter_key(source: object) -> str:
    server = getattr(source, "server", None)
    if isinstance(server, str):
        return server
    provider = getattr(source, "provider", None)
    if isinstance(provider, str):
        return provider
    raise TypeError("source must expose a string 'server' or 'provider' attribute")


def require_adapter(
    source: AdapterLookupRef,
    adapters: Mapping[str, BackendAdapter],
) -> BackendAdapter:
    """Return the adapter for a source or raise a useful lookup error."""
    key = _adapter_key(source)
    adapter = adapters.get(key)
    if adapter is None:
        raise KeyError(f"no adapter registered for source {key!r}")
    return adapter


__all__ = ["AdapterLookupRef", "LegacyAdapterRef", "SourceAdapterRef", "require_adapter"]
```

Note: `_adapter_key` still uses runtime attribute checks because this helper is a compatibility boundary. The public type alias must express "legacy server ref OR typed provider ref"; do not require both attributes.

- [ ] **Step 2: Run canonical tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_adapters.py -q
```

Expected: pass.

---

### Task 3: Export Adapter Helper From `wf_sources_mcp`

**Files:**
- Modify: `src/wf_sources_mcp/__init__.py`
- Modify: `tests/wf_sources_mcp/test_adapters.py`

- [ ] **Step 1: Add package-root exports**

Update `src/wf_sources_mcp/__init__.py` so this works:

```python
from wf_sources_mcp import AdapterLookupRef, LegacyAdapterRef, SourceAdapterRef, require_adapter
```

If the package uses lazy `__getattr__`, add these names to `__all__` and route them to `.adapters`:

```python
    if name in {"AdapterLookupRef", "LegacyAdapterRef", "SourceAdapterRef", "require_adapter"}:
        from . import adapters

        return getattr(adapters, name)
```

- [ ] **Step 2: Add package-root export test**

Append to `tests/wf_sources_mcp/test_adapters.py`:

```python
def test_adapter_helper_exports_from_package_root() -> None:
    from wf_sources_mcp import require_adapter as root_require_adapter
    from wf_sources_mcp.adapters import require_adapter

    assert root_require_adapter is require_adapter
```

- [ ] **Step 3: Run canonical tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_adapters.py -q
```

Expected: pass.

---

### Task 4: Replace Broker Service Adapter Module With Shim

**Files:**
- Modify: `src/wf_mcp/broker/service/adapters.py`
- Modify: `tests/wf_mcp/test_compat_imports.py`

- [ ] **Step 1: Replace old implementation with shim**

Replace `src/wf_mcp/broker/service/adapters.py` with:

```python
"""Compatibility shim for upstream MCP adapter lookup.

Canonical implementation lives in `wf_sources_mcp.adapters`.
"""

from __future__ import annotations

from wf_sources_mcp.adapters import (
    AdapterLookupRef,
    LegacyAdapterRef,
    SourceAdapterRef,
    require_adapter,
)

__all__ = ["AdapterLookupRef", "LegacyAdapterRef", "SourceAdapterRef", "require_adapter"]
```

- [ ] **Step 2: Add shim identity test**

Append to `tests/wf_mcp/test_compat_imports.py`:

```python
def test_wf_mcp_broker_service_adapter_shim_reexports_wf_sources_mcp_adapter_helper() -> None:
    from wf_mcp.broker.service.adapters import require_adapter as compat_require_adapter
    from wf_sources_mcp.adapters import require_adapter

    assert compat_require_adapter is require_adapter
```

- [ ] **Step 3: Run compatibility test**

Run:

```bash
uv run pytest tests/wf_mcp/test_compat_imports.py::test_wf_mcp_broker_service_adapter_shim_reexports_wf_sources_mcp_adapter_helper -q
```

Expected: pass.

---

### Task 5: Update Upstream Transport Import

**Files:**
- Modify: `src/wf_mcp/broker/service/upstream_transport.py`

- [ ] **Step 1: Replace import**

Change:

```python
from .adapters import require_adapter
```

to:

```python
from wf_sources_mcp.adapters import require_adapter
```

- [ ] **Step 2: Run upstream transport tests**

Run:

```bash
uv run pytest tests/wf_mcp/service/test_upstream_transport.py tests/wf_mcp/service/test_catalog.py tests/wf_mcp/service/test_events.py::test_service_records_tool_call_events -q
```

Expected: pass.

---

### Task 6: Add Import Guard for Old Adapter Helper

**Files:**
- Modify: `tests/wf_sources_mcp/test_import_direction_guard.py`

- [ ] **Step 1: Add forbidden old adapter import test**

Append to `tests/wf_sources_mcp/test_import_direction_guard.py`:

```python
def test_wf_sources_mcp_does_not_import_old_broker_service_adapter_module() -> None:
    root = Path(__file__).resolve().parents[2] / "src" / "wf_sources_mcp"
    forbidden = {"wf_mcp.broker.service.adapters"}
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
        "wf_sources_mcp still imports old wf_mcp broker service adapter module:\n"
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

### Task 7: Update Docs and Archive Plan

**Files:**
- Modify: `docs/current_roadmap.md`
- Modify: `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`
- Move: `docs/superpowers/plans/2026-06-08-wf-sources-mcp-adapter-helper.md` to `docs/historical/superpowers/plans/2026-06-08-wf-sources-mcp-adapter-helper.md`

- [ ] **Step 1: Update `docs/current_roadmap.md`**

Under the `wf_sources_mcp` cleanup section, add:

```markdown
    - Completed: upstream MCP adapter lookup (`require_adapter`) now lives in
      `wf_sources_mcp.adapters`, with `wf_mcp.broker.service.adapters` retained
      as a compatibility shim.
```

- [ ] **Step 2: Update `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`**

Add a completed numbered item before the pending upstream transport/discovery/session services item:

```markdown
21. Complete: upstream MCP adapter lookup (`require_adapter`) moved to
    `wf_sources_mcp.adapters`, with `wf_mcp.broker.service.adapters` retained
    as a compatibility shim.
```

If numbering differs because new items landed meanwhile, keep the completed item before the broad pending item and renumber.

- [ ] **Step 3: Archive the plan**

Run:

```bash
git mv docs/superpowers/plans/2026-06-08-wf-sources-mcp-adapter-helper.md docs/historical/superpowers/plans/2026-06-08-wf-sources-mcp-adapter-helper.md
```

Expected: `git status --short` shows an `R` rename for the plan.

---

### Task 8: Final Verification

**Files:**
- No code edits unless verification finds a real issue.

- [ ] **Step 1: Run focused tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_adapters.py tests/wf_sources_mcp/test_import_direction_guard.py tests/wf_mcp/test_compat_imports.py tests/wf_mcp/service/test_upstream_transport.py tests/wf_mcp/service/test_catalog.py tests/wf_mcp/service/test_events.py::test_service_records_tool_call_events -q
```

Expected: all selected tests pass.

- [ ] **Step 2: Run source-provider tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp -q
```

Expected: all `wf_sources_mcp` tests pass.

- [ ] **Step 3: Run lint**

Run:

```bash
uv run ruff check src/wf_sources_mcp/adapters.py src/wf_mcp/broker/service/adapters.py src/wf_mcp/broker/service/upstream_transport.py tests/wf_sources_mcp/test_adapters.py tests/wf_sources_mcp/test_import_direction_guard.py tests/wf_mcp/test_compat_imports.py
```

Expected: `All checks passed!`

- [ ] **Step 4: Run typecheck**

Run:

```bash
uv run basedpyright --level error src/wf_sources_mcp/adapters.py src/wf_mcp/broker/service/adapters.py src/wf_mcp/broker/service/upstream_transport.py tests/wf_sources_mcp/test_adapters.py tests/wf_mcp/test_compat_imports.py
```

Expected: `0 errors, 0 warnings, 0 notes`

- [ ] **Step 5: Check old adapter helper import usage**

Run:

```bash
rg -n "require_adapter|wf_mcp\\.broker\\.service\\.adapters|from \\.adapters import" src tests
```

Expected:

- `src/wf_sources_mcp/adapters.py` owns canonical `require_adapter`.
- `src/wf_mcp/broker/service/adapters.py` remains as a shim.
- `src/wf_mcp/broker/service/upstream_transport.py` imports from `wf_sources_mcp.adapters`.
- `tests/wf_mcp/test_compat_imports.py` may reference the old shim path.
- `src/wf_sources_mcp` must not import `wf_mcp.broker.service.adapters`.

- [ ] **Step 6: Check whitespace**

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
- Confirmation that canonical `require_adapter` lives in `wf_sources_mcp.adapters`.
- Confirmation that `wf_mcp.broker.service.adapters` is a compatibility shim.
- Confirmation that `UpstreamTransportService` imports canonical `require_adapter`.
- Any deviations from this plan.

Do not claim "full suite passed" unless the full suite was actually run.
