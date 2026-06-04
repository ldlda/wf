# Source Config Ownership Policy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace implicit "config always shadows registry" behavior with explicit config ownership policy for MCP source entries: `locked` vs `seed`.

**Architecture:** Keep v1 safety by making `locked` the default for existing config connections. Add `seed` as an explicit opt-in that materializes a missing store entry, then lets the store-backed registry own future admin changes. Do this in the MCP broker config path first; neutral `wf_config.server.sources` only models built-in stdlib sources today and should not grow MCP transport config in this slice.

**Tech Stack:** Python 3.14, Pydantic v2, wf_mcp broker config/service, wf_mcp source registry, pytest, ruff, basedpyright.

---

## Current Context

Relevant current behavior:

- `src/wf_mcp/broker/service/connection_service.py::ConnectionService.sync_connections_from_config()` loads config connections first, then ignores same-id registry entries.
- Same-id registry entries emit `source_registry_ignored_config_shadow`.
- `src/wf_mcp/source_registry.py::McpSourceRegistryEntry` is the persisted desired source entry.
- `src/wf_mcp/models.py::ConnectionConfig` is the broker runtime config model used by legacy MCP config.
- `src/wf_mcp/control.py::BrokerConfigFile.to_runtime()` converts config-file connection declarations into `ConnectionConfig`.

Intended new policy:

- `locked`: config owns the source id. Same-id registry entries remain shadowed.
- `seed`: config bootstraps a missing registry entry. Once the registry entry exists, registry owns later runtime state for that id.
- Backward compatibility: existing config with no policy behaves as `locked`.

Out of scope:

- Do not add MCP source transports to neutral `wf_config.server.sources`.
- Do not add auth/catalog cleanup.
- Do not implement live remount without reload.
- Do not alter built-in reserved ids (`wf.std`, `wf.recipes`, `wf.admin`).

---

### Task 1: Add Policy Field to Broker Runtime and Config Models

**Files:**
- Modify: `src/wf_mcp/models.py`
- Modify: `src/wf_mcp/control.py`
- Test: `tests/wf_mcp/test_broker_config.py` or nearest existing broker config test file

- [ ] **Step 1: Inspect existing model shape**

Run:

```bash
rg -n "class ConnectionConfig|class .*Connection" src/wf_mcp/models.py src/wf_mcp/control.py tests/wf_mcp -g '*.py'
```

Expected: locate `ConnectionConfig` and the Pydantic config-file model that constructs it.

- [ ] **Step 2: Add a policy type and field to runtime config**

In `src/wf_mcp/models.py`, add a type alias near `ConnectionConfig`:

```python
SourceConfigOwnership = Literal["locked", "seed"]
```

Add to `ConnectionConfig`:

```python
source_config_ownership: SourceConfigOwnership = "locked"
```

If `Literal` is not imported, import it from `typing`.

- [ ] **Step 3: Add field to config-file connection model**

In `src/wf_mcp/control.py`, add the same field to the config-file connection model:

```python
source_config_ownership: SourceConfigOwnership = "locked"
```

When converting to `ConnectionConfig`, pass:

```python
source_config_ownership=self.source_config_ownership
```

If the config-file model is named differently, update the exact class that owns `id`, `server`, and `account`.

- [ ] **Step 4: Add config parsing tests**

In the existing broker config test file, add:

```python
def test_broker_config_connection_defaults_to_locked(tmp_path: Path) -> None:
    config_path = tmp_path / "wf_mcp.config.json"
    config_path.write_text(
        json.dumps(
            {
                "store_root": str(tmp_path / "store"),
                "connections": [
                    {"id": "demo.default", "server": "demo", "account": "default"}
                ],
            }
        ),
        encoding="utf-8",
    )

    config = load_broker_config(config_path)

    assert config.connections[0].source_config_ownership == "locked"


def test_broker_config_connection_accepts_seed_policy(tmp_path: Path) -> None:
    config_path = tmp_path / "wf_mcp.config.json"
    config_path.write_text(
        json.dumps(
            {
                "store_root": str(tmp_path / "store"),
                "connections": [
                    {
                        "id": "demo.default",
                        "server": "demo",
                        "account": "default",
                        "source_config_ownership": "seed",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    config = load_broker_config(config_path)

    assert config.connections[0].source_config_ownership == "seed"
```

Import `json`, `Path`, and `load_broker_config` as needed.

- [ ] **Step 5: Run focused tests**

Run:

```bash
uv run pytest tests/wf_mcp/test_broker_config.py -q
```

Expected: all tests pass.

---

### Task 2: Convert Seed Config Connections to Registry Entries

**Files:**
- Modify: `src/wf_mcp/source_registry.py`
- Test: `tests/wf_mcp/test_source_registry.py`

- [ ] **Step 1: Add conversion helper**

In `src/wf_mcp/source_registry.py`, add:

```python
def connection_config_to_registry_entry(
    connection: ConnectionConfig,
) -> McpSourceRegistryEntry:
    """Materialize a seed config connection into persisted registry state.

    Seed config is bootstrap-only. The registry entry must carry enough source
    identity to become the future desired-state owner after first startup.
    """
    transport = connection.metadata.get("transport")
    if not isinstance(transport, dict):
        raise ValueError(
            f"seed connection {connection.id!r} requires metadata.transport"
        )
    profile = connection.metadata.get("profile")
    auth_ref = connection.metadata.get("auth_ref")
    return McpSourceRegistryEntry.model_validate(
        {
            "id": connection.id,
            "enabled": connection.enabled,
            "provider": connection.server,
            "account": connection.account,
            "profile": profile if isinstance(profile, str) else None,
            "transport": transport,
            "auth_ref": auth_ref if isinstance(auth_ref, str) else None,
            "metadata": {
                key: value
                for key, value in connection.metadata.items()
                if key not in {"transport", "profile", "auth_ref", "source_registry"}
            },
        }
    )
```

Also export it in `__all__`.

- [ ] **Step 2: Add conversion test**

In `tests/wf_mcp/test_source_registry.py`, add:

```python
def test_connection_config_to_registry_entry_preserves_transport_metadata() -> None:
    connection = ConnectionConfig(
        id="github.work",
        server="github",
        account="work",
        enabled=False,
        metadata={
            "transport": {"kind": "stdio", "command": "npx", "args": ["server"]},
            "profile": "corp",
            "auth_ref": "secret://github/work",
            "region": "us",
        },
    )

    entry = connection_config_to_registry_entry(connection)

    assert entry.id == "github.work"
    assert entry.provider == "github"
    assert entry.account == "work"
    assert entry.enabled is False
    assert entry.profile == "corp"
    assert entry.auth_ref == "secret://github/work"
    assert entry.transport.kind == "stdio"
    assert entry.metadata["region"] == "us"
```

Add imports for `ConnectionConfig` and `connection_config_to_registry_entry`.

- [ ] **Step 3: Add missing transport failure test**

```python
def test_connection_config_to_registry_entry_requires_transport_metadata() -> None:
    connection = ConnectionConfig(id="github.work", server="github", account="work")

    with pytest.raises(ValueError, match="requires metadata.transport"):
        connection_config_to_registry_entry(connection)
```

- [ ] **Step 4: Run source registry tests**

Run:

```bash
uv run pytest tests/wf_mcp/test_source_registry.py -q
```

Expected: all tests pass.

---

### Task 3: Implement Locked vs Seed Startup Merge

**Files:**
- Modify: `src/wf_mcp/broker/service/connection_service.py`
- Test: `tests/wf_mcp/service/test_connection_service.py`

- [ ] **Step 1: Update imports**

In `src/wf_mcp/broker/service/connection_service.py`, import:

```python
from ...source_registry import (
    SourceRegistryFile,
    SourceRegistryStore,
    connection_config_to_registry_entry,
    registry_entry_to_connection_config,
)
```

If `SourceRegistryStore` and `registry_entry_to_connection_config` are already imported, extend the existing import.

- [ ] **Step 2: Rewrite registry merge block**

Inside `sync_connections_from_config`, replace the current registry loop with this logic:

```python
connections = list(config.connections)
config_by_id = {connection.id: connection for connection in connections}
registry_entries = {}
registry_changed = False

if source_registry_store is not None:
    registry = source_registry_store.load_registry()
    registry_entries = registry.source_map()

    for connection in connections:
        if connection.source_config_ownership != "seed":
            continue
        if connection.id in registry_entries:
            continue
        seeded = connection_config_to_registry_entry(connection)
        registry_entries[seeded.id] = seeded
        registry_changed = True
        self.events.record_kind(
            "source_registry_seeded_from_config",
            connection_id=seeded.id,
            payload={"server": seeded.provider, "account": seeded.account},
        )

    if registry_changed:
        source_registry_store.save_registry(
            SourceRegistryFile(sources=list(registry_entries.values()))
        )

    merged_connections: list[ConnectionConfig] = []
    for connection in connections:
        registry_entry = registry_entries.get(connection.id)
        if connection.source_config_ownership == "seed" and registry_entry is not None:
            merged_connections.append(registry_entry_to_connection_config(registry_entry))
            continue
        merged_connections.append(connection)

    merged_ids = {connection.id for connection in merged_connections}
    for entry in registry_entries.values():
        config_connection = config_by_id.get(entry.id)
        if config_connection is not None:
            if config_connection.source_config_ownership == "locked":
                self.events.record_kind(
                    "source_registry_ignored_config_shadow",
                    connection_id=entry.id,
                    payload={
                        "server": entry.provider,
                        "account": entry.account,
                        "reason": "locked_config_connection_takes_precedence",
                    },
                )
            continue
        if entry.id not in merged_ids:
            merged_connections.append(registry_entry_to_connection_config(entry))

    connections = merged_connections
```

Important notes:

- `locked` keeps current behavior.
- `seed` with no store entry writes a store entry, then uses that store entry.
- `seed` with an existing store entry uses the store entry, not config.
- Registry-only entries still hydrate as before.

- [ ] **Step 3: Add locked behavior regression test**

In `tests/wf_mcp/service/test_connection_service.py`, keep or add:

```python
def test_connection_service_sync_locked_config_shadows_registry_entry() -> None:
    service = ConnectionService(events=BrokerEventRecorder(EventBus()))
    catalog = _source_catalog(service)
    store = FileSourceRegistryStore(local_temp_root() / "locked_shadow")
    store.save_registry(
        SourceRegistryFile(
            sources=[
                _registry_entry(
                    "demo.default",
                    provider="registry",
                    account="stored",
                )
            ]
        )
    )
    config = BrokerConfig(
        store_root=local_temp_root(),
        connections=[
            ConnectionConfig(
                id="demo.default",
                server="config",
                account="locked",
                source_config_ownership="locked",
            )
        ],
    )

    service.bind_source_catalog(catalog)
    service.sync_connections_from_config(config, source_registry_store=store)

    connection = service.get("demo.default")
    assert connection.server == "config"
    assert connection.account == "locked"
    assert any(
        event.kind == "source_registry_ignored_config_shadow"
        for event in service.events.list_events()
    )
```

Use existing helpers if names differ.

- [ ] **Step 4: Add seed materialization test**

```python
def test_connection_service_sync_seed_config_materializes_registry_entry() -> None:
    service = ConnectionService(events=BrokerEventRecorder(EventBus()))
    catalog = _source_catalog(service)
    store_root = local_temp_root() / "seed_materialized"
    store = FileSourceRegistryStore(store_root)
    config = BrokerConfig(
        store_root=local_temp_root(),
        connections=[
            ConnectionConfig(
                id="demo.default",
                server="demo",
                account="default",
                metadata={"transport": {"kind": "stdio", "command": "demo-server"}},
                source_config_ownership="seed",
            )
        ],
    )

    service.bind_source_catalog(catalog)
    service.sync_connections_from_config(config, source_registry_store=store)

    registry = store.load_registry()
    assert registry.sources[0].id == "demo.default"
    assert registry.sources[0].provider == "demo"
    assert service.get("demo.default").metadata["source_registry"] is True
    assert any(
        event.kind == "source_registry_seeded_from_config"
        for event in service.events.list_events()
    )
```

- [ ] **Step 5: Add seed existing-store-wins test**

```python
def test_connection_service_sync_seed_existing_registry_entry_wins() -> None:
    service = ConnectionService(events=BrokerEventRecorder(EventBus()))
    catalog = _source_catalog(service)
    store = FileSourceRegistryStore(local_temp_root() / "seed_existing")
    store.save_registry(
        SourceRegistryFile(
            sources=[
                _registry_entry(
                    "demo.default",
                    provider="registry",
                    account="stored",
                )
            ]
        )
    )
    config = BrokerConfig(
        store_root=local_temp_root(),
        connections=[
            ConnectionConfig(
                id="demo.default",
                server="config",
                account="seed",
                metadata={"transport": {"kind": "stdio", "command": "config-server"}},
                source_config_ownership="seed",
            )
        ],
    )

    service.bind_source_catalog(catalog)
    service.sync_connections_from_config(config, source_registry_store=store)

    connection = service.get("demo.default")
    assert connection.server == "registry"
    assert connection.account == "stored"
```

- [ ] **Step 6: Run connection-service tests**

Run:

```bash
uv run pytest tests/wf_mcp/service/test_connection_service.py -q
```

Expected: all tests pass.

---

### Task 4: Update Registry Mutation Shadow Checks

**Files:**
- Modify: `src/wf_mcp/broker/service/source_registry_admin.py`
- Test: `tests/wf_mcp/service/test_source_registry_admin.py`

- [ ] **Step 1: Add config ownership lookup helper**

In `SourceRegistryAdminProvider`, add:

```python
def _config_connection(self, source_id: str) -> ConnectionConfig | None:
    for connection in self.config_connections:
        if connection.id == source_id:
            return connection
    return None
```

- [ ] **Step 2: Change `config_source_ids` if needed**

Keep `config_source_ids()` unchanged for read payload compatibility:

```python
def config_source_ids(self) -> set[str]:
    return {connection.id for connection in self.config_connections}
```

- [ ] **Step 3: Update `add_registry_entry` shadow rejection**

Replace the current config id check with:

```python
config_connection = self._config_connection(source_id)
if (
    config_connection is not None
    and config_connection.source_config_ownership == "locked"
):
    raise ValueError(
        f"cannot add {source_id!r}: id is locked by a config connection"
    )
```

For `seed`, adding remains allowed only if no registry entry already exists.

- [ ] **Step 4: Add locked add rejection test**

In `tests/wf_mcp/service/test_source_registry_admin.py`, add:

```python
def test_add_rejects_locked_config_shadow(tmp_path: Path) -> None:
    provider = _provider(tmp_path, config_ids=frozenset({"github.work"}))

    with pytest.raises(ValueError, match="locked by a config connection"):
        provider.add_registry_entry(_entry_dict("github.work"))
```

If `_provider` cannot pass policy, update it to build `ConnectionConfig(..., source_config_ownership="locked")`.

- [ ] **Step 5: Add seed add allowed test**

Update `_provider` to accept config connections or config policy, then add:

```python
def test_add_allows_seed_config_shadow_when_registry_missing(tmp_path: Path) -> None:
    provider = _provider(
        tmp_path,
        config_connections=[
            ConnectionConfig(
                id="github.work",
                server="github",
                account="work",
                source_config_ownership="seed",
            )
        ],
    )

    result = provider.add_registry_entry(_entry_dict("github.work"))

    assert result.id == "github.work"
```

- [ ] **Step 6: Run source registry admin tests**

Run:

```bash
uv run pytest tests/wf_mcp/service/test_source_registry_admin.py -q
```

Expected: all tests pass.

---

### Task 5: Expose Ownership in Admin Registry Payloads

**Files:**
- Modify: `src/wf_api/source_registry_admin.py`
- Modify: `src/wf_mcp/broker/service/source_registry_admin.py`
- Test: `tests/wf_api/test_source_registry_admin_api.py`
- Test: `tests/wf_mcp/service/test_source_registry_admin.py`

- [ ] **Step 1: Extend provider protocol**

In `WorkflowSourceRegistryProvider`, add:

```python
def config_source_ownership(self) -> Mapping[str, str]: ...
```

- [ ] **Step 2: Implement provider method**

In `SourceRegistryAdminProvider`, add:

```python
def config_source_ownership(self) -> dict[str, str]:
    return {
        connection.id: connection.source_config_ownership
        for connection in self.config_connections
    }
```

- [ ] **Step 3: Include ownership in summary and inspect payloads**

In `WorkflowSourceRegistryApi`, compute:

```python
ownership = self._provider.config_source_ownership()
```

Update `_entry_summary` signature to accept `ownership: Mapping[str, str]`.

Include:

```python
"config_ownership": ownership.get(entry_id),
"mutable": ownership.get(entry_id) != "locked",
```

For inspect payloads, include the same fields at top level:

```python
"config_ownership": ownership.get(source_id),
"mutable": ownership.get(source_id) != "locked",
```

Keep existing `shadowed_by_config` for compatibility.

- [ ] **Step 4: Update fake providers in tests**

In `tests/wf_api/test_source_registry_admin_api.py`, add:

```python
def config_source_ownership(self) -> dict[str, str]:
    return {source_id: "locked" for source_id in self._config_ids}
```

or allow the fake to accept an ownership mapping.

- [ ] **Step 5: Add API payload test**

```python
def test_list_registry_entries_reports_config_ownership_and_mutability() -> None:
    api = WorkflowSourceRegistryApi(
        provider=FakeRegistryProvider(
            [FakeRegistryEntry(id="github.work")],
            config_ids={"github.work"},
        )
    )

    payload = asyncio.run(api.list_registry_entries())

    entry = payload["entries"][0]
    assert entry["shadowed_by_config"] is True
    assert entry["config_ownership"] == "locked"
    assert entry["mutable"] is False
```

- [ ] **Step 6: Run API/provider tests**

Run:

```bash
uv run pytest tests/wf_api/test_source_registry_admin_api.py tests/wf_mcp/service/test_source_registry_admin.py -q
```

Expected: all tests pass.

---

### Task 6: Update Docs and Roadmap Status

**Files:**
- Modify: `docs/superpowers/specs/2026-06-03-store-backed-source-registry-design.md`
- Modify: `docs/superpowers/plans/2026-06-03-source-registry-next-slices.md`
- Modify: `docs/current_roadmap.md`

- [ ] **Step 1: Update spec Slice 6 status**

In `docs/superpowers/specs/2026-06-03-store-backed-source-registry-design.md`, change Slice 6 status from planned to complete and summarize:

```markdown
Status: complete. MCP broker config connections now support
`source_config_ownership="locked" | "seed"`. `locked` preserves v1 shadowing.
`seed` materializes missing store entries and lets existing registry entries
own future runtime state.
```

- [ ] **Step 2: Update next-slices plan**

In `docs/superpowers/plans/2026-06-03-source-registry-next-slices.md`, mark Slice 6 complete.

- [ ] **Step 3: Update current roadmap**

In `docs/current_roadmap.md`, replace the planned wording with implemented wording:

```markdown
Config ownership policy is implemented for MCP broker config connections:
`locked` entries stay operator-owned, while `seed` entries bootstrap missing
store entries and then let the store own later admin changes.
```

- [ ] **Step 4: Run doc diff check**

Run:

```bash
git diff -- docs/superpowers/specs/2026-06-03-store-backed-source-registry-design.md docs/superpowers/plans/2026-06-03-source-registry-next-slices.md docs/current_roadmap.md
```

Expected: docs match the implemented slice and do not claim neutral `wf_config.server.sources` supports MCP source ownership yet.

---

## Final Verification

Run:

```bash
uv run pytest tests/wf_mcp/test_source_registry.py tests/wf_mcp/service/test_connection_service.py tests/wf_mcp/service/test_source_registry_admin.py tests/wf_api/test_source_registry_admin_api.py -q
uv run ruff check src/wf_mcp/models.py src/wf_mcp/control.py src/wf_mcp/source_registry.py src/wf_mcp/broker/service/connection_service.py src/wf_mcp/broker/service/source_registry_admin.py src/wf_api/source_registry_admin.py tests/wf_mcp/test_source_registry.py tests/wf_mcp/service/test_connection_service.py tests/wf_mcp/service/test_source_registry_admin.py tests/wf_api/test_source_registry_admin_api.py
uv run basedpyright --level error src/wf_mcp/models.py src/wf_mcp/control.py src/wf_mcp/source_registry.py src/wf_mcp/broker/service/connection_service.py src/wf_mcp/broker/service/source_registry_admin.py src/wf_api/source_registry_admin.py tests/wf_mcp/test_source_registry.py tests/wf_mcp/service/test_connection_service.py tests/wf_mcp/service/test_source_registry_admin.py tests/wf_api/test_source_registry_admin_api.py
git diff --check
```

Expected: pytest exits 0, ruff exits 0, basedpyright exits 0, and `git diff --check` reports no whitespace errors.

## Self-Review

- This plan intentionally keeps `locked` as the default for backward compatibility.
- This plan does not add MCP source entries to neutral `wf_config` because current neutral source config only supports built-in sources.
- This plan requires `seed` config connections to carry `metadata.transport`; without transport, the config cannot be materialized into a durable registry entry.
- The admin payload adds `config_ownership` and `mutable` without removing `shadowed_by_config`, preserving compatibility.
