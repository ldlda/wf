# RPC Server MCP Config Hookup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let `wf-rpc-server` serve a real MCP-backed `WorkflowServer` from an MCP broker config file, so `wf --url ...` can target a long-lived server with MCP sources and source-registry/admin surfaces.

**Architecture:** Keep JSON-RPC transport code as the place that selects a server composition for the process. `--mcp-config` loads legacy MCP broker config and calls `wf_mcp.broker.build_workflow_server_from_config`; existing `--store-root` / neutral `--config` behavior continues to build the local/static server. The transport still receives only a neutral `WorkflowServer` and calls `create_rpc_app(server)`.

**Tech Stack:** Python 3.14, Typer, `wf_transport_rpc_http`, `wf_mcp.broker`, `wf_server`, pytest, ruff, basedpyright.

---

## Current Context

Implemented before this plan:

- `wf_mcp.broker.server.build_workflow_server_from_config(config)` returns a neutral `WorkflowServer`.
- `wf_transport_rpc_http.cli.serve()` currently always calls `build_local_static_workflow_server(...)`.
- Existing CLI tests in `tests/wf_transport_rpc_http/test_cli.py` monkeypatch server construction, `create_rpc_app`, and `uvicorn.run`; use that pattern.

Out of scope:

- No new neutral config schema for MCP source transports.
- No server hot reload.
- No process manager/daemon work.
- No auth redesign.
- No real socket startup in tests.

---

## File Structure

- Modify `src/wf_transport_rpc_http/cli.py`
  - Add `--mcp-config`.
  - Select MCP-backed server when `--mcp-config` is supplied.
  - Keep local/static path unchanged for existing config/store-root flows.
- Modify `tests/wf_transport_rpc_http/test_cli.py`
  - Add help assertion for `--mcp-config`.
  - Add server-selection tests.
- Modify `docs/wf_cli.md`
  - Document local/static server and MCP-backed server startup examples.
- Modify `docs/current_roadmap.md`
  - Mark RPC server CLI MCP config hookup complete.
- Modify `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`
  - Record Slice 5 status.

---

### Task 1: Add MCP Config Server Selection to RPC CLI

**Files:**
- Modify: `src/wf_transport_rpc_http/cli.py`
- Modify: `tests/wf_transport_rpc_http/test_cli.py`

- [ ] **Step 1: Add failing help and selection tests**

In `tests/wf_transport_rpc_http/test_cli.py`, update `test_rpc_server_cli_help_mentions_store_root`:

```python
def test_rpc_server_cli_help_mentions_store_root() -> None:
    result = CliRunner().invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "--store-root" in result.output
    assert "--mcp-config" in result.output
    assert "--host" in result.output
    assert "--port" in result.output
```

Add:

```python
def test_rpc_server_cli_uses_mcp_config_server(monkeypatch, tmp_path) -> None:
    config_path = tmp_path / "wf_mcp.config.json"
    config_path.write_text(
        json.dumps(
            {
                "store_root": str(tmp_path / "store"),
                "connections": [],
            }
        ),
        encoding="utf-8",
    )
    captured: dict[str, object] = {}

    def fake_load_broker_config(path):
        captured["mcp_config_path"] = path
        return "broker-config"

    def fake_build_mcp_server(config):
        captured["mcp_config"] = config
        return object()

    def fake_create_rpc_app(server, *, rpc_path="/rpc"):
        captured["server"] = server
        captured["rpc_path"] = rpc_path
        return object()

    def fake_uvicorn_run(app_obj, *, host, port, access_log):
        captured["app"] = app_obj
        captured["host"] = host
        captured["port"] = port
        captured["access_log"] = access_log

    monkeypatch.setattr("wf_transport_rpc_http.cli.load_broker_config", fake_load_broker_config)
    monkeypatch.setattr(
        "wf_transport_rpc_http.cli.build_workflow_server_from_config",
        fake_build_mcp_server,
    )
    monkeypatch.setattr("wf_transport_rpc_http.cli.create_rpc_app", fake_create_rpc_app)
    monkeypatch.setattr("wf_transport_rpc_http.cli.uvicorn.run", fake_uvicorn_run)

    result = CliRunner().invoke(
        app,
        [
            "--mcp-config",
            str(config_path),
            "--host",
            "127.0.0.9",
            "--port",
            "9988",
        ],
    )

    assert result.exit_code == 0, result.output
    assert captured["mcp_config_path"] == config_path
    assert captured["mcp_config"] == "broker-config"
    assert captured["server"] is not None
    assert captured["rpc_path"] == "/rpc"
    assert captured["host"] == "127.0.0.9"
    assert captured["port"] == 9988
    assert captured["access_log"] is False
```

Add conflict test:

```python
def test_rpc_server_cli_rejects_mcp_config_with_store_root(tmp_path) -> None:
    config_path = tmp_path / "wf_mcp.config.json"
    config_path.write_text(
        json.dumps({"store_root": str(tmp_path / "store"), "connections": []}),
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        app,
        [
            "--mcp-config",
            str(config_path),
            "--store-root",
            str(tmp_path / "other"),
        ],
    )

    assert result.exit_code != 0
    assert "--mcp-config cannot be combined with --store-root" in result.output
```

Run:

```bash
uv run pytest tests/wf_transport_rpc_http/test_cli.py -q
```

Expected: FAIL because `--mcp-config` is not implemented.

- [ ] **Step 2: Implement `--mcp-config` option**

In `src/wf_transport_rpc_http/cli.py`, import:

```python
from wf_mcp.broker import build_workflow_server_from_config, load_broker_config
```

Add option to `serve(...)`:

```python
mcp_config: Path | None = typer.Option(
    None,
    "--mcp-config",
    help="Path to MCP broker config JSON for MCP-backed workflow server.",
),
```

Update docstring:

```python
"""Serve WorkflowApi over JSON-RPC HTTP."""
```

Before resolving local/static store root, add validation:

```python
if mcp_config is not None and store_root is not None:
    raise typer.BadParameter("--mcp-config cannot be combined with --store-root")
```

If `mcp_config` is supplied, build MCP server:

```python
server = None
if mcp_config is not None:
    broker_config = load_broker_config(mcp_config)
    server = build_workflow_server_from_config(broker_config)
```

Then keep existing neutral `--config` parsing for host/port/path. When selecting
the final server, only call `build_local_static_workflow_server(...)` if
`server is None`:

```python
if server is None:
    if resolved_store_root is None:
        raise typer.BadParameter(
            "--store-root is required when --config is not supplied"
        )
    server = build_local_static_workflow_server(resolved_store_root)
```

Important:

- `--config` may still be used with `--mcp-config` for transport host/port/path.
- `--mcp-config` owns the workflow server/store/source side.
- `--store-root` is local/static-only and must conflict with `--mcp-config`.

- [ ] **Step 3: Run CLI tests**

Run:

```bash
uv run pytest tests/wf_transport_rpc_http/test_cli.py -q
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add src/wf_transport_rpc_http/cli.py tests/wf_transport_rpc_http/test_cli.py
git commit -m "feat: serve mcp backed rpc server"
```

---

### Task 2: Prove MCP Config Server Supports Registry RPC Through CLI Path

**Files:**
- Modify: `tests/wf_transport_rpc_http/test_cli.py`

- [ ] **Step 1: Add integration-style construction test**

Add this test to `tests/wf_transport_rpc_http/test_cli.py`:

```python
def test_rpc_server_cli_mcp_config_builds_registry_capable_server(monkeypatch, tmp_path) -> None:
    config_path = tmp_path / "wf_mcp.config.json"
    config_path.write_text(
        json.dumps(
            {
                "store_root": str(tmp_path / "store"),
                "connections": [],
            }
        ),
        encoding="utf-8",
    )
    captured: dict[str, object] = {}

    def fake_create_rpc_app(server, *, rpc_path="/rpc"):
        captured["source_registry_admin"] = server.source_registry_admin
        captured["rpc_path"] = rpc_path
        return object()

    def fake_uvicorn_run(app_obj, *, host, port, access_log):
        captured["host"] = host
        captured["port"] = port

    monkeypatch.setattr("wf_transport_rpc_http.cli.create_rpc_app", fake_create_rpc_app)
    monkeypatch.setattr("wf_transport_rpc_http.cli.uvicorn.run", fake_uvicorn_run)

    result = CliRunner().invoke(app, ["--mcp-config", str(config_path)])

    assert result.exit_code == 0, result.output
    assert captured["source_registry_admin"] is not None
    assert captured["rpc_path"] == "/rpc"
    assert captured["host"] == "127.0.0.1"
    assert captured["port"] == 8765
```

This test uses the real `load_broker_config()` and
`build_workflow_server_from_config()` but still avoids starting uvicorn.

- [ ] **Step 2: Run CLI tests**

Run:

```bash
uv run pytest tests/wf_transport_rpc_http/test_cli.py -q
```

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/wf_transport_rpc_http/test_cli.py
git commit -m "test: cover mcp config rpc server path"
```

---

### Task 3: Update User-Facing Docs and Roadmap

**Files:**
- Modify: `docs/wf_cli.md`
- Modify: `docs/current_roadmap.md`
- Modify: `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`

- [ ] **Step 1: Add RPC server startup docs**

In `docs/wf_cli.md`, after the opening config paragraph, add:

```markdown
## Remote Server

Start a local/static JSON-RPC workflow server:

```bash
wf-rpc-server --store-root .wf_store --host 127.0.0.1 --port 8765
```

Start a JSON-RPC server backed by MCP broker config and MCP-capable sources:

```bash
wf-rpc-server --mcp-config wf_mcp.config.json --host 127.0.0.1 --port 8765
```

Then point `wf` at it:

```bash
wf --url http://127.0.0.1:8765/rpc cap list
wf --url http://127.0.0.1:8765/rpc admin registry list
```

`--mcp-config` owns the server's workflow stores, MCP connections, and source
registry. `--store-root` is for the local/static server path and cannot be
combined with `--mcp-config`.
```

- [ ] **Step 2: Update roadmap**

In `docs/current_roadmap.md`, under **Durable API service shape**, add:

```markdown
   - Completed: `wf-rpc-server --mcp-config wf_mcp.config.json` starts the
      JSON-RPC transport over an MCP-backed `WorkflowServer`, making the remote
      CLI path usable with MCP sources and desired source registry operations.
```

- [ ] **Step 3: Update long-lived API spec**

In `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`,
update status from "Slices 1-4 implemented" to "Slices 1-5 implemented", and
add under implementation status:

```markdown
- Slice 5 complete: `wf-rpc-server --mcp-config <path>` starts JSON-RPC over an
  MCP-backed `WorkflowServer`; `--store-root` remains local/static-only.
```

- [ ] **Step 4: Run docs grep**

Run:

```bash
rg -n "wf-rpc-server --mcp-config|Slices 1-5 implemented|--store-root.*--mcp-config" docs/wf_cli.md docs/current_roadmap.md docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md
```

Expected: all three docs mention the new server path.

- [ ] **Step 5: Commit**

```bash
git add docs/wf_cli.md docs/current_roadmap.md docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md
git commit -m "docs: document mcp backed rpc server"
```

---

### Task 4: Final Verification

**Files:**
- Verify only.

- [ ] **Step 1: Run focused tests**

Run:

```bash
uv run pytest tests/wf_transport_rpc_http/test_cli.py tests/wf_transport_rpc_http/test_mcp_backed_server_rpc.py tests/wf_mcp/test_mcp_workflow_server.py -q
```

Expected: all tests pass.

- [ ] **Step 2: Run lint and type checks**

Run:

```bash
uv run ruff check src/wf_transport_rpc_http/cli.py tests/wf_transport_rpc_http/test_cli.py
uv run basedpyright --level error src/wf_transport_rpc_http/cli.py tests/wf_transport_rpc_http/test_cli.py
git diff --check
```

Expected: all commands exit 0. CRLF warnings from Git are acceptable; whitespace
errors are not.

- [ ] **Step 3: Final report**

Report:

- changed files
- verification output
- exact command a user can run for MCP-backed RPC server
- any deviations from this plan

Do not run the full suite unless the focused verification is green.

---

## Self-Review

- Product fit: this is the smallest visible hook after MCP-backed `WorkflowServer` construction.
- Boundary: `wf_transport_rpc_http.cli` imports `wf_mcp.broker` only for process startup selection; JSON-RPC app/method modules still take a neutral `WorkflowServer`.
- Config semantics: `--mcp-config` and `--store-root` conflict because they own different server composition paths.
- Testing: no real socket startup; tests monkeypatch `uvicorn.run`.
