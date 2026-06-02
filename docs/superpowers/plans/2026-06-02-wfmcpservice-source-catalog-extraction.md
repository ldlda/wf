# WfMcpService Source Catalog Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract source registry and catalog inventory responsibilities out of `WfMcpService` while preserving the existing service API and MCP/CLI behavior.

**Architecture:** Add a focused `SourceCatalogService` owned by `WfMcpService`. The new service owns capability-source registration, source inventory, planner/backend catalog projection, snapshot hydration, local docs lookup, and qualified spec lookup. `WfMcpService` stays as the compatibility coordinator and still owns connections, adapters, auth, upstream I/O, workflow runtime execution, event recording, and artifact/draft/run stores.

**Tech Stack:** Python 3.14, dataclasses, Pydantic models already in `wf_platform`/`wf_mcp.models`, pytest, ruff, basedpyright.

---

## Scope

This is a reduction slice, not a rewrite. It should make `WfMcpService` thinner without changing public method names, MCP payloads, CLI behavior, or runtime execution semantics.

Move now:

- Capability source map ownership.
- `register_capability_source`.
- `get_catalog`.
- `get_planner_catalog`.
- `list_sources`.
- `list_source_summaries`.
- `inspect_source`.
- `list_available_specs`.
- `get_connection_snapshot`.
- `connection_statuses`.
- `list_resources`.
- `list_prompts`.
- `get_resource`.
- `get_prompt`.
- Local documentation resource/prompt lookup.
- Connection source hydration from stored catalog snapshots.
- Rebuilding `NodeSpec` from `CatalogNodeEntry`.
- Qualified spec lookup.

Do not move in this slice:

- Connection registration policy.
- Adapter registry.
- Auth store methods.
- Upstream discovery I/O in `refresh_connection_catalog`.
- Resource/prompt upstream reads.
- Raw method/notification upstream calls.
- Workflow compile/run/resume runtime execution.
- Event bus implementation.
- Artifact/draft/run stores.

---

## Target File Structure

- Create `src/wf_mcp/broker/service/source_catalog.py`
  - Owns the new `SourceCatalogService`.
  - Imports MCP catalog/store models and `wf_platform` source models.
  - Accepts small callback dependencies for connection lookup, tool executor lookup, auth loading, and event emission where snapshot-hydrated specs need them.
  - Contains docstrings that state this is a service-internal extraction, not a protocol-neutral API.

- Modify `src/wf_mcp/broker/service/core.py`
  - Add `source_catalog: SourceCatalogService = field(init=False)`.
  - Keep `capability_sources` as a property returning `self.source_catalog.capability_sources`.
  - Delegate moved public methods to `self.source_catalog`.
  - Keep `refresh_connection_catalog`, `read_resource`, `render_prompt`, `compile_plan`, `_prepare_workflow_runtime`, `run_workflow_from_plan`, and `resume_workflow_from_plan` on `WfMcpService`.

- Modify `src/wf_mcp/broker/service/workflow_operation_context.py`
  - Keep adapting through `WfMcpService`, but source/spec provider should read via `service.source_catalog` or the compatibility property.

- Modify tests under `tests/wf_mcp/service/test_catalog.py`
  - Keep existing service-facing tests as compatibility coverage.
  - Add direct `SourceCatalogService` tests for the new extracted component.

- Modify docs:
  - `docs/current_roadmap.md`
  - `docs/superpowers/research/2026-06-01-wf-api-extraction-map.md` if it still mentions `WfMcpService` owning source/catalog state directly.

---

## Task 1: Add SourceCatalogService Skeleton

**Files:**

- Create: `src/wf_mcp/broker/service/source_catalog.py`
- Modify: `src/wf_mcp/broker/service/core.py`
- Test: `tests/wf_mcp/service/test_catalog.py`

- [ ] **Step 1: Write a direct component smoke test**

Add this test near the source inventory tests in `tests/wf_mcp/service/test_catalog.py`:

```python
from wf_mcp.broker.service.source_catalog import SourceCatalogService
```

```python
def test_source_catalog_service_registers_and_lists_sources_directly() -> None:
    store = FileStore(local_temp_root() / "source_catalog_direct")

    def unused_tool_executor(connection: ConnectionConfig):
        raise AssertionError("tool executor should not be used by source listing")

    catalog = SourceCatalogService(
        store=store,
        connection_lookup=lambda connection_id: ConnectionConfig(
            id=connection_id,
            server="demo",
            account="personal",
        ),
        tool_executor_for=unused_tool_executor,
        load_auth=lambda connection_id: None,
        emit_event=lambda event: None,
    )

    catalog.register_capability_source(
        CapabilitySource(
            id="demo.personal",
            kind="connection",
            capabilities=CapabilityBuckets(),
            visibility=SourceVisibility(planner=True),
        )
    )

    payload = catalog.list_source_summaries(limit=10)

    assert payload["total"] == 1
    assert payload["sources"][0]["id"] == "demo.personal"
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run:

```bash
uv run pytest tests/wf_mcp/service/test_catalog.py::test_source_catalog_service_registers_and_lists_sources_directly -q
```

Expected: import failure because `wf_mcp.broker.service.source_catalog` does not exist.

- [ ] **Step 3: Create the skeleton component**

Create `src/wf_mcp/broker/service/source_catalog.py`:

```python
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from wf_platform import (
    CapabilitySource,
    page_items,
)

from ...connections import ConnectionConfig
from ...events import McpEvent
from ...models import (
    AuthRecord,
)
from ...runtime import ToolExecutor
from ...storage import Store


ConnectionLookup = Callable[[str], ConnectionConfig]
ToolExecutorLookup = Callable[[ConnectionConfig], ToolExecutor]
AuthLoader = Callable[[str], AuthRecord | None]
EventEmitter = Callable[[McpEvent], None]


@dataclass(slots=True)
class SourceCatalogService:
    """Own service-local capability sources and catalog projections.

    This is deliberately still MCP-broker-internal. It knows about stored MCP
    catalog snapshots because hydrated workflow NodeSpecs must call back through
    the broker's configured tool executor.
    """

    store: Store
    connection_lookup: ConnectionLookup
    tool_executor_for: ToolExecutorLookup
    load_auth: AuthLoader
    emit_event: EventEmitter
    default_catalog_max_age_seconds: int = 300
    capability_sources: dict[str, CapabilitySource] = field(default_factory=dict)

    def register_capability_source(self, source: CapabilitySource) -> None:
        """Register one source as canonical planner/runtime source state."""
        self.capability_sources[source.id] = source

    def list_source_summaries(
        self,
        *,
        cursor: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Return compact paged source summaries for progressive discovery."""
        summaries = [
            source.as_status().model_dump(mode="json")
            for source in sorted(
                self.capability_sources.values(),
                key=lambda source: source.id,
            )
        ]
        page = page_items(summaries, cursor=cursor, limit=limit)
        return {
            "sources": list(page.items),
            "next_cursor": page.next_cursor,
            "total": page.total,
        }
```

Later tasks add imports as methods move. Keep imports minimal at each step because
`ruff check` must pass at the end of every task.

- [ ] **Step 4: Run the focused test**

Run:

```bash
uv run pytest tests/wf_mcp/service/test_catalog.py::test_source_catalog_service_registers_and_lists_sources_directly -q
```

Expected: pass.

- [ ] **Step 5: Run ruff on the new file and test file**

Run:

```bash
uv run ruff check src/wf_mcp/broker/service/source_catalog.py tests/wf_mcp/service/test_catalog.py
```

Expected: pass. Remove any imports that are still unused at this point.

---

## Task 2: Wire SourceCatalogService Into WfMcpService Without Moving Behavior

**Files:**

- Modify: `src/wf_mcp/broker/service/core.py`
- Test: `tests/wf_mcp/service/test_catalog.py`

- [ ] **Step 1: Add a compatibility identity test**

Add this test to `tests/wf_mcp/service/test_catalog.py`:

```python
def test_wfmcpservice_capability_sources_proxy_source_catalog() -> None:
    service = WfMcpService(store=FileStore(local_temp_root() / "source_catalog_proxy"))

    assert service.capability_sources is service.source_catalog.capability_sources
    assert "wf.std" in service.source_catalog.capability_sources
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```bash
uv run pytest tests/wf_mcp/service/test_catalog.py::test_wfmcpservice_capability_sources_proxy_source_catalog -q
```

Expected: fail because `service.source_catalog` does not exist.

- [ ] **Step 3: Add the component field and compatibility property**

In `src/wf_mcp/broker/service/core.py`, import:

```python
from .source_catalog import SourceCatalogService
```

Change the dataclass fields:

```python
    adapters: dict[str, BackendAdapter] = field(default_factory=dict)
    event_bus: EventBus = field(default_factory=EventBus)
    include_builtin_specs: bool = True
    artifact_store: WorkflowArtifactStore | None = None
    draft_workspace_store: DraftWorkspaceStore | None = None
    run_store: RunStore | None = None
    tool_executor: ToolExecutor | None = None
    source_catalog: SourceCatalogService = field(init=False)
```

Add a property inside `WfMcpService`:

```python
    @property
    def capability_sources(self) -> dict[str, CapabilitySource]:
        """Compatibility view of source catalog state.

        Source ownership is moving into SourceCatalogService. Keep this property
        because workflow APIs and existing tests still consume the service facade.
        """
        return self.source_catalog.capability_sources
```

At the top of `__post_init__`, before builtin source registration, create the source catalog:

```python
        self.source_catalog = SourceCatalogService(
            store=self.store,
            connection_lookup=self.connections.get,
            tool_executor_for=self._tool_executor_for,
            load_auth=self.load_auth,
            emit_event=self._record_event,
            default_catalog_max_age_seconds=self.default_catalog_max_age_seconds,
        )
```

Remove the old dataclass field:

```python
    capability_sources: dict[str, CapabilitySource] = field(default_factory=dict)
```

- [ ] **Step 4: Run focused compatibility tests**

Run:

```bash
uv run pytest tests/wf_mcp/service/test_catalog.py::test_wfmcpservice_capability_sources_proxy_source_catalog tests/wf_mcp/service/test_catalog.py::test_service_installs_builtin_stdlib_specs_by_default -q
```

Expected: both pass.

- [ ] **Step 5: Run ruff on service files**

Run:

```bash
uv run ruff check src/wf_mcp/broker/service/core.py src/wf_mcp/broker/service/source_catalog.py
```

Expected: pass.

---

## Task 3: Move Source Inventory and Planner Catalog Methods

**Files:**

- Modify: `src/wf_mcp/broker/service/source_catalog.py`
- Modify: `src/wf_mcp/broker/service/core.py`
- Test: `tests/wf_mcp/service/test_catalog.py`

- [ ] **Step 1: Add direct component tests for inventory and planner visibility**

Add this test:

```python
def test_source_catalog_service_excludes_hidden_sources_from_planner_catalog() -> None:
    def unused_tool_executor(connection: ConnectionConfig):
        raise AssertionError("tool executor should not be used by planner listing")

    catalog = SourceCatalogService(
        store=FileStore(local_temp_root() / "source_catalog_hidden"),
        connection_lookup=lambda connection_id: ConnectionConfig(
            id=connection_id,
            server="demo",
            account="personal",
        ),
        tool_executor_for=unused_tool_executor,
        load_auth=lambda connection_id: None,
        emit_event=lambda event: None,
    )
    visible_tool = NodeSpec(
        name="visible.source.echo_tool",
        input_model=echo_tool.input_model,
        output_model=echo_tool.output_model,
        outcomes=echo_tool.outcomes,
        fn=echo_tool.fn,
        description=echo_tool.description,
        is_async=echo_tool.is_async,
        accepts_context=echo_tool.accepts_context,
        input_schema_contract=echo_tool.input_schema_contract,
        output_schema_contract=echo_tool.output_schema_contract,
    )
    hidden_tool = NodeSpec(
        name="hidden.source.echo_tool",
        input_model=echo_tool.input_model,
        output_model=echo_tool.output_model,
        outcomes=echo_tool.outcomes,
        fn=echo_tool.fn,
        description=echo_tool.description,
        is_async=echo_tool.is_async,
        accepts_context=echo_tool.accepts_context,
        input_schema_contract=echo_tool.input_schema_contract,
        output_schema_contract=echo_tool.output_schema_contract,
    )
    catalog.register_capability_source(
        CapabilitySource(
            id="visible.source",
            kind="system",
            capabilities=CapabilityBuckets(
                node_specs={"visible.source.echo_tool": visible_tool}
            ),
            visibility=SourceVisibility(planner=True),
        )
    )
    catalog.register_capability_source(
        CapabilitySource(
            id="hidden.source",
            kind="system",
            capabilities=CapabilityBuckets(
                node_specs={"hidden.source.echo_tool": hidden_tool}
            ),
            visibility=SourceVisibility(planner=False, admin_dashboard=False),
        )
    )

    planner_names = {
        entry.qualified_name for entry in catalog.get_planner_catalog().entries()
    }

    assert "visible.source.echo_tool" in planner_names
    assert "hidden.source.echo_tool" not in planner_names
```

- [ ] **Step 2: Run the direct test and verify it fails**

Run:

```bash
uv run pytest tests/wf_mcp/service/test_catalog.py::test_source_catalog_service_excludes_hidden_sources_from_planner_catalog -q
```

Expected: fail because `SourceCatalogService.get_planner_catalog` does not exist.

- [ ] **Step 3: Move catalog and source methods into SourceCatalogService**

Move these methods from `WfMcpService` to `SourceCatalogService` with unchanged bodies except `self.capability_sources` now means the component field:

```python
    def get_catalog(self) -> CombinedCatalog:
        snapshots: dict[str, CatalogSnapshot] = {}
        for connection in self.connection_list_enabled():
            snapshot = self.store.load_catalog(connection.id)
            if snapshot is not None:
                snapshots[connection.id] = snapshot
        return CombinedCatalog(snapshots=snapshots)
```

The component needs connection list callbacks. Update callback types:

```python
ConnectionList = Callable[[], list[ConnectionConfig]]
```

Add fields:

```python
    connection_list_enabled: ConnectionList
    connection_list_all: ConnectionList
```

Update `WfMcpService.__post_init__` construction:

```python
            connection_list_enabled=self.connections.list_enabled,
            connection_list_all=self.connections.list_all,
```

Update every existing direct `SourceCatalogService(...)` construction in
`tests/wf_mcp/service/test_catalog.py` to include:

```python
        connection_list_enabled=lambda: [],
        connection_list_all=lambda: [],
```

For tests that already define a concrete `connection`, use:

```python
        connection_list_enabled=lambda: [connection],
        connection_list_all=lambda: [connection],
```

Move these methods exactly, adjusting connection list calls:

```python
    def get_catalog(self) -> CombinedCatalog: ...
    def get_planner_catalog(self) -> CombinedCatalog: ...
    def list_sources(self) -> list[dict[str, Any]]: ...
    def inspect_source(self, source_id: str) -> dict[str, Any]: ...
    def list_available_specs(self) -> list[CatalogNodeEntry]: ...
    def get_connection_snapshot(self, connection_id: str) -> CatalogSnapshot | None: ...
    def connection_statuses(self) -> list[dict[str, Any]]: ...
    def list_resources(self, *, connection_id: str | None = None) -> list[CatalogResourceEntry]: ...
    def list_prompts(self, *, connection_id: str | None = None) -> list[CatalogPromptEntry]: ...
    def get_resource(self, qualified_name: str) -> CatalogResourceEntry: ...
    def get_prompt(self, qualified_name: str) -> CatalogPromptEntry: ...
```

For `get_connection_snapshot`, use `self.connection_lookup(connection_id)` instead of `self.connections.get(connection_id)`.

- [ ] **Step 4: Delegate the same methods from WfMcpService**

Replace each moved method body in `src/wf_mcp/broker/service/core.py` with a one-line delegate:

```python
    def get_planner_catalog(self) -> CombinedCatalog:
        return self.source_catalog.get_planner_catalog()
```

Use the same pattern for every moved public method. Keep method signatures unchanged.

- [ ] **Step 5: Run catalog tests**

Run:

```bash
uv run pytest tests/wf_mcp/service/test_catalog.py -q
```

Expected: all tests in the file pass.

- [ ] **Step 6: Run ruff**

Run:

```bash
uv run ruff check src/wf_mcp/broker/service/core.py src/wf_mcp/broker/service/source_catalog.py tests/wf_mcp/service/test_catalog.py
```

Expected: pass.

---

## Task 4: Move Connection Source Hydration and Snapshot Spec Rebuild

**Files:**

- Modify: `src/wf_mcp/broker/service/source_catalog.py`
- Modify: `src/wf_mcp/broker/service/core.py`
- Test: `tests/wf_mcp/service/test_catalog.py`

- [ ] **Step 1: Add a direct hydration test**

Add this test:

```python
def test_source_catalog_hydrates_connection_source_from_snapshot_directly() -> None:
    root = local_temp_root() / "source_catalog_hydrate_direct"
    shutil.rmtree(root, ignore_errors=True)
    first_service = WfMcpService(store=FileStore(root))
    first_service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    first_service.register_adapter("demo", FakeAdapter())
    asyncio.run(first_service.refresh_connection_catalog("demo.personal"))

    second_service = WfMcpService(store=FileStore(root))
    second_service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )

    specs = second_service.source_catalog.capability_sources[
        "demo.personal"
    ].capabilities.node_specs

    assert "demo.personal.echo_tool" in specs
```

- [ ] **Step 2: Run the direct hydration test**

Run:

```bash
uv run pytest tests/wf_mcp/service/test_catalog.py::test_source_catalog_hydrates_connection_source_from_snapshot_directly -q
```

Expected: pass before moving code, because this is still routed through `WfMcpService`; this is a characterization test that must stay green.

- [ ] **Step 3: Move hydration helpers into SourceCatalogService**

Move these methods to `SourceCatalogService`:

```python
    def hydrate_connection_source_from_snapshot(
        self,
        connection: ConnectionConfig,
    ) -> None: ...

    def spec_from_snapshot_entry(
        self,
        entry: CatalogNodeEntry,
    ) -> NodeSpec[Any, Any]: ...

    def get_qualified_spec(self, qualified_name: str) -> NodeSpec[Any, Any]: ...
```

Rename the public component methods without leading underscores because this is now the component API.

Inside `spec_from_snapshot_entry`, preserve the async tool wrapper exactly:

```python
        async def invoke_tool(payload: BaseModel) -> NodeReturn[BaseModel]:
            connection = self.connection_lookup(entry.connection_id)
            auth = self.load_auth(entry.connection_id)
            result = await self.tool_executor_for(connection).call_tool(
                connection,
                auth,
                entry.local_name,
                payload.model_dump(exclude_unset=True),
            )
            return NodeReturn(
                outcome=result.outcome,
                output=output_model.model_validate(result.output),
            )
```

Add the needed imports in `source_catalog.py`:

```python
from pydantic import BaseModel
from wf_platform import CapabilityBuckets, SourcePermissions, SourceVisibility
from ...connections import qualify_node_name
from ...workflow.wrappers import _model_from_schema
from .specs import get_qualified_spec, qualify_spec
```

- [ ] **Step 4: Update WfMcpService delegate call sites**

In `WfMcpService.register_connection`, replace:

```python
        self._hydrate_connection_source_from_snapshot(connection)
```

with:

```python
        self.source_catalog.hydrate_connection_source_from_snapshot(connection)
```

In `sync_connections_from_config`, replace:

```python
                self._hydrate_connection_source_from_snapshot(connection)
```

with:

```python
                self.source_catalog.hydrate_connection_source_from_snapshot(connection)
```

Replace `_get_qualified_spec` body:

```python
    def _get_qualified_spec(self, qualified_name: str) -> NodeSpec[Any, Any]:
        return self.source_catalog.get_qualified_spec(qualified_name)
```

Remove `_hydrate_connection_source_from_snapshot` and `_spec_from_snapshot_entry` from `core.py`.

- [ ] **Step 5: Run hydration and runtime regression tests**

Run:

```bash
uv run pytest tests/wf_mcp/service/test_catalog.py::test_service_hydrates_planner_specs_from_stored_catalog tests/wf_mcp/service/test_catalog.py::test_source_catalog_hydrates_connection_source_from_snapshot_directly -q
```

Expected: both pass. The first test proves hydrated specs still execute through runtime.

- [ ] **Step 6: Run ruff**

Run:

```bash
uv run ruff check src/wf_mcp/broker/service/core.py src/wf_mcp/broker/service/source_catalog.py tests/wf_mcp/service/test_catalog.py
```

Expected: pass.

---

## Task 5: Move Spec Registration Into SourceCatalogService

**Files:**

- Modify: `src/wf_mcp/broker/service/source_catalog.py`
- Modify: `src/wf_mcp/broker/service/core.py`
- Test: `tests/wf_mcp/service/test_catalog.py`

- [ ] **Step 1: Add a direct register-specs test**

Add this test:

```python
def test_source_catalog_register_specs_replaces_discovered_specs_directly() -> None:
    connection = ConnectionConfig(
        id="demo.personal",
        server="demo",
        account="personal",
    )

    def unused_tool_executor(connection: ConnectionConfig):
        raise AssertionError("tool executor should not be used by spec registration")

    catalog = SourceCatalogService(
        store=FileStore(local_temp_root() / "source_catalog_register_specs"),
        connection_lookup=lambda connection_id: connection,
        connection_list_enabled=lambda: [connection],
        connection_list_all=lambda: [connection],
        tool_executor_for=unused_tool_executor,
        load_auth=lambda connection_id: None,
        emit_event=lambda event: None,
    )

    catalog.hydrate_connection_source_from_snapshot(connection)
    catalog.register_specs("demo.personal", echo_tool)

    specs = catalog.capability_sources["demo.personal"].capabilities.node_specs

    assert set(specs) == {"demo.personal.echo_tool"}
    assert catalog.store.load_catalog("demo.personal") is not None
```

- [ ] **Step 2: Run the direct test and verify it fails**

Run:

```bash
uv run pytest tests/wf_mcp/service/test_catalog.py::test_source_catalog_register_specs_replaces_discovered_specs_directly -q
```

Expected: fail because `SourceCatalogService.register_specs` does not exist.

- [ ] **Step 3: Move register_specs into SourceCatalogService**

Move the logic from `WfMcpService.register_specs` to `SourceCatalogService.register_specs`:

```python
    def register_specs(
        self,
        connection_id: str,
        *specs: NodeSpec[Any, Any],
        max_age_seconds: int | None = None,
        emit_change_events: bool = True,
        record_catalog_change_events: Callable[
            [str, CatalogSnapshot, str],
            None,
        ]
        | None = None,
    ) -> CatalogSnapshot:
        self.connection_lookup(connection_id)
        qualified_specs = {
            qualify_node_name(connection_id, spec.name): qualify_spec(
                connection_id, spec
            )
            for spec in specs
        }
        existing_source = self.capability_sources.get(connection_id)
        if existing_source is not None:
            existing_source.capabilities.node_specs = qualified_specs
        else:
            self.register_capability_source(
                CapabilitySource(
                    id=connection_id,
                    kind="connection",
                    capabilities=CapabilityBuckets(node_specs=qualified_specs),
                    enabled=self.connection_lookup(connection_id).enabled,
                    visibility=SourceVisibility(
                        planner=True,
                        mcp_client=True,
                        admin_dashboard=True,
                    ),
                    permissions=SourcePermissions(calls_upstream=True),
                    description=(
                        f"Specs discovered or registered for {connection_id}."
                    ),
                )
            )
        snapshot = snapshot_from_specs(
            connection_id,
            specs=qualified_specs,
            fetched_at_epoch_ms=int(time.time() * 1000),
            max_age_seconds=max_age_seconds or self.default_catalog_max_age_seconds,
        )
        self.store.save_catalog(snapshot)
        self.emit_event(
            make_event(
                "specs_registered",
                connection_id=connection_id,
                payload={"node_count": len(qualified_specs)},
            )
        )
        if emit_change_events and record_catalog_change_events is not None:
            record_catalog_change_events(connection_id, snapshot, "specs_registered")
        return snapshot
```

Add imports:

```python
from ...events import make_event
from ..catalog import CombinedCatalog, snapshot_from_specs
```

- [ ] **Step 4: Delegate WfMcpService.register_specs**

Replace `WfMcpService.register_specs` body with:

```python
        self.source_catalog.register_specs(
            connection_id,
            *specs,
            max_age_seconds=max_age_seconds,
            emit_change_events=emit_change_events,
            record_catalog_change_events=lambda source_id, snapshot, reason: (
                self._record_catalog_change_events(
                    source_id,
                    snapshot,
                    reason=reason,
                )
            ),
        )
```

Keep the public method signature unchanged.

- [ ] **Step 5: Run spec registration tests**

Run:

```bash
uv run pytest tests/wf_mcp/service/test_catalog.py::test_service_builds_namespaced_catalog tests/wf_mcp/service/test_catalog.py::test_source_catalog_register_specs_replaces_discovered_specs_directly -q
```

Expected: both pass.

- [ ] **Step 6: Run ruff**

Run:

```bash
uv run ruff check src/wf_mcp/broker/service/core.py src/wf_mcp/broker/service/source_catalog.py tests/wf_mcp/service/test_catalog.py
```

Expected: pass.

---

## Task 6: Move Local Documentation Lookup

**Files:**

- Modify: `src/wf_mcp/broker/service/source_catalog.py`
- Modify: `src/wf_mcp/broker/service/core.py`
- Test: `tests/wf_mcp/service/test_catalog.py`

- [ ] **Step 1: Add direct local docs lookup tests**

Add this test:

```python
def test_source_catalog_finds_local_documentation_resource_directly() -> None:
    service = WfMcpService(store=FileStore(local_temp_root() / "source_local_docs"))

    resource = service.source_catalog.local_documentation_resource(
        "wf.docs.workflow_lifecycle"
    )

    assert resource is not None
    assert resource.uri == "wf://docs/workflow-lifecycle.md"
```

If the exact docs key differs in this repository, use the actual key from `service.capability_sources["wf.docs"].capabilities.resources` and assert against that exact key. Do not make the test search for “any resource”; it must prove lookup by qualified name.

- [ ] **Step 2: Run the direct test and verify it fails**

Run:

```bash
uv run pytest tests/wf_mcp/service/test_catalog.py::test_source_catalog_finds_local_documentation_resource_directly -q
```

Expected: fail because `local_documentation_resource` does not exist, or because the guessed key is wrong. If the key is wrong, inspect `service.capability_sources["wf.docs"].capabilities.resources.keys()` and update the test to the actual key.

- [ ] **Step 3: Move local docs helpers into SourceCatalogService**

Move these methods from `WfMcpService` and rename them:

```python
    def local_documentation_resource(
        self,
        qualified_name: str,
    ) -> DocumentationResource | None:
        """Return a local docs resource from capability sources by qualified name."""
        for source in self.capability_sources.values():
            resource = source.capabilities.resources.get(qualified_name)
            if isinstance(resource, DocumentationResource):
                return resource
        return None

    def local_documentation_prompt(
        self,
        qualified_name: str,
    ) -> DocumentationPrompt | None:
        """Return a local docs prompt from capability sources by qualified name."""
        for source in self.capability_sources.values():
            prompt = source.capabilities.prompts.get(qualified_name)
            if isinstance(prompt, DocumentationPrompt):
                return prompt
        return None
```

- [ ] **Step 4: Delegate WfMcpService read/render call sites**

In `WfMcpService.read_resource`, replace:

```python
        local_resource = self._local_documentation_resource(qualified_name)
```

with:

```python
        local_resource = self.source_catalog.local_documentation_resource(
            qualified_name
        )
```

In `WfMcpService.render_prompt`, replace:

```python
        local_prompt = self._local_documentation_prompt(qualified_name)
```

with:

```python
        local_prompt = self.source_catalog.local_documentation_prompt(qualified_name)
```

Remove `_local_documentation_resource` and `_local_documentation_prompt` from `core.py`.

- [ ] **Step 5: Run docs/resource tests**

Run:

```bash
uv run pytest tests/wf_mcp/service/test_catalog.py::test_source_catalog_finds_local_documentation_resource_directly tests/wf_mcp/test_broker_server.py -q
```

Expected: pass.

- [ ] **Step 6: Run ruff**

Run:

```bash
uv run ruff check src/wf_mcp/broker/service/core.py src/wf_mcp/broker/service/source_catalog.py tests/wf_mcp/service/test_catalog.py
```

Expected: pass.

---

## Task 7: Update Workflow Operation Context and Live Checks to Use the Extracted Service

**Files:**

- Modify: `src/wf_mcp/broker/service/workflow_operation_context.py`
- Modify: `src/wf_mcp/broker/service/workflow_live_checks.py`
- Test: `tests/wf_api/test_operation_context.py`
- Test: `tests/wf_mcp/workflow_surface/test_deployments.py`

- [ ] **Step 1: Add a context identity test**

In `tests/wf_api/test_operation_context.py`, add:

```python
def test_context_uses_source_catalog_mapping() -> None:
    service = WfMcpService(store=FileStore(local_temp_root() / "context_sources"))
    context = context_from_service(service)

    assert context.capability_sources is service.source_catalog.capability_sources
```

Use the existing imports/helpers in that file. If `WfMcpService`, `FileStore`, or `local_temp_root` are not imported there, add the same imports used by neighboring tests.

- [ ] **Step 2: Run the context test**

Run:

```bash
uv run pytest tests/wf_api/test_operation_context.py::test_context_uses_source_catalog_mapping -q
```

Expected: pass after earlier tasks.

- [ ] **Step 3: Update operation context adapter**

In `src/wf_mcp/broker/service/workflow_operation_context.py`, update:

```python
    @property
    def capability_sources(self):
        return self.service.source_catalog.capability_sources

    def get_qualified_spec(self, qualified_name: str) -> object:
        return self.service.source_catalog.get_qualified_spec(qualified_name)
```

In `context_from_service`, keep:

```python
        capability_sources=specs.capability_sources,
```

- [ ] **Step 4: Update live checks to read source catalog explicitly**

In `src/wf_mcp/broker/service/workflow_live_checks.py`, replace:

```python
        source = service.capability_sources.get(source_id)
```

with:

```python
        source = service.source_catalog.capability_sources.get(source_id)
```

This makes the live-check dependency on source registry explicit while still leaving connection/adapters/auth on `WfMcpService`.

- [ ] **Step 5: Run deployment live-check tests**

Run:

```bash
uv run pytest tests/wf_mcp/workflow_surface/test_deployments.py -q
```

Expected: pass.

- [ ] **Step 6: Run ruff**

Run:

```bash
uv run ruff check src/wf_mcp/broker/service/workflow_operation_context.py src/wf_mcp/broker/service/workflow_live_checks.py tests/wf_api/test_operation_context.py
```

Expected: pass.

---

## Task 8: Clean Imports, Docs, and Verify Full Behavior

**Files:**

- Modify: `src/wf_mcp/broker/service/core.py`
- Modify: `src/wf_mcp/broker/service/source_catalog.py`
- Modify: `docs/current_roadmap.md`
- Modify: `docs/superpowers/research/2026-06-01-wf-api-extraction-map.md` if present and stale.

- [ ] **Step 1: Remove stale imports from core.py**

After all moves, `src/wf_mcp/broker/service/core.py` should no longer import items used only by `source_catalog.py`, such as:

```python
from pydantic import BaseModel
from wf_platform import DocumentationPrompt, DocumentationResource, page_items
from ...workflow.wrappers import _model_from_schema
from ..catalog import CombinedCatalog
from .specs import get_qualified_spec, qualify_spec
```

Do not remove imports that are still used by `refresh_connection_catalog`, runtime preparation, or public method annotations.

- [ ] **Step 2: Add roadmap status note**

In `docs/current_roadmap.md`, add or update the `wf_api`/service extraction section with:

```markdown
- `WfMcpService` is being reduced into injected implementation services. Source
  registry and catalog projection now live in `SourceCatalogService`; the old
  service methods remain as compatibility delegates for MCP broker callers.
```

- [ ] **Step 3: Update extraction map if it names source ownership**

If `docs/superpowers/research/2026-06-01-wf-api-extraction-map.md` says `WfMcpService` owns source/catalog state directly, change it to:

```markdown
Source/catalog ownership is now split: `WfMcpService` coordinates broker runtime
state, while `SourceCatalogService` owns capability source maps, planner catalog
projection, snapshot hydration, and local docs lookup.
```

If the file does not contain stale source/catalog ownership wording, do not edit it.

- [ ] **Step 4: Run focused source/catalog/workflow checks**

Run:

```bash
uv run pytest tests/wf_mcp/service/test_catalog.py tests/wf_api/test_operation_context.py tests/wf_mcp/workflow_surface/test_deployments.py tests/wf_mcp/workflow_surface/test_runs.py -q
```

Expected: all selected tests pass.

- [ ] **Step 5: Run full verification**

Run:

```bash
uv run pytest -q
uv run ruff check src/wf_mcp/broker/service src/wf_api tests/wf_mcp/service tests/wf_api
uv run ruff format --check src/wf_mcp/broker/service src/wf_api tests/wf_mcp/service tests/wf_api docs/current_roadmap.md
uv run basedpyright --level error
```

Expected:

- pytest passes.
- ruff check passes.
- ruff format check passes.
- basedpyright reports `0 errors`. A workspace enumeration timeout warning may still make the command exit nonzero in this repository; record the exact output if that happens.

---

## Non-Goals and Follow-Up Slices

This plan intentionally leaves `WfMcpService` as the public broker coordinator. After this slice, the next reductions should be separate plans:

1. **Connection/runtime service extraction:** move connection registry, adapter lookup, auth loading, and upstream I/O calls into a transport runtime service.
2. **Workflow runtime runner extraction:** move `compile_plan`, `_prepare_workflow_runtime`, `run_workflow_from_plan`, and `resume_workflow_from_plan` into a dedicated runtime implementation.
3. **Event recorder extraction:** make event emission a dependency instead of private `_record_event` calls.
4. **Resource/prompt API extraction:** decide whether `read_resource` and `render_prompt` belong in a neutral API façade or stay MCP-admin-only.

---

## Self-Review

- Spec coverage: This plan extracts source/catalog state while preserving old `WfMcpService` methods and explicitly defers runtime/transport moves.
- Placeholder scan: No placeholder implementation tasks are left. The one docs lookup test allows correcting an exact key after inspecting actual source keys because the source key can vary with current docs registration.
- Type consistency: `SourceCatalogService` consistently uses callback dependencies for connection lookup, connection listing, tool executor lookup, auth loading, and event emission. `WfMcpService.capability_sources` remains a compatibility property.
