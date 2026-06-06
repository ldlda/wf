# Server Store Role Overrides Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add optional role-specific filesystem store overrides to neutral workflow config while preserving `server.store` as the default for every missing role.

**Architecture:** `wf_config` owns the neutral config shape and path resolution. `wf_server` and MCP bridge composition consume resolved role roots instead of assuming every persistence role uses `server.store.root`. This slice stays filesystem-only and does not add SQL, object storage, or secret-manager backends.

**Tech Stack:** Pydantic v2 discriminated models, Typer CLI config loading, existing file stores (`wf_api.file_workflow_stores`, `wf_mcp.storage.FileStore`, `wf_mcp.source_registry.FileSourceRegistryStore`), pytest, ruff, basedpyright.

---

## File Map

- `src/wf_config/models.py`: add `ServerStoresConfig` with optional role-specific store overrides.
- `src/wf_config/loader.py`: resolve relative paths for `server.store` and every configured role store.
- `src/wf_config/__init__.py`: export `ServerStoresConfig`.
- `src/wf_server/config.py`: add helper for local/static workflow store root selection.
- `src/wf_mcp/broker/config.py`: consume role-specific roots when building MCP-backed services from neutral config.
- `src/wf_mcp/broker/models.py`: add runtime `BrokerStoreRoots` so the legacy bridge can carry separate roots internally.
- `src/wf_transport_rpc_http/cli.py`: preserve `--store-root` behavior and avoid accidental role-store bypass for MCP configs.
- `src/wf_cli/context.py`: local `--local` target should use `stores.workflow` when provided.
- `tests/wf_config/test_config_models.py`: config parsing and path-resolution tests.
- `tests/wf_mcp/test_workflow_config_bridge.py`: neutral config to broker runtime store-root tests.
- `tests/wf_transport_rpc_http/test_cli.py`: server CLI behavior with role-store config.
- `tests/wf_cli/test_context.py`: local CLI store-root selection test.
- `docs/current_roadmap.md`, `docs/superpowers/specs/2026-06-03-workflow-config-targets-and-sources.md`, `docs/wf_cli.md`: mark first implementation slice complete.

---

## Role Names

Use these exact field names in config:

```python
workflow
auth
source_registry
catalog_cache
```

Resolution rule:

```python
effective_store(role) = server.stores.<role> if present else server.store
```

Use `catalog_cache` in config even though the current MCP compatibility `FileStore` stores auth and catalog in one class. The implementation may pass the same root to `FileStore` for `auth` and `catalog_cache` until the underlying store classes split.

---

## Task 1: Add Store Role Config Model

**Files:**
- Modify: `src/wf_config/models.py`
- Modify: `src/wf_config/__init__.py`
- Test: `tests/wf_config/test_config_models.py`

- [ ] **Step 1: Add failing config parse test**

Append this test to `tests/wf_config/test_config_models.py`:

```python
def test_workflow_config_parses_role_specific_store_overrides() -> None:
    config = WorkflowConfigFile.model_validate(
        {
            "version": 1,
            "server": {
                "store": {"kind": "filesystem", "root": ".wf_store"},
                "stores": {
                    "workflow": {"kind": "filesystem", "root": ".wf_workflow"},
                    "auth": {"kind": "filesystem", "root": ".wf_auth"},
                    "source_registry": {
                        "kind": "filesystem",
                        "root": ".wf_sources",
                    },
                    "catalog_cache": {
                        "kind": "filesystem",
                        "root": ".wf_catalog",
                    },
                },
            },
        }
    )

    assert isinstance(config.server.stores.workflow, FilesystemStoreConfig)
    assert config.server.stores.workflow.root.as_posix() == ".wf_workflow"
    assert isinstance(config.server.stores.auth, FilesystemStoreConfig)
    assert config.server.stores.auth.root.as_posix() == ".wf_auth"
    assert isinstance(config.server.stores.source_registry, FilesystemStoreConfig)
    assert config.server.stores.source_registry.root.as_posix() == ".wf_sources"
    assert isinstance(config.server.stores.catalog_cache, FilesystemStoreConfig)
    assert config.server.stores.catalog_cache.root.as_posix() == ".wf_catalog"
```

- [ ] **Step 2: Run the failing test**

Run:

```bash
uv run pytest tests/wf_config/test_config_models.py::test_workflow_config_parses_role_specific_store_overrides -q
```

Expected: fail because `ServerConfig` rejects unknown field `stores`.

- [ ] **Step 3: Implement `ServerStoresConfig`**

In `src/wf_config/models.py`, after `StoreConfig`, add:

```python
class ServerStoresConfig(WorkflowConfigModel):
    """Optional role-specific store overrides.

    Missing roles fall back to `ServerConfig.store`. Keep this config role-based
    so future backends can split workflow records, auth, desired sources, and
    cache storage independently.
    """

    workflow: StoreConfig | None = None
    auth: StoreConfig | None = None
    source_registry: StoreConfig | None = None
    catalog_cache: StoreConfig | None = None
```

In `ServerConfig`, add:

```python
stores: ServerStoresConfig = Field(default_factory=ServerStoresConfig)
```

- [ ] **Step 4: Export the new model**

In `src/wf_config/__init__.py`, import `ServerStoresConfig` from `.models` and add it to `__all__`.

- [ ] **Step 5: Verify task tests**

Run:

```bash
uv run pytest tests/wf_config/test_config_models.py::test_workflow_config_parses_role_specific_store_overrides -q
```

Expected: pass.

---

## Task 2: Resolve Role Store Paths Relative To Config File

**Files:**
- Modify: `src/wf_config/loader.py`
- Test: `tests/wf_config/test_config_models.py`

- [ ] **Step 1: Add failing path resolution test**

Append this test to `tests/wf_config/test_config_models.py`:

```python
def test_load_workflow_config_resolves_role_store_paths_relative_to_config(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "nested" / "wf.json"
    config_path.parent.mkdir()
    config_path.write_text(
        json.dumps(
            {
                "version": 1,
                "server": {
                    "store": {"kind": "filesystem", "root": ".default_store"},
                    "stores": {
                        "workflow": {
                            "kind": "filesystem",
                            "root": ".workflow_store",
                        },
                        "auth": {
                            "kind": "filesystem",
                            "root": ".auth_store",
                        },
                        "source_registry": {
                            "kind": "filesystem",
                            "root": ".source_store",
                        },
                        "catalog_cache": {
                            "kind": "filesystem",
                            "root": ".catalog_store",
                        },
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    config = load_workflow_config(config_path)

    assert config.server.store.root == (
        config_path.parent / ".default_store"
    ).resolve()
    assert config.server.stores.workflow is not None
    assert config.server.stores.workflow.root == (
        config_path.parent / ".workflow_store"
    ).resolve()
    assert config.server.stores.auth is not None
    assert config.server.stores.auth.root == (
        config_path.parent / ".auth_store"
    ).resolve()
    assert config.server.stores.source_registry is not None
    assert config.server.stores.source_registry.root == (
        config_path.parent / ".source_store"
    ).resolve()
    assert config.server.stores.catalog_cache is not None
    assert config.server.stores.catalog_cache.root == (
        config_path.parent / ".catalog_store"
    ).resolve()
```

- [ ] **Step 2: Run the failing test**

Run:

```bash
uv run pytest tests/wf_config/test_config_models.py::test_load_workflow_config_resolves_role_store_paths_relative_to_config -q
```

Expected: fail because role store paths are not resolved yet.

- [ ] **Step 3: Add path resolver helpers**

Replace `src/wf_config/loader.py` with this implementation:

```python
from __future__ import annotations

import json
from pathlib import Path

from .models import (
    FilesystemStoreConfig,
    ServerStoresConfig,
    StoreConfig,
    WorkflowConfigFile,
)


def load_workflow_config(path: str | Path) -> WorkflowConfigFile:
    """Load neutral workflow config and resolve local filesystem paths.

    Relative filesystem store roots are config-file relative so `wf --config`
    behaves the same regardless of the caller's current working directory.
    Role-specific store overrides follow the same rule.
    """

    config_path = Path(path)
    data = json.loads(config_path.read_text(encoding="utf-8"))
    config = WorkflowConfigFile.model_validate(data)
    return _resolve_store_paths(config, base_dir=config_path.parent)


def _resolve_store_paths(
    config: WorkflowConfigFile,
    *,
    base_dir: Path,
) -> WorkflowConfigFile:
    server = config.server
    resolved_stores = ServerStoresConfig(
        workflow=_resolve_store(server.stores.workflow, base_dir=base_dir),
        auth=_resolve_store(server.stores.auth, base_dir=base_dir),
        source_registry=_resolve_store(
            server.stores.source_registry,
            base_dir=base_dir,
        ),
        catalog_cache=_resolve_store(
            server.stores.catalog_cache,
            base_dir=base_dir,
        ),
    )
    return config.model_copy(
        update={
            "server": server.model_copy(
                update={
                    "store": _resolve_store(server.store, base_dir=base_dir),
                    "stores": resolved_stores,
                }
            )
        }
    )


def _resolve_store(
    store: StoreConfig | None,
    *,
    base_dir: Path,
) -> StoreConfig | None:
    if isinstance(store, FilesystemStoreConfig) and not store.root.is_absolute():
        return store.model_copy(update={"root": (base_dir / store.root).resolve()})
    return store
```

- [ ] **Step 4: Verify wf_config tests**

Run:

```bash
uv run pytest tests/wf_config/test_config_models.py -q
```

Expected: all `wf_config` model tests pass.

---

## Task 3: Add Store Role Resolver Helpers

**Files:**
- Modify: `src/wf_config/models.py`
- Test: `tests/wf_config/test_config_models.py`

- [ ] **Step 1: Add fallback behavior test**

Append this test to `tests/wf_config/test_config_models.py`:

```python
def test_server_config_resolves_missing_role_stores_to_default_store() -> None:
    config = WorkflowConfigFile.model_validate(
        {
            "version": 1,
            "server": {
                "store": {"kind": "filesystem", "root": ".default"},
                "stores": {
                    "auth": {"kind": "filesystem", "root": ".auth"},
                },
            },
        }
    )

    assert config.server.workflow_store.root.as_posix() == ".default"
    assert config.server.auth_store.root.as_posix() == ".auth"
    assert config.server.source_registry_store.root.as_posix() == ".default"
    assert config.server.catalog_cache_store.root.as_posix() == ".default"
```

- [ ] **Step 2: Run the failing test**

Run:

```bash
uv run pytest tests/wf_config/test_config_models.py::test_server_config_resolves_missing_role_stores_to_default_store -q
```

Expected: fail because `workflow_store`, `auth_store`, `source_registry_store`, and `catalog_cache_store` do not exist.

- [ ] **Step 3: Add properties on `ServerConfig`**

In `src/wf_config/models.py`, inside `ServerConfig`, add these properties after `sources`:

```python
    @property
    def workflow_store(self) -> StoreConfig:
        return self.stores.workflow or self.store

    @property
    def auth_store(self) -> StoreConfig:
        return self.stores.auth or self.store

    @property
    def source_registry_store(self) -> StoreConfig:
        return self.stores.source_registry or self.store

    @property
    def catalog_cache_store(self) -> StoreConfig:
        return self.stores.catalog_cache or self.store
```

- [ ] **Step 4: Verify resolver tests**

Run:

```bash
uv run pytest tests/wf_config/test_config_models.py::test_server_config_resolves_missing_role_stores_to_default_store -q
```

Expected: pass.

---

## Task 4: Use Workflow Role Store For Local/Static Server Composition

**Files:**
- Modify: `src/wf_server/config.py`
- Modify: `src/wf_cli/context.py`
- Modify: `src/wf_transport_rpc_http/cli.py`
- Test: `tests/wf_transport_rpc_http/test_cli.py`
- Test: `tests/wf_cli/test_context.py`

- [ ] **Step 1: Add CLI server test for workflow store override**

In `tests/wf_transport_rpc_http/test_cli.py`, find the test that captures `store_root` for `wf-rpc-server --config`. Add this new test next to it:

```python
def test_rpc_server_cli_config_uses_workflow_store_override(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config_path = tmp_path / "wf.json"
    config_path.write_text(
        json.dumps(
            {
                "version": 1,
                "server": {
                    "store": {"kind": "filesystem", "root": ".default"},
                    "stores": {
                        "workflow": {
                            "kind": "filesystem",
                            "root": ".workflow",
                        }
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    captured: dict[str, object] = {}

    def fake_build_local_static_workflow_server(root: Path):
        captured["store_root"] = root
        return _server()

    monkeypatch.setattr(
        rpc_cli,
        "build_local_static_workflow_server",
        fake_build_local_static_workflow_server,
    )
    monkeypatch.setattr(rpc_cli.uvicorn, "run", lambda *args, **kwargs: None)

    result = runner.invoke(rpc_cli.app, ["--config", str(config_path)])

    assert result.exit_code == 0, result.output
    assert captured["store_root"] == (tmp_path / ".workflow").resolve()
```

Adjust helper names (`runner`, `rpc_cli`, `_server`) to match existing `tests/wf_transport_rpc_http/test_cli.py` conventions exactly.

- [ ] **Step 2: Add local CLI context test**

In `tests/wf_cli/test_context.py`, add:

```python
def test_load_cli_context_local_uses_workflow_store_override(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config_path = tmp_path / "wf.json"
    config_path.write_text(
        json.dumps(
            {
                "version": 1,
                "client": {"target": {"kind": "local"}},
                "server": {
                    "store": {"kind": "filesystem", "root": ".default"},
                    "stores": {
                        "workflow": {
                            "kind": "filesystem",
                            "root": ".workflow",
                        }
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    captured: dict[str, object] = {}

    def fake_build_local_static_workflow_server(root: Path):
        captured["store_root"] = root
        return build_local_static_workflow_server(tmp_path / "actual")

    monkeypatch.setattr(
        "wf_cli.context.build_local_static_workflow_server",
        fake_build_local_static_workflow_server,
    )

    context = load_cli_context(config_path)

    assert context.service is None
    assert captured["store_root"] == (tmp_path / ".workflow").resolve()
```

If imports are missing, add `import json`, `from pathlib import Path`, and `build_local_static_workflow_server`/`load_cli_context` using the style already in the file.

- [ ] **Step 3: Run failing tests**

Run:

```bash
uv run pytest tests/wf_transport_rpc_http/test_cli.py::test_rpc_server_cli_config_uses_workflow_store_override tests/wf_cli/test_context.py::test_load_cli_context_local_uses_workflow_store_override -q
```

Expected: fail because both call sites still use `config.server.store`.

- [ ] **Step 4: Update local/static composition helpers**

In `src/wf_server/config.py`, change:

```python
store = config.server.store
```

to:

```python
store = config.server.workflow_store
```

In `src/wf_cli/context.py`, in the local target branch, change:

```python
store = config.server.store
```

to:

```python
store = config.server.workflow_store
```

In `src/wf_transport_rpc_http/cli.py`, in the neutral config path, change:

```python
store = workflow_config.server.store
```

to:

```python
store = workflow_config.server.workflow_store
```

Keep the existing `FilesystemStoreConfig` guards unchanged.

- [ ] **Step 5: Verify local/static store override tests**

Run:

```bash
uv run pytest tests/wf_transport_rpc_http/test_cli.py::test_rpc_server_cli_config_uses_workflow_store_override tests/wf_cli/test_context.py::test_load_cli_context_local_uses_workflow_store_override -q
```

Expected: pass.

---

## Task 5: Carry Role Store Roots Through MCP Bridge Runtime Config

**Files:**
- Modify: `src/wf_mcp/broker/models.py`
- Modify: `src/wf_mcp/broker/config.py`
- Test: `tests/wf_mcp/test_workflow_config_bridge.py`

- [ ] **Step 1: Add failing bridge test**

Append this test to `tests/wf_mcp/test_workflow_config_bridge.py`:

```python
def test_broker_config_from_workflow_config_carries_role_store_roots() -> None:
    config = WorkflowConfigFile.model_validate(
        {
            "version": 1,
            "server": {
                "store": {"kind": "filesystem", "root": ".default"},
                "stores": {
                    "workflow": {"kind": "filesystem", "root": ".workflow"},
                    "auth": {"kind": "filesystem", "root": ".auth"},
                    "source_registry": {
                        "kind": "filesystem",
                        "root": ".sources",
                    },
                    "catalog_cache": {
                        "kind": "filesystem",
                        "root": ".catalog",
                    },
                },
            },
        }
    )

    broker = broker_config_from_workflow_config(config)

    assert broker.store_roots.workflow_root == Path(".workflow")
    assert broker.store_roots.auth_root == Path(".auth")
    assert broker.store_roots.source_registry_root == Path(".sources")
    assert broker.store_roots.catalog_cache_root == Path(".catalog")
```

Ensure imports include `Path`, `WorkflowConfigFile`, and `broker_config_from_workflow_config`.

- [ ] **Step 2: Run failing test**

Run:

```bash
uv run pytest tests/wf_mcp/test_workflow_config_bridge.py::test_broker_config_from_workflow_config_carries_role_store_roots -q
```

Expected: fail because `BrokerConfig.store_roots` does not exist.

- [ ] **Step 3: Add runtime store-root bundle**

In `src/wf_mcp/broker/models.py`, add:

```python
@dataclass(frozen=True, slots=True)
class BrokerStoreRoots:
    """Resolved filesystem roots for MCP compatibility stores.

    `default_root` preserves legacy `store_root` behavior. Role roots let
    neutral config split workflow records, auth, desired source registry, and
    catalog/cache storage without changing legacy config files.
    """

    default_root: Path
    workflow_root: Path
    auth_root: Path
    source_registry_root: Path
    catalog_cache_root: Path

    @classmethod
    def from_default(cls, root: Path) -> BrokerStoreRoots:
        return cls(
            default_root=root,
            workflow_root=root,
            auth_root=root,
            source_registry_root=root,
            catalog_cache_root=root,
        )
```

Update `BrokerConfig` to include:

```python
store_roots: BrokerStoreRoots | None = None
```

Add a `__post_init__`:

```python
    def __post_init__(self) -> None:
        if self.store_roots is None:
            self.store_roots = BrokerStoreRoots.from_default(self.store_root)
```

If `BrokerConfig` is frozen, use `object.__setattr__`. If it is not frozen, direct assignment is fine. Do not remove `store_root`; legacy code still expects it.

- [ ] **Step 4: Build store roots from neutral config**

In `src/wf_mcp/broker/config.py`, import `BrokerStoreRoots`. Add helper:

```python
def _filesystem_store_root(store: object, *, role: str) -> Path:
    if not isinstance(store, FilesystemStoreConfig):
        raise ValueError(f"MCP-backed workflow server requires filesystem {role} store")
    return store.root
```

In `broker_config_from_workflow_config`, pass:

```python
store_roots=BrokerStoreRoots(
    default_root=_filesystem_store_root(config.server.store, role="default"),
    workflow_root=_filesystem_store_root(
        config.server.workflow_store,
        role="workflow",
    ),
    auth_root=_filesystem_store_root(config.server.auth_store, role="auth"),
    source_registry_root=_filesystem_store_root(
        config.server.source_registry_store,
        role="source_registry",
    ),
    catalog_cache_root=_filesystem_store_root(
        config.server.catalog_cache_store,
        role="catalog_cache",
    ),
),
```

Keep `store_root=config.server.store.root` for compatibility.

- [ ] **Step 5: Verify bridge test**

Run:

```bash
uv run pytest tests/wf_mcp/test_workflow_config_bridge.py::test_broker_config_from_workflow_config_carries_role_store_roots -q
```

Expected: pass.

---

## Task 6: Use Role Roots In MCP Service Construction

**Files:**
- Modify: `src/wf_mcp/broker/config.py`
- Test: `tests/wf_mcp/test_workflow_config_bridge.py`

- [ ] **Step 1: Add service construction test**

Append this test to `tests/wf_mcp/test_workflow_config_bridge.py`:

```python
def test_build_service_from_neutral_config_uses_role_store_roots(
    tmp_path: Path,
) -> None:
    config = WorkflowConfigFile.model_validate(
        {
            "version": 1,
            "server": {
                "store": {"kind": "filesystem", "root": str(tmp_path / "default")},
                "stores": {
                    "workflow": {
                        "kind": "filesystem",
                        "root": str(tmp_path / "workflow"),
                    },
                    "auth": {
                        "kind": "filesystem",
                        "root": str(tmp_path / "auth"),
                    },
                    "source_registry": {
                        "kind": "filesystem",
                        "root": str(tmp_path / "sources"),
                    },
                    "catalog_cache": {
                        "kind": "filesystem",
                        "root": str(tmp_path / "catalog"),
                    },
                },
                "sources": [
                    {
                        "kind": "mcp",
                        "id": "everything.default",
                        "provider": "everything",
                        "account": "default",
                        "transport": {
                            "kind": "stdio",
                            "command": "uvx",
                            "args": ["mcp-server-everything"],
                        },
                    }
                ],
            },
        }
    )

    broker = broker_config_from_workflow_config(config)
    service = build_service_from_config(broker)

    assert service.store.root == tmp_path / "auth"
    assert service.artifact_store.root == tmp_path / "workflow"
    assert service.draft_workspace_store.root == tmp_path / "workflow"
    assert service.run_store.root == tmp_path / "workflow"
    assert (tmp_path / "sources").exists()
```

If `artifact_store.root` is not public on the concrete store, assert by writing a draft/artifact/run through the store or inspect the concrete type used in nearby tests. Keep the assertion specific to the existing file store implementation.

- [ ] **Step 2: Run failing test**

Run:

```bash
uv run pytest tests/wf_mcp/test_workflow_config_bridge.py::test_build_service_from_neutral_config_uses_role_store_roots -q
```

Expected: fail because `build_service_from_config` still uses `config.store_root` for every store.

- [ ] **Step 3: Wire role roots into `build_service_from_config`**

In `src/wf_mcp/broker/config.py`, update `build_service_from_config`:

```python
    store_roots = config.store_roots or BrokerStoreRoots.from_default(config.store_root)
    workflow_stores = file_workflow_stores(store_roots.workflow_root)
    service = WfMcpService(
        store=FileStore(store_roots.auth_root),
        artifact_store=workflow_stores.artifact_store,
        draft_workspace_store=workflow_stores.draft_workspace_store,
        run_store=workflow_stores.run_store,
        ...
    )
    source_registry_store = FileSourceRegistryStore(store_roots.source_registry_root)
```

Catalog/cache still goes through `FileStore(store_roots.auth_root)` in this slice unless there is already a clean constructor seam to split auth and catalog. Add this comment above `store=FileStore(...)`:

```python
# FileStore still owns both auth files and catalog snapshots. Role roots are
# carried separately so a later FileStore split can move catalog_cache without a
# config migration.
```

This comment is required because docs mention the limitation and future agents see code first.

- [ ] **Step 4: Verify MCP bridge tests**

Run:

```bash
uv run pytest tests/wf_mcp/test_workflow_config_bridge.py -q
```

Expected: all tests pass.

---

## Task 7: Docs And Final Verification

**Files:**
- Modify: `docs/current_roadmap.md`
- Modify: `docs/superpowers/specs/2026-06-03-workflow-config-targets-and-sources.md`
- Modify: `docs/wf_cli.md`

- [ ] **Step 1: Update docs status**

In `docs/current_roadmap.md`, update the role-specific server stores bullet to say:

```markdown
  - First role-specific store slice complete: neutral config now accepts optional
    `server.stores.workflow`, `server.stores.auth`,
    `server.stores.source_registry`, and `server.stores.catalog_cache`
    filesystem overrides. Missing roles still fall back to `server.store`.
    MCP compatibility still uses one `FileStore` class for auth and catalog
    snapshots internally; the separate catalog root is carried for the future
    store split.
```

In `docs/superpowers/specs/2026-06-03-workflow-config-targets-and-sources.md`, add a short status sentence under `### Store Roles`:

```markdown
Implementation status: first filesystem-only slice implemented. Role overrides
are optional and fall back to `server.store`.
```

In `docs/wf_cli.md`, update the store paragraph to say role-specific overrides are supported for filesystem stores, not only future.

- [ ] **Step 2: Run focused tests**

Run:

```bash
uv run pytest tests/wf_config/test_config_models.py tests/wf_mcp/test_workflow_config_bridge.py tests/wf_transport_rpc_http/test_cli.py tests/wf_cli/test_context.py -q
```

Expected: pass.

- [ ] **Step 3: Run lint and type checks**

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

Expected: existing suite shape, currently around `1195 passed, 1 skipped, 1 xfailed`.

- [ ] **Step 5: Final report**

Report:

- files changed
- tests run and exact output
- whether full suite was run
- any deviations
- the remaining limitation: `FileStore` still combines auth and catalog snapshot storage, even though config now carries separate role roots

---

## Self-Review Notes

- Scope is one slice: config model, path resolution, local/static composition, MCP bridge role roots.
- No SQL/object/secret-manager backend implementation.
- No source registry behavior changes except choosing the configured registry root.
- No automatic migration edits; existing configs keep working because every role falls back to `server.store`.
