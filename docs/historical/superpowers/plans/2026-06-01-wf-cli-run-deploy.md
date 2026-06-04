# wf CLI Run And Deploy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the first useful `wf` CLI vertical slice: `wf deploy validate`, `wf run start`, `wf run inspect`, and `wf run trace`.

**Architecture:** Keep command modules thin Typer wrappers over `WorkflowSurfaceHandlers` loaded through `wf_cli.context`. Use real file-backed stores in tests so CLI behavior matches the MCP workflow surface. Keep JSON output as the default and reuse `wf_cli.io` for payload parsing/printing.

**Tech Stack:** Python 3.14, Typer, Pydantic v2, pytest, ruff, basedpyright.

---

## File Structure

- Modify `src/wf_cli/app.py`
  - Store root `--config` in Typer context so subcommands can load the requested config.

- Modify `src/wf_cli/context.py`
  - Add `config_path_from_context(ctx)` helper.

- Modify `src/wf_cli/commands/deployments.py`
  - Add `validate` command.

- Modify `src/wf_cli/commands/runs.py`
  - Add `start`, `inspect`, and `trace` commands.

- Create `tests/wf_cli/test_run_deploy.py`
  - End-to-end CLI tests using `CliRunner`.
  - Seed artifact/deployment data into the configured store.

## Scope Boundaries

- Do not implement `wf deploy save`, `wf deploy delete`, or `wf deploy inspect`.
- Do not implement `wf run resume`.
- Do not implement `wf cap`, `wf draft`, `wf explain`, or `wf schema`.
- Do not add table/ids/compact formatting.
- Do not add stdin input yet; use `--input` and `--input-file`.
- Do not mock `WorkflowSurfaceHandlers`; use the real service/store path.

---

### Task 1: Make Global `--config` Available To Commands

**Files:**

- Modify: `src/wf_cli/app.py`
- Modify: `src/wf_cli/context.py`
- Modify: `tests/wf_cli/test_app.py`

- [ ] **Step 1: Add a failing test for config propagation**

Append to `tests/wf_cli/test_app.py`:

```python
def test_root_callback_stores_config_path() -> None:
    result = runner.invoke(app, ["--config", "custom.json", "run", "--help"])

    assert result.exit_code == 0
    assert "Run workflow deployments" in result.output
```

This mostly locks down that root `--config` remains accepted before subcommands.

- [ ] **Step 2: Update root callback to use Typer context**

In `src/wf_cli/app.py`, change the callback signature to:

```python
@app.callback()
def root(
    ctx: typer.Context,
    config: Annotated[
        str,
        typer.Option(
            "--config",
            help="Path to workflow/MCP config JSON.",
        ),
    ] = "wf_mcp.config.json",
) -> None:
    """Run workflow platform commands."""
    ctx.obj = {"config_path": config}
```

Keep `import typer` already present.

- [ ] **Step 3: Add config helper**

In `src/wf_cli/context.py`, add:

```python
import typer
```

Then add below `CliContext`:

```python
def config_path_from_context(ctx: typer.Context) -> str:
    """Return the root --config path captured by the Typer callback."""
    obj = ctx.obj if isinstance(ctx.obj, dict) else {}
    value = obj.get("config_path", "wf_mcp.config.json")
    return value if isinstance(value, str) else "wf_mcp.config.json"
```

- [ ] **Step 4: Run app/context tests**

Run:

```bash
uv run pytest tests/wf_cli/test_app.py tests/wf_cli/test_context.py -q
```

Expected: PASS.

---

### Task 2: Add CLI Run/Deploy Test Fixture Helpers

**Files:**

- Create: `tests/wf_cli/test_run_deploy.py`

- [ ] **Step 1: Create fixture helpers**

Create `tests/wf_cli/test_run_deploy.py` with this opening:

```python
from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from wf_artifacts import FileWorkflowArtifactStore, WorkflowDeployment
from wf_cli.app import app
from wf_mcp.models import ConnectionConfig

from tests.wf_mcp.test_support import echo_tool, local_temp_root
from tests.wf_mcp.workflow_surface.conftest import echo_artifact


runner = CliRunner()


def _write_config(root: Path) -> Path:
    config_path = root / "wf_mcp.config.json"
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
    return config_path


def _seed_echo_deployment(root: Path) -> Path:
    config_path = _write_config(root)
    store_root = root / ".wf_mcp_store"
    artifact_store = FileWorkflowArtifactStore(store_root)
    artifact_store.save_artifact(echo_artifact())
    artifact_store.save_deployment(
        WorkflowDeployment(
            id="echo.personal",
            artifact_id="echo",
            artifact_version=1,
            bindings=[{"logical_source": "demo", "concrete_source": "demo.personal"}],
        )
    )
    return config_path
```

This fixture writes the same config/store shape that `wf_cli.context` loads.

- [ ] **Step 2: Add failing deploy validate test**

Append:

```python
def test_wf_deploy_validate_outputs_json() -> None:
    root = local_temp_root() / "wf_cli_deploy_validate"
    root.mkdir(parents=True, exist_ok=True)
    config_path = _seed_echo_deployment(root)

    result = runner.invoke(
        app,
        ["--config", str(config_path), "deploy", "validate", "echo.personal"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["deployment_id"] == "echo.personal"
    assert payload["status"] == "runnable"
    assert payload["next_actions"]["recommended_next_tool"] == (
        "wf.workflow.run_deployment"
    )
```

- [ ] **Step 3: Run test to verify it fails**

Run:

```bash
uv run pytest tests/wf_cli/test_run_deploy.py::test_wf_deploy_validate_outputs_json -q
```

Expected: FAIL because `deploy validate` does not exist.

---

### Task 3: Implement `wf deploy validate`

**Files:**

- Modify: `src/wf_cli/commands/deployments.py`

- [ ] **Step 1: Add imports and command**

Replace `src/wf_cli/commands/deployments.py` with:

```python
from __future__ import annotations

import asyncio
from typing import Annotated

import typer

from wf_cli.context import config_path_from_context, load_cli_context
from wf_cli.io import emit_json

app = typer.Typer(
    name="deploy",
    help="Save, inspect, validate, and delete workflow deployments.",
    no_args_is_help=True,
)


@app.command("validate")
def validate_deployment(
    ctx: typer.Context,
    deployment_id: Annotated[str, typer.Argument(help="Deployment id to validate.")],
    live: Annotated[
        bool,
        typer.Option(
            "--live",
            help="Also perform opt-in upstream liveness checks.",
        ),
    ] = False,
) -> None:
    """Validate one saved workflow deployment."""
    context = load_cli_context(config_path_from_context(ctx))
    payload = asyncio.run(
        context.handlers.validate_deployment(
            deployment_id=deployment_id,
            live_check=live,
        )
    )
    emit_json(payload)
```

- [ ] **Step 2: Run deploy test**

Run:

```bash
uv run pytest tests/wf_cli/test_run_deploy.py::test_wf_deploy_validate_outputs_json -q
```

Expected: PASS.

---

### Task 4: Add Run Command Tests

**Files:**

- Modify: `tests/wf_cli/test_run_deploy.py`

- [ ] **Step 1: Add run start test**

Append:

```python
def test_wf_run_start_accepts_inline_json_input() -> None:
    root = local_temp_root() / "wf_cli_run_start"
    root.mkdir(parents=True, exist_ok=True)
    config_path = _seed_echo_deployment(root)

    result = runner.invoke(
        app,
        [
            "--config",
            str(config_path),
            "run",
            "start",
            "echo.personal",
            "--input",
            '{"text": "hello"}',
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["status"] == "completed"
    assert payload["output"]["echoed"] == "hello"
    assert isinstance(payload["run_id"], str)
    assert payload["next_actions"]["can_continue"] is False
```

- [ ] **Step 2: Add run start file input test**

Append:

```python
def test_wf_run_start_accepts_input_file() -> None:
    root = local_temp_root() / "wf_cli_run_start_file"
    root.mkdir(parents=True, exist_ok=True)
    config_path = _seed_echo_deployment(root)
    input_path = root / "input.json"
    input_path.write_text('{"text": "from file"}', encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "--config",
            str(config_path),
            "run",
            "start",
            "echo.personal",
            "--input-file",
            str(input_path),
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["status"] == "completed"
    assert payload["output"]["echoed"] == "from file"
```

- [ ] **Step 3: Add inspect and trace test**

Append:

```python
def test_wf_run_inspect_and_trace_existing_run() -> None:
    root = local_temp_root() / "wf_cli_run_inspect_trace"
    root.mkdir(parents=True, exist_ok=True)
    config_path = _seed_echo_deployment(root)
    start = runner.invoke(
        app,
        [
            "--config",
            str(config_path),
            "run",
            "start",
            "echo.personal",
            "--input",
            '{"text": "hello"}',
        ],
    )
    run_id = json.loads(start.output)["run_id"]

    inspected = runner.invoke(
        app,
        ["--config", str(config_path), "run", "inspect", run_id],
    )
    traced = runner.invoke(
        app,
        [
            "--config",
            str(config_path),
            "run",
            "trace",
            run_id,
            "--from",
            "0",
            "--limit",
            "1",
        ],
    )

    assert inspected.exit_code == 0
    inspected_payload = json.loads(inspected.output)
    assert inspected_payload["run_id"] == run_id
    assert inspected_payload["status"] == "completed"
    assert "trace" not in inspected_payload

    assert traced.exit_code == 0
    traced_payload = json.loads(traced.output)
    assert traced_payload["run_id"] == run_id
    assert traced_payload["trace_start"] == 0
    assert traced_payload["trace_limit"] == 1
    assert traced_payload["trace"][0]["node_id"] == "echo"
```

- [ ] **Step 4: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/wf_cli/test_run_deploy.py -q
```

Expected: deploy test passes, run tests fail because run commands do not exist.

---

### Task 5: Implement Run Commands

**Files:**

- Modify: `src/wf_cli/commands/runs.py`

- [ ] **Step 1: Replace run command module**

Replace `src/wf_cli/commands/runs.py` with:

```python
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated

import typer

from wf_cli.context import config_path_from_context, load_cli_context
from wf_cli.io import CliInputError, emit_json, parse_json_input
from wf_mcp.workflow_surface import TraceRange

app = typer.Typer(
    name="run",
    help="Run workflow deployments and inspect durable runs.",
    no_args_is_help=True,
)


@app.command("start")
def start_run(
    ctx: typer.Context,
    deployment_id: Annotated[str, typer.Argument(help="Deployment id to run.")],
    input_json: Annotated[
        str | None,
        typer.Option("--input", help="Workflow input JSON object."),
    ] = None,
    input_file: Annotated[
        Path | None,
        typer.Option("--input-file", help="Path to workflow input JSON object."),
    ] = None,
    trace_from: Annotated[
        int | None,
        typer.Option("--trace-from", min=0, help="Optional trace slice start."),
    ] = None,
    trace_limit: Annotated[
        int | None,
        typer.Option("--trace-limit", min=1, max=100, help="Optional trace slice limit."),
    ] = None,
) -> None:
    """Start one workflow deployment."""
    try:
        workflow_input = parse_json_input(input_json=input_json, input_file=input_file)
    except CliInputError as exc:
        raise typer.BadParameter(str(exc)) from exc
    context = load_cli_context(config_path_from_context(ctx))
    trace_range = _optional_trace_range(start=trace_from, limit=trace_limit)
    payload = asyncio.run(
        context.handlers.run_deployment(
            deployment_id=deployment_id,
            workflow_input=workflow_input,
            trace_range=trace_range,
        )
    )
    emit_json(payload)


@app.command("inspect")
def inspect_run(
    ctx: typer.Context,
    run_id: Annotated[str, typer.Argument(help="Durable run id to inspect.")],
) -> None:
    """Inspect a durable run without trace entries."""
    context = load_cli_context(config_path_from_context(ctx))
    emit_json(asyncio.run(context.handlers.inspect_run(run_id=run_id)))


@app.command("trace")
def trace_run(
    ctx: typer.Context,
    run_id: Annotated[str, typer.Argument(help="Durable run id to trace.")],
    trace_from: Annotated[
        int,
        typer.Option("--from", min=0, help="Zero-based trace start offset."),
    ] = 0,
    limit: Annotated[
        int,
        typer.Option("--limit", min=1, max=100, help="Maximum trace entries."),
    ] = 25,
) -> None:
    """Read a bounded debug trace slice."""
    context = load_cli_context(config_path_from_context(ctx))
    payload = asyncio.run(
        context.handlers.read_run_trace(
            run_id=run_id,
            trace_range=TraceRange(start=trace_from, limit=limit),
        )
    )
    emit_json(payload)


def _optional_trace_range(*, start: int | None, limit: int | None) -> TraceRange | None:
    """Build a trace range only when the caller requested trace detail."""
    if start is None and limit is None:
        return None
    return TraceRange(start=start or 0, limit=limit or 25)
```

- [ ] **Step 2: Run CLI run/deploy tests**

Run:

```bash
uv run pytest tests/wf_cli/test_run_deploy.py -q
```

Expected: PASS.

---

### Task 6: Verify Help And Input Error Behavior

**Files:**

- Modify: `tests/wf_cli/test_app.py`
- Modify: `tests/wf_cli/test_run_deploy.py`

- [ ] **Step 1: Add help assertions**

Append to `tests/wf_cli/test_app.py`:

```python
def test_wf_deploy_validate_help_exists() -> None:
    result = runner.invoke(app, ["deploy", "validate", "--help"])

    assert result.exit_code == 0
    assert "Validate one saved workflow deployment" in result.output


def test_wf_run_start_help_exists() -> None:
    result = runner.invoke(app, ["run", "start", "--help"])

    assert result.exit_code == 0
    assert "--input-file" in result.output
```

- [ ] **Step 2: Add bad JSON assertion**

Append to `tests/wf_cli/test_run_deploy.py`:

```python
def test_wf_run_start_reports_bad_json() -> None:
    root = local_temp_root() / "wf_cli_run_bad_json"
    root.mkdir(parents=True, exist_ok=True)
    config_path = _seed_echo_deployment(root)

    result = runner.invoke(
        app,
        [
            "--config",
            str(config_path),
            "run",
            "start",
            "echo.personal",
            "--input",
            "{",
        ],
    )

    assert result.exit_code != 0
    assert "invalid JSON" in result.output
```

- [ ] **Step 3: Run tests**

Run:

```bash
uv run pytest tests/wf_cli/test_app.py tests/wf_cli/test_run_deploy.py -q
```

Expected: PASS.

---

### Task 7: Verification

**Files:**

- All touched files.

- [ ] **Step 1: Run all CLI tests**

Run:

```bash
uv run pytest tests/wf_cli -q
```

Expected: PASS.

- [ ] **Step 2: Run focused workflow surface tests**

Run:

```bash
uv run pytest tests/wf_mcp/workflow_surface/test_deployments.py tests/wf_mcp/workflow_surface/test_runs.py -q
```

Expected: PASS.

- [ ] **Step 3: Run lint**

Run:

```bash
uv run ruff check src/wf_cli tests/wf_cli
```

Expected: PASS.

- [ ] **Step 4: Run format check**

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

- `wf deploy validate` returns handler JSON with `next_actions`.
- `wf run start` accepts `--input` and `--input-file`.
- `wf run inspect` omits trace entries.
- `wf run trace` requires bounded `--from` / `--limit`.
- Commands load the root `--config` path.
- Command modules stay thin and do not duplicate workflow logic.
- No unrelated CLI groups or draft authoring commands were implemented.

## Notes For Opencode

- Keep this to run/deploy commands only.
- Do not implement `wf run resume` in this slice.
- Do not add `--format`; JSON stays default.
- Use real file-backed stores in tests.
- If Typer callback context is annoying, keep the smallest helper in `wf_cli.context` rather than passing global state.
