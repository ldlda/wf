# MCP Catalog Aggregation Move Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move MCP source catalog aggregation helpers from `wf_mcp.broker.catalog` into canonical `wf_sources_mcp.catalog` while keeping `wf_mcp` compatibility imports working.

**Architecture:** `wf_sources_mcp.catalog.aggregate` will own `CombinedCatalog` and `snapshot_from_specs`. `wf_mcp.broker.catalog` becomes a thin re-export shim. Production import sites should prefer the canonical path, but `wf_mcp.broker.__init__` can keep re-exporting for compatibility.

**Tech Stack:** Python 3.14, dataclasses, `wf_authoring.NodeCatalog`, `wf_sources_mcp.catalog` DTOs, pytest, ruff, basedpyright.

---

## Hard Boundaries

- Do not move `SourceCatalogService`, `UpstreamTransportService`, `discover_connection_capabilities`, or `wrap_discovered_tool` in this slice.
- Do not introduce any `wf_mcp` import inside `src/wf_sources_mcp/catalog/aggregate.py`.
- Keep `wf_mcp.broker.catalog.CombinedCatalog` and `wf_mcp.broker.catalog.snapshot_from_specs` import-compatible via a shim.
- Do not change payload shape from `CombinedCatalog.as_payload()`.
- Do not change catalog refresh/discovery policy; this is only a code ownership move.
- Do not commit unless the caller explicitly asks for a commit.

## File Map

- Create `src/wf_sources_mcp/catalog/aggregate.py`: canonical `snapshot_from_specs`, `CombinedCatalog`, and private `_qualify_local_name`.
- Modify `src/wf_sources_mcp/catalog/__init__.py`: export `CombinedCatalog` and `snapshot_from_specs`.
- Replace `src/wf_mcp/broker/catalog.py`: compatibility shim re-exporting from `wf_sources_mcp.catalog`.
- Modify `src/wf_mcp/broker/service/source_catalog.py`: import canonical `CombinedCatalog` and `snapshot_from_specs`.
- Modify `src/wf_mcp/broker/service/upstream_transport.py`: import canonical `snapshot_from_specs`.
- Keep or adjust `src/wf_mcp/broker/__init__.py`: re-export from the shim or canonical path, as long as public imports remain stable.
- Create `tests/wf_sources_mcp/test_catalog_aggregate.py`: canonical behavior tests.
- Modify `tests/wf_sources_mcp/test_import_direction_guard.py`: forbid `wf_mcp.broker.catalog` imports inside `wf_sources_mcp`.
- Modify `tests/wf_mcp/test_compat_imports.py`: add shim identity tests.
- Modify docs: `docs/current_roadmap.md` and `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`.
- Move this plan to `docs/historical/superpowers/plans/` after implementation is verified.

---

### Task 1: Add Canonical Catalog Aggregation Tests

**Files:**
- Create: `tests/wf_sources_mcp/test_catalog_aggregate.py`

- [ ] **Step 1: Write canonical tests before implementation**

Create `tests/wf_sources_mcp/test_catalog_aggregate.py`:

```python
from __future__ import annotations

from wf_authoring import NodeSpec
from pydantic import BaseModel

from wf_sources_mcp.catalog import (
    CombinedCatalog,
    DiscoveredPrompt,
    DiscoveredResource,
    snapshot_from_specs,
)


class EchoInput(BaseModel):
    message: str


class EchoOutput(BaseModel):
    text: str


async def _echo(payload: EchoInput) -> EchoOutput:
    return EchoOutput(text=payload.message)


def _echo_spec() -> NodeSpec[EchoInput, EchoOutput]:
    return NodeSpec(
        name="echo",
        input_model=EchoInput,
        output_model=EchoOutput,
        outcomes=("ok",),
        fn=_echo,
        description="Echo message",
        is_async=True,
        input_schema_contract={
            "type": "object",
            "properties": {"message": {"type": "string"}},
            "required": ["message"],
        },
        output_schema_contract={
            "type": "object",
            "properties": {"text": {"type": "string"}},
        },
    )


def test_snapshot_from_specs_qualifies_nodes_resources_and_prompts() -> None:
    snapshot = snapshot_from_specs(
        "demo.default",
        specs={"echo": _echo_spec()},
        tool_display_names={"echo": "Echo Tool"},
        resources=[
            DiscoveredResource(
                uri="demo://docs/guide",
                name="guide",
                title="Guide",
                description="Read me",
                mime_type="text/markdown",
                metadata={"kind": "doc"},
            )
        ],
        prompts=[
            DiscoveredPrompt(
                name="summarize",
                title="Summarize",
                description="Summarize text",
                arguments=[{"name": "topic"}],
                metadata={"kind": "prompt"},
            )
        ],
        metadata={"source": "test"},
        fetched_at_epoch_ms=123,
        max_age_seconds=60,
    )

    assert snapshot.connection_id == "demo.default"
    assert snapshot.nodes[0].qualified_name == "demo.default.echo"
    assert snapshot.nodes[0].local_name == "echo"
    assert snapshot.nodes[0].title == "Echo Tool"
    assert snapshot.resources[0].qualified_name == "demo.default.guide"
    assert snapshot.resources[0].uri == "demo://docs/guide"
    assert snapshot.prompts[0].qualified_name == "demo.default.summarize"
    assert snapshot.prompts[0].arguments == [{"name": "topic"}]
    assert snapshot.metadata == {"source": "test"}


def test_snapshot_from_specs_preserves_already_qualified_node_name() -> None:
    spec = _echo_spec().model_copy(update={"name": "demo.default.echo"})

    snapshot = snapshot_from_specs(
        "demo.default",
        specs={"demo.default.echo": spec},
        fetched_at_epoch_ms=123,
        max_age_seconds=60,
    )

    assert snapshot.nodes[0].qualified_name == "demo.default.echo"
    assert snapshot.nodes[0].local_name == "echo"


def test_combined_catalog_sorts_entries_and_serializes_payload() -> None:
    first = snapshot_from_specs(
        "zeta.default",
        specs={"echo": _echo_spec()},
        resources=[DiscoveredResource(uri="zeta://guide", name="guide")],
        prompts=[DiscoveredPrompt(name="prompt")],
        metadata={"order": "second"},
        fetched_at_epoch_ms=2,
        max_age_seconds=60,
    )
    second = snapshot_from_specs(
        "alpha.default",
        specs={"echo": _echo_spec()},
        resources=[DiscoveredResource(uri="alpha://guide", name="guide")],
        prompts=[DiscoveredPrompt(name="prompt")],
        metadata={"order": "first"},
        fetched_at_epoch_ms=1,
        max_age_seconds=60,
    )

    catalog = CombinedCatalog(
        snapshots={
            first.connection_id: first,
            second.connection_id: second,
        }
    )
    payload = catalog.as_payload()

    assert [entry.qualified_name for entry in catalog.entries()] == [
        "alpha.default.echo",
        "zeta.default.echo",
    ]
    assert catalog.find_resource("alpha.default.guide") is not None
    assert catalog.find_prompt("zeta.default.prompt") is not None
    assert [node["qualified_name"] for node in payload["nodes"]] == [
        "alpha.default.echo",
        "zeta.default.echo",
    ]
    assert [item["connection_id"] for item in payload["connections"]] == [
        "alpha.default",
        "zeta.default",
    ]
```

- [ ] **Step 2: Run the new tests and verify they fail**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_catalog_aggregate.py -q
```

Expected: fail with `ImportError` because `CombinedCatalog` and `snapshot_from_specs` are not exported from `wf_sources_mcp.catalog` yet.

---

### Task 2: Create Canonical `wf_sources_mcp.catalog.aggregate`

**Files:**
- Create: `src/wf_sources_mcp/catalog/aggregate.py`
- Modify: `src/wf_sources_mcp/catalog/__init__.py`

- [ ] **Step 1: Create the canonical implementation**

Create `src/wf_sources_mcp/catalog/aggregate.py` with the current implementation from `src/wf_mcp/broker/catalog.py`, but replace `wf_mcp.connections.qualify_node_name` with a local helper:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from wf_authoring import NodeCatalog, NodeSpec

from wf_sources_mcp.ids import parse_connection_id
from wf_sources_mcp.sdk.converters import workflow_output_schema_from_mcp_tool_schema

from .entries import (
    CatalogNodeEntry,
    CatalogPromptEntry,
    CatalogResourceEntry,
    DiscoveredPrompt,
    DiscoveredResource,
)
from .models import CatalogSnapshot


def _qualify_local_name(connection_id: str, local_name: str) -> str:
    """Qualify a source-local catalog name without depending on wf_mcp shims."""
    parse_connection_id(connection_id)
    if not local_name:
        raise ValueError("local catalog name must not be empty")
    return f"{connection_id}.{local_name}"


def snapshot_from_specs(
    connection_id: str,
    *,
    specs: dict[str, NodeSpec[Any, Any]],
    tool_display_names: dict[str, str | None] | None = None,
    resources: list[DiscoveredResource] | None = None,
    prompts: list[DiscoveredPrompt] | None = None,
    metadata: dict[str, Any] | None = None,
    fetched_at_epoch_ms: int,
    max_age_seconds: int,
) -> CatalogSnapshot:
    catalog = NodeCatalog.from_specs(*specs.values())
    nodes = [
        CatalogNodeEntry(
            qualified_name=entry.name
            if entry.name.startswith(f"{connection_id}.")
            else _qualify_local_name(connection_id, entry.name),
            connection_id=connection_id,
            local_name=entry.name.removeprefix(f"{connection_id}."),
            title=(tool_display_names or {}).get(
                entry.name.removeprefix(f"{connection_id}."),
                entry.display_name,
            ),
            description=entry.description,
            outcomes=entry.outcomes,
            input_schema=entry.input_schema,
            output_schema=workflow_output_schema_from_mcp_tool_schema(
                entry.output_schema
            ),
        )
        for entry in catalog.entries()
    ]
    resource_entries = [
        CatalogResourceEntry(
            qualified_name=_qualify_local_name(connection_id, resource.name),
            connection_id=connection_id,
            local_name=resource.name,
            title=resource.title,
            uri=resource.uri,
            description=resource.description,
            mime_type=resource.mime_type,
            metadata=resource.metadata,
        )
        for resource in resources or []
    ]
    prompt_entries = [
        CatalogPromptEntry(
            qualified_name=_qualify_local_name(connection_id, prompt.name),
            connection_id=connection_id,
            local_name=prompt.name,
            title=prompt.title,
            description=prompt.description,
            arguments=prompt.arguments,
            metadata=prompt.metadata,
        )
        for prompt in prompts or []
    ]
    return CatalogSnapshot(
        connection_id=connection_id,
        fetched_at_epoch_ms=fetched_at_epoch_ms,
        max_age_seconds=max_age_seconds,
        nodes=nodes,
        resources=resource_entries,
        prompts=prompt_entries,
        metadata=metadata or {},
    )


@dataclass(slots=True)
class CombinedCatalog:
    snapshots: dict[str, CatalogSnapshot] = field(default_factory=dict)

    def entries(self) -> list[CatalogNodeEntry]:
        result: list[CatalogNodeEntry] = []
        for snapshot in self.snapshots.values():
            result.extend(snapshot.nodes)
        return sorted(result, key=lambda entry: entry.qualified_name)

    def resource_entries(self) -> list[CatalogResourceEntry]:
        result: list[CatalogResourceEntry] = []
        for snapshot in self.snapshots.values():
            result.extend(snapshot.resources)
        return sorted(result, key=lambda entry: entry.qualified_name)

    def prompt_entries(self) -> list[CatalogPromptEntry]:
        result: list[CatalogPromptEntry] = []
        for snapshot in self.snapshots.values():
            result.extend(snapshot.prompts)
        return sorted(result, key=lambda entry: entry.qualified_name)

    def find_resource(self, qualified_name: str) -> CatalogResourceEntry | None:
        for entry in self.resource_entries():
            if entry.qualified_name == qualified_name:
                return entry
        return None

    def find_prompt(self, qualified_name: str) -> CatalogPromptEntry | None:
        for entry in self.prompt_entries():
            if entry.qualified_name == qualified_name:
                return entry
        return None

    def as_payload(self) -> dict[str, Any]:
        return {
            "nodes": [
                {
                    "qualified_name": entry.qualified_name,
                    "connection_id": entry.connection_id,
                    "local_name": entry.local_name,
                    "title": entry.title,
                    "description": entry.description,
                    "outcomes": list(entry.outcomes),
                    "input_schema": entry.input_schema,
                    "output_schema": entry.output_schema,
                }
                for entry in self.entries()
            ],
            "resources": [
                {
                    "qualified_name": entry.qualified_name,
                    "connection_id": entry.connection_id,
                    "local_name": entry.local_name,
                    "title": entry.title,
                    "uri": entry.uri,
                    "description": entry.description,
                    "mime_type": entry.mime_type,
                    "metadata": entry.metadata,
                }
                for entry in self.resource_entries()
            ],
            "prompts": [
                {
                    "qualified_name": entry.qualified_name,
                    "connection_id": entry.connection_id,
                    "local_name": entry.local_name,
                    "title": entry.title,
                    "description": entry.description,
                    "arguments": entry.arguments,
                    "metadata": entry.metadata,
                }
                for entry in self.prompt_entries()
            ],
            "connections": [
                {
                    "connection_id": snapshot.connection_id,
                    "fetched_at_epoch_ms": snapshot.fetched_at_epoch_ms,
                    "max_age_seconds": snapshot.max_age_seconds,
                    "metadata": snapshot.metadata,
                }
                for snapshot in sorted(
                    self.snapshots.values(),
                    key=lambda snapshot: snapshot.connection_id,
                )
            ],
        }


__all__ = ["CombinedCatalog", "snapshot_from_specs"]
```

- [ ] **Step 2: Export the canonical symbols**

Modify `src/wf_sources_mcp/catalog/__init__.py`:

```python
from __future__ import annotations

from .aggregate import CombinedCatalog, snapshot_from_specs
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
    "CombinedCatalog",
    "DiscoveredPrompt",
    "DiscoveredResource",
    "DiscoveredTool",
    "dump_catalog_snapshot",
    "snapshot_from_specs",
]
```

- [ ] **Step 3: Run canonical tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_catalog_aggregate.py -q
```

Expected: all tests pass.

---

### Task 3: Replace `wf_mcp.broker.catalog` With a Compatibility Shim

**Files:**
- Modify: `src/wf_mcp/broker/catalog.py`
- Modify: `tests/wf_mcp/test_compat_imports.py`

- [ ] **Step 1: Replace the old implementation with a shim**

Replace `src/wf_mcp/broker/catalog.py` with:

```python
"""Compatibility shim for MCP source catalog aggregation helpers.

Canonical implementation lives in `wf_sources_mcp.catalog`.
"""

from __future__ import annotations

from wf_sources_mcp.catalog import CombinedCatalog, snapshot_from_specs

__all__ = ["CombinedCatalog", "snapshot_from_specs"]
```

- [ ] **Step 2: Add shim identity tests**

Append this test to `tests/wf_mcp/test_compat_imports.py`:

```python
def test_wf_mcp_broker_catalog_shim_reexports_wf_sources_mcp_catalog() -> None:
    from wf_mcp.broker.catalog import CombinedCatalog as CompatCombinedCatalog
    from wf_mcp.broker.catalog import snapshot_from_specs as compat_snapshot_from_specs
    from wf_sources_mcp.catalog import CombinedCatalog, snapshot_from_specs

    assert CompatCombinedCatalog is CombinedCatalog
    assert compat_snapshot_from_specs is snapshot_from_specs
```

- [ ] **Step 3: Run the compatibility test**

Run:

```bash
uv run pytest tests/wf_mcp/test_compat_imports.py::test_wf_mcp_broker_catalog_shim_reexports_wf_sources_mcp_catalog -q
```

Expected: pass.

---

### Task 4: Update Production Imports to Canonical Path

**Files:**
- Modify: `src/wf_mcp/broker/service/source_catalog.py`
- Modify: `src/wf_mcp/broker/service/upstream_transport.py`
- Review: `src/wf_mcp/broker/__init__.py`

- [ ] **Step 1: Update `source_catalog.py` imports**

Change:

```python
from ..catalog import CombinedCatalog, snapshot_from_specs
```

to:

```python
from wf_sources_mcp.catalog import CombinedCatalog, snapshot_from_specs
```

- [ ] **Step 2: Update `upstream_transport.py` imports**

Change:

```python
from wf_mcp.broker.catalog import snapshot_from_specs
```

to:

```python
from wf_sources_mcp.catalog import snapshot_from_specs
```

- [ ] **Step 3: Leave or simplify broker package exports**

Inspect `src/wf_mcp/broker/__init__.py`. If it still imports from `.catalog`, that is acceptable because `.catalog` is now a compatibility shim. If ruff flags anything, change only the import line to:

```python
from wf_sources_mcp.catalog import CombinedCatalog, snapshot_from_specs
```

Do not remove `CombinedCatalog` or `snapshot_from_specs` from `__all__`.

- [ ] **Step 4: Run focused service tests**

Run:

```bash
uv run pytest tests/wf_mcp/service/test_catalog.py tests/wf_mcp/service/test_adapters.py tests/wf_mcp/service/test_upstream_transport.py -q
```

Expected: pass.

---

### Task 5: Strengthen Import-Direction Guard

**Files:**
- Modify: `tests/wf_sources_mcp/test_import_direction_guard.py`

- [ ] **Step 1: Add old broker catalog module to the forbidden catalog imports**

In `test_wf_sources_mcp_does_not_import_wf_mcp_catalog_dtos`, extend `forbidden`:

```python
    forbidden = {
        "wf_mcp.broker.catalog",
        "wf_mcp.capabilities",
        "wf_mcp.catalog",
        "wf_mcp.catalog.models",
    }
```

- [ ] **Step 2: Run the import-direction guard**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_import_direction_guard.py -q
```

Expected: pass.

---

### Task 6: Update Docs and Archive Plan

**Files:**
- Modify: `docs/current_roadmap.md`
- Modify: `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`
- Move: `docs/superpowers/plans/2026-06-07-wf-sources-mcp-catalog-aggregation.md` to `docs/historical/superpowers/plans/2026-06-07-wf-sources-mcp-catalog-aggregation.md`

- [ ] **Step 1: Update `docs/current_roadmap.md`**

Under the MCP upstream source runtime cleanup / `wf_sources_mcp` section, add:

```markdown
    - Completed: MCP source catalog aggregation helpers (`CombinedCatalog` and
      `snapshot_from_specs`) now live in `wf_sources_mcp.catalog`; the old
      `wf_mcp.broker.catalog` path is a compatibility shim.
```

- [ ] **Step 2: Update `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`**

Add a completed numbered item after the current catalog/runtime items:

```markdown
16. Complete: MCP source catalog aggregation helpers (`CombinedCatalog` and
    `snapshot_from_specs`) moved to `wf_sources_mcp.catalog`, with
    `wf_mcp.broker.catalog` retained as a compatibility shim.
```

If the numbering differs because new items landed meanwhile, keep the order chronological and renumber the following item.

- [ ] **Step 3: Archive the plan**

Run:

```bash
git mv docs/superpowers/plans/2026-06-07-wf-sources-mcp-catalog-aggregation.md docs/historical/superpowers/plans/2026-06-07-wf-sources-mcp-catalog-aggregation.md
```

Expected: `git status --short` shows an `R` rename for the plan.

---

### Task 7: Final Verification

**Files:**
- No code edits unless verification finds a real issue.

- [ ] **Step 1: Run focused tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_catalog_aggregate.py tests/wf_sources_mcp/test_catalog_dtos.py tests/wf_sources_mcp/test_import_direction_guard.py tests/wf_mcp/test_compat_imports.py tests/wf_mcp/service/test_catalog.py tests/wf_mcp/service/test_adapters.py tests/wf_mcp/service/test_upstream_transport.py -q
```

Expected: all selected tests pass.

- [ ] **Step 2: Run source package tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp -q
```

Expected: all `wf_sources_mcp` tests pass.

- [ ] **Step 3: Run lint**

Run:

```bash
uv run ruff check src/wf_sources_mcp/catalog src/wf_mcp/broker/catalog.py src/wf_mcp/broker/service/source_catalog.py src/wf_mcp/broker/service/upstream_transport.py tests/wf_sources_mcp/test_catalog_aggregate.py tests/wf_sources_mcp/test_import_direction_guard.py tests/wf_mcp/test_compat_imports.py
```

Expected: `All checks passed!`

- [ ] **Step 4: Run typecheck**

Run:

```bash
uv run basedpyright --level error src/wf_sources_mcp src/wf_mcp/broker/catalog.py src/wf_mcp/broker/service/source_catalog.py src/wf_mcp/broker/service/upstream_transport.py
```

Expected: `0 errors, 0 warnings, 0 notes`

- [ ] **Step 5: Check old import usage**

Run:

```bash
rg -n "wf_mcp\.broker\.catalog|from \.\.catalog import|from \.catalog import" src tests
```

Expected: only compatibility exports/tests or unrelated non-MCP package imports remain. `src/wf_mcp/broker/service/source_catalog.py` and `src/wf_mcp/broker/service/upstream_transport.py` should not import the old broker catalog path.

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
- Whether `wf_mcp.broker.catalog` is now a shim.
- Whether `wf_sources_mcp.catalog.aggregate` imports any `wf_mcp` module. It should not.
- Any deviations from this plan.

Do not claim "full suite passed" unless the full suite was actually run.
