# WfMcpService ConnectionService Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move connection registration and config reconciliation out of `WfMcpService` into a focused `ConnectionService`.

**Architecture:** `ConnectionService` owns the broker-local `ConnectionRegistry` and emits connection lifecycle events. `SourceCatalogService` still owns capability sources, so `ConnectionService` binds to it after both services are constructed. `WfMcpService` remains a compatibility facade with `.connections`, `register_connection()`, and `sync_connections_from_config()` delegating to the new service.

**Tech Stack:** Python 3.14, dataclasses, pytest, ruff, basedpyright, existing `wf_mcp` broker service modules.

---

## File Structure

- Create `src/wf_mcp/broker/service/connection_service.py`
  - Owns `ConnectionRegistry`.
  - Validates connection IDs and reserved IDs.
  - Registers connections and hydrates source catalog snapshots.
  - Reconciles config reload changes.
- Modify `src/wf_mcp/broker/service/core.py`
  - Removes direct `ConnectionRegistry` field from `WfMcpService`.
  - Constructs `ConnectionService`, passes its lookup/list callbacks into `SourceCatalogService`, then binds the source catalog back to `ConnectionService`.
  - Keeps compatibility property/method delegates.
- Create `tests/wf_mcp/service/test_connection_service.py`
  - Direct tests for `ConnectionService`.
  - Service facade smoke test for `.connections` compatibility.
- Modify `docs/current_roadmap.md`
  - Mark the connection-service extraction as the current/complete slice after implementation.
- Optionally modify `docs/superpowers/research/2026-06-01-wf-api-extraction-map.md`
  - Add one ownership note if the file still tracks `WfMcpService` decomposition.

---

### Task 1: Add Direct ConnectionService Tests

**Files:**
- Create: `tests/wf_mcp/service/test_connection_service.py`

- [ ] **Step 1: Create direct tests for the new service boundary**

Create `tests/wf_mcp/service/test_connection_service.py` with:

```python
from __future__ import annotations

from wf_mcp.broker.service.connection_service import ConnectionService
from wf_mcp.broker.service.events import BrokerEventRecorder
from wf_mcp.broker.service.source_catalog import SourceCatalogService
from wf_mcp.events import EventBus
from wf_mcp.models import BrokerConfig, ConnectionConfig
from wf_mcp.runtime import ToolExecutor
from wf_mcp.storage import FileStore

from ..test_support import local_temp_root


def _source_catalog(service: ConnectionService) -> SourceCatalogService:
    store = FileStore(local_temp_root() / "connection_service_catalog")

    def _tool_executor_for(_connection: ConnectionConfig) -> ToolExecutor:
        raise AssertionError("tool executor should not be needed in these tests")

    catalog = SourceCatalogService(
        store=store,
        connection_lookup=service.get,
        connection_list_enabled=service.list_enabled,
        connection_list_all=service.list_all,
        tool_executor_for=_tool_executor_for,
        load_auth=lambda _connection_id: None,
        emit_event=service.events.record_event,
    )
    service.bind_source_catalog(catalog)
    return catalog


def test_connection_service_rejects_reserved_connection_ids() -> None:
    service = ConnectionService(events=BrokerEventRecorder(EventBus()))
    _source_catalog(service)

    for connection_id in ("wf.admin", "wf.mcp"):
        try:
            service.register_connection(
                ConnectionConfig(id=connection_id, server="wf", account="reserved")
            )
        except ValueError as exc:
            assert connection_id in str(exc)
            assert "reserved by wf-mcp" in str(exc)
        else:
            raise AssertionError(f"expected {connection_id!r} to be rejected")


def test_connection_service_registers_connection_and_empty_source() -> None:
    service = ConnectionService(events=BrokerEventRecorder(EventBus()))
    catalog = _source_catalog(service)

    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )

    assert service.get("demo.personal").server == "demo"
    assert [connection.id for connection in service.list_enabled()] == ["demo.personal"]
    source = catalog.capability_sources["demo.personal"]
    assert source.enabled is True
    assert source.description == "No catalog loaded for demo.personal."
    assert service.events.list_events()[0].kind == "connection_registered"
    assert service.events.list_events()[0].connection_id == "demo.personal"


def test_connection_service_sync_removes_retired_connections_and_sources() -> None:
    service = ConnectionService(events=BrokerEventRecorder(EventBus()))
    catalog = _source_catalog(service)
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )

    service.sync_connections_from_config(
        BrokerConfig(store_root=local_temp_root(), connections=[])
    )

    assert service.list_all() == []
    assert "demo.personal" not in catalog.capability_sources


def test_connection_service_sync_updates_existing_source_enabled_flag() -> None:
    service = ConnectionService(events=BrokerEventRecorder(EventBus()))
    catalog = _source_catalog(service)
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )

    service.sync_connections_from_config(
        BrokerConfig(
            store_root=local_temp_root(),
            connections=[
                ConnectionConfig(
                    id="demo.personal",
                    server="demo",
                    account="personal",
                    enabled=False,
                )
            ],
        )
    )

    assert service.get("demo.personal").enabled is False
    assert catalog.capability_sources["demo.personal"].enabled is False
```

- [ ] **Step 2: Run the direct test and confirm it fails before implementation**

Run:

```bash
uv run pytest tests/wf_mcp/service/test_connection_service.py -q
```

Expected: import failure for `wf_mcp.broker.service.connection_service`.

---

### Task 2: Implement ConnectionService

**Files:**
- Create: `src/wf_mcp/broker/service/connection_service.py`

- [ ] **Step 1: Add the service implementation**

Create `src/wf_mcp/broker/service/connection_service.py` with:

```python
from __future__ import annotations

from dataclasses import dataclass, field

from ...connections import ConnectionRegistry, parse_connection_id
from ...models import BrokerConfig, ConnectionConfig
from ...shared.names import RESERVED_CONNECTION_IDS
from .events import BrokerEventRecorder
from .source_catalog import SourceCatalogService


@dataclass(slots=True)
class ConnectionService:
    """Own broker connection registration and config reconciliation.

    SourceCatalogService needs connection lookup callbacks during construction,
    while registering a connection needs source-catalog hydration. The catalog is
    therefore bound after both services exist; `_source_catalog()` makes that
    construction cycle explicit and fail-fast.
    """

    events: BrokerEventRecorder
    connections: ConnectionRegistry = field(default_factory=ConnectionRegistry)
    source_catalog: SourceCatalogService | None = None

    def bind_source_catalog(self, source_catalog: SourceCatalogService) -> None:
        self.source_catalog = source_catalog

    def get(self, connection_id: str) -> ConnectionConfig:
        return self.connections.get(connection_id)

    def list_all(self) -> list[ConnectionConfig]:
        return self.connections.list_all()

    def list_enabled(self) -> list[ConnectionConfig]:
        return self.connections.list_enabled()

    def register_connection(self, connection: ConnectionConfig) -> None:
        self._validate_connection_id(connection.id)
        self.connections.register(connection)
        self._source_catalog().hydrate_connection_source_from_snapshot(connection)
        self.events.record_kind(
            "connection_registered",
            connection_id=connection.id,
            payload={"server": connection.server, "account": connection.account},
        )

    def sync_connections_from_config(self, config: BrokerConfig) -> None:
        """Reconcile registry/source state after the public server reloads config."""
        source_catalog = self._source_catalog()
        next_ids = {connection.id for connection in config.connections}
        previous_ids = set(self.connections.connections)
        for connection_id in previous_ids - next_ids:
            del self.connections.connections[connection_id]
            source_catalog.capability_sources.pop(connection_id, None)

        for connection in config.connections:
            self._validate_connection_id(connection.id)
            self.connections.register(connection)
            source = source_catalog.capability_sources.get(connection.id)
            if source is None:
                source_catalog.hydrate_connection_source_from_snapshot(connection)
            else:
                source.enabled = connection.enabled

    def _source_catalog(self) -> SourceCatalogService:
        if self.source_catalog is None:
            raise RuntimeError("ConnectionService requires a bound SourceCatalogService")
        return self.source_catalog

    @staticmethod
    def _validate_connection_id(connection_id: str) -> None:
        parse_connection_id(connection_id)
        if connection_id in RESERVED_CONNECTION_IDS:
            raise ValueError(f"connection id {connection_id!r} is reserved by wf-mcp")
```

- [ ] **Step 2: Run the direct tests**

Run:

```bash
uv run pytest tests/wf_mcp/service/test_connection_service.py -q
```

Expected: all tests pass.

- [ ] **Step 3: Run ruff on the new files**

Run:

```bash
uv run ruff check src/wf_mcp/broker/service/connection_service.py tests/wf_mcp/service/test_connection_service.py
```

Expected: all checks pass.

---

### Task 3: Wire WfMcpService Through ConnectionService

**Files:**
- Modify: `src/wf_mcp/broker/service/core.py`

- [ ] **Step 1: Update imports and dataclass fields**

In `src/wf_mcp/broker/service/core.py`:

Remove:

```python
from ...connections import ConnectionRegistry, parse_connection_id
from ...shared.names import RESERVED_CONNECTION_IDS
```

Replace with:

```python
from ...connections import ConnectionRegistry
```

Add:

```python
from .connection_service import ConnectionService
```

In `WfMcpService`, remove the dataclass field:

```python
connections: ConnectionRegistry = field(default_factory=ConnectionRegistry)
```

Add this init-false field near the other service fields:

```python
connection_service: ConnectionService = field(init=False)
```

- [ ] **Step 2: Construct and bind the connection service**

In `__post_init__`, replace the source-catalog construction block with this shape:

```python
self.events = BrokerEventRecorder(self.event_bus)
self.connection_service = ConnectionService(events=self.events)
self.upstream = UpstreamTransportService(
    store=self.store,
    event_sink=self.events.record_event,
    tool_executor=self.tool_executor,
)
self.source_catalog = SourceCatalogService(
    store=self.store,
    connection_lookup=self.connection_service.get,
    connection_list_enabled=self.connection_service.list_enabled,
    connection_list_all=self.connection_service.list_all,
    tool_executor_for=self.upstream.tool_executor_for,
    load_auth=self.upstream.load_auth,
    emit_event=self.events.record_event,
    default_catalog_max_age_seconds=self.default_catalog_max_age_seconds,
)
self.connection_service.bind_source_catalog(self.source_catalog)
```

- [ ] **Step 3: Preserve `.connections` compatibility as a property**

Add this property below `capability_sources` or above it:

```python
@property
def connections(self) -> ConnectionRegistry:
    """Compatibility view of the broker connection registry.

    Connection lifecycle ownership has moved to ConnectionService. Keep this
    property because admin handlers, CLI helpers, and tests still inspect the
    registry through the service facade.
    """
    return self.connection_service.connections
```

- [ ] **Step 4: Replace connection lifecycle method bodies with delegates**

Replace `register_connection` with:

```python
def register_connection(self, connection: ConnectionConfig) -> None:
    self.connection_service.register_connection(connection)
```

Replace `sync_connections_from_config` with:

```python
def sync_connections_from_config(self, config: BrokerConfig) -> None:
    self.connection_service.sync_connections_from_config(config)
```

- [ ] **Step 5: Run focused service tests**

Run:

```bash
uv run pytest tests/wf_mcp/service/test_connection_service.py tests/wf_mcp/service/test_catalog.py tests/wf_mcp/service/test_sources.py tests/wf_mcp/test_events.py -q
```

Expected: all selected tests pass.

---

### Task 4: Add Facade Compatibility Tests

**Files:**
- Modify: `tests/wf_mcp/service/test_connection_service.py`

- [ ] **Step 1: Add WfMcpService compatibility coverage**

Append these imports:

```python
from wf_mcp.broker import WfMcpService
```

Append these tests:

```python
def test_wfmcpservice_exposes_connection_registry_from_connection_service() -> None:
    service = WfMcpService(store=FileStore(local_temp_root() / "connection_facade"))

    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )

    assert service.connections is service.connection_service.connections
    assert service.connections.get("demo.personal").account == "personal"
    assert "demo.personal" in service.capability_sources


def test_wfmcpservice_sync_connections_delegates_to_connection_service() -> None:
    service = WfMcpService(store=FileStore(local_temp_root() / "connection_sync"))
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )

    service.sync_connections_from_config(
        BrokerConfig(
            store_root=local_temp_root(),
            connections=[
                ConnectionConfig(
                    id="demo.work",
                    server="demo",
                    account="work",
                    enabled=True,
                )
            ],
        )
    )

    assert [connection.id for connection in service.connections.list_all()] == [
        "demo.work"
    ]
    assert "demo.personal" not in service.capability_sources
    assert "demo.work" in service.capability_sources
```

- [ ] **Step 2: Run the compatibility tests**

Run:

```bash
uv run pytest tests/wf_mcp/service/test_connection_service.py -q
```

Expected: all tests pass.

---

### Task 5: Clean Imports and Verify Call Sites

**Files:**
- Modify: `src/wf_mcp/broker/service/core.py`
- Possibly modify files only if ruff reports stale imports.

- [ ] **Step 1: Search for stale direct ownership assumptions**

Run:

```bash
rg -n 'parse_connection_id|RESERVED_CONNECTION_IDS|connection_service|ConnectionRegistry|connections: ConnectionRegistry' src/wf_mcp/broker/service tests/wf_mcp/service
```

Expected:
- `parse_connection_id` and `RESERVED_CONNECTION_IDS` appear in `connection_service.py`, not `core.py`.
- `connections: ConnectionRegistry` appears in `connection_service.py`, not `core.py`.
- `connection_service` appears in `core.py` and direct tests.

- [ ] **Step 2: Run ruff on modified service files**

Run:

```bash
uv run ruff check src/wf_mcp/broker/service/core.py src/wf_mcp/broker/service/connection_service.py tests/wf_mcp/service/test_connection_service.py
```

Expected: all checks pass. If ruff reports unused imports in `core.py`, remove only those imports.

- [ ] **Step 3: Run basedpyright on modified source**

Run:

```bash
uv run basedpyright --level error
```

Expected: 0 errors.

---

### Task 6: Update Roadmap and Extraction Map

**Files:**
- Modify: `docs/current_roadmap.md`
- Modify if present/relevant: `docs/superpowers/research/2026-06-01-wf-api-extraction-map.md`

- [ ] **Step 1: Update `docs/current_roadmap.md`**

Find the bullet that says:

```markdown
- Next planned service extraction: move connection registration/config reconciliation
  into a `ConnectionService`. That slice should own reserved connection-id
  rejection, `register_connection`, `sync_connections_from_config`, and source
  hydration coordination while leaving `WfMcpService` as a compatibility
  coordinator.
```

Replace it with:

```markdown
- Connection ownership now lives in `ConnectionService`: it owns the broker
  `ConnectionRegistry`, reserved connection-id rejection, `register_connection`,
  and `sync_connections_from_config`. `WfMcpService.connections` remains a
  compatibility property while source hydration still belongs to
  `SourceCatalogService`.
```

- [ ] **Step 2: Update the extraction map if it contains the WfMcpService split notes**

Run:

```bash
rg -n 'ConnectionService|connection registration|sync_connections_from_config|WfMcpService' docs/superpowers/research/2026-06-01-wf-api-extraction-map.md
```

If the file exists and contains the service split section, add this short note near the other extracted-service bullets:

```markdown
- Connection registration/config reload reconciliation is now owned by
  `wf_mcp.broker.service.connection_service.ConnectionService`. The service owns
  the `ConnectionRegistry`; `WfMcpService.connections` is only a compatibility
  property.
```

- [ ] **Step 3: Run docs grep to verify roadmap wording**

Run:

```bash
rg -n 'ConnectionService|Connection ownership|Next planned service extraction' docs/current_roadmap.md docs/superpowers/research/2026-06-01-wf-api-extraction-map.md
```

Expected:
- `docs/current_roadmap.md` mentions completed `ConnectionService` ownership.
- No stale "Next planned service extraction" wording for this same slice remains.

---

### Task 7: Final Verification

**Files:**
- No new files.

- [ ] **Step 1: Run focused tests**

Run:

```bash
uv run pytest tests/wf_mcp/service/test_connection_service.py tests/wf_mcp/service/test_catalog.py tests/wf_mcp/service/test_sources.py tests/wf_mcp/service/test_events.py tests/wf_mcp/test_broker_server.py tests/wf_mcp/test_admin_surface.py -q
```

Expected: all selected tests pass.

- [ ] **Step 2: Run full test suite**

Run:

```bash
uv run pytest -q
```

Expected: full suite passes with the existing skipped/xfailed counts only.

- [ ] **Step 3: Run final static checks**

Run:

```bash
uv run ruff check
uv run ruff format --check
uv run basedpyright --level error
```

Expected:
- ruff check passes.
- ruff format check passes for Python files.
- basedpyright reports 0 errors.

If markdown format checks complain about preview-only markdown behavior, do not rewrite unrelated markdown. Report it as a formatting-tool limitation and keep the code checks green.

---

## Self-Review

- Spec coverage: The plan moves reserved ID validation, `register_connection`, and `sync_connections_from_config` into `ConnectionService`; preserves `.connections` compatibility; keeps source hydration coordination explicit through a post-construction bind.
- Placeholder scan: No `TBD`, generic "add tests", or unfilled implementation steps remain.
- Type consistency: `ConnectionService` exposes `get`, `list_all`, and `list_enabled` so `SourceCatalogService` can use bound methods without depending on `WfMcpService`.
- Risk: The construction cycle between connection lookup and source hydration is intentionally represented by `bind_source_catalog()`. The fail-fast `_source_catalog()` guard prevents silent use before binding.
