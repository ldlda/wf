# Server CLI Ownership Move Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the `wf-rpc-server` Typer startup CLI from the JSON-RPC transport package to `wf_server` without changing runtime behavior.

**Architecture:** `wf_server.cli` will own process startup, config parsing, server composition, and transport startup selection. `wf_transport_rpc_http` will keep owning `create_rpc_app(server)` and JSON-RPC method/client code; its old `cli.py` becomes a compatibility shim re-exporting `app` and `main`.

**Tech Stack:** Python 3.14, Typer, Uvicorn, `wf_server`, `wf_transport_rpc_http`, pytest, ruff, basedpyright.

---

## File Structure

- Create `src/wf_server/cli.py`
  - Move the current `wf_transport_rpc_http.cli` implementation here.
  - Import `create_rpc_app` from `wf_transport_rpc_http`.
  - Keep the existing Typer command behavior and options unchanged.
- Replace `src/wf_transport_rpc_http/cli.py`
  - Compatibility shim only:
    ```python
    from wf_server.cli import app, main

    __all__ = ["app", "main"]
    ```
- Modify `pyproject.toml`
  - Change script entrypoint to `wf_server.cli:main`.
- Move `tests/wf_transport_rpc_http/test_cli.py` to `tests/wf_server/test_cli.py`
  - Update imports and monkeypatch targets to `wf_server.cli`.
- Create or modify `tests/wf_transport_rpc_http/test_cli_compat.py`
  - Prove old import path remains identity-compatible.
- Modify docs:
  - `docs/project_map.md`
  - `docs/current_roadmap.md`
  - `docs/superpowers/specs/2026-06-10-server-cli-transport-boundary.md`

Non-goal: do not change `create_rpc_app`, JSON-RPC methods, client mixins, server config semantics, or `wf` client targeting.

---

### Task 1: Add Compatibility Test Before Moving

**Files:**
- Create: `tests/wf_transport_rpc_http/test_cli_compat.py`

- [ ] **Step 1: Write the compatibility test**

Create `tests/wf_transport_rpc_http/test_cli_compat.py`:

```python
from __future__ import annotations


def test_rpc_server_cli_compat_import_matches_server_cli() -> None:
    from wf_server import cli as server_cli
    from wf_transport_rpc_http import cli as transport_cli

    assert transport_cli.app is server_cli.app
    assert transport_cli.main is server_cli.main
```

- [ ] **Step 2: Run it and confirm it fails**

Run:

```bash
uv run pytest tests/wf_transport_rpc_http/test_cli_compat.py -q
```

Expected: FAIL with `ImportError` or `ModuleNotFoundError` for `wf_server.cli`.

---

### Task 2: Move CLI Implementation Into `wf_server.cli`

**Files:**
- Create: `src/wf_server/cli.py`
- Modify: `src/wf_transport_rpc_http/cli.py`

- [ ] **Step 1: Create `src/wf_server/cli.py` from the current implementation**

Copy the current contents of `src/wf_transport_rpc_http/cli.py` into `src/wf_server/cli.py`, with these import changes:

```python
from __future__ import annotations

from pathlib import Path

import typer
import uvicorn

from wf_config import (
    FilesystemStoreConfig,
    RpcHttpTransportConfig,
    load_workflow_config,
)
from wf_server.config import (
    build_workflow_server_from_legacy_mcp_config,
    build_workflow_server_from_workflow_config,
)
from wf_server.context import build_local_static_workflow_server
from wf_transport_rpc_http import create_rpc_app
```

Keep the existing `app = typer.Typer(add_completion=False)`, `serve(...)`, and `main()` bodies unchanged.

- [ ] **Step 2: Replace `src/wf_transport_rpc_http/cli.py` with a shim**

Replace the entire file with:

```python
from __future__ import annotations

from wf_server.cli import app, main

__all__ = ["app", "main"]
```

- [ ] **Step 3: Run compatibility test**

Run:

```bash
uv run pytest tests/wf_transport_rpc_http/test_cli_compat.py -q
```

Expected: PASS.

---

### Task 3: Move Behavior Tests To `tests/wf_server`

**Files:**
- Move: `tests/wf_transport_rpc_http/test_cli.py` -> `tests/wf_server/test_cli.py`

- [ ] **Step 1: Move the test file**

Run:

```bash
git mv tests/wf_transport_rpc_http/test_cli.py tests/wf_server/test_cli.py
```

- [ ] **Step 2: Update imports**

In `tests/wf_server/test_cli.py`, change:

```python
from wf_transport_rpc_http.cli import app
```

to:

```python
from wf_server.cli import app
```

Remove any function-local duplicate imports of `wf_transport_rpc_http.cli.app`; replace them with `wf_server.cli.app`.

- [ ] **Step 3: Update monkeypatch targets**

In `tests/wf_server/test_cli.py`, replace every monkeypatch string prefix:

```python
"wf_transport_rpc_http.cli.
```

with:

```python
"wf_server.cli.
```

Concrete replacements include:

```python
monkeypatch.setattr(
    "wf_server.cli.build_workflow_server_from_workflow_config",
    fake_build_server,
)
monkeypatch.setattr(
    "wf_server.cli.build_workflow_server_from_legacy_mcp_config",
    fake_build_mcp_server,
)
monkeypatch.setattr("wf_server.cli.create_rpc_app", fake_create_rpc_app)
monkeypatch.setattr("wf_server.cli.uvicorn.run", fake_uvicorn_run)
```

- [ ] **Step 4: Run moved tests**

Run:

```bash
uv run pytest tests/wf_server/test_cli.py tests/wf_transport_rpc_http/test_cli_compat.py -q
```

Expected: all tests pass.

---

### Task 4: Update Script Entrypoint

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Change the script entrypoint**

In `pyproject.toml`, change:

```toml
wf-rpc-server = "wf_transport_rpc_http.cli:main"
```

to:

```toml
wf-rpc-server = "wf_server.cli:main"
```

- [ ] **Step 2: Run CLI tests again**

Run:

```bash
uv run pytest tests/wf_server/test_cli.py tests/wf_transport_rpc_http/test_cli_compat.py -q
```

Expected: all tests pass.

- [ ] **Step 3: Smoke help command**

Run:

```bash
uv run wf-rpc-server --help
```

Expected: help output includes `--config`, `--store-root`, `--mcp-config`, `--host`, and `--port`.

---

### Task 5: Update Docs

**Files:**
- Modify: `docs/project_map.md`
- Modify: `docs/current_roadmap.md`
- Modify: `docs/superpowers/specs/2026-06-10-server-cli-transport-boundary.md`

- [ ] **Step 1: Update project map**

In `docs/project_map.md`, update the package table row for `wf_server` to state the move is implemented:

```markdown
| `wf_server` | Durable server composition boundary around `WorkflowApi` plus optional admin/source-registry surfaces. Owns the `wf-rpc-server` startup CLI/policy. | Transport packages and server startup code. |
```

Update the `wf_transport_rpc_http` row:

```markdown
| `wf_transport_rpc_http` | JSON-RPC-over-HTTP app/client and compatibility CLI shim. | Remote `wf` clients and local server smoke tests. |
```

Update the entrypoint bullet:

```markdown
- `wf-rpc-server`: preferred durable workflow server script for CLI/API clients,
  implemented by `wf_server.cli`.
```

- [ ] **Step 2: Update roadmap**

In `docs/current_roadmap.md`, under Priority 3, replace the server CLI boundary bullet with:

```markdown
- Completed: server startup policy moved to `wf_server.cli`; JSON-RPC HTTP
  remains in `wf_transport_rpc_http`:
  [`server CLI and transport boundary`](superpowers/specs/2026-06-10-server-cli-transport-boundary.md).
```

- [ ] **Step 3: Update the boundary spec status**

In `docs/superpowers/specs/2026-06-10-server-cli-transport-boundary.md`, change:

```markdown
Status: design direction; implementation not started
```

to:

```markdown
Status: first move slice implemented
```

Add this section after `## Desired Shape`:

```markdown
## Implementation Status

First move slice complete:

- `wf-rpc-server` script entrypoint points at `wf_server.cli:main`.
- `wf_server.cli` owns startup config parsing and server composition.
- `wf_transport_rpc_http.cli` remains as a compatibility shim.
- `wf_transport_rpc_http.create_rpc_app(server)` remains the JSON-RPC HTTP
  transport adapter.
```

- [ ] **Step 4: Move this plan to historical after implementation**

After verification succeeds, move this plan:

```bash
git mv docs/superpowers/plans/2026-06-10-server-cli-ownership-move.md docs/historical/superpowers/plans/2026-06-10-server-cli-ownership-move.md
```

---

### Task 6: Final Verification And Commit

**Files:**
- All touched files.

- [ ] **Step 1: Run focused tests**

Run:

```bash
uv run pytest tests/wf_server/test_cli.py tests/wf_transport_rpc_http/test_cli_compat.py tests/wf_transport_rpc_http/test_app.py -q
```

Expected: all tests pass.

- [ ] **Step 2: Run broader server/transport smoke tests**

Run:

```bash
uv run pytest tests/wf_server tests/wf_transport_rpc_http/test_structure.py tests/wf_transport_rpc_http/test_client.py -q
```

Expected: all tests pass.

- [ ] **Step 3: Run lint and typecheck**

Run:

```bash
uv run ruff check src/wf_server/cli.py src/wf_transport_rpc_http/cli.py tests/wf_server/test_cli.py tests/wf_transport_rpc_http/test_cli_compat.py
uv run ruff format --check src/wf_server/cli.py src/wf_transport_rpc_http/cli.py tests/wf_server/test_cli.py tests/wf_transport_rpc_http/test_cli_compat.py
uv run basedpyright --level error src/wf_server/cli.py src/wf_transport_rpc_http/cli.py tests/wf_server/test_cli.py tests/wf_transport_rpc_http/test_cli_compat.py
```

Expected:

```text
All checks passed!
0 errors, 0 warnings, 0 notes
```

- [ ] **Step 4: Check import direction**

Run:

```bash
uv run pytest tests/wf_transport_rpc_http/test_structure.py -q
```

Expected: PASS. The transport package may import `wf_server` for the compatibility shim only if the structure test permits it; if the test flags the shim, update the guard with an explicit exception for `wf_transport_rpc_http.cli`.

- [ ] **Step 5: Commit**

Run:

```bash
git add pyproject.toml src/wf_server/cli.py src/wf_transport_rpc_http/cli.py tests/wf_server/test_cli.py tests/wf_transport_rpc_http/test_cli_compat.py docs/project_map.md docs/current_roadmap.md docs/superpowers/specs/2026-06-10-server-cli-transport-boundary.md docs/historical/superpowers/plans/2026-06-10-server-cli-ownership-move.md
git commit -m "refactor: move server startup CLI to wf_server"
```

---

## Self-Review

- Spec coverage: Implements the first move slice from `2026-06-10-server-cli-transport-boundary.md`.
- Runtime behavior: No intended behavior changes; same Typer options and Uvicorn startup.
- Compatibility: Old `wf_transport_rpc_http.cli` import path remains.
- Scope control: Does not add multi-transport hosting or alter JSON-RPC method/client code.
