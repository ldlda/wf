# wf CLI Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the `wf_cli` package, Typer entrypoint, shared CLI context/config loader, and JSON IO helpers without implementing workflow commands yet.

**Architecture:** Create a protocol-neutral `wf_cli` package as a second front door beside `wf_mcp`. The first slice wires Typer command groups and reusable helpers only; later plans will add `deploy/run`, `explain`, and draft authoring commands. The CLI may construct `wf_mcp` service/handler objects through `wf_cli.context` for v1, but command modules should not directly own MCP-specific setup.

**Tech Stack:** Python 3.14, Typer, Pydantic v2, pytest, ruff, basedpyright.

---

## File Structure

- Modify `pyproject.toml`
  - Add `typer>=0.16`.
  - Add script entrypoint `wf = "wf_cli.app:main"`.

- Create `src/wf_cli/__init__.py`
  - Minimal package marker and future exports.

- Create `src/wf_cli/app.py`
  - Owns the Typer root app.
  - Registers lifecycle command groups.
  - Exposes `main()`.

- Create `src/wf_cli/context.py`
  - Owns config loading and service/handler construction.
  - Reuses `wf_mcp.broker.load_broker_config` and `build_service_from_config` for v1.

- Create `src/wf_cli/io.py`
  - Owns JSON input parsing from inline JSON and files.
  - Owns JSON output formatting.
  - Provides a small `CliInputError` for bad CLI payloads.

- Create `src/wf_cli/commands/__init__.py`
  - Exports command group apps.

- Create command modules:
  - `src/wf_cli/commands/caps.py`
  - `src/wf_cli/commands/drafts.py`
  - `src/wf_cli/commands/artifacts.py`
  - `src/wf_cli/commands/deployments.py`
  - `src/wf_cli/commands/runs.py`
  - `src/wf_cli/commands/docs.py`
  - `src/wf_cli/commands/schema.py`
  - `src/wf_cli/commands/explain.py`

- Create tests:
  - `tests/wf_cli/test_app.py`
  - `tests/wf_cli/test_context.py`
  - `tests/wf_cli/test_io.py`

## Scope Boundaries

- Do not implement real workflow commands in this slice.
- Do not duplicate MCP workflow logic.
- Do not add draft mutation helpers yet.
- Do not add `wf explain` registry entries yet.
- Do not add subprocess CLI tests yet; use Typer `CliRunner` and direct function tests.

---

### Task 1: Add Typer Dependency And Script

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add dependency and entrypoint**

In `pyproject.toml`, add `typer>=0.16` to `[project].dependencies`:

```toml
dependencies = [
    "fastmcp>=3.2.4",
    "httpx>=0.28",
    "jsonpatch>=1.33",
    "jsonschema>=4.26",
    "mcp[cli,rich]>=1",
    "openapi-core>=0.19",
    "pydantic>=2",
    "typer>=0.16",
]
```

In `[project.scripts]`, add `wf` while preserving `wf-mcp`:

```toml
[project.scripts]
wf = "wf_cli.app:main"
wf-mcp = "wf_mcp.cli:main"
```

- [ ] **Step 2: Sync dependencies if needed**

Run:

```bash
uv lock
```

Expected: `uv.lock` updates if Typer is not already present transitively.

If `uv lock` cannot access the network, stop and report the dependency-lock blocker. Do not manually edit `uv.lock`.

---

### Task 2: Add App Skeleton Tests

**Files:**
- Create: `tests/wf_cli/test_app.py`

- [ ] **Step 1: Write failing Typer app tests**

Create `tests/wf_cli/test_app.py`:

```python
from __future__ import annotations

from typer.testing import CliRunner

from wf_cli.app import app


runner = CliRunner()


def test_wf_help_lists_lifecycle_groups() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "cap" in result.output
    assert "draft" in result.output
    assert "artifact" in result.output
    assert "deploy" in result.output
    assert "run" in result.output
    assert "schema" in result.output
    assert "explain" in result.output


def test_wf_run_group_help_exists() -> None:
    result = runner.invoke(app, ["run", "--help"])

    assert result.exit_code == 0
    assert "Run workflow deployments" in result.output
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/wf_cli/test_app.py -q
```

Expected: FAIL because `wf_cli` does not exist.

---

### Task 3: Create Typer App And Command Groups

**Files:**
- Create: `src/wf_cli/__init__.py`
- Create: `src/wf_cli/app.py`
- Create: `src/wf_cli/commands/__init__.py`
- Create: `src/wf_cli/commands/caps.py`
- Create: `src/wf_cli/commands/drafts.py`
- Create: `src/wf_cli/commands/artifacts.py`
- Create: `src/wf_cli/commands/deployments.py`
- Create: `src/wf_cli/commands/runs.py`
- Create: `src/wf_cli/commands/docs.py`
- Create: `src/wf_cli/commands/schema.py`
- Create: `src/wf_cli/commands/explain.py`

- [ ] **Step 1: Create package marker**

Create `src/wf_cli/__init__.py`:

```python
"""Workflow platform command-line interface."""
```

- [ ] **Step 2: Create command group modules**

Create `src/wf_cli/commands/caps.py`:

```python
from __future__ import annotations

import typer

app = typer.Typer(
    name="cap",
    help="Inspect and call workflow capabilities.",
    no_args_is_help=True,
)
```

Create `src/wf_cli/commands/drafts.py`:

```python
from __future__ import annotations

import typer

app = typer.Typer(
    name="draft",
    help="Create, inspect, patch, validate, and save draft workflows.",
    no_args_is_help=True,
)
```

Create `src/wf_cli/commands/artifacts.py`:

```python
from __future__ import annotations

import typer

app = typer.Typer(
    name="artifact",
    help="List and inspect saved workflow artifacts.",
    no_args_is_help=True,
)
```

Create `src/wf_cli/commands/deployments.py`:

```python
from __future__ import annotations

import typer

app = typer.Typer(
    name="deploy",
    help="Save, inspect, validate, and delete workflow deployments.",
    no_args_is_help=True,
)
```

Create `src/wf_cli/commands/runs.py`:

```python
from __future__ import annotations

import typer

app = typer.Typer(
    name="run",
    help="Run workflow deployments and inspect durable runs.",
    no_args_is_help=True,
)
```

Create `src/wf_cli/commands/docs.py`:

```python
from __future__ import annotations

import typer

app = typer.Typer(
    name="docs",
    help="List and read workflow documentation resources.",
    no_args_is_help=True,
)
```

Create `src/wf_cli/commands/schema.py`:

```python
from __future__ import annotations

import typer

app = typer.Typer(
    name="schema",
    help="Print expected input shapes for wf commands.",
    no_args_is_help=True,
)
```

Create `src/wf_cli/commands/explain.py`:

```python
from __future__ import annotations

import typer

app = typer.Typer(
    name="explain",
    help="Explain workflow diagnostic and CLI error codes.",
    no_args_is_help=True,
)
```

- [ ] **Step 3: Create command package exports**

Create `src/wf_cli/commands/__init__.py`:

```python
"""Typer command groups for the wf CLI."""

from . import artifacts, caps, deployments, docs, drafts, explain, runs, schema

__all__ = [
    "artifacts",
    "caps",
    "deployments",
    "docs",
    "drafts",
    "explain",
    "runs",
    "schema",
]
```

- [ ] **Step 4: Create root app**

Create `src/wf_cli/app.py`:

```python
from __future__ import annotations

from typing import Annotated

import typer

from .commands import artifacts, caps, deployments, docs, drafts, explain, runs, schema

app = typer.Typer(
    name="wf",
    help="Workflow platform CLI.",
    no_args_is_help=True,
)


@app.callback()
def root(
    config: Annotated[
        str,
        typer.Option(
            "--config",
            help="Path to workflow/MCP config JSON.",
        ),
    ] = "wf_mcp.config.json",
) -> None:
    """Run workflow platform commands."""
    # The root callback owns global options only. Command modules should load
    # context explicitly so tests can call command functions without Typer state.
    _ = config


app.add_typer(caps.app, name="cap")
app.add_typer(drafts.app, name="draft")
app.add_typer(artifacts.app, name="artifact")
app.add_typer(deployments.app, name="deploy")
app.add_typer(runs.app, name="run")
app.add_typer(docs.app, name="docs")
app.add_typer(schema.app, name="schema")
app.add_typer(explain.app, name="explain")


def main() -> None:
    """Console script entrypoint for `wf`."""
    app()
```

- [ ] **Step 5: Run app tests**

Run:

```bash
uv run pytest tests/wf_cli/test_app.py -q
```

Expected: PASS.

---

### Task 4: Add JSON IO Tests

**Files:**
- Create: `tests/wf_cli/test_io.py`

- [ ] **Step 1: Write failing IO tests**

Create `tests/wf_cli/test_io.py`:

```python
from __future__ import annotations

import json

import pytest

from wf_cli.io import CliInputError, emit_json, parse_json_input


def test_parse_json_input_reads_inline_json() -> None:
    payload = parse_json_input(input_json='{"text": "hello"}', input_file=None)

    assert payload["text"] == "hello"


def test_parse_json_input_reads_file(tmp_path) -> None:
    path = tmp_path / "payload.json"
    path.write_text('{"text": "from file"}', encoding="utf-8")

    payload = parse_json_input(input_json=None, input_file=path)

    assert payload["text"] == "from file"


def test_parse_json_input_rejects_both_inline_and_file(tmp_path) -> None:
    path = tmp_path / "payload.json"
    path.write_text("{}", encoding="utf-8")

    with pytest.raises(CliInputError, match="mutually exclusive"):
        parse_json_input(input_json="{}", input_file=path)


def test_parse_json_input_rejects_invalid_json() -> None:
    with pytest.raises(CliInputError, match="invalid JSON"):
        parse_json_input(input_json="{", input_file=None)


def test_emit_json_writes_pretty_json(capsys) -> None:
    emit_json({"ok": True, "items": [1]})
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert payload["ok"] is True
    assert payload["items"][0] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/wf_cli/test_io.py -q
```

Expected: FAIL because `wf_cli.io` does not exist.

---

### Task 5: Implement JSON IO Helpers

**Files:**
- Create: `src/wf_cli/io.py`

- [ ] **Step 1: Create IO helpers**

Create `src/wf_cli/io.py`:

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class CliInputError(ValueError):
    """Raised when CLI JSON/file input cannot be parsed safely."""


def parse_json_input(
    *,
    input_json: str | None,
    input_file: Path | None,
) -> dict[str, Any]:
    """Parse exactly one JSON object from inline JSON or a file path."""
    if input_json is not None and input_file is not None:
        raise CliInputError("--input and --input-file are mutually exclusive")
    if input_json is None and input_file is None:
        return {}
    raw = input_json if input_json is not None else _read_input_file(input_file)
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CliInputError(f"invalid JSON input: {exc.msg}") from exc
    if not isinstance(payload, dict):
        raise CliInputError("JSON input must be an object")
    return payload


def emit_json(payload: Any) -> None:
    """Write JSON output in the CLI default machine-readable format."""
    print(json.dumps(payload, indent=2, sort_keys=True))


def _read_input_file(path: Path | None) -> str:
    """Read a required JSON input file."""
    if path is None:
        raise CliInputError("input file path is required")
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CliInputError(f"could not read input file {path!s}: {exc}") from exc
```

- [ ] **Step 2: Run IO tests**

Run:

```bash
uv run pytest tests/wf_cli/test_io.py -q
```

Expected: PASS.

---

### Task 6: Add CLI Context Tests

**Files:**
- Create: `tests/wf_cli/test_context.py`

- [ ] **Step 1: Write failing context tests**

Create `tests/wf_cli/test_context.py`:

```python
from __future__ import annotations

import json

from wf_cli.context import load_cli_context

from tests.wf_mcp.test_support import local_temp_root


def test_load_cli_context_builds_service_and_handlers() -> None:
    tmp_path = local_temp_root() / "wf_cli_context"
    tmp_path.mkdir(parents=True, exist_ok=True)
    config_path = tmp_path / "wf_mcp.config.json"
    config_path.write_text(
        json.dumps(
            {
                "store_root": ".wf_mcp_store",
                "connections": [
                    {
                        "id": "demo.personal",
                        "server": "demo",
                        "account": "personal",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    context = load_cli_context(config_path)

    assert context.config_path == config_path
    assert context.service.connections.list_all()[0].id == "demo.personal"
    assert context.handlers.service is context.service
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/wf_cli/test_context.py -q
```

Expected: FAIL because `wf_cli.context` does not exist.

---

### Task 7: Implement CLI Context Loader

**Files:**
- Create: `src/wf_cli/context.py`

- [ ] **Step 1: Create context loader**

Create `src/wf_cli/context.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from wf_mcp.broker import build_service_from_config, load_broker_config
from wf_mcp.broker.service import WfMcpService
from wf_mcp.workflow_surface import WorkflowSurfaceHandlers


@dataclass(frozen=True)
class CliContext:
    """Protocol-neutral CLI handle over the current workflow service stack.

    V1 intentionally reuses wf_mcp service construction because that is where
    config, store, source, artifact, draft, and run wiring currently lives. Keep
    this dependency behind context.py so later extraction does not affect every
    command module.
    """

    config_path: Path
    service: WfMcpService
    handlers: WorkflowSurfaceHandlers


def load_cli_context(config_path: str | Path) -> CliContext:
    """Load config and build workflow-surface handlers for CLI commands."""
    resolved_config_path = Path(config_path)
    config = load_broker_config(resolved_config_path)
    service = build_service_from_config(config)
    return CliContext(
        config_path=resolved_config_path,
        service=service,
        handlers=WorkflowSurfaceHandlers(service),
    )
```

- [ ] **Step 2: Run context tests**

Run:

```bash
uv run pytest tests/wf_cli/test_context.py -q
```

Expected: PASS.

---

### Task 8: Run Foundation Verification

**Files:**
- All touched files.

- [ ] **Step 1: Run focused CLI tests**

Run:

```bash
uv run pytest tests/wf_cli/test_app.py tests/wf_cli/test_io.py tests/wf_cli/test_context.py -q
```

Expected: PASS.

- [ ] **Step 2: Run Typer help manually through uv**

Run:

```bash
uv run wf --help
```

Expected: exit 0 and output lists lifecycle groups including `deploy`, `run`, `draft`, and `explain`.

- [ ] **Step 3: Run lint on touched files**

Run:

```bash
uv run ruff check src/wf_cli tests/wf_cli
```

Expected: PASS.

- [ ] **Step 4: Run format check on touched files**

Run:

```bash
uv run ruff format --check src/wf_cli tests/wf_cli
```

Expected: PASS.

- [ ] **Step 5: Run type check**

Run:

```bash
uv run basedpyright --level error
```

Expected: `0 errors`.

---

## Self-Review Checklist

- `wf_cli` is a new package, not under `wf_mcp`.
- `wf` script exists and `wf-mcp` still exists.
- Typer is the only CLI framework used in `wf_cli`.
- Command groups exist but do not pretend to implement workflow behavior.
- Shared config/service construction lives in `wf_cli.context`.
- JSON parsing/printing lives in `wf_cli.io`.
- No workflow logic is duplicated from MCP handlers.
- No app-domain command groups (`scenario`, `risk`, `decision`, etc.) were added.

## Notes For Opencode

- This is a foundation slice. Do not implement `deploy validate` or `run start` here.
- If Typer dependency locking fails because of network access, stop and report it.
- Keep command modules boring and small.
- Do not move stores out of `wf_mcp` yet; only hide the dependency behind `wf_cli.context`.
