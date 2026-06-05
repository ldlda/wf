# Source Registry Apply/Reload Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an explicit `wf admin registry apply` operation so persisted source registry changes can affect the running MCP-backed `WorkflowServer` without restarting the process.

**Architecture:** Keep registry add/update/enable/disable/remove as desired-state writes only. Add a separate apply operation that mirrors the old `wf.admin.reload_config` pattern: reconcile current config plus registry store into runtime connection/source state using `ConnectionService.sync_connections_from_config(...)`. Expose the operation through `wf_api`, JSON-RPC HTTP, and CLI.

**Tech Stack:** Python 3.14, Pydantic v2, Typer, JSON-RPC HTTP transport, `wf_api.source_registry_admin`, `wf_mcp.broker.service.ConnectionService`, `FileSourceRegistryStore`, pytest, ruff, basedpyright.

---

## File Structure

- Modify `src/wf_api/source_registry_admin.py`: add an apply provider protocol and `WorkflowSourceRegistryApi.apply_registry_changes()`.
- Modify `src/wf_api/surface.py`: add `apply_registry_changes()` to `WorkflowSourceRegistrySurface`.
- Modify `src/wf_mcp/broker/service/source_registry_admin.py`: implement apply/reload logic for MCP-backed runtime state.
- Modify `src/wf_mcp/broker/server.py`: wire apply dependencies into `SourceRegistryAdminProvider`.
- Modify `src/wf_transport_rpc_http/models.py`: add empty params model if needed.
- Modify `src/wf_transport_rpc_http/methods_source_registry.py`: register `workflow.admin.source_registry.apply`.
- Modify `src/wf_transport_rpc_http/client_source_registry.py`: add RPC client method.
- Modify `src/wf_cli/commands/source_registry.py`: add `wf admin registry apply`.
- Modify tests in `tests/wf_api`, `tests/wf_mcp/service`, `tests/wf_transport_rpc_http`, and `tests/wf_cli`.
- Update `docs/current_roadmap.md` and `docs/superpowers/specs/2026-06-03-store-backed-source-registry-design.md`.

## Current Context

Registry mutation operations currently write desired state only:

```text
wf admin registry add/update/enable/disable/remove
  -> WorkflowSourceRegistryApi
  -> SourceRegistryAdminProvider
  -> FileSourceRegistryStore
```

Runtime source state is built by:

```python
service.sync_connections_from_config(
    config,
    source_registry_store=FileSourceRegistryStore(config.store_root),
)
```

The old config reload path already uses the same reconciliation hook:

```python
def sync_service(config: BrokerConfig) -> None:
    service.sync_connections_from_config(
        config,
        source_registry_store=FileSourceRegistryStore(config.store_root),
    )
```

This plan adds the registry equivalent of reload, but does not mutate config and
does not attempt proxy/FastMCP remount semantics. It updates the neutral
workflow server's runtime source/catalog state.

## Apply Semantics

`apply_registry_changes` should:

- Load the current registry from the registry store.
- Re-run `ConnectionService.sync_connections_from_config(config, source_registry_store=store)`.
- Ensure SDK adapters exist for any newly registered connection server.
- Return a compact summary:

```python
{
    "applied": True,
    "registered": ["new.source"],
    "updated": ["existing.source"],
    "removed": ["old.source"],
    "connection_count": 5,
    "registry_entry_count": 2,
}
```

Rules:

- Config `locked` entries still win over same-id registry entries.
- Config `seed` entries still yield to existing registry entries.
- Disabled registry entries should remain visible as disabled runtime sources when current reconciliation does that today; do not invent new hide/remove semantics in this slice.
- Local/static servers without registry admin still return `source_registry_unavailable`.
- No automatic apply after add/update/enable/disable/remove in v1.
- No upstream proxy remount, no long-lived subscription handling, no auth prompt flow in this slice.

## Task 1: Add API-Layer Apply Contract

**Files:**
- Modify: `src/wf_api/source_registry_admin.py`
- Modify: `src/wf_api/surface.py`
- Test: `tests/wf_api/test_source_registry_admin_api.py`

- [ ] **Step 1: Add a failing API test**

Add this test to `tests/wf_api/test_source_registry_admin_api.py`:

```python
class RecordingApplyProvider:
    def __init__(self) -> None:
        self.called = False

    def apply_registry_changes(self) -> dict[str, object]:
        self.called = True
        return {
            "applied": True,
            "registered": ["demo.new"],
            "updated": [],
            "removed": [],
            "connection_count": 1,
            "registry_entry_count": 1,
        }


async def test_apply_registry_changes_delegates_to_apply_provider() -> None:
    read_provider = _provider([])
    apply_provider = RecordingApplyProvider()
    api = WorkflowSourceRegistryApi(
        provider=read_provider,
        apply_provider=apply_provider,
    )

    payload = await api.apply_registry_changes()

    assert apply_provider.called is True
    assert payload["applied"] is True
    assert payload["registered"] == ["demo.new"]
    assert payload["connection_count"] == 1
```

Also add:

```python
async def test_apply_registry_changes_requires_apply_provider() -> None:
    api = WorkflowSourceRegistryApi(provider=_provider([]))

    with pytest.raises(TypeError, match="apply_registry_changes requires"):
        await api.apply_registry_changes()
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
uv run pytest tests/wf_api/test_source_registry_admin_api.py -q
```

Expected: fail because `WorkflowSourceRegistryApi.__init__` does not accept `apply_provider` and `apply_registry_changes` does not exist.

- [ ] **Step 3: Add provider protocol and API method**

In `src/wf_api/source_registry_admin.py`, add:

```python
@runtime_checkable
class WorkflowSourceRegistryApplyProvider(Protocol):
    """Applies desired registry state to the currently running server."""

    def apply_registry_changes(self) -> Mapping[str, Any] | object: ...
```

Change `WorkflowSourceRegistryApi.__init__` to:

```python
def __init__(
    self,
    *,
    provider: WorkflowSourceRegistryProvider,
    mutation_provider: WorkflowSourceRegistryMutationProvider | None = None,
    apply_provider: WorkflowSourceRegistryApplyProvider | None = None,
) -> None:
    self._provider = provider
    self._mutation_provider = mutation_provider
    self._apply_provider = apply_provider
```

Add:

```python
async def apply_registry_changes(self) -> dict[str, Any]:
    if self._apply_provider is None:
        raise TypeError("apply_registry_changes requires an apply provider")
    return _payload(self._apply_provider.apply_registry_changes())
```

Export `WorkflowSourceRegistryApplyProvider` from `src/wf_api/__init__.py`.

- [ ] **Step 4: Extend protocol surface**

In `src/wf_api/surface.py`, add to `WorkflowSourceRegistrySurface`:

```python
async def apply_registry_changes(self) -> dict[str, Any]: ...
```

- [ ] **Step 5: Run API tests**

Run:

```bash
uv run pytest tests/wf_api/test_source_registry_admin_api.py -q
```

Expected: pass.

## Task 2: Implement MCP Runtime Apply Provider

**Files:**
- Modify: `src/wf_mcp/broker/service/source_registry_admin.py`
- Modify: `src/wf_mcp/broker/server.py`
- Test: `tests/wf_mcp/service/test_source_registry_admin.py`

- [ ] **Step 1: Add failing service test**

Add this helper near existing test helpers in `tests/wf_mcp/service/test_source_registry_admin.py`:

```python
def _apply_provider(
    tmp_path,
    *,
    config_connections=(),
    registry_sources=(),
):
    from wf_mcp.broker.service.connection_service import ConnectionService
    from wf_mcp.broker.service.events import BrokerEventRecorder
    from wf_mcp.broker.service.source_catalog import SourceCatalogService
    from wf_mcp.models import BrokerConfig
    from wf_mcp.source_registry import FileSourceRegistryStore, SourceRegistryFile
    from wf_mcp.storage import FileStore
    from wf_mcp.events import EventBus

    events = BrokerEventRecorder(EventBus())
    connection_service = ConnectionService(events=events)
    source_catalog = SourceCatalogService(
        store=FileStore(tmp_path),
        connection_lookup=connection_service.get,
        connection_list_enabled=connection_service.list_enabled,
        connection_list_all=connection_service.list_all,
        tool_executor_for=lambda connection: None,
        load_auth=lambda connection_id: None,
        emit_event=events.record_event,
    )
    connection_service.bind_source_catalog(source_catalog)
    store = FileSourceRegistryStore(tmp_path)
    store.save_registry(SourceRegistryFile(sources=list(registry_sources)))
    config = BrokerConfig(store_root=tmp_path, connections=list(config_connections))
    provider = SourceRegistryAdminProvider(
        source_registry_store=store,
        config_connections=config.connections,
        connection_service=connection_service,
        config=config,
        ensure_adapter=lambda connection: None,
    )
    return provider, connection_service, source_catalog
```

Then add:

```python
def test_source_registry_apply_materializes_registry_connection(tmp_path) -> None:
    entry = _registry_entry("dynamic.default", provider="dynamic", account="default")
    provider, connection_service, source_catalog = _apply_provider(
        tmp_path,
        registry_sources=[entry],
    )

    payload = provider.apply_registry_changes()

    assert payload["applied"] is True
    assert payload["registered"] == ["dynamic.default"]
    assert payload["updated"] == []
    assert payload["removed"] == []
    assert payload["connection_count"] == 1
    assert payload["registry_entry_count"] == 1
    assert connection_service.get("dynamic.default").server == "dynamic"
    assert source_catalog.capability_sources["dynamic.default"].enabled is True
```

Add a second test for removal:

```python
def test_source_registry_apply_removes_deleted_registry_connection(tmp_path) -> None:
    entry = _registry_entry("dynamic.default", provider="dynamic", account="default")
    provider, connection_service, source_catalog = _apply_provider(
        tmp_path,
        registry_sources=[entry],
    )
    provider.apply_registry_changes()
    provider.remove_registry_entry("dynamic.default")

    payload = provider.apply_registry_changes()

    assert payload["removed"] == ["dynamic.default"]
    assert "dynamic.default" not in connection_service.connections.connections
    assert "dynamic.default" not in source_catalog.capability_sources
```

- [ ] **Step 2: Run failing service tests**

Run:

```bash
uv run pytest tests/wf_mcp/service/test_source_registry_admin.py -q
```

Expected: fail because `SourceRegistryAdminProvider` lacks runtime apply dependencies and method.

- [ ] **Step 3: Extend provider dataclass**

In `src/wf_mcp/broker/service/source_registry_admin.py`, import:

```python
from collections.abc import Callable

from ...models import BrokerConfig
from .connection_service import ConnectionService
```

Change the dataclass fields to include:

```python
connection_service: ConnectionService | None = None
config: BrokerConfig | None = None
ensure_adapter: Callable[[ConnectionConfig], None] | None = None
```

- [ ] **Step 4: Add apply implementation**

Add this method to `SourceRegistryAdminProvider`:

```python
def apply_registry_changes(self) -> dict[str, Any]:
    """Reconcile desired registry state into the live service connection graph.

    This mirrors config reload reconciliation, but it only applies persisted
    registry state. It does not mutate config files or remount FastMCP proxy
    providers.
    """
    if self.connection_service is None or self.config is None:
        raise RuntimeError("source registry apply requires runtime service context")

    before = {connection.id: connection for connection in self.connection_service.list_all()}
    registry = self.source_registry_store.load_registry()
    self.connection_service.sync_connections_from_config(
        self.config,
        source_registry_store=self.source_registry_store,
    )
    after = {connection.id: connection for connection in self.connection_service.list_all()}

    if self.ensure_adapter is not None:
        for connection in after.values():
            self.ensure_adapter(connection)

    before_ids = set(before)
    after_ids = set(after)
    updated = sorted(
        source_id
        for source_id in before_ids & after_ids
        if before[source_id] != after[source_id]
    )
    return {
        "applied": True,
        "registered": sorted(after_ids - before_ids),
        "updated": updated,
        "removed": sorted(before_ids - after_ids),
        "connection_count": len(after),
        "registry_entry_count": len(registry.sources),
    }
```

- [ ] **Step 5: Wire provider in MCP-backed WorkflowServer**

In `src/wf_mcp/broker/server.py`, inside `workflow_server_from_service`, replace:

```python
registry_provider = SourceRegistryAdminProvider(
    source_registry_store=source_registry_store,
    config_connections=config.connections,
)
```

with:

```python
def ensure_adapter(connection: ConnectionConfig) -> None:
    if connection.server not in service.adapters:
        service.register_adapter(connection.server, McpSdkAdapter())


registry_provider = SourceRegistryAdminProvider(
    source_registry_store=source_registry_store,
    config_connections=config.connections,
    connection_service=service.connection_service,
    config=config,
    ensure_adapter=ensure_adapter,
)
```

Add `apply_provider=registry_provider` when constructing `WorkflowSourceRegistryApi`:

```python
source_registry_admin = WorkflowSourceRegistryApi(
    provider=registry_provider,
    mutation_provider=registry_provider,
    apply_provider=registry_provider,
)
```

Import `ConnectionConfig` if needed.

- [ ] **Step 6: Run service tests**

Run:

```bash
uv run pytest tests/wf_mcp/service/test_source_registry_admin.py tests/wf_mcp/service/test_connection_service.py -q
```

Expected: pass.

## Task 3: Add JSON-RPC Apply Method and Client

**Files:**
- Modify: `src/wf_transport_rpc_http/models.py`
- Modify: `src/wf_transport_rpc_http/methods_source_registry.py`
- Modify: `src/wf_transport_rpc_http/client_source_registry.py`
- Test: `tests/wf_transport_rpc_http/test_source_registry_rpc.py`

- [ ] **Step 1: Add failing RPC tests**

In `tests/wf_transport_rpc_http/test_source_registry_rpc.py`, add:

```python
async def test_rpc_source_registry_apply_unavailable_on_local_static(tmp_path) -> None:
    app = create_rpc_app(build_local_static_workflow_server(tmp_path / "store"))
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        payload = await _rpc(
            client,
            "workflow.admin.source_registry.apply",
            {},
        )

    assert payload["error"]["data"]["code"] == "source_registry_unavailable"
```

Add a fake method test:

```python
async def test_rpc_source_registry_apply_returns_summary(tmp_path) -> None:
    admin = AsyncMock()
    admin.apply_registry_changes.return_value = {
        "applied": True,
        "registered": ["demo.new"],
        "updated": [],
        "removed": [],
        "connection_count": 1,
        "registry_entry_count": 1,
    }
    server = build_local_static_workflow_server(tmp_path / "store")
    server.source_registry_admin = admin
    app = create_rpc_app(server)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        payload = await _rpc(
            client,
            "workflow.admin.source_registry.apply",
            {},
        )

    assert payload["result"]["applied"] is True
    assert payload["result"]["registered"] == ["demo.new"]
    admin.apply_registry_changes.assert_awaited_once()
```

Add a client method existence test near existing client tests:

```python
async def test_rpc_client_source_registry_apply_method_exists() -> None:
    calls = []

    class Client(RpcSourceRegistryClientMixin):
        async def _call(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
            calls.append((method, params))
            return {"applied": True}

    payload = await Client().apply_registry_changes()

    assert payload["applied"] is True
    assert calls == [("workflow.admin.source_registry.apply", {})]
```

- [ ] **Step 2: Run failing RPC tests**

Run:

```bash
uv run pytest tests/wf_transport_rpc_http/test_source_registry_rpc.py -q
```

Expected: fail because the method/client do not exist.

- [ ] **Step 3: Add params model**

In `src/wf_transport_rpc_http/models.py`, add:

```python
class ApplyRegistryChangesParams(RpcParamsModel):
    pass
```

- [ ] **Step 4: Register JSON-RPC method**

In `src/wf_transport_rpc_http/methods_source_registry.py`, import `ApplyRegistryChangesParams`.

Add inside `register_methods`:

```python
@entrypoint.method(
    name="workflow.admin.source_registry.apply",
    errors=[WorkflowRpcError],
)
async def workflow_admin_source_registry_apply(
    params: ApplyRegistryChangesParams = RpcParams(),
) -> dict[str, Any]:
    admin = _require_source_registry_admin(server, operation="apply")
    try:
        return await admin.apply_registry_changes()
    except (ValueError, KeyError, LookupError, FileNotFoundError, RuntimeError) as exc:
        raise_workflow_rpc_error(exc)
```

- [ ] **Step 5: Add client method**

In `src/wf_transport_rpc_http/client_source_registry.py`, add:

```python
async def apply_registry_changes(self) -> dict[str, Any]:
    return await self._call(
        "workflow.admin.source_registry.apply",
        {},
    )
```

- [ ] **Step 6: Run RPC tests**

Run:

```bash
uv run pytest tests/wf_transport_rpc_http/test_source_registry_rpc.py -q
```

Expected: pass.

## Task 4: Add CLI Apply Command

**Files:**
- Modify: `src/wf_cli/commands/source_registry.py`
- Test: `tests/wf_cli/test_source_registry.py`

- [ ] **Step 1: Add failing CLI test**

In `tests/wf_cli/test_source_registry.py`, add:

```python
def test_registry_apply_calls_surface(monkeypatch) -> None:
    surface = MagicMock()
    surface.apply_registry_changes.return_value = {
        "applied": True,
        "registered": ["demo.new"],
        "updated": [],
        "removed": [],
        "connection_count": 1,
        "registry_entry_count": 1,
    }
    _patch_context(monkeypatch, source_registry_admin=surface)
    result = CliRunner().invoke(app, ["apply"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["applied"] is True
    assert payload["registered"] == ["demo.new"]
```

Use the existing test helper names in that file. If the helper is named differently, adapt only the helper call; keep the assertion payload.

- [ ] **Step 2: Run failing CLI tests**

Run:

```bash
uv run pytest tests/wf_cli/test_source_registry.py -q
```

Expected: fail because `apply` command does not exist.

- [ ] **Step 3: Add command**

In `src/wf_cli/commands/source_registry.py`, add:

```python
@app.command("apply")
def apply_registry_changes(ctx: typer.Context) -> None:
    """Apply desired registry state to the running server."""
    context = load_cli_context_from_typer(ctx)
    admin = _require_registry_admin(context)
    payload = asyncio.run(admin.apply_registry_changes())
    emit_json(payload)
```

- [ ] **Step 4: Run CLI tests**

Run:

```bash
uv run pytest tests/wf_cli/test_source_registry.py -q
```

Expected: pass.

## Task 5: MCP-Backed RPC Integration Test

**Files:**
- Modify: `tests/wf_transport_rpc_http/test_mcp_backed_server_rpc.py`

- [ ] **Step 1: Add integration test**

Add a test that proves persisted registry changes affect live source inventory after apply:

```python
async def test_mcp_backed_rpc_applies_source_registry_changes(tmp_path) -> None:
    config = BrokerConfig(store_root=tmp_path / "store", connections=[])
    server = build_workflow_server_from_config(config)
    app = create_rpc_app(server)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        await _rpc(
            client,
            "workflow.admin.source_registry.add",
            {
                "entry": {
                    "kind": "mcp",
                    "id": "dynamic.default",
                    "enabled": True,
                    "provider": "dynamic",
                    "account": "default",
                    "transport": {
                        "kind": "stdio",
                        "command": "dynamic-server",
                        "args": [],
                        "env": {},
                    },
                }
            },
        )
        before = await _rpc(
            client,
            "workflow.sources.list",
            {"limit": 50},
        )
        applied = await _rpc(
            client,
            "workflow.admin.source_registry.apply",
            {},
        )
        after = await _rpc(
            client,
            "workflow.sources.list",
            {"limit": 50},
        )

    before_ids = {source["id"] for source in before["result"]["sources"]}
    after_ids = {source["id"] for source in after["result"]["sources"]}
    assert "dynamic.default" not in before_ids
    assert applied["result"]["registered"] == ["dynamic.default"]
    assert "dynamic.default" in after_ids
```

If the existing helper for source list uses a different JSON-RPC method name, use the method already registered in `methods_sources.py`.

- [ ] **Step 2: Run integration test**

Run:

```bash
uv run pytest tests/wf_transport_rpc_http/test_mcp_backed_server_rpc.py -q
```

Expected: pass.

## Task 6: Docs and Final Verification

**Files:**
- Modify: `docs/current_roadmap.md`
- Modify: `docs/superpowers/specs/2026-06-03-store-backed-source-registry-design.md`
- Modify: `docs/wf_cli.md`

- [ ] **Step 1: Update roadmap**

In `docs/current_roadmap.md`, under "Source registry apply/reload", add:

```markdown
    Completed: desired source registry mutations can now be applied explicitly
    through `wf admin registry apply` / `workflow.admin.source_registry.apply`.
    V1 apply reconciles registry state into the current server connection/source
    graph; it does not auto-apply mutations, mutate config files, or remount
    MCP proxy providers.
```

- [ ] **Step 2: Update source registry spec**

In `docs/superpowers/specs/2026-06-03-store-backed-source-registry-design.md`, add an "Apply semantics" section:

```markdown
### Apply Semantics

Registry mutation commands write desired persisted state. They do not implicitly
change the running server. `apply_registry_changes` is the explicit boundary
that reconciles desired registry state with the current runtime source graph.

The apply operation mirrors config reload reconciliation by calling the same
connection/source merge logic. It preserves `locked` config shadowing and `seed`
config handoff rules. It does not mutate config files, remount public MCP proxy
providers, or handle upstream credential prompts.
```

- [ ] **Step 3: Update CLI docs**

In `docs/wf_cli.md`, near source registry commands, add:

```markdown
After `wf admin registry add/update/enable/disable/remove`, call:

```bash
wf --url http://127.0.0.1:8765/rpc admin registry apply
```

Apply updates the running server's source graph from desired registry state.
It is explicit in v1; registry mutations are not auto-applied.
```

- [ ] **Step 4: Run focused tests**

Run:

```bash
uv run pytest tests/wf_api/test_source_registry_admin_api.py tests/wf_mcp/service/test_source_registry_admin.py tests/wf_transport_rpc_http/test_source_registry_rpc.py tests/wf_transport_rpc_http/test_mcp_backed_server_rpc.py tests/wf_cli/test_source_registry.py -q
```

Expected: pass.

- [ ] **Step 5: Run lint/type checks**

Run:

```bash
uv run ruff check src/wf_api src/wf_mcp/broker src/wf_transport_rpc_http src/wf_cli tests/wf_api tests/wf_mcp tests/wf_transport_rpc_http tests/wf_cli
uv run basedpyright --level error src/wf_api src/wf_mcp/broker src/wf_transport_rpc_http src/wf_cli tests/wf_api tests/wf_mcp tests/wf_transport_rpc_http tests/wf_cli
```

Expected: 0 errors.

- [ ] **Step 6: Commit**

Run:

```bash
git add src/wf_api src/wf_mcp/broker src/wf_transport_rpc_http src/wf_cli tests/wf_api tests/wf_mcp tests/wf_transport_rpc_http tests/wf_cli docs/current_roadmap.md docs/superpowers/specs/2026-06-03-store-backed-source-registry-design.md docs/wf_cli.md
git commit -m "feat: apply source registry changes"
```

## Self-Review Checklist

- Registry mutation methods still only persist desired state.
- `apply_registry_changes` is the only new runtime-adoption operation.
- Local/static servers still return `source_registry_unavailable`.
- Locked config entries still shadow same-id registry entries.
- Seed config entries still bootstrap/yield according to existing merge logic.
- No proxy/FastMCP remount behavior is introduced.
- No registry operation mutates `wf_mcp.config.json` or neutral workflow config.
