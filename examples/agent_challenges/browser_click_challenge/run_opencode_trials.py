from __future__ import annotations

import argparse
import json
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

Classification = Literal[
    "success",
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


@dataclass(frozen=True, slots=True)
class TrialConfig:
    model: str
    variant: str
    prompt_path: Path
    attach_url: str | None
    timeout_seconds: int


def build_opencode_command(config: TrialConfig) -> list[str]:
    prompt_text = config.prompt_path.read_text(encoding="utf-8")
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
            return parsed
    if last_error is not None:
        raise last_error
    raise ValueError("opencode output did not contain JSON lines")


def classify_output(text: str) -> Classification:
    lowered = text.lower()
    workflow_markers = [
        "wf ",
        "wf-rpc-server",
        "deployment",
        "run id",
        "run_",
    ]
    used_workflow = any(marker in lowered for marker in workflow_markers)
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
    before_false = (
        "before.clicked is false" in lowered
        or '"before"' in lowered
        and '"clicked": false' in lowered
    )
    after_true = (
        "after.clicked is true" in lowered
        or '"after"' in lowered
        and '"clicked": true' in lowered
    )

    if used_workflow and before_false and after_true and not failed:
        return "success"
    if used_workflow and failed:
        return "run_failed"
    if not used_workflow and (before_false or after_true or "playwright" in lowered):
        return "workflow_not_used"
    return "unknown"


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
    parser.add_argument("--attach", dest="attach_url", default=None)
    parser.add_argument("--prompt", type=Path, default=DEFAULT_PROMPT)
    parser.add_argument("--results-dir", type=Path, default=DEFAULT_RESULTS_DIR)
    args = parser.parse_args(argv)

    if args.trials < 1:
        parser.error("--trials must be >= 1")

    config = TrialConfig(
        model=args.model,
        variant=args.variant,
        prompt_path=args.prompt,
        attach_url=args.attach_url,
        timeout_seconds=args.timeout_seconds,
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

    success_count = sum(1 for item in summaries if item["classification"] == "success")
    print(json.dumps({"success_count": success_count, "trial_count": len(summaries)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
