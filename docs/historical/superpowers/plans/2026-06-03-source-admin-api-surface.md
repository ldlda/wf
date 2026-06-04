# Source Admin API Surface Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a protocol-neutral read-only source/admin surface in `wf_api` and make MCP admin source tools delegate through it.

**Architecture:** `WorkflowApiSurface` stays workflow-lifecycle-only. Source/admin operations get a sibling `WorkflowSourceAdminSurface` plus `WorkflowSourceAdminApi` implementation over `WorkflowOperationContext.specs.capability_sources`. The MCP admin handler becomes an adapter over this neutral API while connection/raw MCP methods remain MCP-broker-owned.

**Tech Stack:** Python 3.14, dataclasses, Protocols, Pydantic-backed platform models, pytest, ruff, basedpyright.

---

## Current Findings

- Source catalog internals already moved out of the old god service into `src/wf_mcp/broker/service/source_catalog.py`.
- `wf_api` does not currently have a source/admin API module.
- MCP admin source tools still flow through:

```text
wf_mcp.admin_surface.tools
  -> BrokerAdminHandlers
  -> WfMcpService.list_source_summaries / inspect_source
  -> SourceCatalogService
```

- `WorkflowOperationContext.specs.capability_sources` already exposes the source inventory `wf_api` needs for read-only source listing and inspection.

## Scope

In scope:

- `list_sources(cursor=None, limit=50) -> dict`
- `inspect_source(source_id: str) -> dict`
- Protocol-neutral `WorkflowSourceAdminSurface`
- Local implementation `WorkflowSourceAdminApi`
- MCP `BrokerAdminHandlers.list_sources()` and `.inspect_source()` delegate through `WorkflowSourceAdminApi`
- Focused tests proving payload compatibility with existing MCP source output

Out of scope for this slice:

- Adding/removing/updating sources
- Store-backed source registry
- Connection status, catalog refresh, raw method invocation
- JSON-RPC transport methods for source admin
- CLI `wf source ...` commands

Those are follow-up slices once this neutral seam exists.

## File Structure

- Create `src/wf_api/source_admin.py`
  - Owns `WorkflowSourceAdminApi`.
  - Uses only `WorkflowOperationContext` and platform source models.
  - Imports no `wf_mcp`.

- Modify `src/wf_api/surface.py`
  - Adds sibling protocol `WorkflowSourceAdminSurface`.
  - Does not make `WorkflowApiSurface` inherit it.

- Modify `src/wf_api/__init__.py`
  - Exports `WorkflowSourceAdminApi` and `WorkflowSourceAdminSurface`.

- Modify `src/wf_mcp/admin_surface/handlers/broker.py`
  - Construct `WorkflowSourceAdminApi(context_from_service(service))`.
  - Delegate `list_sources` and `inspect_source` to it.
  - Keep connection/catalog/resource/raw methods unchanged.
  - Make those two source methods async, matching the async MCP tool boundary.

- Modify `src/wf_mcp/admin_surface/tools.py`
  - Await async source handler methods.

- Create `tests/wf_api/test_source_admin_api.py`
  - Direct neutral API tests.

- Modify `tests/wf_mcp/test_admin_surface.py`
  - Add adapter smoke coverage for the neutral source admin delegation.

- Modify `docs/current_roadmap.md`
  - Mark the read-only neutral source/admin seam as completed.

---

### Task 1: Add failing `wf_api` source admin tests

**Files:**
- Create: `tests/wf_api/test_source_admin_api.py`

- [ ] **Step 1: Write direct tests**

Create `tests/wf_api/test_source_admin_api.py`:

```python
from __future__ import annotations

from typing import Any

import pytest

from wf_api import WorkflowSourceAdminApi
from wf_api.operation_context import WorkflowOperationContext
from wf_authoring import NodeSpec
from wf_platform import (
    CapabilityBuckets,
    CapabilitySource,
    SourcePermissions,
    SourceVisibility,
)


class DummyEvents:
    def record_event(self, event: object) -> None:
        pass

    def record_workflow_event(
        self,
        event_type: str,
        *,
        capability_id: str,
        payload: dict[str, Any],
    ) -> None:
        pass


class DummyRuntime:
    async def run_workflow_from_plan(self, *args: Any, **kwargs: Any) -> object:
        raise AssertionError("source admin tests must not run workflows")

    async def resume_workflow_from_plan(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> object:
        raise AssertionError("source admin tests must not resume workflows")


class StaticSpecProvider:
    def __init__(self, sources: dict[str, CapabilitySource]) -> None:
        self._sources = sources

    @property
    def capability_sources(self) -> dict[str, CapabilitySource]:
        return self._sources

    def get_qualified_spec(self, qualified_name: str) -> NodeSpec[Any, Any]:
        raise KeyError(f"unknown capability {qualified_name!r}")


def _api(*sources: CapabilitySource) -> WorkflowSourceAdminApi:
    provider = StaticSpecProvider({source.id: source for source in sources})
    return WorkflowSourceAdminApi(
        WorkflowOperationContext(
            artifact_store=None,
            draft_workspace_store=None,
            run_store=None,
            events=DummyEvents(),
            specs=provider,
            runtime=DummyRuntime(),
            live_sources=None,
        )
    )


def _source(source_id: str, *, enabled: bool = True) -> CapabilitySource:
    return CapabilitySource(
        id=source_id,
        kind="connection",
        enabled=enabled,
        capabilities=CapabilityBuckets(),
        visibility=SourceVisibility(
            planner=True,
            mcp_client=True,
            admin_dashboard=True,
        ),
        permissions=SourcePermissions(calls_upstream=True),
        description=f"{source_id} source",
    )


@pytest.mark.asyncio
async def test_source_admin_lists_compact_sources_in_id_order() -> None:
    api = _api(_source("zeta.personal"), _source("alpha.personal", enabled=False))

    payload = await api.list_sources(limit=10)

    assert payload["total"] == 2
    assert payload["next_cursor"] is None
    assert [source["id"] for source in payload["sources"]] == [
        "alpha.personal",
        "zeta.personal",
    ]
    assert payload["sources"][0]["enabled"] is False
    assert payload["sources"][1]["description"] == "zeta.personal source"


@pytest.mark.asyncio
async def test_source_admin_pages_sources() -> None:
    api = _api(_source("a"), _source("b"), _source("c"))

    first = await api.list_sources(limit=2)
    second = await api.list_sources(cursor=first["next_cursor"], limit=2)

    assert [source["id"] for source in first["sources"]] == ["a", "b"]
    assert first["next_cursor"] == "2"
    assert [source["id"] for source in second["sources"]] == ["c"]
    assert second["next_cursor"] is None


@pytest.mark.asyncio
async def test_source_admin_inspects_full_source_inventory() -> None:
    api = _api(_source("demo.personal"))

    payload = await api.inspect_source(source_id="demo.personal")

    assert payload["id"] == "demo.personal"
    assert payload["kind"] == "connection"
    assert payload["description"] == "demo.personal source"
    assert payload["visibility"]["planner"] is True
    assert payload["permissions"]["calls_upstream"] is True


@pytest.mark.asyncio
async def test_source_admin_inspect_unknown_source_raises_clear_key_error() -> None:
    api = _api(_source("demo.personal"))

    with pytest.raises(KeyError, match="unknown source 'missing.source'"):
        await api.inspect_source(source_id="missing.source")
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
uv run pytest tests/wf_api/test_source_admin_api.py -q
```

Expected: FAIL because `WorkflowSourceAdminApi` is not exported yet.

---

### Task 2: Implement `WorkflowSourceAdminApi`

**Files:**
- Create: `src/wf_api/source_admin.py`
- Modify: `src/wf_api/__init__.py`

- [ ] **Step 1: Add source admin API**

Create `src/wf_api/source_admin.py`:

```python
from __future__ import annotations

from typing import Any

from wf_platform import page_items

from .operation_context import WorkflowOperationContext


class WorkflowSourceAdminApi:
    """Read-only protocol-neutral source inventory operations.

    This is a sibling to WorkflowApi, not part of WorkflowApiSurface, because
    source administration is server/platform management rather than workflow
    lifecycle execution.
    """

    def __init__(self, context: WorkflowOperationContext) -> None:
        self.context = context

    async def list_sources(
        self,
        *,
        cursor: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        summaries = [
            source.as_status().model_dump(mode="json")
            for source in sorted(
                self.context.specs.capability_sources.values(),
                key=lambda source: source.id,
            )
        ]
        page = page_items(summaries, cursor=cursor, limit=limit)
        return {
            "sources": list(page.items),
            "next_cursor": page.next_cursor,
            "total": page.total,
        }

    async def inspect_source(self, *, source_id: str) -> dict[str, Any]:
        try:
            source = self.context.specs.capability_sources[source_id]
        except KeyError as exc:
            raise KeyError(f"unknown source {source_id!r}") from exc
        return source.as_inventory().model_dump(mode="json")
```

- [ ] **Step 2: Export from `wf_api`**

Modify `src/wf_api/__init__.py`:

```python
from .source_admin import WorkflowSourceAdminApi
```

Add `"WorkflowSourceAdminApi"` to `__all__`.

- [ ] **Step 3: Run direct tests**

Run:

```bash
uv run pytest tests/wf_api/test_source_admin_api.py -q
```

Expected: PASS.

---

### Task 3: Add sibling surface protocol

**Files:**
- Modify: `src/wf_api/surface.py`
- Modify: `src/wf_api/__init__.py`
- Test: `tests/wf_api/test_source_admin_api.py`

- [ ] **Step 1: Add protocol conformance test**

Append to `tests/wf_api/test_source_admin_api.py`:

```python
from wf_api import WorkflowSourceAdminSurface


def test_source_admin_api_satisfies_surface_protocol() -> None:
    api: WorkflowSourceAdminSurface = _api(_source("demo.personal"))

    assert api is not None
```

- [ ] **Step 2: Add protocol**

In `src/wf_api/surface.py`, add this class near the other surface protocols:

```python
class WorkflowSourceAdminSurface(Protocol):
    """Read-only source/admin methods exposed by platform frontends."""

    async def list_sources(
        self,
        *,
        cursor: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]: ...

    async def inspect_source(
        self,
        *,
        source_id: str,
    ) -> dict[str, Any]: ...
```

Add `"WorkflowSourceAdminSurface"` to `__all__`.

Do not add it as a base class of `WorkflowApiSurface`.

- [ ] **Step 3: Export protocol**

Modify `src/wf_api/__init__.py`:

```python
from .surface import WorkflowSourceAdminSurface
```

Add `"WorkflowSourceAdminSurface"` to `__all__`.

- [ ] **Step 4: Run tests and type check**

Run:

```bash
uv run pytest tests/wf_api/test_source_admin_api.py tests/wf_api/test_import_direction.py -q
uv run basedpyright --level error src/wf_api tests/wf_api/test_source_admin_api.py
```

Expected: tests PASS, basedpyright reports 0 errors.

---

### Task 4: Delegate MCP admin source tools through `wf_api`

**Files:**
- Modify: `src/wf_mcp/admin_surface/handlers/broker.py`
- Modify: `src/wf_mcp/admin_surface/tools.py`
- Test: `tests/wf_mcp/test_admin_surface.py`

- [ ] **Step 1: Add adapter smoke assertion**

In `tests/wf_mcp/test_admin_surface.py`, inside
`test_broker_admin_handlers_list_connections_and_events`, add:

```python
    sources = _run(handlers.list_sources(limit=100))

    source_ids = {source["id"] for source in sources["sources"]}
    assert "wf.std" in source_ids
    assert "wf.docs" in source_ids
    assert sources["total"] >= 2
```

This test uses the existing `_run()` helper.

- [ ] **Step 2: Run the updated test and verify failure**

Run:

```bash
uv run pytest tests/wf_mcp/test_admin_surface.py::test_broker_admin_handlers_list_connections_and_events -q
```

Expected before delegation: FAIL because `BrokerAdminHandlers.list_sources()`
is still sync and returns a dict, not an awaitable. This failure drives the async
source-handler cleanup.

- [ ] **Step 3: Change handler implementation**

Modify `src/wf_mcp/admin_surface/handlers/broker.py`:

```python
from wf_api import WorkflowSourceAdminApi, WorkflowSourceAdminSurface
from wf_mcp.broker.service.workflow_operation_context import context_from_service
```

Update `__init__`:

```python
    def __init__(self, service: WfMcpService) -> None:
        self.service = service
        self.sources: WorkflowSourceAdminSurface = WorkflowSourceAdminApi(
            context_from_service(service)
        )
```

Update source methods:

```python
    async def list_sources(
        self,
        *,
        cursor: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        return await self.sources.list_sources(cursor=cursor, limit=limit)

    async def inspect_source(self, source_id: str) -> dict[str, Any]:
        return await self.sources.inspect_source(source_id=source_id)
```

Do not add an `asyncio.run()` bridge. The handler is called from async MCP tools,
so source methods should be async at this boundary.

- [ ] **Step 4: Await source handler calls in MCP tools**

In `src/wf_mcp/admin_surface/tools.py`, update:

```python
        return await handlers.list_sources(cursor=cursor, limit=limit)
```

and:

```python
        return await handlers.inspect_source(source_id)
```

- [ ] **Step 5: Run MCP admin tests**

Run:

```bash
uv run pytest tests/wf_mcp/test_admin_surface.py tests/wf_mcp/server/test_config.py tests/wf_mcp/test_broker_server.py -q
```

Expected: PASS.

---

### Task 5: Documentation and verification

**Files:**
- Modify: `docs/current_roadmap.md`
- Modify: `docs/superpowers/specs/2026-06-03-cli-api-alignment-notes.md`

- [ ] **Step 1: Update roadmap**

In `docs/current_roadmap.md`, under **Durable API service shape** or
**CLI/API alignment**, add:

```markdown
- Completed: read-only source inventory now has a protocol-neutral
  `WorkflowSourceAdminApi` / `WorkflowSourceAdminSurface`; MCP admin source
  tools delegate through it while connection/raw MCP operations remain
  broker-owned.
```

- [ ] **Step 2: Update CLI/API notes**

In `docs/superpowers/specs/2026-06-03-cli-api-alignment-notes.md`, under
**Next Slices**, replace the source/admin item with:

```markdown
1. **Source/admin transport and CLI commands**
   - Build JSON-RPC methods and `wf source ...` commands over
     `WorkflowSourceAdminSurface`.
   - Keep mutation out until the store-backed source registry is designed.
```

- [ ] **Step 3: Run verification**

Run:

```bash
uv run pytest tests/wf_api/test_source_admin_api.py tests/wf_mcp/test_admin_surface.py tests/wf_mcp/server/test_config.py tests/wf_mcp/test_broker_server.py -q
uv run ruff check src/wf_api src/wf_mcp/admin_surface tests/wf_api/test_source_admin_api.py tests/wf_mcp/test_admin_surface.py tests/wf_mcp/server/test_config.py tests/wf_mcp/test_broker_server.py
uv run ruff format --check src/wf_api src/wf_mcp/admin_surface tests/wf_api/test_source_admin_api.py tests/wf_mcp/test_admin_surface.py tests/wf_mcp/server/test_config.py tests/wf_mcp/test_broker_server.py
uv run basedpyright --level error src/wf_api src/wf_mcp/admin_surface tests/wf_api/test_source_admin_api.py tests/wf_mcp/test_admin_surface.py
```

Expected:

- pytest PASS
- ruff check PASS
- ruff format PASS
- basedpyright 0 errors

- [ ] **Step 4: Commit**

```bash
git add src/wf_api/source_admin.py src/wf_api/surface.py src/wf_api/__init__.py src/wf_mcp/admin_surface/handlers/broker.py src/wf_mcp/admin_surface/tools.py tests/wf_api/test_source_admin_api.py tests/wf_mcp/test_admin_surface.py docs/current_roadmap.md docs/superpowers/specs/2026-06-03-cli-api-alignment-notes.md
git commit -m "feat: add source admin api surface"
```

---

## Follow-Up Slices

1. **Source/admin JSON-RPC transport**
   - Add fixed methods such as `workflow.sources.list` and
     `workflow.sources.inspect`.
   - Add a dedicated RPC source-admin client or mixin, but keep the lifecycle
     `RpcWorkflowApiClient` contract clear.

2. **CLI `wf source` commands**
   - Add `wf source list` and `wf source inspect`.
   - Use the same target-aware context pattern as workflow lifecycle commands,
     but the CLI context may need a second handler field for source admin.

3. **Store-backed source registry**
   - Config remains bootstrap.
   - Server-owned dynamic source changes persist through a source registry store.
   - Source identity stays structural: source id, provider/account/profile, and
     concrete transport details are not inferred from dotted display names.

4. **Mutable source admin**
   - Add source create/update/delete only after store persistence and validation
     rules exist.
   - Enforce duplicate id behavior and liveness/validation diagnostics before
     a source can become runnable.

## Self-Review

- Spec coverage: read-only source list/inspect, neutral surface, MCP adapter, and docs are covered.
- Placeholder scan: no TBD/TODO placeholders.
- Type consistency: `WorkflowSourceAdminApi`, `WorkflowSourceAdminSurface`, `source_id`, `cursor`, and `limit` names are consistent across tasks.
- Risk: `BrokerAdminHandlers.list_sources` / `inspect_source` become async. The plan updates the direct handler test and the MCP tool wrappers that call them.
