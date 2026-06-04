# WfMcpService Upstream Transport Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract upstream MCP transport/auth/adapter operations from `WfMcpService` into a focused implementation service while preserving existing admin, MCP, CLI, and workflow behavior.

**Architecture:** Add `UpstreamTransportService` under `wf_mcp.broker.service`. It owns adapter registration, auth save/load, tool executor selection, catalog refresh I/O, broker resource reads, prompt rendering, raw method calls, raw notifications, and live-source probes. `WfMcpService` remains the coordinator and compatibility façade; connection registration and config reconciliation stay on `WfMcpService` because they mutate source registration and reserved-id policy.

**Tech Stack:** Python 3.14, dataclasses, `BackendAdapter`, `ConnectionRegistry`, MCP SDK adapters, `SourceCatalogService`, pytest, ruff, basedpyright.

---

## Scope

Move now:

- `register_adapter`.
- `_tool_executor_for`, public on the new service as `tool_executor_for`.
- `save_auth`.
- `load_auth`.
- `read_resource`.
- `render_prompt`.
- `invoke_method`.
- `send_notification`.
- `refresh_connection_catalog`.
- Live source diagnostics from `workflow_live_checks.py`, adapted to use `UpstreamTransportService`.

Keep now:

- `register_connection`.
- `sync_connections_from_config`.
- Connection registry field on `WfMcpService`.
- Source catalog field on `WfMcpService`.
- Event bus implementation on `WfMcpService`.
- Public `WfMcpService` methods as delegates.
- Admin handler public behavior.
- MCP tool schema and CLI behavior.

Do not do in this slice:

- Do not move `ConnectionRegistry` out of `WfMcpService`.
- Do not rename `WfMcpService`.
- Do not move event recorder implementation.
- Do not change adapter implementations.
- Do not change live-check failure semantics.

---

## Target File Structure

- Create `src/wf_mcp/broker/service/upstream_transport.py`
  - Owns adapter/auth/upstream I/O operations.
  - Depends on `ConnectionConfig` values supplied by callers, `SourceCatalogService` for catalog refresh/live checks, `Store`, optional `ToolExecutor`, and event emitter callbacks.
  - Contains docstrings for why generated workflow NodeSpecs use `tool_executor_for`.

- Modify `src/wf_mcp/broker/service/core.py`
  - Add `upstream: UpstreamTransportService = field(init=False)`.
  - Construct it before `SourceCatalogService`, because source hydration needs `tool_executor_for` and `load_auth`.
  - Keep public service methods as delegates.

- Modify `src/wf_mcp/broker/service/source_catalog.py`
  - No behavior change; it will receive callbacks from `service.upstream` instead of private `WfMcpService` methods.

- Modify `src/wf_mcp/broker/service/workflow_live_checks.py`
  - Either move diagnostics into `UpstreamTransportService` or make the function accept `UpstreamTransportService` instead of `WfMcpService`.
  - Preferred for this slice: move live diagnostics as `UpstreamTransportService.deployment_diagnostics(...)`, and leave `workflow_live_checks.py` as a compatibility shim if imports still reference it.

- Modify `src/wf_mcp/broker/service/workflow_operation_context.py`
  - `WfMcpWorkflowLiveSourceChecker` calls `service.upstream.deployment_diagnostics(...)`.

- Add tests in `tests/wf_mcp/service/test_upstream_transport.py`.

- Update docs:
  - `docs/current_roadmap.md`.
  - `docs/superpowers/research/2026-06-01-wf-api-extraction-map.md` if stale.

---

## Task 1: Add UpstreamTransportService Skeleton

**Files:**

- Create: `src/wf_mcp/broker/service/upstream_transport.py`
- Create: `tests/wf_mcp/service/test_upstream_transport.py`
- Modify: `src/wf_mcp/broker/service/core.py`

- [ ] **Step 1: Write adapter registration and auth tests**

Create `tests/wf_mcp/service/test_upstream_transport.py`:

```python
from __future__ import annotations

from wf_mcp.broker.service.upstream_transport import UpstreamTransportService
from wf_mcp.events import McpEvent
from wf_mcp.models import AuthRecord
from wf_mcp.storage import FileStore

from ..test_support import FakeAdapter, local_temp_root


def test_upstream_transport_registers_adapter() -> None:
    events: list[McpEvent] = []
    transport = UpstreamTransportService(
        store=FileStore(local_temp_root() / "upstream_adapter"),
        event_sink=events.append,
    )
    adapter = FakeAdapter()

    transport.register_adapter("demo", adapter)

    assert transport.adapters["demo"] is adapter


def test_upstream_transport_saves_and_loads_auth_with_event() -> None:
    events: list[McpEvent] = []
    transport = UpstreamTransportService(
        store=FileStore(local_temp_root() / "upstream_auth"),
        event_sink=events.append,
    )
    record = AuthRecord(connection_id="demo.personal", scheme="bearer")

    transport.save_auth(record)
    loaded = transport.load_auth("demo.personal")

    assert loaded is not None
    assert loaded.connection_id == "demo.personal"
    assert events[-1].kind == "auth_saved"
    assert events[-1].connection_id == "demo.personal"
```

- [ ] **Step 2: Run the tests and verify they fail**

Run:

```bash
uv run pytest tests/wf_mcp/service/test_upstream_transport.py::test_upstream_transport_registers_adapter tests/wf_mcp/service/test_upstream_transport.py::test_upstream_transport_saves_and_loads_auth_with_event -q
```

Expected: import failure because `upstream_transport.py` does not exist.

- [ ] **Step 3: Create the skeleton service**

Create `src/wf_mcp/broker/service/upstream_transport.py`:

```python
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from wf_mcp.events import McpEvent, make_event
from wf_mcp.models import AuthRecord
from wf_mcp.runtime import ToolExecutor
from wf_mcp.sdk import BackendAdapter
from wf_mcp.storage import Store

EventSink = Callable[[McpEvent], None]


@dataclass(slots=True)
class UpstreamTransportService:
    """Own upstream MCP adapter/auth operations for the broker service.

    This is not protocol-neutral. It is the MCP transport implementation used by
    admin calls, discovery, generated workflow NodeSpecs, and live source checks.
    """

    store: Store
    event_sink: EventSink
    adapters: dict[str, BackendAdapter] = field(default_factory=dict)
    tool_executor: ToolExecutor | None = None

    def register_adapter(self, server: str, adapter: BackendAdapter) -> None:
        self.adapters[server] = adapter

    def save_auth(self, record: AuthRecord) -> None:
        self.store.save_auth(record)
        self.event_sink(
            make_event(
                "auth_saved",
                connection_id=record.connection_id,
                payload={"scheme": record.scheme},
            )
        )

    def load_auth(self, connection_id: str) -> AuthRecord | None:
        return self.store.load_auth(connection_id)
```

- [ ] **Step 4: Run the tests**

Run:

```bash
uv run pytest tests/wf_mcp/service/test_upstream_transport.py::test_upstream_transport_registers_adapter tests/wf_mcp/service/test_upstream_transport.py::test_upstream_transport_saves_and_loads_auth_with_event -q
```

Expected: pass.

- [ ] **Step 5: Run ruff**

Run:

```bash
uv run ruff check src/wf_mcp/broker/service/upstream_transport.py tests/wf_mcp/service/test_upstream_transport.py
```

Expected: pass.

---

## Task 2: Wire UpstreamTransportService Into WfMcpService

**Files:**

- Modify: `src/wf_mcp/broker/service/core.py`
- Test: `tests/wf_mcp/service/test_upstream_transport.py`

- [ ] **Step 1: Add service delegate tests**

Append to `tests/wf_mcp/service/test_upstream_transport.py`:

```python
from wf_mcp.broker import WfMcpService


def test_wfmcpservice_uses_upstream_transport_for_adapters_and_auth() -> None:
    service = WfMcpService(store=FileStore(local_temp_root() / "service_upstream"))
    adapter = FakeAdapter()

    service.register_adapter("demo", adapter)
    service.save_auth(AuthRecord(connection_id="demo.personal", scheme="bearer"))

    assert service.upstream.adapters["demo"] is adapter
    assert service.adapters is service.upstream.adapters
    assert service.load_auth("demo.personal") is not None
    assert service.list_events()[-1].kind == "auth_saved"
```

- [ ] **Step 2: Run the delegate test and verify it fails**

Run:

```bash
uv run pytest tests/wf_mcp/service/test_upstream_transport.py::test_wfmcpservice_uses_upstream_transport_for_adapters_and_auth -q
```

Expected: fail because `service.upstream` does not exist.

- [ ] **Step 3: Add upstream field and compatibility adapters property**

In `src/wf_mcp/broker/service/core.py`, import:

```python
from .upstream_transport import UpstreamTransportService
```

Replace the dataclass field:

```python
    adapters: dict[str, BackendAdapter] = field(default_factory=dict)
```

with:

```python
    upstream: UpstreamTransportService = field(init=False)
```

Keep `tool_executor: ToolExecutor | None = None` on `WfMcpService` for construction compatibility.

Add property:

```python
    @property
    def adapters(self) -> dict[str, BackendAdapter]:
        """Compatibility view of upstream adapter registry."""
        return self.upstream.adapters
```

In `__post_init__`, before constructing `SourceCatalogService`, add:

```python
        self.upstream = UpstreamTransportService(
            store=self.store,
            event_sink=self._record_event,
            tool_executor=self.tool_executor,
        )
```

Then update `SourceCatalogService(...)` construction:

```python
            tool_executor_for=self.upstream.tool_executor_for,
            load_auth=self.upstream.load_auth,
```

- [ ] **Step 4: Delegate adapter/auth methods**

Replace these `WfMcpService` method bodies:

```python
    def register_adapter(self, server: str, adapter: BackendAdapter) -> None:
        self.upstream.register_adapter(server, adapter)

    def _tool_executor_for(self, connection: ConnectionConfig) -> ToolExecutor:
        return self.upstream.tool_executor_for(connection)

    def save_auth(self, record: AuthRecord) -> None:
        self.upstream.save_auth(record)

    def load_auth(self, connection_id: str) -> AuthRecord | None:
        return self.upstream.load_auth(connection_id)
```

The private `_tool_executor_for` delegate stays temporarily because existing internal call sites may still reference it during this slice.

- [ ] **Step 5: Add tool_executor_for implementation**

In `src/wf_mcp/broker/service/upstream_transport.py`, add imports:

```python
from wf_mcp.models import ConnectionConfig
from wf_mcp.broker.service.adapters import require_adapter
```

Add:

```python
    def tool_executor_for(self, connection: ConnectionConfig) -> ToolExecutor:
        """Return the executor used by generated workflow NodeSpecs.

        Discovery uses short-lived adapters. Generated workflow nodes use this
        hook so config-built services can swap in a persistent runtime pool for
        stateful MCP servers.
        """
        if self.tool_executor is not None:
            return self.tool_executor
        return require_adapter(connection, self.adapters)
```

- [ ] **Step 6: Run focused tests**

Run:

```bash
uv run pytest tests/wf_mcp/service/test_upstream_transport.py tests/wf_mcp/service/test_catalog.py::test_source_catalog_hydrates_connection_source_from_snapshot_directly -q
```

Expected: pass.

- [ ] **Step 7: Run ruff**

Run:

```bash
uv run ruff check src/wf_mcp/broker/service/core.py src/wf_mcp/broker/service/upstream_transport.py tests/wf_mcp/service/test_upstream_transport.py
```

Expected: pass.

---

## Task 3: Move Resource, Prompt, Raw Method, and Notification Calls

**Files:**

- Modify: `src/wf_mcp/broker/service/upstream_transport.py`
- Modify: `src/wf_mcp/broker/service/core.py`
- Test: `tests/wf_mcp/service/test_upstream_transport.py`
- Test: `tests/wf_mcp/service/test_events.py`

- [ ] **Step 1: Add a direct raw method test**

Append to `tests/wf_mcp/service/test_upstream_transport.py`:

```python
from wf_mcp.connections import ConnectionRegistry
from wf_mcp.models import ConnectionConfig


def test_upstream_transport_invokes_raw_method_and_records_events() -> None:
    events: list[McpEvent] = []
    connections = ConnectionRegistry()
    connections.register(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    transport = UpstreamTransportService(
        store=FileStore(local_temp_root() / "upstream_raw_method"),
        event_sink=events.append,
    )
    transport.register_adapter("demo", FakeAdapter())

    result = asyncio.run(
        transport.invoke_method(
            connections.get("demo.personal"),
            "demo.echo",
            params={"text": "hello"},
        )
    )

    assert result["echoed"] == {"text": "hello"}
    assert [event.kind for event in events] == [
        "raw_method_started",
        "raw_method_completed",
    ]
```

Add `import asyncio` at the top of the test file.

- [ ] **Step 2: Run the direct raw method test and verify it fails**

Run:

```bash
uv run pytest tests/wf_mcp/service/test_upstream_transport.py::test_upstream_transport_invokes_raw_method_and_records_events -q
```

Expected: fail because `invoke_method` does not exist on `UpstreamTransportService`.

- [ ] **Step 3: Move upstream call methods**

In `src/wf_mcp/broker/service/upstream_transport.py`, add imports:

```python
from typing import Any
```

Add methods:

```python
    async def read_resource(
        self,
        connection: ConnectionConfig,
        qualified_name: str,
        uri: str,
    ) -> dict[str, Any]:
        adapter = require_adapter(connection, self.adapters)
        auth = self.load_auth(connection.id)
        self.event_sink(
            make_event(
                "resource_read_started",
                connection_id=connection.id,
                capability_id=qualified_name,
                payload={"uri": uri},
            )
        )
        result = await adapter.read_resource(connection, auth, uri)
        self.event_sink(
            make_event(
                "resource_read_completed",
                connection_id=connection.id,
                capability_id=qualified_name,
                payload={"uri": uri},
            )
        )
        return result

    async def render_prompt(
        self,
        connection: ConnectionConfig,
        qualified_name: str,
        local_name: str,
        arguments: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        adapter = require_adapter(connection, self.adapters)
        auth = self.load_auth(connection.id)
        self.event_sink(
            make_event(
                "prompt_get_started",
                connection_id=connection.id,
                capability_id=qualified_name,
                payload={"argument_keys": sorted((arguments or {}).keys())},
            )
        )
        result = await adapter.get_prompt(connection, auth, local_name, arguments)
        self.event_sink(
            make_event(
                "prompt_get_completed",
                connection_id=connection.id,
                capability_id=qualified_name,
                payload={"argument_keys": sorted((arguments or {}).keys())},
            )
        )
        return result

    async def invoke_method(
        self,
        connection: ConnectionConfig,
        method: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        adapter = require_adapter(connection, self.adapters)
        auth = self.load_auth(connection.id)
        self.event_sink(
            make_event(
                "raw_method_started",
                connection_id=connection.id,
                capability_id=method,
                payload={"params": params or {}},
            )
        )
        result = await adapter.invoke_method(connection, auth, method, params)
        self.event_sink(
            make_event(
                "raw_method_completed",
                connection_id=connection.id,
                capability_id=method,
                payload={"result_keys": sorted(result.keys())},
            )
        )
        return result

    async def send_notification(
        self,
        connection: ConnectionConfig,
        method: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> None:
        adapter = require_adapter(connection, self.adapters)
        auth = self.load_auth(connection.id)
        self.event_sink(
            make_event(
                "raw_notification_started",
                connection_id=connection.id,
                capability_id=method,
                payload={"params": params or {}},
            )
        )
        await adapter.send_notification(connection, auth, method, params)
        self.event_sink(
            make_event(
                "raw_notification_completed",
                connection_id=connection.id,
                capability_id=method,
                payload={},
            )
        )
```

- [ ] **Step 4: Delegate WfMcpService upstream calls**

In `src/wf_mcp/broker/service/core.py`, keep local docs handling in `WfMcpService.read_resource` and `render_prompt`, but delegate remote calls:

```python
        resource = self.get_resource(qualified_name)
        connection = self.connections.get(resource.connection_id)
        return await self.upstream.read_resource(
            connection,
            qualified_name,
            resource.uri,
        )
```

For prompts:

```python
        prompt = self.get_prompt(qualified_name)
        connection = self.connections.get(prompt.connection_id)
        return await self.upstream.render_prompt(
            connection,
            qualified_name,
            prompt.local_name,
            arguments,
        )
```

For raw method:

```python
        connection = self.connections.get(connection_id)
        return await self.upstream.invoke_method(
            connection,
            method,
            params=params,
        )
```

For notification:

```python
        connection = self.connections.get(connection_id)
        await self.upstream.send_notification(connection, method, params=params)
```

- [ ] **Step 5: Run service event tests**

Run:

```bash
uv run pytest tests/wf_mcp/service/test_upstream_transport.py::test_upstream_transport_invokes_raw_method_and_records_events tests/wf_mcp/service/test_events.py::test_service_records_resource_prompt_and_raw_method_events -q
```

If the exact event test name differs, run:

```bash
uv run pytest tests/wf_mcp/service/test_events.py -q
```

Expected: pass.

- [ ] **Step 6: Run ruff**

Run:

```bash
uv run ruff check src/wf_mcp/broker/service/core.py src/wf_mcp/broker/service/upstream_transport.py tests/wf_mcp/service/test_upstream_transport.py
```

Expected: pass.

---

## Task 4: Move Catalog Refresh Upstream I/O

**Files:**

- Modify: `src/wf_mcp/broker/service/upstream_transport.py`
- Modify: `src/wf_mcp/broker/service/core.py`
- Test: `tests/wf_mcp/service/test_upstream_transport.py`
- Test: `tests/wf_mcp/service/test_catalog.py`
- Test: `tests/wf_mcp/service/test_events.py`

- [ ] **Step 1: Add a direct refresh test**

Append:

```python
from wf_mcp.broker.service.source_catalog import SourceCatalogService


def test_upstream_transport_refreshes_catalog_directly() -> None:
    events: list[McpEvent] = []
    store = FileStore(local_temp_root() / "upstream_refresh")
    connections = ConnectionRegistry()
    connection = ConnectionConfig(id="demo.personal", server="demo", account="personal")
    connections.register(connection)
    transport = UpstreamTransportService(store=store, event_sink=events.append)
    transport.register_adapter("demo", FakeAdapter())
    source_catalog = SourceCatalogService(
        store=store,
        connection_lookup=connections.get,
        connection_list_enabled=connections.list_enabled,
        connection_list_all=connections.list_all,
        tool_executor_for=transport.tool_executor_for,
        load_auth=transport.load_auth,
        emit_event=events.append,
    )
    source_catalog.hydrate_connection_source_from_snapshot(connection)

    asyncio.run(
        transport.refresh_connection_catalog(
            connection,
            source_catalog=source_catalog,
            record_catalog_change_events=lambda source_id, snapshot, reason: None,
        )
    )

    snapshot = store.load_catalog("demo.personal")
    assert snapshot is not None
    assert len(snapshot.nodes) >= 1
    assert "catalog_refresh_started" in [event.kind for event in events]
    assert "catalog_refresh_completed" in [event.kind for event in events]
```

- [ ] **Step 2: Run the direct refresh test and verify it fails**

Run:

```bash
uv run pytest tests/wf_mcp/service/test_upstream_transport.py::test_upstream_transport_refreshes_catalog_directly -q
```

Expected: fail because `refresh_connection_catalog` does not exist on `UpstreamTransportService`.

- [ ] **Step 3: Move refresh I/O into UpstreamTransportService**

In `src/wf_mcp/broker/service/upstream_transport.py`, add imports:

```python
import time

from wf_mcp.broker.catalog import snapshot_from_specs
from wf_mcp.broker.discovery import discover_connection_capabilities, specs_from_discovered_tools
from wf_mcp.models import CatalogSnapshot
from wf_mcp.shared.errors import error_payload
from .source_catalog import SourceCatalogService
```

Add:

```python
    async def refresh_connection_catalog(
        self,
        connection: ConnectionConfig,
        *,
        source_catalog: SourceCatalogService,
        max_age_seconds: int | None = None,
        default_catalog_max_age_seconds: int = 300,
        record_catalog_change_events: Callable[[str, CatalogSnapshot, str], None],
    ) -> None:
        auth = self.load_auth(connection.id)
        self.event_sink(
            make_event(
                "catalog_refresh_started",
                connection_id=connection.id,
                payload={"server": connection.server},
            )
        )
        try:
            adapter = require_adapter(connection, self.adapters)
            capabilities = await discover_connection_capabilities(
                connection=connection,
                auth=auth,
                adapter=adapter,
            )
            specs = specs_from_discovered_tools(
                connection=connection,
                auth=auth,
                executor=self.tool_executor_for(connection),
                tools=capabilities.tools,
                emit_event=self.event_sink,
            )
            source_catalog.register_specs(
                connection.id,
                *specs,
                max_age_seconds=max_age_seconds,
                emit_change_events=False,
            )
            snapshot = snapshot_from_specs(
                connection.id,
                specs=source_catalog.capability_sources[
                    connection.id
                ].capabilities.node_specs,
                tool_display_names={tool.name: tool.title for tool in capabilities.tools},
                resources=capabilities.resources,
                prompts=capabilities.prompts,
                metadata=capabilities.metadata,
                fetched_at_epoch_ms=int(time.time() * 1000),
                max_age_seconds=max_age_seconds or default_catalog_max_age_seconds,
            )
            self.store.save_catalog(snapshot)
            record_catalog_change_events(connection.id, snapshot, "catalog_refresh")
            self.event_sink(
                make_event(
                    "catalog_refresh_completed",
                    connection_id=connection.id,
                    payload={
                        "node_count": len(snapshot.nodes),
                        "resource_count": len(snapshot.resources),
                        "prompt_count": len(snapshot.prompts),
                    },
                )
            )
        except Exception as exc:
            self.event_sink(
                make_event(
                    "catalog_refresh_failed",
                    connection_id=connection.id,
                    payload=error_payload(exc),
                )
            )
            raise
```

- [ ] **Step 4: Delegate WfMcpService refresh**

Replace `WfMcpService.refresh_connection_catalog` body with:

```python
        connection = self.connections.get(connection_id)
        await self.upstream.refresh_connection_catalog(
            connection,
            source_catalog=self.source_catalog,
            max_age_seconds=max_age_seconds,
            default_catalog_max_age_seconds=self.default_catalog_max_age_seconds,
            record_catalog_change_events=lambda source_id, snapshot, reason: (
                self._record_catalog_change_events(
                    source_id,
                    snapshot,
                    reason=reason,
                )
            ),
        )
```

- [ ] **Step 5: Run refresh and catalog regression tests**

Run:

```bash
uv run pytest tests/wf_mcp/service/test_upstream_transport.py::test_upstream_transport_refreshes_catalog_directly tests/wf_mcp/service/test_catalog.py::test_service_hydrates_planner_specs_from_stored_catalog tests/wf_mcp/service/test_events.py::test_service_records_catalog_refresh_failure_event -q
```

If the exact failure-event test name differs, run:

```bash
uv run pytest tests/wf_mcp/service/test_events.py -q
```

Expected: pass.

- [ ] **Step 6: Run ruff**

Run:

```bash
uv run ruff check src/wf_mcp/broker/service/core.py src/wf_mcp/broker/service/upstream_transport.py tests/wf_mcp/service/test_upstream_transport.py
```

Expected: pass.

---

## Task 5: Move Live Source Diagnostics to UpstreamTransportService

**Files:**

- Modify: `src/wf_mcp/broker/service/upstream_transport.py`
- Modify: `src/wf_mcp/broker/service/workflow_live_checks.py`
- Modify: `src/wf_mcp/broker/service/workflow_operation_context.py`
- Test: `tests/wf_mcp/workflow_surface/test_deployments.py`

- [ ] **Step 1: Add a direct live-check missing connection test**

Append to `tests/wf_mcp/service/test_upstream_transport.py`:

```python
def test_upstream_transport_live_diagnostics_report_missing_connection() -> None:
    transport = UpstreamTransportService(
        store=FileStore(local_temp_root() / "upstream_live_missing"),
        event_sink=lambda event: None,
    )
    source_catalog = SourceCatalogService(
        store=transport.store,
        connection_lookup=lambda connection_id: (_ for _in ()).throw(
            KeyError(connection_id)
        ),
        connection_list_enabled=lambda: [],
        connection_list_all=lambda: [],
        tool_executor_for=transport.tool_executor_for,
        load_auth=transport.load_auth,
        emit_event=lambda event: None,
    )
    source_catalog.register_capability_source(
        CapabilitySource(
            id="demo.personal",
            kind="connection",
            permissions=SourcePermissions(calls_upstream=True),
            capabilities=CapabilityBuckets(),
        )
    )
    artifact = echo_artifact()
    deployment = WorkflowDeployment(
        id="echo.personal",
        artifact_id="echo",
        artifact_version=1,
        bindings=[{"logical_source": "demo", "concrete_source": "demo.personal"}],
    )

    diagnostics = asyncio.run(
        transport.deployment_diagnostics(
            deployment=deployment,
            artifacts=[artifact],
            source_catalog=source_catalog,
        )
    )

    assert diagnostics[0].code == "source_unreachable"
    assert diagnostics[0].bound_source == "demo.personal"

```

Add this import with the other test helpers:

```python
from wf_artifacts import WorkflowDeployment
from wf_platform import SourcePermissions

from ..workflow_surface.conftest import echo_artifact
```

Keep this test focused on `UpstreamTransportService`; do not call
`WorkflowSurfaceHandlers.validate_deployment` here.

- [ ] **Step 2: Run the live-check test and verify it fails**

Run:

```bash
uv run pytest tests/wf_mcp/service/test_upstream_transport.py::test_upstream_transport_live_diagnostics_report_missing_connection -q
```

Expected: fail because `deployment_diagnostics` does not exist.

- [ ] **Step 3: Move live diagnostics implementation**

Move the implementation from `src/wf_mcp/broker/service/workflow_live_checks.py` into `UpstreamTransportService` as:

```python
    async def deployment_diagnostics(
        self,
        *,
        deployment: WorkflowDeployment,
        artifacts: Sequence[WorkflowArtifact],
        source_catalog: SourceCatalogService,
    ) -> list[DependencyDiagnostic]:
        ...
```

Use:

```python
source = source_catalog.capability_sources.get(source_id)
connection = source_catalog.connection_lookup(source_id)
adapter = require_adapter(connection, self.adapters)
auth = self.load_auth(source_id)
```

Keep the same timeout constant and same caught exception tuple.

- [ ] **Step 4: Leave workflow_live_checks.py as a shim or delete if unused**

Search:

```bash
rg -n "live_source_diagnostics|LIVE_SOURCE_CHECK_TIMEOUT_SECONDS|workflow_live_checks" src tests
```

If only `workflow_operation_context.py` uses it, update that file and delete `workflow_live_checks.py`.

If tests import it directly, keep `workflow_live_checks.py` as a compatibility shim:

```python
"""Compatibility wrappers for live source diagnostics.

Canonical live-check implementation now lives on UpstreamTransportService.
"""
```

and delegate through `service.upstream.deployment_diagnostics(...)`.

- [ ] **Step 5: Update workflow operation context**

In `src/wf_mcp/broker/service/workflow_operation_context.py`, remove the import:

```python
from .workflow_live_checks import live_source_diagnostics
```

Change `WfMcpWorkflowLiveSourceChecker.deployment_diagnostics` to:

```python
        return await self.service.upstream.deployment_diagnostics(
            deployment=deployment,
            artifacts=artifacts,
            source_catalog=self.service.source_catalog,
        )
```

- [ ] **Step 6: Run deployment live-check tests**

Run:

```bash
uv run pytest tests/wf_mcp/service/test_upstream_transport.py::test_upstream_transport_live_diagnostics_report_missing_connection tests/wf_mcp/workflow_surface/test_deployments.py -q
```

Expected: pass.

- [ ] **Step 7: Run ruff**

Run:

```bash
uv run ruff check src/wf_mcp/broker/service/upstream_transport.py src/wf_mcp/broker/service/workflow_live_checks.py src/wf_mcp/broker/service/workflow_operation_context.py tests/wf_mcp/service/test_upstream_transport.py
```

If `workflow_live_checks.py` was deleted, remove it from the ruff command.

Expected: pass.

---

## Task 6: Clean Imports, Docs, and Verify

**Files:**

- Modify: `src/wf_mcp/broker/service/core.py`
- Modify: `src/wf_mcp/broker/service/upstream_transport.py`
- Modify: `docs/current_roadmap.md`
- Modify: `docs/superpowers/research/2026-06-01-wf-api-extraction-map.md` if stale.

- [ ] **Step 1: Remove stale imports from core.py**

After the move, `src/wf_mcp/broker/service/core.py` should no longer import items used only by upstream transport, such as:

```python
import time
from ...shared.errors import error_payload
from ..discovery import discover_connection_capabilities, specs_from_discovered_tools
from .adapters import require_adapter
from ..catalog import snapshot_from_specs
```

Keep imports still used by source catalog delegates, runtime delegates, public signatures, or event catalog-change methods.

- [ ] **Step 2: Add roadmap note**

In `docs/current_roadmap.md`, under the service extraction bullets, add:

```markdown
  - Upstream MCP transport is being separated from broker coordination.
    `UpstreamTransportService` now owns adapter registration, auth persistence,
    catalog refresh I/O, resource/prompt reads, raw method/notification calls,
    generated-tool executor selection, and live source diagnostics.
```

- [ ] **Step 3: Update extraction map if stale**

If `docs/superpowers/research/2026-06-01-wf-api-extraction-map.md` says `WfMcpService` directly owns upstream transport/auth/adapter behavior, add:

```markdown
Upstream MCP transport ownership is now split: `UpstreamTransportService` owns
adapter registry, auth persistence, catalog refresh I/O, resource/prompt reads,
raw method/notification calls, generated-tool executor selection, and live
source diagnostics. `WfMcpService` remains the coordinator and compatibility
façade.
```

- [ ] **Step 4: Run focused verification**

Run:

```bash
uv run pytest tests/wf_mcp/service/test_upstream_transport.py tests/wf_mcp/service/test_events.py tests/wf_mcp/service/test_catalog.py::test_service_hydrates_planner_specs_from_stored_catalog tests/wf_mcp/service/test_sources.py tests/wf_mcp/workflow_surface/test_deployments.py tests/wf_mcp/workflow_surface/test_runs.py -q
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
- basedpyright reports `0 errors`. If the known workspace enumeration warning causes a nonzero exit despite `0 errors`, record the exact output.

---

## Non-Goals and Follow-Up Slices

This plan intentionally leaves these for later:

1. **Connection registry extraction:** `register_connection`, reserved-id policy, and config reconciliation still live on `WfMcpService`.
2. **Event recorder extraction:** event bus and catalog-change event fanout still live on `WfMcpService`.
3. **Admin surface extraction:** admin handlers still call `WfMcpService` delegate methods.
4. **Final coordinator rename:** only consider renaming `WfMcpService` once most implementation services are extracted.

---

## Self-Review

- Spec coverage: The plan extracts upstream adapter/auth/I/O/live-check responsibilities while preserving current public service methods and admin behavior.
- Placeholder scan: No placeholder implementation tasks are left. Test snippets use existing artifact/deployment constructor shapes from the workflow surface tests.
- Type consistency: `UpstreamTransportService` owns `store`, `event_sink`, `adapters`, and optional `tool_executor`; `WfMcpService` delegates through `service.upstream`.
