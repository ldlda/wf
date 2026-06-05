# RPC Transport Config Boundary Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove direct `wf_mcp` imports from `wf_transport_rpc_http` now that neutral `wf_config.server.sources[]` can describe MCP sources.

**Architecture:** Keep JSON-RPC transport modules focused on serving a `WorkflowServer`. Move config-to-server composition into a server-layer module that can select local/static or MCP-backed composition by config source kind. `wf_server.context` remains MCP-free; the new config composition module is the explicit boundary for source-provider selection.

**Tech Stack:** Typer CLI, `wf_config.WorkflowConfigFile`, `wf_server.WorkflowServer`, existing MCP-backed builder in `wf_mcp.broker.server`, AST import-direction tests.

---

## File Structure

- Create `src/wf_server/config.py`: server composition from neutral workflow config and legacy MCP config path.
- Modify `src/wf_transport_rpc_http/cli.py`: import server composition helpers from `wf_server.config`, not `wf_mcp.broker`.
- Modify `tests/wf_transport_rpc_http/test_cli.py`: monkeypatch new helper paths.
- Modify `tests/wf_transport_rpc_http/test_import_direction.py`: no change expected; it should pass once direct imports are removed.
- Create `tests/wf_server/test_config_composition.py`: cover local/static and MCP-source selection.
- Modify docs after implementation.

## Current Context

`src/wf_transport_rpc_http/cli.py` currently imports:

```python
from wf_mcp.broker import (
    build_workflow_server_from_config,
    build_workflow_server_from_workflow_config,
    load_broker_config,
)
```

That makes `tests/wf_transport_rpc_http/test_import_direction.py` fail:

```python
def test_wf_transport_rpc_http_imports_no_wfmcp_modules() -> None:
    ...
    assert violations == []
```

Do not remove the test. The transport package should not import MCP modules directly.

`src/wf_server/context.py` has a narrower guard in `tests/wf_server/test_local_static_server.py` that only checks `context.py` for `WfMcpService`. Keep `context.py` untouched.

## Task 1: Add Server Composition Tests

**Files:**
- Create: `tests/wf_server/test_config_composition.py`

- [ ] **Step 1: Create test file**

Create `tests/wf_server/test_config_composition.py`:

```python
from __future__ import annotations

from wf_config import WorkflowConfigFile
from wf_server.config import (
    build_workflow_server_from_legacy_mcp_config,
    build_workflow_server_from_workflow_config,
)
from wf_server.context import WorkflowServer


def test_build_workflow_server_from_workflow_config_uses_local_static_for_no_mcp_sources(
    tmp_path,
) -> None:
    config = WorkflowConfigFile.model_validate(
        {
            "version": 1,
            "server": {
                "store": {"kind": "filesystem", "root": str(tmp_path / "store")},
                "sources": [{"kind": "stdlib", "id": "wf.std"}],
            },
        }
    )

    server = build_workflow_server_from_workflow_config(config)

    assert isinstance(server, WorkflowServer)
    assert server.config.store_root == tmp_path / "store"
    assert server.source_registry_admin is None


def test_build_workflow_server_from_workflow_config_uses_mcp_builder_for_mcp_sources(
    monkeypatch, tmp_path
) -> None:
    captured = {}

    def fake_builder(config):
        captured["source_kinds"] = [source.kind for source in config.server.sources]
        return "mcp-server"

    monkeypatch.setattr(
        "wf_server.config._build_mcp_workflow_server_from_workflow_config",
        fake_builder,
    )
    config = WorkflowConfigFile.model_validate(
        {
            "version": 1,
            "server": {
                "store": {"kind": "filesystem", "root": str(tmp_path / "store")},
                "sources": [
                    {
                        "kind": "mcp",
                        "id": "everything.default",
                        "provider": "everything",
                        "account": "default",
                        "transport": {"kind": "stdio", "command": "uvx"},
                    }
                ],
            },
        }
    )

    server = build_workflow_server_from_workflow_config(config)

    assert server == "mcp-server"
    assert captured["source_kinds"] == ["mcp"]


def test_build_workflow_server_from_legacy_mcp_config_delegates_to_mcp_builder(
    monkeypatch, tmp_path
) -> None:
    captured = {}

    def fake_builder(path):
        captured["path"] = path
        return "legacy-mcp-server"

    monkeypatch.setattr(
        "wf_server.config._build_mcp_workflow_server_from_legacy_config",
        fake_builder,
    )
    legacy_path = tmp_path / "wf_mcp.config.json"
    legacy_path.write_text('{"store_root": "store", "connections": []}', encoding="utf-8")

    server = build_workflow_server_from_legacy_mcp_config(legacy_path)

    assert server == "legacy-mcp-server"
    assert captured["path"] == legacy_path
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
uv run pytest tests/wf_server/test_config_composition.py -q
```

Expected: fail because `wf_server.config` does not exist.

## Task 2: Implement Server Config Composition Module

**Files:**
- Create: `src/wf_server/config.py`

- [ ] **Step 1: Create module**

Create `src/wf_server/config.py`:

```python
from __future__ import annotations

from pathlib import Path

from wf_config import FilesystemStoreConfig, WorkflowConfigFile

from .context import WorkflowServer, build_local_static_workflow_server


def _has_mcp_sources(config: WorkflowConfigFile) -> bool:
    return any(getattr(source, "kind", None) == "mcp" for source in config.server.sources)


def _build_mcp_workflow_server_from_workflow_config(
    config: WorkflowConfigFile,
) -> WorkflowServer:
    """Build an MCP-backed server from neutral config.

    This import is intentionally isolated here: transport packages should not
    import MCP modules, while this server composition boundary is allowed to
    select source-provider implementations by source kind.
    """
    from wf_mcp.broker import build_workflow_server_from_workflow_config

    return build_workflow_server_from_workflow_config(config)


def _build_mcp_workflow_server_from_legacy_config(path: Path) -> WorkflowServer:
    """Build an MCP-backed server from legacy broker config."""
    from wf_mcp.broker import build_workflow_server_from_config, load_broker_config

    return build_workflow_server_from_config(load_broker_config(path))


def build_workflow_server_from_workflow_config(
    config: WorkflowConfigFile,
) -> WorkflowServer:
    """Build a WorkflowServer from neutral workflow config.

    Local/static configs use built-in sources. Configs with `kind: "mcp"`
    sources delegate to the MCP provider adapter.
    """
    if _has_mcp_sources(config):
        return _build_mcp_workflow_server_from_workflow_config(config)
    store = config.server.store
    if not isinstance(store, FilesystemStoreConfig):
        raise ValueError("wf-rpc-server currently requires filesystem store")
    return build_local_static_workflow_server(store.root)


def build_workflow_server_from_legacy_mcp_config(path: str | Path) -> WorkflowServer:
    """Build a WorkflowServer from legacy wf_mcp.config.json.

    Prefer neutral `wf_config` for new setups. This compatibility hook keeps the
    transport CLI free of direct MCP imports while existing users migrate.
    """
    return _build_mcp_workflow_server_from_legacy_config(Path(path))
```

- [ ] **Step 2: Run tests**

Run:

```bash
uv run pytest tests/wf_server/test_config_composition.py -q
```

Expected: pass.

- [ ] **Step 3: Run import-boundary check**

Run:

```bash
uv run pytest tests/wf_server/test_local_static_server.py::test_wf_server_context_imports_no_wfmcp_service -q
```

Expected: pass because `context.py` was not changed.

## Task 3: Update RPC CLI to Use Server Composition Helpers

**Files:**
- Modify: `src/wf_transport_rpc_http/cli.py`
- Modify: `tests/wf_transport_rpc_http/test_cli.py`

- [ ] **Step 1: Update imports**

Replace:

```python
from wf_mcp.broker import (
    build_workflow_server_from_config,
    build_workflow_server_from_workflow_config,
    load_broker_config,
)

from wf_server import build_local_static_workflow_server
```

with:

```python
from wf_server.config import (
    build_workflow_server_from_legacy_mcp_config,
    build_workflow_server_from_workflow_config,
)
from wf_server.context import build_local_static_workflow_server
```

- [ ] **Step 2: Update legacy mcp config branch**

Replace:

```python
    if mcp_config is not None:
        broker_config = load_broker_config(mcp_config)
        server = build_workflow_server_from_config(broker_config)
```

with:

```python
    if mcp_config is not None:
        server = build_workflow_server_from_legacy_mcp_config(mcp_config)
```

- [ ] **Step 3: Remove duplicated mcp source detection from CLI**

Inside the `if config is not None:` block, remove:

```python
        has_mcp_sources = any(
            getattr(source, "kind", None) == "mcp"
            for source in workflow_config.server.sources
        )
        if server is None and has_mcp_sources:
            server = build_workflow_server_from_workflow_config(workflow_config)
```

Then replace the local/static store handling block:

```python
        store = workflow_config.server.store
        if server is None and not isinstance(store, FilesystemStoreConfig):
            raise typer.BadParameter(
                "wf-rpc-server currently requires filesystem store"
            )
        if server is None:
            resolved_store_root = resolved_store_root or store.root
```

with:

```python
        store = workflow_config.server.store
        if server is None and store_root is None:
            server = build_workflow_server_from_workflow_config(workflow_config)
        elif server is None:
            if not isinstance(store, FilesystemStoreConfig):
                raise typer.BadParameter(
                    "wf-rpc-server currently requires filesystem store"
                )
            resolved_store_root = resolved_store_root or store.root
```

Keep `--store-root` as an override for local/static configs. `--store-root` is still forbidden with `--mcp-config`; do not add new behavior there.

- [ ] **Step 4: Update tests monkeypatch paths**

In `tests/wf_transport_rpc_http/test_cli.py`, update existing monkeypatches to
match the new boundary.

For `test_rpc_server_cli_uses_configured_store_and_transport`, stop monkeypatching
`build_local_static_workflow_server`; the CLI now delegates config-based server
composition to `build_workflow_server_from_workflow_config`.

Replace:

```python
def fake_build_server(root):
    captured["store_root"] = root
    return object()
```

with:

```python
def fake_build_server(config):
    captured["store_root"] = config.server.store.root
    return object()
```

Replace this monkeypatch:

```python
monkeypatch.setattr(
    "wf_transport_rpc_http.cli.build_local_static_workflow_server",
    fake_build_server,
)
```

with:

```python
monkeypatch.setattr(
    "wf_transport_rpc_http.cli.build_workflow_server_from_workflow_config",
    fake_build_server,
)
```

Keep the assertion:

```python
assert captured["store_root"] == (tmp_path / ".wf_store").resolve()
```

For legacy MCP config tests, replace monkeypatch paths:

```python
"wf_transport_rpc_http.cli.build_workflow_server_from_config"
"wf_transport_rpc_http.cli.build_workflow_server_from_workflow_config"
```

with:

```python
"wf_transport_rpc_http.cli.build_workflow_server_from_legacy_mcp_config"
"wf_transport_rpc_http.cli.build_workflow_server_from_workflow_config"
```

If a test currently monkeypatches `load_broker_config`, remove that monkeypatch and have the fake legacy builder capture the config path directly.

For `test_rpc_server_cli_uses_mcp_config_server`, replace the two fake helpers:

```python
def fake_load_broker_config(path):
    captured["mcp_config_path"] = path
    return "broker-config"

def fake_build_mcp_server(config):
    captured["mcp_config"] = config
    return object()
```

with one helper:

```python
def fake_build_mcp_server(path):
    captured["mcp_config_path"] = path
    return object()
```

Replace the two monkeypatches:

```python
monkeypatch.setattr("wf_transport_rpc_http.cli.load_broker_config", fake_load_broker_config)
monkeypatch.setattr(
    "wf_transport_rpc_http.cli.build_workflow_server_from_config",
    fake_build_mcp_server,
)
```

with:

```python
monkeypatch.setattr(
    "wf_transport_rpc_http.cli.build_workflow_server_from_legacy_mcp_config",
    fake_build_mcp_server,
)
```

Remove the assertion:

```python
assert captured["mcp_config"] == "broker-config"
```

- [ ] **Step 5: Run CLI tests**

Run:

```bash
uv run pytest tests/wf_transport_rpc_http/test_cli.py -q
```

Expected: pass.

## Task 4: Restore Transport Import-Direction Guard

**Files:**
- Test: `tests/wf_transport_rpc_http/test_import_direction.py`

- [ ] **Step 1: Run guard**

Run:

```bash
uv run pytest tests/wf_transport_rpc_http/test_import_direction.py -q
```

Expected: pass. If it fails, inspect `src/wf_transport_rpc_http` for any remaining `wf_mcp` imports and remove them.

- [ ] **Step 2: Run wider RPC subset**

Run:

```bash
uv run pytest tests/wf_transport_rpc_http tests/wf_cli/test_remote_target.py -q
```

Expected: pass. The prior known failure should be gone.

## Task 5: Update Docs and Mark Cleanup Complete

**Files:**
- Modify: `docs/current_roadmap.md`
- Modify: `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`

- [ ] **Step 1: Update roadmap**

In `docs/current_roadmap.md`, under "Transport package boundary cleanup", append:

```markdown
    Completed: `wf_transport_rpc_http` no longer imports `wf_mcp`; server
    composition from neutral or legacy MCP config lives behind `wf_server.config`.
```

- [ ] **Step 2: Update long-lived API spec**

In `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`, under "Transport package boundary cleanup", append:

```markdown
   Completed when `tests/wf_transport_rpc_http/test_import_direction.py` passes
   and the RPC transport CLI imports only `wf_config`, `wf_server`, and transport
   modules for server construction.
```

## Task 6: Final Verification and Commit

**Files:**
- All touched files.

- [ ] **Step 1: Run focused tests**

Run:

```bash
uv run pytest tests/wf_server/test_config_composition.py tests/wf_transport_rpc_http tests/wf_cli/test_remote_target.py -q
```

Expected: pass.

- [ ] **Step 2: Run lint/type checks**

Run:

```bash
uv run ruff check src/wf_server src/wf_transport_rpc_http tests/wf_server tests/wf_transport_rpc_http
uv run basedpyright --level error src/wf_server src/wf_transport_rpc_http tests/wf_server tests/wf_transport_rpc_http
```

Expected: pass with 0 errors.

- [ ] **Step 3: Commit**

Run:

```bash
git add src/wf_server src/wf_transport_rpc_http tests/wf_server tests/wf_transport_rpc_http docs/current_roadmap.md docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md
git commit -m "refactor: isolate rpc server config composition"
```

## Self-Review Checklist

- `src/wf_transport_rpc_http` contains no direct `wf_mcp` imports.
- `src/wf_server/context.py` remains MCP-free.
- The MCP-specific import is isolated in `src/wf_server/config.py` with a docstring explaining the boundary.
- `wf-rpc-server --config` still works for local/static and MCP-source neutral configs.
- `wf-rpc-server --mcp-config` still works as a legacy compatibility path.
