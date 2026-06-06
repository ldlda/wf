# wf_sources_mcp Catalog DTOs Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move upstream MCP discovery/catalog DTOs from `wf_mcp` into canonical `wf_sources_mcp.catalog` modules while preserving `wf_mcp` compatibility shims.

**Architecture:** `wf_sources_mcp` owns MCP-as-upstream-source data shapes. `wf_mcp` keeps old import paths and frontend/entrypoint compatibility. This slice moves DTOs only; it does not move catalog services, discovery I/O, SDK adapters, runtime/session pools, or broker orchestration.

**Tech Stack:** Python 3.14, dataclasses, pytest, Ruff, basedpyright, `src/` package layout.

---

## Boundaries

Move only DTO/model code:

- `DiscoveredTool`
- `DiscoveredResource`
- `DiscoveredPrompt`
- `CatalogNodeEntry`
- `CatalogResourceEntry`
- `CatalogPromptEntry`
- `CatalogSnapshot`
- `dump_catalog_snapshot`

Do not move:

- `wf_mcp.broker.catalog.CombinedCatalog`
- `wf_mcp.broker.catalog.snapshot_from_specs`
- `wf_mcp.broker.discovery`
- `wf_mcp.sdk.*`
- `wf_mcp.runtime.*`
- `SourceCatalogService`
- `UpstreamTransportService`
- MCP frontend/admin/workflow tools

Rationale: this removes current temporary DTO dependencies from `wf_sources_mcp.storage.store` without dragging live upstream I/O into this slice.

## File Map

Create:

- `src/wf_sources_mcp/catalog/__init__.py` — exports canonical catalog DTOs.
- `src/wf_sources_mcp/catalog/entries.py` — discovered tool/resource/prompt DTOs and catalog entry DTOs.
- `src/wf_sources_mcp/catalog/models.py` — `CatalogSnapshot` and `dump_catalog_snapshot`.
- `tests/wf_sources_mcp/test_catalog_dtos.py` — canonical DTO tests.

Modify:

- `src/wf_sources_mcp/storage/store.py` — import catalog DTOs from `wf_sources_mcp.catalog`.
- `src/wf_sources_mcp/__init__.py` — optionally lazy-export catalog DTOs if direct root exports are already expected.
- `src/wf_mcp/capabilities.py` — replace with compatibility shim.
- `src/wf_mcp/catalog/models.py` — replace with compatibility shim.
- `src/wf_mcp/catalog/__init__.py` — re-export shim symbols.
- `src/wf_mcp/models.py` — canonical import from `wf_sources_mcp.catalog.models`.
- Production imports that currently use `wf_mcp.capabilities` or `wf_mcp.catalog.models` for DTOs may be changed to `wf_sources_mcp.catalog`.
- `tests/wf_mcp/test_compat_imports.py` — shim identity tests.
- `tests/wf_sources_mcp/test_import_direction_guard.py` — ensure catalog DTOs do not import forbidden MCP frontend/proxy modules.
- `docs/current_roadmap.md` — mark catalog DTO slice complete.
- `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md` — mark catalog DTO slice complete.

After implementation, move this plan to:

- `docs/historical/superpowers/plans/2026-06-07-wf-sources-mcp-catalog-dtos-slice.md`

---

### Task 1: Create Canonical Catalog DTO Modules

**Files:**
- Create: `src/wf_sources_mcp/catalog/entries.py`
- Create: `src/wf_sources_mcp/catalog/models.py`
- Create: `src/wf_sources_mcp/catalog/__init__.py`
- Test: `tests/wf_sources_mcp/test_catalog_dtos.py`

- [ ] **Step 1: Create `entries.py`**

Create `src/wf_sources_mcp/catalog/entries.py` with the current contents of `src/wf_mcp/capabilities.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class DiscoveredTool:
    """Tool snapshot after converting from an upstream MCP SDK tool."""

    name: str
    title: str | None
    description: str | None
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    outcomes: tuple[str, ...] = ("ok",)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class DiscoveredResource:
    """Resource snapshot after converting from an upstream MCP SDK resource."""

    uri: str
    name: str
    title: str | None
    description: str | None
    mime_type: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class DiscoveredPrompt:
    """Prompt snapshot after converting from an upstream MCP SDK prompt."""

    name: str
    title: str | None
    description: str | None
    arguments: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class CatalogNodeEntry:
    """Namespaced tool entry stored in an MCP upstream catalog snapshot."""

    qualified_name: str
    connection_id: str
    local_name: str
    title: str | None
    description: str | None
    outcomes: tuple[str, ...]
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]


@dataclass(slots=True)
class CatalogResourceEntry:
    """Namespaced resource entry stored in an MCP upstream catalog snapshot."""

    qualified_name: str
    connection_id: str
    local_name: str
    title: str | None
    uri: str
    description: str | None
    mime_type: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class CatalogPromptEntry:
    """Namespaced prompt entry stored in an MCP upstream catalog snapshot."""

    qualified_name: str
    connection_id: str
    local_name: str
    title: str | None
    description: str | None
    arguments: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


__all__ = [
    "CatalogNodeEntry",
    "CatalogPromptEntry",
    "CatalogResourceEntry",
    "DiscoveredPrompt",
    "DiscoveredResource",
    "DiscoveredTool",
]
```

- [ ] **Step 2: Create `models.py`**

Create `src/wf_sources_mcp/catalog/models.py`:

```python
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .entries import CatalogNodeEntry, CatalogPromptEntry, CatalogResourceEntry


@dataclass(slots=True)
class CatalogSnapshot:
    """Stored upstream MCP catalog snapshot for one source connection."""

    connection_id: str
    fetched_at_epoch_ms: int
    max_age_seconds: int
    nodes: list[CatalogNodeEntry] = field(default_factory=list)
    resources: list[CatalogResourceEntry] = field(default_factory=list)
    prompts: list[CatalogPromptEntry] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_stale(self, now_epoch_ms: int) -> bool:
        age_ms = now_epoch_ms - self.fetched_at_epoch_ms
        return age_ms > self.max_age_seconds * 1000


def dump_catalog_snapshot(snapshot: CatalogSnapshot) -> dict[str, Any]:
    return {
        "connection_id": snapshot.connection_id,
        "fetched_at_epoch_ms": snapshot.fetched_at_epoch_ms,
        "max_age_seconds": snapshot.max_age_seconds,
        "nodes": [asdict(node) for node in snapshot.nodes],
        "resources": [asdict(resource) for resource in snapshot.resources],
        "prompts": [asdict(prompt) for prompt in snapshot.prompts],
        "metadata": snapshot.metadata,
    }


__all__ = [
    "CatalogSnapshot",
    "dump_catalog_snapshot",
]
```

- [ ] **Step 3: Create package exports**

Create `src/wf_sources_mcp/catalog/__init__.py`:

```python
from __future__ import annotations

from .entries import (
    CatalogNodeEntry,
    CatalogPromptEntry,
    CatalogResourceEntry,
    DiscoveredPrompt,
    DiscoveredResource,
    DiscoveredTool,
)
from .models import CatalogSnapshot, dump_catalog_snapshot

__all__ = [
    "CatalogNodeEntry",
    "CatalogPromptEntry",
    "CatalogResourceEntry",
    "CatalogSnapshot",
    "DiscoveredPrompt",
    "DiscoveredResource",
    "DiscoveredTool",
    "dump_catalog_snapshot",
]
```

- [ ] **Step 4: Add canonical DTO tests**

Create `tests/wf_sources_mcp/test_catalog_dtos.py`:

```python
from __future__ import annotations

from wf_sources_mcp.catalog import (
    CatalogNodeEntry,
    CatalogPromptEntry,
    CatalogResourceEntry,
    CatalogSnapshot,
    DiscoveredPrompt,
    DiscoveredResource,
    DiscoveredTool,
    dump_catalog_snapshot,
)


def test_discovered_tool_default_outcome_and_metadata() -> None:
    tool = DiscoveredTool(
        name="echo",
        title=None,
        description="Echo input",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
    )

    assert tool.outcomes == ("ok",)
    assert tool.metadata == {}


def test_discovered_resource_and_prompt_keep_structural_fields() -> None:
    resource = DiscoveredResource(
        uri="docs://guide",
        name="guide",
        title="Guide",
        description="Read me",
        mime_type="text/markdown",
    )
    prompt = DiscoveredPrompt(
        name="summarize",
        title=None,
        description="Summarize",
        arguments=[{"name": "topic"}],
    )

    assert resource.uri == "docs://guide"
    assert resource.mime_type == "text/markdown"
    assert prompt.arguments == [{"name": "topic"}]


def test_catalog_snapshot_staleness_and_dump_shape() -> None:
    snapshot = CatalogSnapshot(
        connection_id="demo.default",
        fetched_at_epoch_ms=1_000,
        max_age_seconds=2,
        nodes=[
            CatalogNodeEntry(
                qualified_name="demo.default.echo",
                connection_id="demo.default",
                local_name="echo",
                title=None,
                description="Echo",
                outcomes=("ok",),
                input_schema={"type": "object"},
                output_schema={"type": "object"},
            )
        ],
        resources=[
            CatalogResourceEntry(
                qualified_name="demo.default.guide",
                connection_id="demo.default",
                local_name="guide",
                title=None,
                uri="docs://guide",
                description="Guide",
            )
        ],
        prompts=[
            CatalogPromptEntry(
                qualified_name="demo.default.summarize",
                connection_id="demo.default",
                local_name="summarize",
                title=None,
                description="Summarize",
            )
        ],
        metadata={"source": "test"},
    )

    assert snapshot.is_stale(3_001) is True
    dumped = dump_catalog_snapshot(snapshot)
    assert dumped["connection_id"] == "demo.default"
    assert dumped["nodes"][0]["qualified_name"] == "demo.default.echo"
    assert dumped["resources"][0]["uri"] == "docs://guide"
    assert dumped["prompts"][0]["local_name"] == "summarize"
    assert dumped["metadata"] == {"source": "test"}
```

- [ ] **Step 5: Run canonical DTO tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_catalog_dtos.py -q
```

Expected: 3 tests pass.

---

### Task 2: Replace Old DTO Modules With Shims

**Files:**
- Modify: `src/wf_mcp/capabilities.py`
- Modify: `src/wf_mcp/catalog/models.py`
- Modify: `src/wf_mcp/catalog/__init__.py`
- Modify: `tests/wf_mcp/test_compat_imports.py`

- [ ] **Step 1: Replace `wf_mcp.capabilities` with shim**

Replace `src/wf_mcp/capabilities.py` with:

```python
"""Compatibility shim for MCP upstream catalog entry DTOs.

Canonical implementation lives in `wf_sources_mcp.catalog.entries`.
"""

from __future__ import annotations

from wf_sources_mcp.catalog.entries import (
    CatalogNodeEntry,
    CatalogPromptEntry,
    CatalogResourceEntry,
    DiscoveredPrompt,
    DiscoveredResource,
    DiscoveredTool,
)

__all__ = [
    "CatalogNodeEntry",
    "CatalogPromptEntry",
    "CatalogResourceEntry",
    "DiscoveredPrompt",
    "DiscoveredResource",
    "DiscoveredTool",
]
```

- [ ] **Step 2: Replace `wf_mcp.catalog.models` with shim**

Replace `src/wf_mcp/catalog/models.py` with:

```python
"""Compatibility shim for MCP upstream catalog snapshot DTOs.

Canonical implementation lives in `wf_sources_mcp.catalog.models`.
"""

from __future__ import annotations

from wf_sources_mcp.catalog.models import CatalogSnapshot, dump_catalog_snapshot

__all__ = [
    "CatalogSnapshot",
    "dump_catalog_snapshot",
]
```

- [ ] **Step 3: Keep `wf_mcp.catalog` package re-exporting**

Set `src/wf_mcp/catalog/__init__.py` to:

```python
from __future__ import annotations

from .models import CatalogSnapshot, dump_catalog_snapshot

__all__ = [
    "CatalogSnapshot",
    "dump_catalog_snapshot",
]
```

- [ ] **Step 4: Add shim identity tests**

Append to `tests/wf_mcp/test_compat_imports.py`:

```python
def test_wf_mcp_capabilities_shim_reexports_wf_sources_mcp_catalog_entries() -> None:
    from wf_mcp.capabilities import CatalogNodeEntry as CompatCatalogNodeEntry
    from wf_mcp.capabilities import DiscoveredTool as CompatDiscoveredTool
    from wf_sources_mcp.catalog import CatalogNodeEntry, DiscoveredTool

    assert CompatCatalogNodeEntry is CatalogNodeEntry
    assert CompatDiscoveredTool is DiscoveredTool


def test_wf_mcp_catalog_models_shim_reexports_wf_sources_mcp_catalog_models() -> None:
    from wf_mcp.catalog.models import CatalogSnapshot as CompatCatalogSnapshot
    from wf_mcp.catalog.models import dump_catalog_snapshot as compat_dump
    from wf_sources_mcp.catalog import CatalogSnapshot, dump_catalog_snapshot

    assert CompatCatalogSnapshot is CatalogSnapshot
    assert compat_dump is dump_catalog_snapshot
```

- [ ] **Step 5: Run compatibility tests**

Run:

```bash
uv run pytest tests/wf_mcp/test_compat_imports.py tests/wf_mcp/test_store.py -q
```

Expected: tests pass, proving old imports still work.

---

### Task 3: Update Canonical Imports in `wf_sources_mcp` and Production Code

**Files:**
- Modify: `src/wf_sources_mcp/storage/store.py`
- Modify: `src/wf_mcp/models.py`
- Modify: selected production files under `src/wf_mcp/`

- [ ] **Step 1: Update `wf_sources_mcp.storage.store` imports**

Change the `TYPE_CHECKING` import:

```python
if TYPE_CHECKING:
    from wf_sources_mcp.catalog.models import CatalogSnapshot
```

Change `save_catalog()` lazy import:

```python
from wf_sources_mcp.catalog.models import dump_catalog_snapshot
```

Change `load_catalog()` lazy imports:

```python
from wf_sources_mcp.catalog import (
    CatalogNodeEntry,
    CatalogPromptEntry,
    CatalogResourceEntry,
    CatalogSnapshot as CatalogSnapshotType,
)
```

- [ ] **Step 2: Update `wf_mcp.models` canonical import**

Change `src/wf_mcp/models.py`:

```python
from wf_sources_mcp.catalog.models import CatalogSnapshot, dump_catalog_snapshot
```

Keep existing `AuthRecord`, `BrokerConfig`, and `ConnectionConfig` exports unchanged.

- [ ] **Step 3: Rewrite production DTO imports where safe**

Change production files that directly import DTOs to canonical package imports:

```python
from wf_sources_mcp.catalog import (
    CatalogNodeEntry,
    CatalogPromptEntry,
    CatalogResourceEntry,
    CatalogSnapshot,
    DiscoveredPrompt,
    DiscoveredResource,
    DiscoveredTool,
    dump_catalog_snapshot,
)
```

Likely files:

- `src/wf_mcp/broker/catalog.py`
- `src/wf_mcp/broker/discovery.py`
- `src/wf_mcp/broker/service/core.py`
- `src/wf_mcp/broker/service/events.py`
- `src/wf_mcp/broker/service/source_catalog.py`
- `src/wf_mcp/broker/service/upstream_transport.py`
- `src/wf_mcp/sdk/adapter.py`
- `src/wf_mcp/sdk/base.py`
- `src/wf_mcp/sdk/converters.py`
- `src/wf_mcp/workflow/wrappers.py`

Do not chase every test import. Tests importing `wf_mcp.capabilities` are useful compatibility coverage unless the test is specifically about the canonical package.

- [ ] **Step 4: Confirm production imports no longer depend on shims**

Run:

```bash
rg -n "from wf_mcp\\.capabilities|from wf_mcp\\.catalog\\.models|from \\.\\.capabilities|from \\.capabilities|from \\.\\.models import CatalogSnapshot|from wf_mcp\\.models import CatalogSnapshot" src
```

Expected: no production imports use old DTO paths except shim files and possibly `wf_mcp.__init__` facade exports. If `wf_mcp.__init__` imports `DiscoveredTool` from `.capabilities`, leave it as facade behavior.

- [ ] **Step 5: Run focused production tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp tests/wf_mcp/test_store.py tests/wf_mcp/test_sdk_adapter.py tests/wf_mcp/service/test_catalog.py tests/wf_mcp/service/test_upstream_transport.py tests/wf_mcp/test_workflow_wrappers.py -q
```

Expected: all focused tests pass.

---

### Task 4: Strengthen Import-Direction Guard

**Files:**
- Modify: `tests/wf_sources_mcp/test_import_direction_guard.py`
- Test: `tests/wf_sources_mcp/test_import_direction_guard.py`

- [ ] **Step 1: Keep forbidden frontend/proxy prefixes**

Ensure `FORBIDDEN_WF_MCP_PREFIXES` still includes:

```python
FORBIDDEN_WF_MCP_PREFIXES = (
    "wf_mcp.admin_surface",
    "wf_mcp.workflow_surface",
    "wf_mcp.server",
    "wf_mcp.proxy",
    "wf_mcp.cli",
)
```

- [ ] **Step 2: Update comment for current temporary imports**

Update the comment above the prefix tuple:

```python
# Temporary low-level wf_mcp imports are allowed for connection id parsing,
# reserved names, and broker DTO conversion. Catalog DTOs should now be local
# to wf_sources_mcp. Frontend/proxy/workflow-surface imports are forbidden
# because wf_sources_mcp is upstream-source code.
```

- [ ] **Step 3: Add a targeted no-old-catalog-import assertion**

Add this test:

```python
def test_wf_sources_mcp_does_not_import_wf_mcp_catalog_dtos() -> None:
    root = Path(__file__).resolve().parents[2] / "src" / "wf_sources_mcp"
    forbidden = {
        "wf_mcp.capabilities",
        "wf_mcp.catalog",
        "wf_mcp.catalog.models",
    }
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
        "wf_sources_mcp still imports old wf_mcp catalog DTO modules:\n"
        + "\n".join(f"  {violation}" for violation in violations)
    )
```

- [ ] **Step 4: Run guard tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_import_direction_guard.py -q
```

Expected: guard tests pass.

---

### Task 5: Docs Status and Plan Archival

**Files:**
- Modify: `docs/current_roadmap.md`
- Modify: `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`
- Move: `docs/superpowers/plans/2026-06-07-wf-sources-mcp-catalog-dtos-slice.md` to `docs/historical/superpowers/plans/2026-06-07-wf-sources-mcp-catalog-dtos-slice.md`

- [ ] **Step 1: Update roadmap**

In `docs/current_roadmap.md`, under the MCP package split section, add:

```markdown
      Third `wf_sources_mcp` slice complete: upstream MCP catalog/discovery DTOs
      and catalog snapshot dumping now live in `wf_sources_mcp.catalog`, with
      `wf_mcp.capabilities` and `wf_mcp.catalog.models` retained as shims.
```

- [ ] **Step 2: Update long-lived API boundary spec**

In `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`, update the `wf_sources_mcp` status list so it includes:

```markdown
3. Complete: upstream MCP catalog/discovery DTOs moved to `wf_sources_mcp.catalog`, with `wf_mcp.capabilities` and `wf_mcp.catalog.models` retained as shims.
4. Upstream transport/discovery/session services.
```

- [ ] **Step 3: Move completed plan to historical**

Run:

```bash
git mv docs/superpowers/plans/2026-06-07-wf-sources-mcp-catalog-dtos-slice.md docs/historical/superpowers/plans/2026-06-07-wf-sources-mcp-catalog-dtos-slice.md
```

Expected: `git status --short` shows an `R` rename for this plan.

---

### Task 6: Final Verification

**Files:**
- All changed files

- [ ] **Step 1: Run focused extraction tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp tests/wf_mcp/test_compat_imports.py tests/wf_mcp/test_store.py tests/wf_mcp/test_sdk_adapter.py tests/wf_mcp/service/test_catalog.py tests/wf_mcp/service/test_upstream_transport.py tests/wf_mcp/test_workflow_wrappers.py -q
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

Expected: full suite passes with current skip/xfail counts.

- [ ] **Step 4: Review remaining old DTO imports**

Run:

```bash
rg -n "from wf_mcp\\.capabilities|from wf_mcp\\.catalog\\.models|from wf_mcp\\.models import CatalogSnapshot" src tests
```

Expected: remaining occurrences are compatibility shims, facade exports, or tests intentionally exercising old import paths.

- [ ] **Step 5: Report**

Report:

- files created/modified
- focused/full verification output
- whether `wf_sources_mcp.storage.store` now imports catalog DTOs from `wf_sources_mcp.catalog`
- whether compatibility shims remain
- deviations from this plan

Do not commit unless the user explicitly asks. If committing, use:

```bash
git add -A
git commit -m "refactor: move mcp catalog dtos to wf_sources_mcp"
```

---

## Self-Review

- Spec coverage: covers catalog DTO and snapshot cache dependency cleanup before upstream session/runtime moves.
- Placeholder scan: no `TODO`, `TBD`, or unspecified test steps.
- Type consistency: canonical symbols keep the same names and dataclass field shapes as existing `wf_mcp` DTOs, preserving compatibility.
