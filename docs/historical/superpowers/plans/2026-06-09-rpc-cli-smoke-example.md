# RPC CLI Smoke Example Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a runnable Python smoke example that can spawn `wf-rpc-server`, point `wf` at a temporary config/store, run the bounded CLI lifecycle, and clean up.

**Architecture:** Keep the smoke example outside production packages. The script uses `subprocess.Popen` for the server, `subprocess.run` for `wf` commands, a temporary workflow config, a random free port, and a `finally` cleanup path. It uses only `wf.std.constant` by default so it never dumps arbitrary MCP resource/blob output.

**Tech Stack:** Python 3.14 standard library, `uv run wf-rpc-server`, `uv run wf`, pytest for helper tests, ruff, basedpyright.

---

## Files

- Create `examples/rpc_cli_smoke.py`.
- Create `tests/examples/test_rpc_cli_smoke.py` for pure helper tests only.
- Modify `docs/runbooks/rpc-cli-smoke.md` to link the example script.
- Modify `docs/README.md` or `docs/project_map.md` if needed to mention the example.
- Modify `docs/current_roadmap.md` after implementation.
- Move this plan to `docs/historical/superpowers/plans/` after implementation.

## Behavior Contract

The script should:

- Use a temporary directory by default.
- Write a neutral `wf.config.json` that targets the spawned server over RPC HTTP.
- Use a free local port by default.
- Spawn `uv run wf-rpc-server --config <config> --host 127.0.0.1 --port <port>`.
- Poll `uv run wf --config <config> status` until ready.
- Run bounded discovery and lifecycle commands from the runbook.
- Generate unique ids per run.
- Always attempt cleanup in `finally`.
- Terminate the spawned server.
- Print concise command progress and `PASS`/`FAIL`.
- Support `--keep-temp` to preserve the temp directory and log files on failure.
- Support `--config <path>` only as an advanced mode that uses an existing config and does **not** rewrite it.

Non-goals:

- Do not call arbitrary MCP tools by default.
- Do not inspect raw MCP resources.
- Do not make this a CI gate yet.
- Do not require a server to already be running in the default path.

## Task 1: Pure Helpers And Tests

**Files:**
- Create: `examples/rpc_cli_smoke.py`
- Create: `tests/examples/test_rpc_cli_smoke.py`

- [ ] **Step 1: Add helper tests**

Create `tests/examples/test_rpc_cli_smoke.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from examples.rpc_cli_smoke import (
    SmokeIds,
    build_workflow_config,
    parse_json_stdout,
)


def test_build_workflow_config_targets_rpc_server(tmp_path: Path) -> None:
    config = build_workflow_config(store_root=tmp_path / "store", port=9876)

    assert config["version"] == 1
    assert config["client"]["target"]["kind"] == "rpc_http"
    assert config["client"]["target"]["url"] == "http://127.0.0.1:9876/rpc"
    assert config["server"]["store"] == {
        "kind": "filesystem",
        "root": str(tmp_path / "store"),
    }
    assert config["server"]["transports"] == [
        {"kind": "rpc_http", "host": "127.0.0.1", "port": 9876}
    ]


def test_smoke_ids_are_namespaced_by_suffix() -> None:
    ids = SmokeIds.from_suffix("abc123")

    assert ids.workspace_id == "smoke_ws_abc123"
    assert ids.artifact_id == "smoke_artifact_abc123"
    assert ids.deployment_id == "smoke_deploy_abc123"


def test_parse_json_stdout_ignores_surrounding_whitespace() -> None:
    payload = parse_json_stdout('  {"run_id": "run_1"}\n')

    assert payload == {"run_id": "run_1"}


def test_parse_json_stdout_reports_command_context() -> None:
    try:
        parse_json_stdout("not json", command=("wf", "status"))
    except ValueError as exc:
        message = str(exc)
    else:
        raise AssertionError("expected ValueError")

    assert "wf status" in message
    assert "not valid JSON" in message
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
uv run pytest tests/examples/test_rpc_cli_smoke.py -q
```

Expected: FAIL because `examples.rpc_cli_smoke` does not exist.

- [ ] **Step 3: Create helper skeleton**

Create `examples/rpc_cli_smoke.py` with:

```python
from __future__ import annotations

import argparse
import json
import socket
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class SmokeIds:
    workspace_id: str
    artifact_id: str
    deployment_id: str

    @classmethod
    def from_suffix(cls, suffix: str) -> SmokeIds:
        return cls(
            workspace_id=f"smoke_ws_{suffix}",
            artifact_id=f"smoke_artifact_{suffix}",
            deployment_id=f"smoke_deploy_{suffix}",
        )


def build_workflow_config(*, store_root: Path, port: int) -> dict[str, Any]:
    return {
        "version": 1,
        "client": {
            "target": {
                "kind": "rpc_http",
                "url": f"http://127.0.0.1:{port}/rpc",
                "timeout_seconds": 30,
            }
        },
        "server": {
            "store": {"kind": "filesystem", "root": str(store_root)},
            "transports": [
                {"kind": "rpc_http", "host": "127.0.0.1", "port": port}
            ],
            "sources": [],
        },
    }


def parse_json_stdout(
    stdout: str,
    *,
    command: tuple[str, ...] = (),
) -> dict[str, Any]:
    try:
        payload = json.loads(stdout.strip())
    except json.JSONDecodeError as exc:
        rendered_command = " ".join(command) if command else "<unknown command>"
        raise ValueError(f"{rendered_command} did not return valid JSON") from exc
    if not isinstance(payload, dict):
        rendered_command = " ".join(command) if command else "<unknown command>"
        raise ValueError(f"{rendered_command} returned non-object JSON")
    return payload
```

- [ ] **Step 4: Run helper tests**

Run:

```bash
uv run pytest tests/examples/test_rpc_cli_smoke.py -q
```

Expected: PASS.

## Task 2: Command Runner And Server Lifecycle

**Files:**
- Modify: `examples/rpc_cli_smoke.py`

- [ ] **Step 1: Add command result type and runner**

Add:

```python
@dataclass(frozen=True, slots=True)
class CommandResult:
    command: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str


def run_command(command: tuple[str, ...], *, timeout_seconds: float = 60) -> CommandResult:
    print(f"$ {' '.join(command)}", flush=True)
    completed = subprocess.run(
        command,
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
        check=False,
    )
    result = CommandResult(
        command=command,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )
    if result.returncode != 0:
        raise RuntimeError(_format_command_failure(result))
    return result


def _format_command_failure(result: CommandResult) -> str:
    return (
        f"command failed ({result.returncode}): {' '.join(result.command)}\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
```

- [ ] **Step 2: Add free port helper**

Add:

```python
def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])
```

- [ ] **Step 3: Add server start/wait helpers**

Add:

```python
def start_server(
    *,
    config_path: Path,
    port: int,
    log_path: Path,
) -> subprocess.Popen[str]:
    log_file = log_path.open("w", encoding="utf-8")
    return subprocess.Popen(
        (
            "uv",
            "run",
            "wf-rpc-server",
            "--config",
            str(config_path),
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ),
        stdout=log_file,
        stderr=subprocess.STDOUT,
        text=True,
    )


def wait_for_status(*, config_path: Path, timeout_seconds: float = 30) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error = ""
    command = ("uv", "run", "wf", "--config", str(config_path), "status")
    while time.monotonic() < deadline:
        completed = subprocess.run(
            command,
            text=True,
            capture_output=True,
            check=False,
        )
        if completed.returncode == 0:
            return
        last_error = completed.stderr or completed.stdout
        time.sleep(0.5)
    raise TimeoutError(f"server did not become ready: {last_error}")


def stop_server(process: subprocess.Popen[str]) -> None:
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)
```

Note: the log file handle is owned by the child process redirection in this first version. If review flags handle lifetime on Windows, change `start_server` to return a small dataclass containing both process and log file and close the file in `stop_server`.

- [ ] **Step 4: Run helper tests**

Run:

```bash
uv run pytest tests/examples/test_rpc_cli_smoke.py -q
```

Expected: PASS.

## Task 3: Smoke Flow

**Files:**
- Modify: `examples/rpc_cli_smoke.py`

- [ ] **Step 1: Add CLI command builders**

Add:

```python
def wf_command(config_path: Path, *args: str) -> tuple[str, ...]:
    return ("uv", "run", "wf", "--config", str(config_path), *args)
```

- [ ] **Step 2: Add smoke flow**

Add:

```python
def run_smoke_flow(*, config_path: Path, ids: SmokeIds) -> str:
    run_command(wf_command(config_path, "status"))
    run_command(wf_command(config_path, "source", "list", "--format", "compact"))
    run_command(wf_command(config_path, "cap", "list", "--source", "wf.std", "--format", "ids"))
    run_command(wf_command(config_path, "cap", "inspect", "wf.std.constant"))
    run_command(
        wf_command(
            config_path,
            "cap",
            "call",
            "wf.std.constant",
            "--input",
            '{"value":"smoke"}',
            "--format",
            "compact",
        )
    )
    run_command(
        wf_command(
            config_path,
            "draft",
            "create-from-capability",
            ids.workspace_id,
            "wf.std.constant",
            "--name",
            ids.workspace_id,
            "--title",
            "RPC CLI Smoke",
        )
    )
    run_command(wf_command(config_path, "draft", "validate", ids.workspace_id))
    run_command(
        wf_command(
            config_path,
            "draft",
            "save",
            ids.workspace_id,
            "--artifact",
            ids.artifact_id,
            "--version",
            "1",
            "--title",
            "RPC CLI Smoke Artifact",
            "--outcome",
            "ok",
            "--binding",
            "wf.std=wf.std",
        )
    )
    run_command(
        wf_command(
            config_path,
            "deploy",
            "save",
            ids.deployment_id,
            "--artifact",
            ids.artifact_id,
            "--version",
            "1",
            "--binding",
            "wf.std=wf.std",
        )
    )
    run_command(wf_command(config_path, "deploy", "validate", ids.deployment_id))
    run_result = run_command(
        wf_command(
            config_path,
            "run",
            "start",
            ids.deployment_id,
            "--input",
            '{"value":"from workflow"}',
        )
    )
    run_payload = parse_json_stdout(run_result.stdout, command=run_result.command)
    run_id = str(run_payload["run_id"])
    run_command(wf_command(config_path, "run", "inspect", run_id))
    run_command(wf_command(config_path, "run", "trace", run_id, "--from", "0", "--limit", "10"))
    return run_id
```

- [ ] **Step 3: Add cleanup helper**

Add:

```python
def cleanup_smoke(*, config_path: Path, ids: SmokeIds) -> None:
    commands = (
        wf_command(config_path, "deploy", "delete", ids.deployment_id),
        wf_command(config_path, "artifact", "delete", ids.artifact_id, "1", "--confirm"),
        wf_command(config_path, "draft", "delete", ids.workspace_id, "--confirm"),
    )
    for command in commands:
        try:
            run_command(command, timeout_seconds=30)
        except Exception as exc:
            print(f"cleanup warning: {exc}", file=sys.stderr)
```

- [ ] **Step 4: Run helper tests**

Run:

```bash
uv run pytest tests/examples/test_rpc_cli_smoke.py -q
```

Expected: PASS.

## Task 4: Main Function And CLI

**Files:**
- Modify: `examples/rpc_cli_smoke.py`

- [ ] **Step 1: Add argument parser**

Add:

```python
def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Use an existing workflow config and do not spawn a server.",
    )
    parser.add_argument(
        "--keep-temp",
        action="store_true",
        help="Keep temporary config/store/logs after the run.",
    )
    return parser.parse_args(argv)
```

- [ ] **Step 2: Add temp-config runner**

Add:

```python
def run_with_temp_server(*, keep_temp: bool) -> int:
    temp = tempfile.TemporaryDirectory(prefix="wf-rpc-smoke-")
    temp_path = Path(temp.name)
    server: subprocess.Popen[str] | None = None
    try:
        port = find_free_port()
        config_path = temp_path / "wf.config.json"
        store_root = temp_path / "store"
        config_path.write_text(
            json.dumps(build_workflow_config(store_root=store_root, port=port), indent=2),
            encoding="utf-8",
        )
        server = start_server(
            config_path=config_path,
            port=port,
            log_path=temp_path / "wf-rpc-server.log",
        )
        wait_for_status(config_path=config_path)
        ids = SmokeIds.from_suffix(str(int(time.time())))
        try:
            run_id = run_smoke_flow(config_path=config_path, ids=ids)
        finally:
            cleanup_smoke(config_path=config_path, ids=ids)
        print(f"PASS rpc cli smoke run_id={run_id}")
        return 0
    except Exception as exc:
        print(f"FAIL rpc cli smoke: {exc}", file=sys.stderr)
        print(f"temp dir: {temp_path}", file=sys.stderr)
        return 1
    finally:
        if server is not None:
            stop_server(server)
        if keep_temp:
            temp.cleanup = lambda: None  # type: ignore[method-assign]
        temp.cleanup()
```

If basedpyright dislikes assigning `temp.cleanup`, replace with manual `temp_path` creation via `tempfile.mkdtemp()` and `shutil.rmtree()` when `keep_temp` is false.

- [ ] **Step 3: Add existing-config runner**

Add:

```python
def run_with_existing_config(config_path: Path) -> int:
    ids = SmokeIds.from_suffix(str(int(time.time())))
    try:
        run_id = run_smoke_flow(config_path=config_path, ids=ids)
    finally:
        cleanup_smoke(config_path=config_path, ids=ids)
    print(f"PASS rpc cli smoke run_id={run_id}")
    return 0
```

- [ ] **Step 4: Add main entrypoint**

Add:

```python
def main(argv: list[str] | None = None) -> int:
    args = parse_args(list(sys.argv[1:] if argv is None else argv))
    if args.config is not None:
        return run_with_existing_config(args.config)
    return run_with_temp_server(keep_temp=bool(args.keep_temp))


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run static checks**

Run:

```bash
uv run ruff check examples/rpc_cli_smoke.py tests/examples/test_rpc_cli_smoke.py
uv run basedpyright --level error examples/rpc_cli_smoke.py tests/examples/test_rpc_cli_smoke.py
```

Expected: PASS. If the `TemporaryDirectory.cleanup` assignment fails type-checking, switch to `mkdtemp`/`shutil.rmtree` as noted above.

## Task 5: Live Script Verification

**Files:**
- Runtime only.

- [ ] **Step 1: Run the script**

Run:

```bash
uv run python examples/rpc_cli_smoke.py
```

Expected:

- The script starts a temporary server.
- It prints each command.
- It prints `PASS rpc cli smoke run_id=...`.
- It terminates the server.
- It removes the temp directory unless `--keep-temp` was passed.

- [ ] **Step 2: Run existing-config mode if a server is already running**

Optional:

```bash
uv run python examples/rpc_cli_smoke.py --config wf.config.json
```

Expected: PASS if `wf.config.json` targets a running server.

## Task 6: Docs

**Files:**
- Modify: `docs/runbooks/rpc-cli-smoke.md`
- Modify: `docs/README.md`
- Modify: `docs/project_map.md`
- Modify: `docs/current_roadmap.md`

- [ ] **Step 1: Link the script from the runbook**

Add near the top of `docs/runbooks/rpc-cli-smoke.md`:

```markdown
For an automated version of this runbook:

```bash
uv run python examples/rpc_cli_smoke.py
```

Use `--keep-temp` to preserve logs and the generated config/store after failure.
```

- [ ] **Step 2: Add to docs index or project map**

In `docs/project_map.md`, add `examples/rpc_cli_smoke.py` to the Examples section as the automated RPC CLI smoke script.

- [ ] **Step 3: Update roadmap**

Mark smoke automation complete in `docs/current_roadmap.md`.

## Task 7: Final Verification

- [ ] **Step 1: Run focused tests**

Run:

```bash
uv run pytest tests/examples/test_rpc_cli_smoke.py -q
```

Expected: PASS.

- [ ] **Step 2: Run lint/type checks**

Run:

```bash
uv run ruff check examples/rpc_cli_smoke.py tests/examples/test_rpc_cli_smoke.py docs/runbooks/rpc-cli-smoke.md docs/project_map.md docs/current_roadmap.md
uv run basedpyright --level error examples/rpc_cli_smoke.py tests/examples/test_rpc_cli_smoke.py
```

Expected: PASS.

- [ ] **Step 3: Run live smoke**

Run:

```bash
uv run python examples/rpc_cli_smoke.py
```

Expected: PASS.

- [ ] **Step 4: Archive plan**

Move this plan to:

```text
docs/historical/superpowers/plans/2026-06-09-rpc-cli-smoke-example.md
```

Update any live roadmap link to the historical path.

