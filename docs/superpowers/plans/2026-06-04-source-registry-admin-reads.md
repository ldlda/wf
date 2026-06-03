# Source Registry Admin Reads Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose the persisted desired source registry through read-only admin APIs, JSON-RPC, and CLI without confusing it with observed runtime source inventory.

**Architecture:** Desired registry state is server/platform configuration. It is not workflow lifecycle state and not observed catalog/source inventory. Add a neutral read-only `WorkflowSourceRegistryApi` over a provider protocol in `wf_api`; implement the provider in `wf_mcp` using `FileSourceRegistryStore` and optional config connection ids for shadow information. Keep mutations out of scope.

**Tech Stack:** Python 3.14, Pydantic v2, `wf_api`, `wf_mcp.source_registry`, `wf_transport_rpc_http`, `wf_cli`, Typer, pytest, ruff, basedpyright.

---

## Naming Decision

Use admin/config naming:

- JSON-RPC:
  - `workflow.admin.source_registry.list`
  - `workflow.admin.source_registry.inspect`
- CLI:
  - `wf admin registry list`
  - `wf admin registry inspect SOURCE_ID`

Do **not** use `wf source registry ...` in this slice. `wf source list` already means observed/hydrated source inventory. Registry reads are desired server-owned configuration state.

---

## Payload Shape

List payload:

```json
{
  "entries": [
    {
      "id": "github.work",
      "kind": "mcp",
      "enabled": true,
      "provider": "github",
      "account": "work",
      "profile": null,
      "transport_kind": "stdio",
      "auth_ref": "github.work",
      "shadowed_by_config": false
    }
  ],
  "next_cursor": null,
  "total": 1
}
```

Inspect payload:

```json
{
  "entry": {
    "id": "github.work",
    "kind": "mcp",
    "enabled": true,
    "provider": "github",
    "account": "work",
    "profile": null,
    "transport": {"kind": "stdio", "command": "npx", "args": [], "env": {}},
    "auth_ref": "github.work",
    "metadata": {}
  },
  "shadowed_by_config": false
}
```

Notes:

- List returns summaries; inspect returns full entry detail.
- `shadowed_by_config` is advisory. If a caller has no config provider, return
  `false` rather than guessing.
- Do not include auth secret payloads. `auth_ref` is only an id/reference.

---

## Task 1: Add Neutral Source Registry Admin API

- [ ] Create `src/wf_api/source_registry_admin.py`.
- [ ] Define:

```python
from __future__ import annotations

from collections.abc import Mapping, Sequence, Set
from dataclasses import asdict, is_dataclass
from typing import Any, Protocol

from wf_platform import page_items


class WorkflowSourceRegistryProvider(Protocol):
    """Provides desired source registry state for read-only admin frontends."""

    def list_registry_entries(self) -> Sequence[Mapping[str, Any] | object]: ...

    def config_source_ids(self) -> Set[str]: ...
```

- [ ] Define `WorkflowSourceRegistryApi` with:

```python
async def list_registry_entries(
    self,
    *,
    cursor: str | None = None,
    limit: int = 50,
) -> dict[str, Any]: ...

async def inspect_registry_entry(self, *, source_id: str) -> dict[str, Any]: ...
```

- [ ] Normalize provider objects using the same style as `wf_api.admin._payload`:
  mapping, dataclass, or Pydantic `model_dump(mode="json")`.
- [ ] Add helpers:

```python
def _entry_summary(entry: dict[str, Any], shadowed_ids: set[str]) -> dict[str, Any]:
    transport = entry.get("transport")
    transport_kind = transport.get("kind") if isinstance(transport, Mapping) else None
    return {
        "id": entry["id"],
        "kind": entry["kind"],
        "enabled": entry["enabled"],
        "provider": entry.get("provider"),
        "account": entry.get("account"),
        "profile": entry.get("profile"),
        "transport_kind": transport_kind,
        "auth_ref": entry.get("auth_ref"),
        "shadowed_by_config": entry["id"] in shadowed_ids,
    }
```

- [ ] `inspect_registry_entry()` should raise `KeyError(f"unknown registry source {source_id!r}")` when missing.
- [ ] Export `WorkflowSourceRegistryApi` and `WorkflowSourceRegistryProvider` from `src/wf_api/__init__.py`.
- [ ] Add `WorkflowSourceRegistrySurface` to `src/wf_api/surface.py` and `__all__`.

### Tests

- [ ] Create `tests/wf_api/test_source_registry_admin_api.py`.
- [ ] Test list returns compact summaries in id order.
- [ ] Test pagination.
- [ ] Test inspect returns full entry and shadow flag.
- [ ] Test unknown inspect raises clear `KeyError`.
- [ ] Test the concrete API satisfies `WorkflowSourceRegistrySurface`.

---

## Task 2: Add MCP Provider for Registry Reads

- [ ] Create `src/wf_mcp/broker/service/source_registry_admin.py`.
- [ ] Define:

```python
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from ...models import ConnectionConfig
from ...source_registry import SourceRegistryStore


@dataclass(slots=True)
class SourceRegistryAdminProvider:
    """Read desired MCP source registry state without mutating it."""

    source_registry_store: SourceRegistryStore
    config_connections: Sequence[ConnectionConfig] = field(default_factory=tuple)

    def list_registry_entries(self) -> list[object]:
        return list(self.source_registry_store.load_registry().sources)

    def config_source_ids(self) -> set[str]:
        return {connection.id for connection in self.config_connections}
```

- [ ] Keep this provider read-only.
- [ ] Do not load auth records or catalog snapshots here.

### Tests

- [ ] Create `tests/wf_mcp/service/test_source_registry_admin.py`.
- [ ] Test provider lists entries from `FileSourceRegistryStore`.
- [ ] Test provider reports config-shadowed ids.

---

## Task 3: Wire Server Context

- [ ] Update `src/wf_server/context.py`.
- [ ] Add a nullable `source_registry_admin` field to `WorkflowServer`:

```python
source_registry_admin: WorkflowSourceRegistryApi | None = None
```

- [ ] For the local/static server builder, leave it as `None`. Local/static server has no file-backed MCP source registry.
- [ ] This field is used by JSON-RPC registration; missing support should return a structured RPC error.

### Tests

- [ ] Update `tests/wf_server/test_local_static_server.py` if needed to assert local/static construction still works.

---

## Task 4: Wire MCP/CLI Server Construction

- [ ] Identify the current `WorkflowServer` construction path for JSON-RPC HTTP target servers.
- [ ] When constructing a server from broker config, create:

```python
source_registry_admin = WorkflowSourceRegistryApi(
    SourceRegistryAdminProvider(
        source_registry_store=FileSourceRegistryStore(config.store_root),
        config_connections=config.connections,
    )
)
```

- [ ] Attach it to `WorkflowServer`.
- [ ] Do not alter source registry startup merge behavior in this slice.

### Tests

- [ ] Add or update a JSON-RPC server construction test that seeds `source_registry.json` and asserts `server.source_registry_admin` is not `None`.

---

## Task 5: Add JSON-RPC Methods and Client Mixin

- [ ] Add `src/wf_transport_rpc_http/methods_source_registry.py`.
- [ ] Register:

```python
workflow.admin.source_registry.list
workflow.admin.source_registry.inspect
```

- [ ] If `server.source_registry_admin is None`, raise `WorkflowRpcError` with:

```json
{
  "code": "source_registry_unavailable",
  "message": "source registry admin reads are not available for this server"
}
```

- [ ] Add `src/wf_transport_rpc_http/client_source_registry.py`.
- [ ] Add `RpcSourceRegistryClientMixin` with:

```python
async def list_registry_entries(self, *, cursor: str | None = None, limit: int = 50) -> dict[str, Any]: ...

async def inspect_registry_entry(self, *, source_id: str) -> dict[str, Any]: ...
```

- [ ] Include the mixin in `src/wf_transport_rpc_http/client.py`.
- [ ] Register methods in `src/wf_transport_rpc_http/app.py`.

### Tests

- [ ] Add focused JSON-RPC method tests.
- [ ] Add client tests proving the mixin calls the correct method names.
- [ ] Add a local/static unavailable test.

---

## Task 6: Add CLI Commands

- [ ] Add `src/wf_cli/commands/source_registry.py`.
- [ ] Register it under the existing `wf admin` app:

```bash
wf admin registry list
wf admin registry inspect SOURCE_ID
```

- [ ] Use the target-aware CLI context, not local-only context.
- [ ] Output JSON by default, following existing CLI command conventions.
- [ ] Do not add mutation flags.

### Tests

- [ ] Add CLI tests:
  - local/server target lists entries
  - inspect returns full entry
  - missing entry exits nonzero or returns structured error, matching current CLI patterns

---

## Task 7: Docs

- [ ] Update `docs/current_roadmap.md`.
- [ ] Update `docs/superpowers/specs/2026-06-03-store-backed-source-registry-design.md`.
- [ ] Update `docs/superpowers/plans/2026-06-03-source-registry-next-slices.md`.
- [ ] Add a short note to CLI docs if there is a current CLI command reference:

```md
`wf admin registry list` shows desired persisted registry entries. `wf source list`
shows observed/hydrated source inventory. Use both when debugging disabled,
shadowed, or not-yet-hydrated sources.
```

---

## Task 8: Verify

- [ ] Focused tests:

```bash
uv run pytest tests/wf_api/test_source_registry_admin_api.py tests/wf_mcp/service/test_source_registry_admin.py -q
```

- [ ] RPC/CLI tests:

```bash
uv run pytest tests/wf_transport_rpc_http tests/wf_cli -q
```

- [ ] Existing source registry tests:

```bash
uv run pytest tests/wf_api/test_source_registry.py tests/wf_mcp/test_source_registry.py -q
```

- [ ] Quality:

```bash
uv run ruff check src/wf_api src/wf_mcp src/wf_transport_rpc_http src/wf_cli tests/wf_api tests/wf_mcp tests/wf_transport_rpc_http tests/wf_cli
uv run basedpyright --level error src/wf_api src/wf_mcp src/wf_transport_rpc_http src/wf_cli tests/wf_api tests/wf_mcp tests/wf_transport_rpc_http tests/wf_cli
```

---

## Acceptance Criteria

- Desired registry reads are available separately from observed source inventory.
- List is compact and paginated.
- Inspect returns full persisted entry details.
- Shadowed-by-config status is visible.
- Local/static servers report registry reads unavailable instead of pretending to have an empty registry.
- No mutation commands are added.
- `wf source list` behavior is unchanged.
