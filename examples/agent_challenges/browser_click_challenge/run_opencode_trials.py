from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

import yaml

Classification = Literal[
    "success",
    "workflow_script",
    "workflow_not_used",
    "run_failed",
    "timeout",
    "parse_error",
    "unknown",
]

ROOT = Path(__file__).resolve().parents[3]
CHALLENGE_DIR = Path(__file__).resolve().parent
DEFAULT_PROMPT = CHALLENGE_DIR / "prompt.md"
DEFAULT_RESULTS_DIR = CHALLENGE_DIR / "results"
DEFAULT_SERVER_PORT = 8772
EXAMPLE_CONFIG = ROOT / "examples" / "browser_click_workflow" / "wf.config.json"


def rpc_url_for_port(port: int) -> str:
    return f"http://127.0.0.1:{port}/rpc"


def server_command(*, port: int) -> list[str]:
    return [
        "uv",
        "run",
        "wf-rpc-server",
        "--config",
        str(EXAMPLE_CONFIG.relative_to(ROOT)).replace("\\", "/"),
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
    ]


def render_prompt(prompt_path: Path, *, rpc_url: str) -> str:
    command_prefix = f"uv run wf --url {rpc_url}"
    return (
        prompt_path.read_text(encoding="utf-8")
        .replace("{{rpc_url}}", rpc_url)
        .replace("{{wf_command_prefix}}", command_prefix)
    )


@dataclass(slots=True)
class ManagedServer:
    process: subprocess.Popen[str]
    rpc_url: str


def start_server(*, port: int, timeout_seconds: int = 30) -> ManagedServer:
    command = server_command(port=port)
    process = subprocess.Popen(
        command,
        cwd=ROOT,
        text=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    rpc_url = rpc_url_for_port(port)
    try:
        wait_for_status(rpc_url=rpc_url, timeout_seconds=timeout_seconds)
    except Exception:
        stop_server(process)
        raise
    return ManagedServer(process=process, rpc_url=rpc_url)


def wait_for_status(*, rpc_url: str, timeout_seconds: int) -> None:
    deadline = time.monotonic() + timeout_seconds
    command = ["uv", "run", "wf", "--url", rpc_url, "status"]
    last_stderr = ""
    while time.monotonic() < deadline:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        if completed.returncode == 0:
            return
        last_stderr = completed.stderr
        time.sleep(0.5)
    raise RuntimeError(f"wf status did not become ready: {last_stderr}")


def stop_server(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(process.pid)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    else:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)


@dataclass(frozen=True, slots=True)
class TrialConfig:
    model: str
    variant: str
    prompt_path: Path
    attach_url: str | None
    timeout_seconds: int
    rpc_url: str


def build_opencode_command(config: TrialConfig) -> list[str]:
    prompt_text = render_prompt(config.prompt_path, rpc_url=config.rpc_url)
    command = [
        "opencode",
        "run",
    ]
    if config.attach_url is not None:
        command.extend(["--attach", config.attach_url])
    command.extend(
        [
            prompt_text,
            "--format",
            "json",
            "--model",
            config.model,
            "--variant",
            config.variant,
        ]
    )
    return command


def parse_opencode_output(stdout: str) -> dict[str, Any]:
    text = stdout.strip()
    if not text:
        raise ValueError("opencode produced no JSON output")

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = _parse_jsonl_tail(text)

    if not isinstance(parsed, dict):
        raise ValueError("opencode output was not a JSON object")
    return parsed


def _parse_jsonl_tail(text: str) -> dict[str, Any]:
    last_error: json.JSONDecodeError | None = None
    parsed_events: list[dict[str, Any]] = []
    for line in reversed(text.splitlines()):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError as exc:
            last_error = exc
            continue
        if isinstance(parsed, dict):
            parsed_events.append(parsed)
            event_text = _event_text(parsed)
            if event_text is not None:
                return {"text": event_text, "event": parsed}
    if parsed_events:
        return parsed_events[0]
    if last_error is not None:
        raise last_error
    raise ValueError("opencode output did not contain JSON lines")


def _event_text(event: dict[str, Any]) -> str | None:
    """Extract assistant text from opencode JSON events.

    `opencode run --format json` emits many events. The final event can be a
    `step_finish`; the answer text is usually the previous `text` event under
    `part.text`.
    """
    part = event.get("part")
    if isinstance(part, dict):
        text = part.get("text")
        if isinstance(text, str):
            return text
    text = event.get("text")
    return text if isinstance(text, str) else None


def classify_output(text: str) -> Classification:
    report = extract_challenge_report(text)
    if report is not None:
        return classify_challenge_report(report)

    lowered = text.lower()
    product_command_markers = [
        "wf ",
        "wf-rpc-server",
    ]
    workflow_evidence_markers = [
        "deployment",
        "run id",
        "run_",
    ]
    used_product_command = any(marker in lowered for marker in product_command_markers)
    has_workflow_evidence = any(
        marker in lowered for marker in workflow_evidence_markers
    )
    used_helper_script = (
        "uv run python" in lowered
        or "python examples/" in lowered
        or "run_workflow.py" in lowered
    )
    failed = any(
        marker in lowered
        for marker in [
            "error:",
            "failed",
            "traceback",
            "exception",
            "validation failed",
        ]
    )
    before_false = _contains_bool_marker(lowered, "before.clicked", "false") or (
        '"before"' in lowered and '"clicked": false' in lowered
    )
    after_true = _contains_bool_marker(lowered, "after.clicked", "true") or (
        '"after"' in lowered and '"clicked": true' in lowered
    )

    if used_product_command and before_false and after_true and not failed:
        return "success"
    if has_workflow_evidence and used_helper_script and before_false and after_true:
        return "workflow_script"
    if (used_product_command or has_workflow_evidence) and failed:
        return "run_failed"
    if not has_workflow_evidence and (
        before_false or after_true or "playwright" in lowered
    ):
        return "workflow_not_used"
    return "unknown"


def extract_challenge_report(text: str) -> dict[str, Any] | None:
    """Extract the required final YAML challenge report from agent output."""
    marker = "```yaml"
    start = text.lower().rfind(marker)
    if start == -1:
        return None
    body_start = text.find("\n", start)
    if body_start == -1:
        return None
    end = text.find("```", body_start + 1)
    if end == -1:
        return None
    raw_yaml = text[body_start + 1 : end]
    loaded = yaml.safe_load(raw_yaml)
    if not isinstance(loaded, dict):
        return None
    report = loaded.get("challenge_report")
    return report if isinstance(report, dict) else None


def classify_challenge_report(report: dict[str, Any]) -> Classification:
    used_product_path = report.get("used_product_path") is True
    used_helper_script = report.get("used_helper_script") is True
    workflow_file = report.get("workflow_file")
    deployment_id = report.get("deployment_id")
    run_id = report.get("run_id")
    before_clicked = report.get("before_clicked")
    after_clicked = report.get("after_clicked")
    failed = report.get("run_failed") is True

    if failed:
        return "run_failed"
    if used_helper_script:
        return "workflow_script"
    if (
        used_product_path
        and isinstance(workflow_file, str)
        and bool(workflow_file)
        and isinstance(deployment_id, str)
        and bool(deployment_id)
        and isinstance(run_id, str)
        and bool(run_id)
        and before_clicked is False
        and after_clicked is True
    ):
        return "success"
    if not used_product_path and (
        before_clicked is not None or after_clicked is not None
    ):
        return "workflow_not_used"
    return "unknown"


def _contains_bool_marker(text: str, marker: str, value: str) -> bool:
    marker_index = text.find(marker)
    if marker_index == -1:
        return False
    return value in text[marker_index : marker_index + 80]


def trial_output_path(results_dir: Path, *, model: str, index: int) -> Path:
    safe_model = model.replace("/", "_").replace(":", "_")
    return results_dir / f"{safe_model}-trial-{index:03d}.json"


def run_trial(config: TrialConfig, *, index: int, results_dir: Path) -> dict[str, Any]:
    command = build_opencode_command(config)
    started = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=config.timeout_seconds,
            check=False,
        )
        duration_seconds = time.monotonic() - started
    except subprocess.TimeoutExpired as exc:
        payload = {
            "index": index,
            "config": _jsonable_config(config),
            "command": command,
            "classification": "timeout",
            "duration_seconds": config.timeout_seconds,
            "returncode": None,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
            "parsed": None,
        }
        _write_trial_result(results_dir, config=config, index=index, payload=payload)
        return payload

    parsed: dict[str, Any] | None
    try:
        parsed = parse_opencode_output(completed.stdout)
        text = _result_text(parsed)
        classification = classify_output(text)
    except Exception:
        parsed = None
        classification = "parse_error"

    payload = {
        "index": index,
        "config": _jsonable_config(config),
        "command": command,
        "classification": classification,
        "duration_seconds": duration_seconds,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "parsed": parsed,
    }
    _write_trial_result(results_dir, config=config, index=index, payload=payload)
    return payload


def _result_text(parsed: dict[str, Any]) -> str:
    for key in ("text", "message", "content", "output"):
        value = parsed.get(key)
        if isinstance(value, str):
            return value
    return json.dumps(parsed, sort_keys=True)


def _jsonable_config(config: TrialConfig) -> dict[str, Any]:
    payload = asdict(config)
    payload["prompt_path"] = str(config.prompt_path)
    return payload


def _write_trial_result(
    results_dir: Path,
    *,
    config: TrialConfig,
    index: int,
    payload: dict[str, Any],
) -> None:
    results_dir.mkdir(parents=True, exist_ok=True)
    path = trial_output_path(results_dir, model=config.model, index=index)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="opencode/mimo-v2.5-free")
    parser.add_argument("--variant", default="high")
    parser.add_argument("--trials", type=int, default=1)
    parser.add_argument("--timeout-seconds", type=int, default=600)
    parser.add_argument(
        "--attach",
        dest="attach_url",
        default=None,
        help=(
            "Attach to a running opencode server URL. This is not a direct MCP "
            "server URL."
        ),
    )
    parser.add_argument("--prompt", type=Path, default=DEFAULT_PROMPT)
    parser.add_argument("--results-dir", type=Path, default=DEFAULT_RESULTS_DIR)
    parser.add_argument("--server-url", default=None)
    parser.add_argument("--start-server", action="store_true", default=True)
    parser.add_argument("--no-start-server", action="store_false", dest="start_server")
    parser.add_argument("--server-port", type=int, default=DEFAULT_SERVER_PORT)
    args = parser.parse_args(argv)

    if args.trials < 1:
        parser.error("--trials must be >= 1")

    if args.server_url is not None:
        rpc_url = args.server_url
        managed_server: ManagedServer | None = None
    elif args.start_server:
        managed_server = start_server(port=args.server_port)
        rpc_url = managed_server.rpc_url
    else:
        rpc_url = rpc_url_for_port(args.server_port)
        managed_server = None

    try:
        config = TrialConfig(
            model=args.model,
            variant=args.variant,
            prompt_path=args.prompt,
            attach_url=args.attach_url,
            timeout_seconds=args.timeout_seconds,
            rpc_url=rpc_url,
        )

        summaries: list[dict[str, Any]] = []
        for index in range(1, args.trials + 1):
            result = run_trial(config, index=index, results_dir=args.results_dir)
            summaries.append(
                {
                    "index": index,
                    "classification": result["classification"],
                    "returncode": result["returncode"],
                    "duration_seconds": round(float(result["duration_seconds"]), 3),
                }
            )
            print(json.dumps(summaries[-1], sort_keys=True))

        success_count = sum(
            1 for item in summaries if item["classification"] == "success"
        )
        print(json.dumps({"success_count": success_count, "trial_count": len(summaries)}))
        return 0
    finally:
        if managed_server is not None:
            stop_server(managed_server.process)


if __name__ == "__main__":
    raise SystemExit(main())
