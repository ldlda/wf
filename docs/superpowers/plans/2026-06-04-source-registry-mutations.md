# Source Registry Mutations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add safe source registry mutation operations so server-owned MCP sources can be added, updated, enabled, disabled, and removed without editing config files by hand.

**Architecture:** Mutations target only the persisted desired registry, never config files. `wf_api` stays protocol-neutral by accepting/returning registry entry dictionaries. The MCP provider owns validation through `McpSourceRegistryEntry` / `SourceRegistryFile` and persistence through `SourceRegistryStore`. Runtime hydration still happens through the existing startup/reload merge path.

**Tech Stack:** Python 3.14, Pydantic v2, `wf_api.source_registry_admin`, `wf_mcp.source_registry`, `wf_transport_rpc_http`, `wf_cli`, Typer, pytest, ruff, basedpyright.

---

## Scope

Add these operations:

- add source registry entry
- update source registry entry
- enable source registry entry
- disable source registry entry
- remove source registry entry

Out of scope:

- no auth record creation/deletion
- no catalog snapshot deletion
- no config file mutation
- no live transport validation by default
- no raw proxy remount behavior changes

---

## Semantics

### Config Shadowing

Config-defined connections still win over registry entries during startup/reload.

For mutation v1:

- `add` rejects a source id that already exists in config to avoid silently adding a registry entry with no runtime effect.
- `update`, `enable`, `disable`, and `remove` may operate on existing registry entries even if they are currently shadowed by config.
- A future `allow_shadow` flag can relax `add`; do not add it in this slice.

Rationale: `add` rejects config-shadowed ids to prevent silent no-ops: adding a
registry entry that cannot activate while config owns the same id. Existing
shadowed registry entries can still be updated, enabled, disabled, or removed so
operators can prepare store state for config removal or future `seed` ownership
policy.

### Full-Registry Validation

Every mutation must:

1. load the current registry
2. build a new `SourceRegistryFile`
3. validate the full file
4. save one atomic replacement
5. return the updated entry or removal payload

Never mutate the loaded registry object in-place and then save after partial validation. Build a new list first.

### Events

Mutations should emit events if an event recorder is available:

- `source_registry_entry_added`
- `source_registry_entry_updated`
- `source_registry_entry_enabled`
- `source_registry_entry_disabled`
- `source_registry_entry_removed`

Payload should include at least:

```json
{"source_id": "github.work", "provider": "github", "account": "work"}
```

If adding event wiring is awkward for this slice, keep mutation payloads correct and document event wiring as future work. Do not block mutation safety on event polish.

---

## Task 1: Extend Neutral API Provider Protocol

- [ ] Update `src/wf_api/source_registry_admin.py`.
- [ ] Add mutation methods to `WorkflowSourceRegistryProvider`:

```python
def add_registry_entry(self, entry: Mapping[str, Any]) -> Mapping[str, Any] | object: ...

def update_registry_entry(
    self,
    source_id: str,
    patch: Mapping[str, Any],
) -> Mapping[str, Any] | object: ...

def set_registry_entry_enabled(
    self,
    source_id: str,
    enabled: bool,
) -> Mapping[str, Any] | object: ...

def remove_registry_entry(self, source_id: str) -> Mapping[str, Any] | object: ...
```

- [ ] Add async API methods:

```python
async def add_registry_entry(self, *, entry: dict[str, Any]) -> dict[str, Any]: ...

async def update_registry_entry(
    self,
    *,
    source_id: str,
    patch: dict[str, Any],
) -> dict[str, Any]: ...

async def enable_registry_entry(self, *, source_id: str) -> dict[str, Any]: ...

async def disable_registry_entry(self, *, source_id: str) -> dict[str, Any]: ...

async def remove_registry_entry(self, *, source_id: str) -> dict[str, Any]: ...
```

- [ ] Return shapes:

```python
{"entry": <full entry>, "shadowed_by_config": bool}
{"removed": true, "source_id": "..."}
```

- [ ] Reuse existing `_payload()` and shadow helper logic.
- [ ] Update `WorkflowSourceRegistrySurface` in `src/wf_api/surface.py`.

### Tests

- [ ] Extend `tests/wf_api/test_source_registry_admin_api.py`.
- [ ] Add fake mutable provider.
- [ ] Test each API method delegates and returns normalized payloads.
- [ ] Test remove payload.

---

## Task 2: Implement MCP Mutation Provider

- [ ] Update `src/wf_mcp/broker/service/source_registry_admin.py`.
- [ ] Keep `SourceRegistryAdminProvider` as the read/write provider.
- [ ] Add optional event sink if practical:

```python
from collections.abc import Callable
from ...events import McpEvent

event_sink: Callable[[McpEvent], None] | None = None
```

If this creates too much coupling, skip event sink and document it.

- [ ] Add helpers:

```python
def _load(self) -> SourceRegistryFile: ...
def _save(self, sources: list[McpSourceRegistryEntry]) -> SourceRegistryFile: ...
def _entry_map(self, registry: SourceRegistryFile) -> dict[str, McpSourceRegistryEntry]: ...
def _require_entry(self, source_id: str) -> McpSourceRegistryEntry: ...
```

- [ ] `add_registry_entry(entry)`:
  - reject if `entry["id"]` is in `config_source_ids()`
  - validate with `McpSourceRegistryEntry.model_validate(entry)`
  - reject duplicate existing registry id
  - save full `SourceRegistryFile`
  - return added entry

- [ ] `update_registry_entry(source_id, patch)`:
  - require existing registry entry
  - reject changing `id` in v1 unless it equals `source_id`
  - merge existing full JSON entry with patch
  - validate with `McpSourceRegistryEntry`
  - save full file
  - return updated entry

- [ ] `set_registry_entry_enabled(source_id, enabled)`:
  - require existing registry entry
  - update `enabled`
  - save full file
  - return updated entry

- [ ] `remove_registry_entry(source_id)`:
  - require existing registry entry
  - save full file without the entry
  - return `{"removed": True, "source_id": source_id}`
  - do not delete auth/catalog

### Tests

- [ ] Extend or create tests in `tests/wf_mcp/service/test_source_registry_admin.py`.
- [ ] Test add persists and round-trips through store.
- [ ] Test add rejects config-shadowed id.
- [ ] Test add rejects duplicate registry id.
- [ ] Test update persists provider/account/transport changes.
- [ ] Test update rejects id change.
- [ ] Test enable/disable persist.
- [ ] Test remove persists absence and does not touch unrelated entries.
- [ ] Test missing source raises clear `KeyError`.
- [ ] Test malformed payload raises validation error with actionable message.

---

## Task 3: Add RPC Mutation Methods

- [ ] Update `src/wf_transport_rpc_http/models.py`.
- [ ] Add params:

```python
class AddRegistryEntryParams(RpcParamsModel):
    entry: dict[str, Any]


class UpdateRegistryEntryParams(RpcParamsModel):
    source_id: str = Field(min_length=1)
    patch: dict[str, Any]


class RegistryEntryIdParams(RpcParamsModel):
    source_id: str = Field(min_length=1)
```

- [ ] Update `src/wf_transport_rpc_http/methods_source_registry.py`.
- [ ] Register:

```text
workflow.admin.source_registry.add
workflow.admin.source_registry.update
workflow.admin.source_registry.enable
workflow.admin.source_registry.disable
workflow.admin.source_registry.remove
```

- [ ] Keep unavailable behavior identical to read methods:

```json
{"code": "source_registry_unavailable", ...}
```

- [ ] Use `Params(...)` for required params, matching inspect methods.
- [ ] Update `src/wf_transport_rpc_http/client_source_registry.py`.
- [ ] Add matching client methods.

### Tests

- [ ] Extend `tests/wf_transport_rpc_http/test_source_registry_rpc.py`.
- [ ] Add positive method tests using a fake `WorkflowServer` with `WorkflowSourceRegistryApi`.
- [ ] Add unavailable mutation test on local/static server.
- [ ] Add client method tests for method names and payloads.

---

## Task 4: Add CLI Mutation Commands

- [ ] Update `src/wf_cli/commands/source_registry.py`.
- [ ] Add commands:

```bash
wf admin registry add --input '{"id":"github.work",...}'
wf admin registry update SOURCE_ID --patch '{"enabled":false}'
wf admin registry enable SOURCE_ID
wf admin registry disable SOURCE_ID
wf admin registry remove SOURCE_ID
```

- [ ] Support `--input-file` for add and `--patch-file` for update if existing CLI helpers make it easy.
- [ ] JSON inline input is required for v1. Do not design a large flag matrix for every MCP field yet.
- [ ] For remove, require `--confirm` to avoid accidental deletion:

```bash
wf admin registry remove github.work --confirm
```

- [ ] If `source_registry_admin is None`, keep the existing "not available" behavior.

### Tests

- [ ] Extend `tests/wf_cli/test_source_registry.py`.
- [ ] Test help includes add/update/enable/disable/remove.
- [ ] Test local/static unavailable for one mutation command.
- [ ] Test remove without `--confirm` fails.
- [ ] Test commands delegate to a fake context where possible, or use RPC client monkeypatch patterns already used in CLI tests.

---

## Task 5: Wire Real MCP Server Provider If Available

Current state: `WorkflowServer.source_registry_admin` exists, but local/static servers set it to `None`. There may still be no concrete MCP-backed `WorkflowServer` construction path.

- [ ] If a concrete MCP-backed `WorkflowServer` construction path exists, wire:

```python
WorkflowSourceRegistryApi(
    provider=SourceRegistryAdminProvider(
        source_registry_store=FileSourceRegistryStore(config.store_root),
        config_connections=config.connections,
    )
)
```

- [ ] If no such path exists, do not invent it in this slice. Keep docs explicit that RPC/CLI mutation methods require a target exposing `source_registry_admin`.

---

## Task 6: Docs

- [ ] Update `docs/current_roadmap.md`.
- [ ] Update `docs/superpowers/specs/2026-06-03-store-backed-source-registry-design.md`.
- [ ] Update `docs/superpowers/plans/2026-06-03-source-registry-next-slices.md`.
- [ ] Document:
  - registry mutations change desired state only
  - config files are not mutated
  - auth/catalog are not deleted on remove
  - startup/reload is still how runtime hydration sees changes
  - config-shadowed add is rejected in v1

---

## Task 7: Verify

- [ ] Focused API/provider tests:

```bash
uv run pytest tests/wf_api/test_source_registry_admin_api.py tests/wf_mcp/service/test_source_registry_admin.py -q
```

- [ ] RPC/CLI tests:

```bash
uv run pytest tests/wf_transport_rpc_http/test_source_registry_rpc.py tests/wf_cli/test_source_registry.py -q
```

- [ ] Existing registry/startup tests:

```bash
uv run pytest tests/wf_api/test_source_registry.py tests/wf_mcp/test_source_registry.py tests/wf_mcp/service/test_connection_service.py tests/wf_mcp/test_broker_server.py -q
```

- [ ] Quality:

```bash
uv run ruff check src/wf_api/source_registry_admin.py src/wf_mcp/broker/service/source_registry_admin.py src/wf_transport_rpc_http src/wf_cli tests/wf_api/test_source_registry_admin_api.py tests/wf_mcp/service/test_source_registry_admin.py tests/wf_transport_rpc_http/test_source_registry_rpc.py tests/wf_cli/test_source_registry.py
uv run basedpyright --level error src/wf_api/source_registry_admin.py src/wf_mcp/broker/service/source_registry_admin.py src/wf_transport_rpc_http src/wf_cli tests/wf_api/test_source_registry_admin_api.py tests/wf_mcp/service/test_source_registry_admin.py tests/wf_transport_rpc_http/test_source_registry_rpc.py tests/wf_cli/test_source_registry.py
```

---

## Acceptance Criteria

- Registry add/update/enable/disable/remove work through neutral API methods.
- MCP provider validates all writes through `McpSourceRegistryEntry` / `SourceRegistryFile`.
- Whole registry is validated before every save.
- Config files are not mutated.
- Auth/catalog files are not deleted.
- Adding an id owned by config is rejected in v1.
- Existing shadowed registry entries can still be updated or removed.
- RPC methods and CLI commands exist.
- Remove requires explicit CLI confirmation.
- Observed source inventory behavior is unchanged until reload/startup rehydrates runtime state.
