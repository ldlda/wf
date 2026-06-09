# wf Status And Product Smoke Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only `wf status` command that tells users what target they are connected to and summarizes server/source/admin state, then add a small product smoke test path for the remote server workflow.

**Architecture:** Do not add a new backend status endpoint in this slice. The CLI should compose status from existing surfaces already available on `CliContext`: workflow capability list, source inventory, admin connection/status/events/auth summaries, and source registry summaries when available. Local/static servers and remote RPC servers should both work; unavailable optional admin surfaces should report `available: false` instead of failing the whole command.

**Tech Stack:** Python 3.14, Typer CLI, existing `WorkflowApiSurface` / admin surface protocols, JSON output via `wf_cli.io.emit_json`, pytest, basedpyright, ruff.

---

## File Structure

- Create: `src/wf_cli/commands/status.py`
  - Owns `wf status`.
  - Builds one compact JSON payload from existing CLI context surfaces.
  - Contains small private helpers for safe optional calls.
- Modify: `src/wf_cli/app.py`
  - Register `status` as a top-level command.
- Modify: `tests/wf_cli/test_remote_target.py`
  - Add remote status test using the existing ASGI-backed RPC client patch seam.
- Create: `tests/wf_cli/test_status.py`
  - Add local/static and partial-unavailable behavior tests.
- Modify: `docs/wf_cli.md`
  - Document `wf status`.
- Modify: `docs/current_roadmap.md`
  - Mark this slice complete after implementation.

Do not modify `wf_server`, `wf_api`, or `wf_transport_rpc_http` unless tests prove an existing surface is missing.

---

## Payload Contract

`wf status` must emit JSON:

```json
{
  "target": {
    "mode": "local|remote",
    "config_path": "wf.config.json",
    "url": "http://127.0.0.1:8765/rpc|null"
  },
  "workflow": {
    "capability_count": 88,
    "sample_capabilities": ["wf.std.constant"]
  },
  "sources": {
    "available": true,
    "source_count": 7,
    "sample_sources": ["wf.std"]
  },
  "admin": {
    "available": true,
    "connection_count": 4,
    "status_count": 4,
    "event_count": 12,
    "auth_count": 1
  },
  "registry": {
    "available": true,
    "entry_count": 0
  }
}
```

Rules:

- Counts may be `0`.
- Optional sections must keep `available: false` when unavailable.
- Do not include auth payload values.
- Do not include full capability/source/connection lists; this command is a quick orientation summary.
- Do not mutate config, stores, registry, auth, or catalog.

---

### Task 1: Add Local Status Command Tests

**Files:**
- Create: `tests/wf_cli/test_status.py`
- Create later: `src/wf_cli/commands/status.py`
- Modify later: `src/wf_cli/app.py`

- [ ] **Step 1: Write failing local status test**

Create `tests/wf_cli/test_status.py`:

```python
from __future__ import annotations

import json

from typer.testing import CliRunner

from wf_cli.app import app


def test_wf_status_local_static_target(tmp_path) -> None:
    config_path = tmp_path / "wf.json"
    config_path.write_text(
        json.dumps(
            {
                "version": 1,
                "client": {"target": {"kind": "local"}},
                "server": {
                    "store": {
                        "kind": "filesystem",
                        "root": str(tmp_path / "store"),
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        app,
        [
            "--config",
            str(config_path),
            "--local",
            "status",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["target"]["mode"] == "local"
    assert payload["target"]["config_path"] == str(config_path)
    assert payload["target"]["url"] is None
    assert payload["workflow"]["capability_count"] >= 1
    assert "wf.std.constant" in payload["workflow"]["sample_capabilities"]
    assert payload["sources"]["available"] is True
    assert payload["sources"]["source_count"] >= 1
    assert payload["admin"]["available"] is True
    assert payload["registry"]["available"] is False
```

- [ ] **Step 2: Run the failing test**

Run:

```powershell
uv run pytest tests/wf_cli/test_status.py::test_wf_status_local_static_target -q
```

Expected: FAIL because `wf status` is not registered.

---

### Task 2: Implement `wf status`

**Files:**
- Create: `src/wf_cli/commands/status.py`
- Modify: `src/wf_cli/app.py`

- [ ] **Step 1: Create status command module**

Create `src/wf_cli/commands/status.py`:

```python
from __future__ import annotations

from typing import Any

import typer

from wf_cli.context import CliTyperState, load_cli_context_from_typer
from wf_cli.io import emit_json
from wf_cli.remote_errors import run_cli_operation


def status_command(ctx: typer.Context) -> None:
    """Print a compact read-only summary of the selected workflow target."""

    state = CliTyperState.from_context(ctx)
    context = load_cli_context_from_typer(ctx)
    payload: dict[str, Any] = {
        "target": {
            "mode": "remote" if state.rpc_url is not None else "local",
            "config_path": str(context.config_path),
            "url": state.rpc_url,
        },
        "workflow": _workflow_status(context),
        "sources": _sources_status(context),
        "admin": _admin_status(context),
        "registry": _registry_status(context),
    }
    emit_json(payload)


def _workflow_status(context) -> dict[str, Any]:
    capabilities = run_cli_operation(
        context,
        context.handlers.list_capabilities(limit=20),
    )
    items = capabilities.get("capabilities", [])
    names = [
        item.get("name")
        for item in items
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    ]
    return {
        "capability_count": len(items),
        "sample_capabilities": names[:5],
    }


def _sources_status(context) -> dict[str, Any]:
    try:
        payload = run_cli_operation(context, context.source_admin.list_sources(limit=20))
    except Exception as exc:
        return _unavailable(exc)
    sources = payload.get("sources", [])
    source_ids = [
        item.get("id")
        for item in sources
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    ]
    return {
        "available": True,
        "source_count": len(sources),
        "sample_sources": source_ids[:5],
    }


def _admin_status(context) -> dict[str, Any]:
    try:
        connections = run_cli_operation(context, context.admin.list_connections())
        statuses = run_cli_operation(context, context.admin.get_connection_statuses())
        events = run_cli_operation(context, context.admin.list_events())
        auth = run_cli_operation(context, context.admin.list_auth_records())
    except Exception as exc:
        return _unavailable(exc)
    return {
        "available": True,
        "connection_count": len(connections.get("connections", [])),
        "status_count": len(statuses.get("statuses", [])),
        "event_count": len(events.get("events", [])),
        "auth_count": len(auth.get("auth_records", [])),
    }


def _registry_status(context) -> dict[str, Any]:
    admin = context.source_registry_admin
    if admin is None:
        return {"available": False, "reason": "source registry admin is not configured"}
    try:
        payload = run_cli_operation(context, admin.list_registry_entries(limit=20))
    except Exception as exc:
        return _unavailable(exc)
    return {
        "available": True,
        "entry_count": len(payload.get("entries", [])),
    }


def _unavailable(exc: Exception) -> dict[str, Any]:
    return {
        "available": False,
        "reason": str(exc),
    }
```

- [ ] **Step 2: Register top-level command**

Modify `src/wf_cli/app.py`:

```python
from .commands import (
    admin,
    artifacts,
    caps,
    deployments,
    docs,
    drafts,
    explain,
    runs,
    schema,
    sources,
    status,
)
```

Add registration near the other top-level commands:

```python
app.command("status")(status.status_command)
```

- [ ] **Step 3: Run local status test**

Run:

```powershell
uv run pytest tests/wf_cli/test_status.py::test_wf_status_local_static_target -q
```

Expected: PASS.

- [ ] **Step 4: Typecheck the new command**

If basedpyright reports unknown types in helper functions, add local annotations by importing `CliContext`:

```python
from wf_cli.context import CliContext, CliTyperState, load_cli_context_from_typer
```

Then annotate helpers:

```python
def _workflow_status(context: CliContext) -> dict[str, Any]:
```

Run:

```powershell
uv run basedpyright --level error src\wf_cli\commands\status.py tests\wf_cli\test_status.py
```

Expected: `0 errors`.

---

### Task 3: Add Remote Status Test

**Files:**
- Modify: `tests/wf_cli/test_remote_target.py`

- [ ] **Step 1: Add remote test using existing RPC patch helper**

Append this test near the existing remote target CLI tests:

```python
def test_wf_status_uses_rpc_url_override(monkeypatch, tmp_path) -> None:
    server = build_local_static_workflow_server(tmp_path / "store")
    _patch_rpc_client_to_server(monkeypatch, server)
    config_path = tmp_path / "wf.json"
    config_path.write_text('{"version": 1}', encoding="utf-8")

    result = CliRunner().invoke(
        app,
        [
            "--config",
            str(config_path),
            "--url",
            "http://test/rpc",
            "status",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["target"]["mode"] == "remote"
    assert payload["target"]["url"] == "http://test/rpc"
    assert payload["workflow"]["capability_count"] >= 1
    assert payload["sources"]["available"] is True
    assert payload["admin"]["available"] is True
    assert payload["registry"]["available"] is False
```

- [ ] **Step 2: Run remote test**

Run:

```powershell
uv run pytest tests/wf_cli/test_remote_target.py::test_wf_status_uses_rpc_url_override -q
```

Expected: PASS.

---

### Task 4: Add Product Smoke Script Documentation

**Files:**
- Modify: `docs/wf_cli.md`
- Modify: `docs/current_roadmap.md`

- [ ] **Step 1: Document `wf status`**

In `docs/wf_cli.md`, under the remote server section or before capability
discovery, add:

````markdown
Check the selected target:

```bash
wf status
wf --url http://127.0.0.1:8765/rpc status
```

`status` is read-only. It reports the selected target, capability/source
availability, admin counts, auth record count, and desired registry count when
the target exposes those admin surfaces. It does not return auth payload values.
```
````

- [ ] **Step 2: Mark roadmap item complete**

In `docs/current_roadmap.md`, under `Priority 1: Product Smoke And Status UX`,
change:

```markdown
- Add `wf status` as a compact target/server status command.
```

to:

```markdown
- Completed: `wf status` is a compact read-only target/server status command.
```

Leave the manual product smoke item open.

- [ ] **Step 3: Run docs lint**

Run:

```powershell
uv run ruff check docs\wf_cli.md docs\current_roadmap.md
```

Expected: no lint errors. Ruff may report "No Python files found"; that is acceptable for markdown-only paths.

---

### Task 5: Final Verification

**Files:** all touched files.

- [ ] **Step 1: Run focused tests**

Run:

```powershell
uv run pytest tests/wf_cli/test_status.py tests/wf_cli/test_remote_target.py -q
```

Expected: all tests pass.

- [ ] **Step 2: Run broader CLI/RPC smoke tests**

Run:

```powershell
uv run pytest tests/wf_transport_rpc_http tests/wf_cli/test_remote_target.py tests/wf_cli/test_status.py -q
```

Expected: all tests pass.

- [ ] **Step 3: Run lint**

Run:

```powershell
uv run ruff check src\wf_cli tests\wf_cli tests\wf_transport_rpc_http
```

Expected: `All checks passed!`

- [ ] **Step 4: Run typecheck**

Run:

```powershell
uv run basedpyright --level error src\wf_cli tests\wf_cli\test_status.py tests\wf_cli\test_remote_target.py
```

Expected: `0 errors, 0 warnings, 0 notes`.

- [ ] **Step 5: Manual product smoke**

If a server is running:

```powershell
uv run wf --url http://127.0.0.1:8765/rpc status
uv run wf --url http://127.0.0.1:8765/rpc cap call wf.std.constant --input '{"value":"status smoke"}'
```

Expected:

- `status` returns JSON with `target.mode == "remote"`.
- `cap call` returns `outcome == "ok"`.

- [ ] **Step 6: Commit**

```powershell
git add src\wf_cli\commands\status.py src\wf_cli\app.py tests\wf_cli\test_status.py tests\wf_cli\test_remote_target.py docs\wf_cli.md docs\current_roadmap.md
git commit -m "feat: add workflow status command"
```

---

## Self-Review Checklist

- Spec coverage: this plan implements the roadmap's first Priority 1 item (`wf status`) and leaves manual product smoke as a visible follow-up.
- Placeholder scan: no TODO/TBD placeholders remain.
- Scope check: no new backend endpoint, no store mutation, no new server state.
- Type consistency: `CliContext`, `CliTyperState`, and existing admin/source methods match current code.
- Security: auth status returns counts only; no payload values.
