"""RPC CLI smoke test: spawn wf-rpc-server, run bounded CLI lifecycle, clean up."""

from __future__ import annotations

import argparse
import json
import shutil
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
            "transports": [{"kind": "rpc_http", "host": "127.0.0.1", "port": port}],
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


@dataclass(frozen=True, slots=True)
class CommandResult:
    command: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str


def run_command(
    command: tuple[str, ...], *, timeout_seconds: float = 60
) -> CommandResult:
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


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@dataclass(frozen=True, slots=True)
class ServerHandle:
    process: subprocess.Popen[str]


def start_server(
    *,
    config_path: Path,
    port: int,
) -> ServerHandle:
    # Use DEVNULL instead of a log file: on Windows, inherited file handles from
    # uv/grandchildren can keep temp directories locked after the smoke exits.
    process = subprocess.Popen(
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
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return ServerHandle(process=process)


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


def stop_server(handle: ServerHandle) -> None:
    if sys.platform == "win32":
        # uv run is the parent process; taskkill /T also stops the spawned server.
        subprocess.run(
            ("taskkill", "/F", "/T", "/PID", str(handle.process.pid)),
            capture_output=True,
            check=False,
        )
    else:
        handle.process.terminate()
    try:
        handle.process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        handle.process.kill()
        handle.process.wait(timeout=10)


def wf_command(config_path: Path, *args: str) -> tuple[str, ...]:
    return ("uv", "run", "wf", "--config", str(config_path), *args)


def run_smoke_flow(*, config_path: Path, ids: SmokeIds) -> str:
    run_command(wf_command(config_path, "status"))
    run_command(wf_command(config_path, "source", "list", "--format", "compact"))
    run_command(
        wf_command(config_path, "cap", "list", "--source", "wf.std", "--format", "ids")
    )
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
    run_command(
        wf_command(config_path, "run", "trace", run_id, "--from", "0", "--limit", "10")
    )
    return run_id


def cleanup_smoke(*, config_path: Path, ids: SmokeIds) -> None:
    commands = (
        wf_command(config_path, "deploy", "delete", ids.deployment_id),
        wf_command(
            config_path, "artifact", "delete", ids.artifact_id, "1", "--confirm"
        ),
        wf_command(config_path, "draft", "delete", ids.workspace_id, "--confirm"),
    )
    for command in commands:
        try:
            run_command(command, timeout_seconds=30)
        except Exception as exc:
            print(f"cleanup warning: {exc}", file=sys.stderr)


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


def run_with_temp_server(*, keep_temp: bool) -> int:
    temp_path = Path(tempfile.mkdtemp(prefix="wf-rpc-smoke-"))
    server: ServerHandle | None = None
    try:
        port = find_free_port()
        config_path = temp_path / "wf.config.json"
        store_root = temp_path / "store"
        config_path.write_text(
            json.dumps(
                build_workflow_config(store_root=store_root, port=port), indent=2
            ),
            encoding="utf-8",
        )
        server = start_server(
            config_path=config_path,
            port=port,
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
        if not keep_temp:
            shutil.rmtree(temp_path, ignore_errors=True)


def run_with_existing_config(config_path: Path) -> int:
    ids = SmokeIds.from_suffix(str(int(time.time())))
    try:
        run_id = run_smoke_flow(config_path=config_path, ids=ids)
    except Exception as exc:
        print(f"FAIL rpc cli smoke: {exc}", file=sys.stderr)
        print(f"config: {config_path}", file=sys.stderr)
        return 1
    finally:
        cleanup_smoke(config_path=config_path, ids=ids)
    print(f"PASS rpc cli smoke run_id={run_id}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(list(sys.argv[1:] if argv is None else argv))
    if args.config is not None:
        return run_with_existing_config(args.config)
    return run_with_temp_server(keep_temp=bool(args.keep_temp))


if __name__ == "__main__":
    raise SystemExit(main())
