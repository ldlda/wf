# Split MCP Auth And Catalog Stores Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split the current MCP compatibility `FileStore` responsibilities so auth records and catalog/cache snapshots can use different configured roots.

**Architecture:** Keep `FileStore(root)` as the backwards-compatible combined store. Add focused `AuthStore` / `CatalogStore` protocols plus `FileAuthStore` / `FileCatalogStore` implementations. `WfMcpService` receives separate auth and catalog stores internally, while existing callers that pass only `store=FileStore(...)` keep working.

**Tech Stack:** Python dataclasses/protocol-style store classes, existing MCP broker services, pytest, ruff, basedpyright.

---

## File Map

- `src/wf_mcp/storage/store.py`: define focused store interfaces/classes and keep `FileStore` as a compatibility wrapper.
- `src/wf_mcp/storage/__init__.py`: export new store types.
- `src/wf_mcp/broker/service/core.py`: add optional `auth_store` and `catalog_store` fields; wire focused services to focused stores.
- `src/wf_mcp/broker/service/upstream_transport.py`: accept `AuthStore` and `CatalogStore` instead of one combined `Store`.
- `src/wf_mcp/broker/service/source_catalog.py`: accept `CatalogStore` instead of combined `Store`.
- `src/wf_mcp/broker/config.py`: construct `FileAuthStore(auth_root)` and `FileCatalogStore(catalog_cache_root)` from `BrokerStoreRoots`.
- `tests/wf_mcp/test_store.py`: focused store behavior tests.
- `tests/wf_mcp/test_workflow_config_bridge.py`: prove auth and catalog role roots are both used.
- `tests/wf_mcp/service/test_upstream_transport.py`, `tests/wf_mcp/service/test_catalog.py`: adjust direct service construction where needed.
- Docs: `docs/current_roadmap.md`, `docs/superpowers/specs/2026-06-03-workflow-config-targets-and-sources.md`, `docs/wf_cli.md`.

---

## Hard Boundaries

- Do not remove `FileStore`; too many tests and compatibility paths still construct it.
- Do not move this into `wf_api`; these stores are still MCP-shaped compatibility stores.
- Do not add SQL/object/secret-manager stores.
- Do not change on-disk JSON shapes:
  - auth remains `<auth-root>/auth/<auth_ref>.json`
  - catalog remains `<catalog-root>/catalog/<connection_id>.json`
- Existing `WfMcpService(store=FileStore(root))` must keep using `root` for both auth and catalog.

---

## Task 1: Add Focused FileAuthStore And FileCatalogStore

**Files:**
- Modify: `src/wf_mcp/storage/store.py`
- Modify: `src/wf_mcp/storage/__init__.py`
- Test: `tests/wf_mcp/test_store.py`

- [ ] **Step 1: Add focused store tests**

Append to `tests/wf_mcp/test_store.py`:

```python
def test_file_auth_store_uses_own_root(tmp_path) -> None:
    store = FileAuthStore(tmp_path / "auth_root")
    record = AuthRecord(
        connection_id="drive.work",
        scheme="bearer",
        payload={"token": "secret"},
    )

    store.save_auth(record)

    assert store.load_auth("drive.work") == record
    assert (tmp_path / "auth_root" / "auth" / "drive.work.json").exists()
    assert not (tmp_path / "auth_root" / "catalog").exists()


def test_file_catalog_store_uses_own_root(tmp_path) -> None:
    store = FileCatalogStore(tmp_path / "catalog_root")
    snapshot = CatalogSnapshot(
        connection_id="drive.work",
        fetched_at_epoch_ms=1,
        max_age_seconds=300,
        nodes=[],
        resources=[],
        prompts=[],
        metadata={},
    )

    store.save_catalog(snapshot)

    assert store.load_catalog("drive.work") == snapshot
    assert (tmp_path / "catalog_root" / "catalog" / "drive.work.json").exists()
    assert not (tmp_path / "catalog_root" / "auth").exists()
```

Add imports if missing:

```python
from wf_mcp.storage import FileAuthStore, FileCatalogStore
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
uv run pytest tests/wf_mcp/test_store.py::test_file_auth_store_uses_own_root tests/wf_mcp/test_store.py::test_file_catalog_store_uses_own_root -q
```

Expected: fail because `FileAuthStore` and `FileCatalogStore` do not exist.

- [ ] **Step 3: Split store interfaces and classes**

In `src/wf_mcp/storage/store.py`, replace the top-level `Store` class with:

```python
class AuthStore:
    def save_auth(self, record: AuthRecord) -> None:
        raise NotImplementedError

    def load_auth(self, connection_id: str) -> AuthRecord | None:
        raise NotImplementedError

    def list_auth_refs(self) -> list[str]:
        raise NotImplementedError

    def save_auth_record(self, record: NeutralAuthRecord) -> None:
        raise NotImplementedError

    def load_auth_record(self, auth_ref: str) -> NeutralAuthRecord | None:
        raise NotImplementedError

    def delete_auth(self, connection_id: str) -> bool:
        raise NotImplementedError

    def delete_auth_record(self, auth_ref: str) -> bool:
        raise NotImplementedError


class CatalogStore:
    def save_catalog(self, snapshot: CatalogSnapshot) -> None:
        raise NotImplementedError

    def load_catalog(self, connection_id: str) -> CatalogSnapshot | None:
        raise NotImplementedError


class Store(AuthStore, CatalogStore):
    """Compatibility store combining MCP auth and catalog/cache storage."""
```

Then add `FileAuthStore` with the existing auth methods and `_auth_path` helper, and `FileCatalogStore` with the existing catalog methods, `_catalog_path`, and `_connection_path` helper.

Keep `FileStore` as:

```python
class FileStore(Store):
    """Compatibility file store that combines auth and catalog stores."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self._auth = FileAuthStore(root)
        self._catalog = FileCatalogStore(root)

    @property
    def auth_dir(self) -> Path:
        return self._auth.auth_dir

    @property
    def catalog_dir(self) -> Path:
        return self._catalog.catalog_dir

    def save_auth(self, record: AuthRecord) -> None:
        self._auth.save_auth(record)

    def load_auth(self, connection_id: str) -> AuthRecord | None:
        return self._auth.load_auth(connection_id)

    def list_auth_refs(self) -> list[str]:
        return self._auth.list_auth_refs()

    def save_auth_record(self, record: NeutralAuthRecord) -> None:
        self._auth.save_auth_record(record)

    def load_auth_record(self, auth_ref: str) -> NeutralAuthRecord | None:
        return self._auth.load_auth_record(auth_ref)

    def delete_auth(self, connection_id: str) -> bool:
        return self._auth.delete_auth(connection_id)

    def delete_auth_record(self, auth_ref: str) -> bool:
        return self._auth.delete_auth_record(auth_ref)

    def save_catalog(self, snapshot: CatalogSnapshot) -> None:
        self._catalog.save_catalog(snapshot)

    def load_catalog(self, connection_id: str) -> CatalogSnapshot | None:
        return self._catalog.load_catalog(connection_id)
```

Use docstrings/comments for the compatibility seam: future code should inject focused stores; `FileStore` remains for older callers.

- [ ] **Step 4: Export new stores**

In `src/wf_mcp/storage/__init__.py`, export:

```python
AuthStore
CatalogStore
FileAuthStore
FileCatalogStore
```

Keep existing `Store` and `FileStore` exports.

- [ ] **Step 5: Verify store tests**

Run:

```bash
uv run pytest tests/wf_mcp/test_store.py -q
```

Expected: pass.

---

## Task 2: Split Store Dependencies In Broker Services

**Files:**
- Modify: `src/wf_mcp/broker/service/upstream_transport.py`
- Modify: `src/wf_mcp/broker/service/source_catalog.py`
- Modify: `src/wf_mcp/broker/service/core.py`
- Test: `tests/wf_mcp/service/test_upstream_transport.py`
- Test: `tests/wf_mcp/service/test_catalog.py`

- [ ] **Step 1: Add direct service tests for separate roots**

In `tests/wf_mcp/service/test_upstream_transport.py`, add:

```python
def test_upstream_transport_uses_separate_auth_and_catalog_stores(tmp_path) -> None:
    auth_store = FileAuthStore(tmp_path / "auth")
    catalog_store = FileCatalogStore(tmp_path / "catalog")
    events = []
    transport = UpstreamTransportService(
        auth_store=auth_store,
        catalog_store=catalog_store,
        event_sink=events.append,
    )
    record = AuthRecord(connection_id="demo.personal", scheme="bearer")
    transport.save_auth(record)
    snapshot = CatalogSnapshot(
        connection_id="demo.personal",
        fetched_at_epoch_ms=1,
        max_age_seconds=300,
        nodes=[],
        resources=[],
        prompts=[],
        metadata={},
    )
    transport.catalog_store.save_catalog(snapshot)

    assert (tmp_path / "auth" / "auth" / "demo.personal.json").exists()
    assert (tmp_path / "catalog" / "catalog" / "demo.personal.json").exists()
```

In `tests/wf_mcp/service/test_catalog.py`, add:

```python
def test_source_catalog_uses_catalog_store_only(tmp_path) -> None:
    catalog_store = FileCatalogStore(tmp_path / "catalog")
    service = SourceCatalogService(
        store=catalog_store,
        connection_lookup=lambda connection_id: ConnectionConfig(
            id=connection_id,
            server="demo",
            account="personal",
        ),
        connection_list_enabled=lambda: [],
        connection_list_all=lambda: [],
        tool_executor_for=lambda connection: (_ for _ in ()).throw(
            AssertionError("unexpected executor")
        ),
        load_auth=lambda connection: None,
        emit_event=lambda event: None,
    )
    snapshot = CatalogSnapshot(
        connection_id="demo.personal",
        fetched_at_epoch_ms=1,
        max_age_seconds=300,
        nodes=[],
        resources=[],
        prompts=[],
        metadata={},
    )
    service.store.save_catalog(snapshot)

    assert service.store.load_catalog("demo.personal") == snapshot
    assert (tmp_path / "catalog" / "catalog" / "demo.personal.json").exists()
```

Adjust imports to match existing test file conventions.

- [ ] **Step 2: Run failing tests**

Run:

```bash
uv run pytest tests/wf_mcp/service/test_upstream_transport.py::test_upstream_transport_uses_separate_auth_and_catalog_stores tests/wf_mcp/service/test_catalog.py::test_source_catalog_uses_catalog_store_only -q
```

Expected: fail because constructors still take one combined `store`.

- [ ] **Step 3: Update `UpstreamTransportService`**

In `src/wf_mcp/broker/service/upstream_transport.py`:

```python
from wf_mcp.storage import AuthStore, CatalogStore
```

Change fields to:

```python
    auth_store: AuthStore
    catalog_store: CatalogStore
```

Update methods:

```python
    def save_auth(self, record: AuthRecord) -> None:
        self.auth_store.save_auth(record)

    def load_auth(self, connection_id: str) -> AuthRecord | None:
        return self.auth_store.load_auth(connection_id)
```

Replace `self.store.save_catalog(snapshot)` with `self.catalog_store.save_catalog(snapshot)`.

If tests or callers still inspect `transport.store`, do not keep a fake combined property. Update those tests/callers to use `auth_store` or `catalog_store`; this is the point of the slice.

- [ ] **Step 4: Update `SourceCatalogService`**

In `src/wf_mcp/broker/service/source_catalog.py`:

```python
from ...storage import CatalogStore
```

Change:

```python
store: Store
```

to:

```python
store: CatalogStore
```

No behavior change is needed; all current calls on `store` are catalog calls.

- [ ] **Step 5: Update `WfMcpService` wiring**

In `src/wf_mcp/broker/service/core.py` import:

```python
from ...storage import AuthStore, CatalogStore, Store
```

Add dataclass fields:

```python
    auth_store: AuthStore | None = None
    catalog_store: CatalogStore | None = None
```

At the top of `__post_init__` after `self.events = ...`, add:

```python
        auth_store = self.auth_store or self.store
        catalog_store = self.catalog_store or self.store
```

Wire:

```python
        self.upstream = UpstreamTransportService(
            auth_store=auth_store,
            catalog_store=catalog_store,
            event_sink=self.events.record_event,
            tool_executor=self.tool_executor,
        )
        self.source_catalog = SourceCatalogService(
            store=catalog_store,
            ...
        )
```

Keep `store: Store` on `WfMcpService` for compatibility and admin auth provider usage until the next slice removes facade reliance.

- [ ] **Step 6: Verify focused service tests**

Run:

```bash
uv run pytest tests/wf_mcp/service/test_upstream_transport.py tests/wf_mcp/service/test_catalog.py -q
```

Expected: pass.

---

## Task 3: Wire Role Roots Into MCP Config Construction

**Files:**
- Modify: `src/wf_mcp/broker/config.py`
- Test: `tests/wf_mcp/test_workflow_config_bridge.py`

- [ ] **Step 1: Strengthen bridge test**

Update `test_build_service_from_neutral_config_uses_role_store_roots` in `tests/wf_mcp/test_workflow_config_bridge.py` to assert both auth and catalog roots:

```python
    assert service.store.root == tmp_path / "auth"
    assert service.auth_store is not None
    assert service.catalog_store is not None
    assert service.auth_store.root == tmp_path / "auth"
    assert service.catalog_store.root == tmp_path / "catalog"
```

Then add a catalog write assertion:

```python
    service.source_catalog.store.save_catalog(
        CatalogSnapshot(
            connection_id="everything.default",
            fetched_at_epoch_ms=1,
            max_age_seconds=300,
            nodes=[],
            resources=[],
            prompts=[],
            metadata={},
        )
    )
    assert (
        tmp_path / "catalog" / "catalog" / "everything.default.json"
    ).exists()
    assert not (
        tmp_path / "auth" / "catalog" / "everything.default.json"
    ).exists()
```

Add `CatalogSnapshot` import if missing.

- [ ] **Step 2: Run failing bridge test**

Run:

```bash
uv run pytest tests/wf_mcp/test_workflow_config_bridge.py::test_build_service_from_neutral_config_uses_role_store_roots -q
```

Expected: fail because `build_service_from_config` still passes only `FileStore(auth_root)` to both auth and catalog services.

- [ ] **Step 3: Construct focused stores in `build_service_from_config`**

In `src/wf_mcp/broker/config.py`, import:

```python
from ..storage import FileAuthStore, FileCatalogStore, FileStore
```

Update service construction:

```python
    auth_store = FileAuthStore(store_roots.auth_root)
    catalog_store = FileCatalogStore(store_roots.catalog_cache_root)
    service = WfMcpService(
        store=FileStore(store_roots.auth_root),
        auth_store=auth_store,
        catalog_store=catalog_store,
        artifact_store=workflow_stores.artifact_store,
        draft_workspace_store=workflow_stores.draft_workspace_store,
        run_store=workflow_stores.run_store,
        tool_executor=McpRuntimePool(runtime_factory.create),
    )
```

Remove the old comment saying FileStore still owns both auth and catalog. Replace it with:

```python
    # Keep FileStore as the compatibility facade on WfMcpService.store while
    # focused services receive role-specific stores.
```

- [ ] **Step 4: Verify bridge tests**

Run:

```bash
uv run pytest tests/wf_mcp/test_workflow_config_bridge.py tests/wf_mcp/test_mcp_workflow_server.py -q
```

Expected: pass.

---

## Task 4: Update Admin Auth Provider To Use Focused Auth Store

**Files:**
- Modify: `src/wf_mcp/broker/server.py`
- Modify: `src/wf_mcp/broker/service/auth_admin.py`
- Test: `tests/wf_mcp/test_mcp_workflow_server.py`

- [ ] **Step 1: Add wiring assertion**

In `tests/wf_mcp/test_mcp_workflow_server.py`, add or update a test to assert the admin auth provider uses the service auth store when present:

```python
def test_workflow_server_from_service_uses_focused_auth_store(tmp_path) -> None:
    auth_store = FileAuthStore(tmp_path / "auth")
    service = WfMcpService(
        store=FileStore(tmp_path / "compat"),
        auth_store=auth_store,
        artifact_store=FileWorkflowArtifactStore(tmp_path / "workflow"),
        draft_workspace_store=FileDraftWorkspaceStore(tmp_path / "workflow"),
        run_store=FileRunStore(tmp_path / "workflow"),
    )
    auth_store.save_auth(AuthRecord(connection_id="drive.work", scheme="bearer"))

    server = workflow_server_from_service(service)
    result = asyncio.run(server.admin.inspect_auth_record("drive.work"))

    assert result["id"] == "drive.work"
```

Follow existing imports/conventions in the file.

- [ ] **Step 2: Run failing test**

Run:

```bash
uv run pytest tests/wf_mcp/test_mcp_workflow_server.py::test_workflow_server_from_service_uses_focused_auth_store -q
```

Expected: fail because `workflow_server_from_service` still builds `McpAuthAdminProvider(store=service.store)`.

- [ ] **Step 3: Widen auth admin provider type**

In `src/wf_mcp/broker/service/auth_admin.py`, import `AuthStore` and change:

```python
store: FileStore
```

or

```python
store: Store
```

to:

```python
store: AuthStore
```

- [ ] **Step 4: Use focused auth store in server composition**

In `src/wf_mcp/broker/server.py`, change:

```python
auth=McpAuthAdminProvider(store=service.store),
```

to:

```python
auth=McpAuthAdminProvider(store=service.auth_store or service.store),
```

- [ ] **Step 5: Verify server tests**

Run:

```bash
uv run pytest tests/wf_mcp/test_mcp_workflow_server.py tests/wf_mcp/service/test_auth_admin.py -q
```

Expected: pass.

---

## Task 5: Docs, Compatibility, And Final Verification

**Files:**
- Modify: `docs/current_roadmap.md`
- Modify: `docs/superpowers/specs/2026-06-03-workflow-config-targets-and-sources.md`
- Modify: `docs/wf_cli.md`

- [ ] **Step 1: Update docs**

In `docs/current_roadmap.md`, replace the role-store limitation sentence with:

```markdown
    Follow-up complete: MCP compatibility auth and catalog/cache stores are now
    split at the service boundary. `FileStore` remains as a compatibility
    wrapper, while neutral config role roots can drive `FileAuthStore` and
    `FileCatalogStore` separately.
```

In `docs/superpowers/specs/2026-06-03-workflow-config-targets-and-sources.md`, update the Store Roles status:

```markdown
Implementation status: filesystem role overrides are implemented. MCP auth and
catalog/cache storage now have separate file-store adapters; `server.store`
still remains the fallback for missing roles.
```

In `docs/wf_cli.md`, keep the user-facing wording short:

```markdown
For filesystem configs, role-specific store overrides can split local/dev auth
records and catalog cache from workflow records.
```

- [ ] **Step 2: Run focused tests**

Run:

```bash
uv run pytest tests/wf_mcp/test_store.py tests/wf_mcp/service/test_upstream_transport.py tests/wf_mcp/service/test_catalog.py tests/wf_mcp/service/test_auth_admin.py tests/wf_mcp/test_workflow_config_bridge.py tests/wf_mcp/test_mcp_workflow_server.py -q
```

Expected: pass.

- [ ] **Step 3: Run lint/type checks**

Run:

```bash
uv run ruff check src tests
uv run basedpyright --level error src
```

Expected: ruff passes and basedpyright reports `0 errors`.

- [ ] **Step 4: Optional full suite**

Run if time allows:

```bash
uv run pytest -q
```

Expected: current suite shape, around `1202 passed, 1 skipped, 1 xfailed`.

- [ ] **Step 5: Final report**

Report:

- files changed
- test/lint/type output
- whether full suite was run
- remaining compatibility shims (`FileStore`, `WfMcpService.store`)
- no on-disk JSON shape changes

---

## Self-Review Notes

- This slice makes `catalog_cache_root` real without changing config shape again.
- Backwards compatibility remains: `FileStore(root)` and `WfMcpService(store=...)` still work.
- The split is MCP-internal. Neutral `wf_api` remains untouched.
- Future package split (`wf_sources_mcp`) becomes easier after this because upstream MCP source code no longer receives a monolithic auth/catalog store.
