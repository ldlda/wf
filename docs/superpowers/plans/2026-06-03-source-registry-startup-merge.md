# Source Registry Startup Merge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Load persisted dynamic MCP source registry entries during broker/server construction and merge them with config-defined connections without changing behavior when the registry file is absent.

**Architecture:** Keep parsing/loading config separate from runtime hydration. `wf_mcp.source_registry` owns MCP registry entries and conversion to `ConnectionConfig`; `ConnectionService` owns connection reconciliation and source-catalog hydration; `build_service_from_config()` wires the default file store from `BrokerConfig.store_root`.

**Tech Stack:** Python 3.14, dataclasses, Pydantic v2, `wf_mcp.source_registry`, `ConnectionService`, `WfMcpService`, `build_service_from_config`, pytest, ruff, basedpyright.

---

## Preconditions

Completed before this plan:

- Generic registry mechanics exist in `wf_api.source_registry`.
- MCP-specific registry models remain in `wf_mcp.source_registry`.
- `registry_entry_to_connection_config()` exists and is tested.
- No startup/runtime merge uses the registry yet.

## Merge Rules

1. Config-defined connections win over registry entries with the same id.
2. Registry entries fill ids not present in config.
3. Reserved ids remain rejected by existing `ConnectionService` validation.
4. Shadowed registry entries must be visible through an event/diagnostic, not silently ignored.
5. Missing `source_registry.json` must preserve current config-only behavior.

Do not mutate config files. Do not delete auth/catalog files.

---

## Task 1: Add Merge Helper Tests First

- [ ] Add focused tests in `tests/wf_mcp/service/test_connection_service.py`.
- [ ] Import:

```python
from wf_mcp.source_registry import (
    FileSourceRegistryStore,
    McpSourceRegistryEntry,
    SourceRegistryFile,
    StdioSourceTransport,
)
```

- [ ] Add helper:

```python
def _registry_entry(
    source_id: str = "demo.registry",
    *,
    enabled: bool = True,
) -> McpSourceRegistryEntry:
    return McpSourceRegistryEntry(
        id=source_id,
        kind="mcp",
        enabled=enabled,
        provider="demo",
        account=source_id.rsplit(".", 1)[-1],
        transport=StdioSourceTransport(command="demo-server"),
    )
```

- [ ] Add `test_connection_service_sync_merges_registry_entries`.

Expected behavior:

```python
store = FileSourceRegistryStore(tmp_path)
store.save_registry(SourceRegistryFile(sources=[_registry_entry()]))

service.sync_connections_from_config(
    BrokerConfig(store_root=tmp_path, connections=[]),
    source_registry_store=store,
)

assert [connection.id for connection in service.list_all()] == ["demo.registry"]
assert "demo.registry" in catalog.capability_sources
```

- [ ] Add `test_connection_service_sync_config_shadows_registry_entry`.

Expected behavior:

```python
store.save_registry(SourceRegistryFile(sources=[_registry_entry("demo.same")]))
service.sync_connections_from_config(
    BrokerConfig(
        store_root=tmp_path,
        connections=[
            ConnectionConfig(id="demo.same", server="demo", account="config"),
        ],
    ),
    source_registry_store=store,
)

assert service.get("demo.same").account == "config"
assert service.events.list_events()[-1].kind == "source_registry_ignored_config_shadow"
assert service.events.list_events()[-1].connection_id == "demo.same"
```

- [ ] Add `test_connection_service_sync_registry_disabled_entry_hydrates_disabled_source`.

Expected behavior:

```python
store.save_registry(SourceRegistryFile(sources=[_registry_entry(enabled=False)]))
service.sync_connections_from_config(
    BrokerConfig(store_root=tmp_path, connections=[]),
    source_registry_store=store,
)

assert service.get("demo.registry").enabled is False
assert catalog.capability_sources["demo.registry"].enabled is False
```

- [ ] Run:

```bash
uv run pytest tests/wf_mcp/service/test_connection_service.py -q
```

Expected: new tests fail until Task 2.

---

## Task 2: Implement Registry-Aware Connection Reconciliation

- [ ] Update `src/wf_mcp/broker/service/connection_service.py`.
- [ ] Import:

```python
from ...source_registry import (
    SourceRegistryStore,
    registry_entry_to_connection_config,
)
```

- [ ] Change `sync_connections_from_config` signature:

```python
def sync_connections_from_config(
    self,
    config: BrokerConfig,
    *,
    source_registry_store: SourceRegistryStore | None = None,
) -> None:
```

- [ ] Build a merged connection list before existing remove/update/register logic:

```python
connections = list(config.connections)
config_ids = {connection.id for connection in connections}
if source_registry_store is not None:
    registry = source_registry_store.load_registry()
    for entry in registry.sources:
        if entry.id in config_ids:
            self.events.record_kind(
                "source_registry_ignored_config_shadow",
                connection_id=entry.id,
                payload={
                    "server": entry.provider,
                    "account": entry.account,
                    "reason": "config_connection_takes_precedence",
                },
            )
            continue
        connections.append(registry_entry_to_connection_config(entry))
```

- [ ] Reuse the existing reconciliation logic against the merged `connections` list.
- [ ] Keep `BrokerConfig` immutable; do not mutate `config.connections`.
- [ ] Keep existing event behavior for registered/updated/removed connections.
- [ ] Add a short comment near the merge explaining config precedence.

- [ ] Run:

```bash
uv run pytest tests/wf_mcp/service/test_connection_service.py -q
```

Expected: all connection service tests pass.

---

## Task 3: Wire WfMcpService Facade

- [ ] Update `src/wf_mcp/broker/service/core.py`.
- [ ] Import `SourceRegistryStore` from `wf_mcp.source_registry`.
- [ ] Change facade method signature:

```python
def sync_connections_from_config(
    self,
    config: BrokerConfig,
    *,
    source_registry_store: SourceRegistryStore | None = None,
) -> None:
    self.connection_service.sync_connections_from_config(
        config,
        source_registry_store=source_registry_store,
    )
```

- [ ] Add/adjust a facade test in `tests/wf_mcp/service/test_connection_service.py` proving `WfMcpService.sync_connections_from_config(..., source_registry_store=store)` delegates and hydrates a registry connection.

---

## Task 4: Wire Build From Config

- [ ] Update `src/wf_mcp/broker/config.py`.
- [ ] Import `FileSourceRegistryStore`.
- [ ] Construct the store in `build_service_from_config(config)`:

```python
source_registry_store = FileSourceRegistryStore(config.store_root)
```

- [ ] Replace the manual connection loop with one registry-aware sync call:

```python
service.sync_connections_from_config(
    config,
    source_registry_store=source_registry_store,
)
for connection in service.connections.list_all():
    if connection.server not in service.adapters:
        service.register_adapter(connection.server, McpSdkAdapter())
```

Important:

- Preserve adapter registration for config-defined and registry-defined connections.
- Do not load the registry in `load_broker_config`; it should only parse config files.
- Do not save the registry during startup.

---

## Task 5: Add Build-Service Integration Tests

- [ ] Update `tests/wf_mcp/test_broker_server.py` or `tests/wf_mcp/server/test_config.py`.
- [ ] Add `test_build_service_from_config_loads_source_registry_entries`.

Setup:

```python
config = BrokerConfig(store_root=tmp_path, connections=[])
FileSourceRegistryStore(tmp_path).save_registry(
    SourceRegistryFile(sources=[_registry_entry("fixture.registry")])
)
service = build_service_from_config(config)
```

Assertions:

```python
assert service.connections.get("fixture.registry").server == "fixture"
assert "fixture" in service.adapters
assert "fixture.registry" in service.capability_sources
```

- [ ] Add `test_build_service_from_config_config_shadows_registry`.

Assertions:

```python
assert service.connections.get("fixture.same").account == "config"
assert any(
    event.kind == "source_registry_ignored_config_shadow"
    and event.connection_id == "fixture.same"
    for event in service.list_events()
)
```

- [ ] Add `test_build_service_from_config_absent_registry_preserves_existing_behavior` if no existing test already covers this. It can extend the current `test_build_service_from_config_registers_connections`.

---

## Task 6: Update Docs

- [ ] Update `docs/superpowers/specs/2026-06-03-store-backed-source-registry-design.md`.

Mark startup merge as complete or in-progress, depending on final status:

```md
### Slice 3: Startup Merge

Status: complete. Broker/service construction now loads `source_registry.json`,
merges config-defined connections with dynamic registry entries, preserves config
precedence, and emits `source_registry_ignored_config_shadow` for shadowed
registry entries.
```

- [ ] Update `docs/current_roadmap.md`.

Replace the source-registry note with:

```md
- Source registry startup merge is implemented: absent registry preserves
  config-only behavior, registry-only entries hydrate as dynamic connections,
  and config entries shadow same-id registry entries with an event.
```

- [ ] Update `docs/superpowers/plans/2026-06-03-source-registry-next-slices.md`.

Mark Slice 2A and Slice 2B complete if not already done, and mark Slice 3 complete after implementation.

---

## Task 7: Verify

- [ ] Run focused tests:

```bash
uv run pytest tests/wf_mcp/service/test_connection_service.py tests/wf_mcp/test_broker_server.py tests/wf_mcp/server/test_config.py -q
```

- [ ] Run source registry tests:

```bash
uv run pytest tests/wf_api/test_source_registry.py tests/wf_mcp/test_source_registry.py -q
```

- [ ] Run quality checks:

```bash
uv run ruff check src/wf_mcp/source_registry.py src/wf_mcp/broker/config.py src/wf_mcp/broker/service/connection_service.py src/wf_mcp/broker/service/core.py tests/wf_mcp/service/test_connection_service.py tests/wf_mcp/test_broker_server.py tests/wf_mcp/server/test_config.py
uv run basedpyright --level error src/wf_mcp/source_registry.py src/wf_mcp/broker/config.py src/wf_mcp/broker/service/connection_service.py src/wf_mcp/broker/service/core.py tests/wf_mcp/service/test_connection_service.py tests/wf_mcp/test_broker_server.py tests/wf_mcp/server/test_config.py
```

- [ ] If focused tests pass, run the full suite if time permits:

```bash
uv run pytest -q
```

---

## Acceptance Criteria

- Missing registry file keeps existing config-only behavior.
- Registry-only entries become registered connections and hydrated source catalog entries.
- Config entries shadow same-id registry entries.
- Shadowing emits `source_registry_ignored_config_shadow`.
- Disabled registry entries hydrate disabled connection/source state.
- `load_broker_config()` remains config-only parsing.
- No registry mutation commands are added in this slice.
- `wf_api` still imports no `wf_mcp`.
