from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]

from examples.agent_challenges.opencode_io import (  # noqa: E402
    build_opencode_command,
    parse_opencode_output,
    result_text,
)
from examples.agent_challenges.reports import (  # noqa: E402
    save_report_from_result_payload,
)
from examples.agent_challenges.workspace import (  # noqa: E402
    ChallengeDef,
    TrialConfig,
    _display_path,
    prepare_trial_workspace,
    rpc_url_for_port,
    server_command,
    starting_trial_index,
    trial_output_path,
    wf_command_prefix_for_config,
)


@dataclass(slots=True)
class ManagedServer:
    process: subprocess.Popen[str]
    rpc_url: str


def start_server(
    defn: ChallengeDef,
    *,
    port: int,
    timeout_seconds: int = 30,
) -> ManagedServer:
    command = server_command(port=port, config_arg=defn.server_config_arg)
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
        try:
            process.terminate()
        except OSError:
            return
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)


def run_trial(
    config: TrialConfig,
    *,
    index: int,
    results_dir: Path,
    classify_fn: Callable[[str], str],
) -> dict[str, Any]:
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
        _write_trial_report(payload)
        _write_trial_result(results_dir, config=config, index=index, payload=payload)
        return payload

    parsed: dict[str, Any] | None
    parse_error: dict[str, str] | None = None
    try:
        parsed = parse_opencode_output(completed.stdout)
        text = result_text(parsed)
        classification = classify_fn(text)
    except Exception as exc:
        parsed = None
        classification = "parse_error"
        parse_error = {
            "type": type(exc).__name__,
            "message": str(exc),
        }

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
    if parse_error is not None:
        payload["parse_error"] = parse_error
    _write_trial_report(payload)
    _write_trial_result(results_dir, config=config, index=index, payload=payload)
    return payload


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


def _write_trial_report(payload: dict[str, Any]) -> None:
    try:
        report_path = save_report_from_result_payload(payload)
    except ValueError as exc:
        payload["report_save_error"] = str(exc)
        return
    payload["report_path"] = report_path.as_posix()


def main(
    defn: ChallengeDef,
    classify_fn: Callable[[str], str],
    argv: list[str] | None = None,
) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="opencode/mimo-v2.5-free")
    parser.add_argument("--variant", default="high")
    parser.add_argument("--trials", type=int, default=1)
    parser.add_argument("--timeout-seconds", type=int, default=1000)
    parser.add_argument(
        "--attach",
        dest="attach_url",
        default=None,
        help=(
            "Attach to a running opencode server URL. This is not a direct MCP "
            "server URL."
        ),
    )
    parser.add_argument("--prompt", type=Path, default=defn.default_prompt)
    parser.add_argument("--results-dir", type=Path, default=defn.default_results_dir)
    parser.add_argument(
        "--workspaces-dir", type=Path, default=defn.default_workspaces_dir
    )
    parser.add_argument(
        "--workspace-template",
        type=Path,
        default=defn.default_workspace_template,
        help="Template directory copied for each local-mode trial workspace.",
    )
    parser.add_argument(
        "--source-root",
        type=Path,
        default=defn.source_root,
        help="Python source root written into each generated trial config.",
    )
    parser.add_argument("--server-url", default=None)
    parser.add_argument("--start-server", action="store_true", default=False)
    parser.add_argument("--no-start-server", action="store_false", dest="start_server")
    parser.add_argument("--server-port", type=int, default=defn.default_server_port)
    args = parser.parse_args(argv)

    if args.trials < 1:
        parser.error("--trials must be >= 1")

    if args.server_url is not None:
        rpc_url = args.server_url
        managed_server: ManagedServer | None = None
        wf_command_prefix = f"uv run wf --url {rpc_url}"
        server_context = f"A workflow RPC server is available at `{rpc_url}`."
    elif args.start_server:
        managed_server = start_server(defn, port=args.server_port)
        rpc_url = managed_server.rpc_url
        wf_command_prefix = f"uv run wf --url {rpc_url}"
        server_context = (
            f"The harness started a workflow RPC server at `{rpc_url}` for this trial."
        )
    else:
        managed_server = None
        local_prefix = f"uv run wf --config {defn.server_config_arg} --local"
        wf_command_prefix = local_prefix
        server_context = (
            "No external workflow RPC server is staged. The command prefix uses "
            "`--local`, which builds the configured workflow server in the CLI "
            "process for each command."
        )

    try:
        use_trial_workspace = args.server_url is None and not args.start_server
        first_index = starting_trial_index(
            model=args.model,
            results_dir=args.results_dir,
            workspaces_dir=args.workspaces_dir,
        )
        summaries: list[dict[str, Any]] = []
        for index in range(first_index, first_index + args.trials):
            prompt_path = args.prompt
            trial_wf_command_prefix = wf_command_prefix
            trial_server_context = server_context
            if use_trial_workspace:
                workspace = prepare_trial_workspace(
                    defn,
                    model=args.model,
                    index=index,
                    workspaces_dir=args.workspaces_dir,
                    template_dir=args.workspace_template,
                    source_root=args.source_root,
                )
                if args.prompt == defn.default_prompt:
                    prompt_path = workspace.prompt_path
                trial_wf_command_prefix = wf_command_prefix_for_config(
                    workspace.config_path
                )
                workspace_path = _display_path(workspace.root)
                config_path = _display_path(workspace.config_path)
                trial_server_context = (
                    "No external workflow RPC server is staged. Use the "
                    "per-trial workspace config copied to "
                    f"`{config_path}`. Your writable trial workspace is "
                    f"`{workspace_path}`."
                )
            config = TrialConfig(
                model=args.model,
                variant=args.variant,
                prompt_path=prompt_path,
                attach_url=args.attach_url,
                timeout_seconds=args.timeout_seconds,
                wf_command_prefix=trial_wf_command_prefix,
                server_context=trial_server_context,
            )
            result = run_trial(
                config,
                index=index,
                results_dir=args.results_dir,
                classify_fn=classify_fn,
            )
            summaries.append(
                {
                    "index": index,
                    "classification": result["classification"],
                    "returncode": result["returncode"],
                    "duration_seconds": round(float(result["duration_seconds"]), 3),
                    "report_path": _optional_string(result.get("report_path")),
                    "report_save_error": result.get("report_save_error"),
                }
            )
            print(json.dumps(summaries[-1], sort_keys=True))

        success_count = sum(
            1 for item in summaries if item["classification"] == "success"
        )
        print(
            json.dumps({"success_count": success_count, "trial_count": len(summaries)})
        )
        return 0
    finally:
        if managed_server is not None:
            stop_server(managed_server.process)


def _optional_string(value: object) -> str | None:
    return None if value is None else str(value)


def _get_git_commit() -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        if completed.returncode == 0:
            return completed.stdout.strip()
    except Exception:
        pass
    return "unknown"


def _get_git_dirty() -> bool:
    try:
        completed = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        if completed.returncode == 0:
            return bool(completed.stdout.strip())
    except Exception:
        pass
    return False


def run_v2_trial(
    challenge: object,
    *,
    profile: object,
    model: str,
    variant: str,
    index: int,
    workspaces_dir: Path,
    results_dir: Path,
    instruction_bundle: Path,
    timeout_seconds: int = 3600,
    attach_url: str | None = None,
    run_fn: Any = None,
) -> dict[str, Any]:
    from .metrics import extract_trial_metrics, metrics_payload
    from .models import InstructionProfile, LoadedChallenge
    from .policy import evaluate_policy
    from .prompts import compose_trial_prompt
    from .workspace import (
        _display_path,
        prepare_v2_trial_workspace,
        wf_command_prefix_for_config,
    )

    if run_fn is None:
        run_fn = subprocess.run

    if not isinstance(challenge, LoadedChallenge):
        raise TypeError("challenge must be a LoadedChallenge")
    if not isinstance(profile, InstructionProfile):
        profile = InstructionProfile(profile)

    workspace = prepare_v2_trial_workspace(
        challenge,
        profile=profile,
        model=model,
        index=index,
        workspaces_dir=workspaces_dir,
        instruction_bundle=instruction_bundle,
    )

    wf_command_prefix = wf_command_prefix_for_config(workspace.config_path)
    workspace_path = _display_path(workspace.root)
    config_path_display = _display_path(workspace.config_path)
    server_context = (
        "No external workflow RPC server is staged. Use the "
        "per-trial workspace config copied to "
        f"`{config_path_display}`. Your writable trial workspace is "
        f"`{workspace_path}`."
    )

    rendered = compose_trial_prompt(
        challenge,
        profile=profile,
        wf_command_prefix=wf_command_prefix,
        server_context=server_context,
        workspace_path=workspace.root,
    )

    workspace.rendered_prompt_path.write_text(rendered.text, encoding="utf-8")

    command = [
        "opencode",
        "run",
    ]
    if attach_url is not None:
        command.extend(["--attach", attach_url])
    command.extend(
        [
            rendered.text,
            "--format",
            "json",
            "--model",
            model,
            "--variant",
            variant,
        ]
    )

    started = time.monotonic()
    stdout = ""
    stderr = ""
    returncode = 0
    task_outcome = "success"
    parse_error: dict[str, str] | None = None

    try:
        completed = run_fn(
            command,
            cwd=str(workspace.root),
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
        duration_seconds = time.monotonic() - started
        stdout = completed.stdout
        stderr = completed.stderr
        returncode = completed.returncode
        if returncode != 0:
            task_outcome = "failed"
    except subprocess.TimeoutExpired as exc:
        duration_seconds = time.monotonic() - started
        stdout = (
            exc.stdout
            if isinstance(exc.stdout, str)
            else (exc.stdout or b"").decode("utf-8", errors="replace")
            if exc.stdout
            else ""
        )
        stderr = (
            exc.stderr
            if isinstance(exc.stderr, str)
            else (exc.stderr or b"").decode("utf-8", errors="replace")
            if exc.stderr
            else ""
        )
        task_outcome = "timeout"
    except Exception as exc:
        duration_seconds = time.monotonic() - started
        task_outcome = "parse_error"
        parse_error = {
            "type": type(exc).__name__,
            "message": str(exc),
        }

    metrics = extract_trial_metrics(stdout)
    metrics_dir = workspace.root
    metrics_dir.mkdir(parents=True, exist_ok=True)
    (metrics_dir / "metrics.json").write_text(
        json.dumps(metrics_payload(metrics), indent=2, sort_keys=True),
        encoding="utf-8",
    )

    repository_root = ROOT
    policy = evaluate_policy(
        profile,
        metrics.tool_calls,
        workspace_root=workspace.root,
        repository_root=repository_root,
        workspaces_root=workspaces_dir,
    )

    success_assertions = challenge.manifest.report.success_assertions
    required_fields = challenge.manifest.report.required_fields
    assertion_failures: list[str] = []
    challenge_report: dict[str, Any] | None = None
    parsed_output: dict[str, Any] | None = None
    report_parse_error: dict[str, str] | None = None

    if stdout.strip():
        try:
            parsed_output = parse_opencode_output(stdout)
            report_text = result_text(parsed_output)
            from examples.agent_challenges.classification import (
                extract_challenge_report,
            )

            challenge_report = extract_challenge_report(report_text)
        except (ValueError, KeyError, yaml.YAMLError) as exc:
            challenge_report = None
            report_parse_error = {
                "type": type(exc).__name__,
                "message": str(exc),
            }

    if task_outcome == "success":
        if required_fields and challenge_report is None:
            assertion_failures.append(
                "could not extract challenge report for required_fields evaluation"
            )
        elif required_fields and challenge_report is not None:
            for field in required_fields:
                if field not in challenge_report:
                    assertion_failures.append(f"required field missing: {field}")

        if success_assertions and challenge_report is not None:
            for field, expected in success_assertions.items():
                actual = challenge_report.get(field)
                if actual != expected:
                    assertion_failures.append(
                        f"{field}: expected {expected!r}, got {actual!r}"
                    )
        elif success_assertions and challenge_report is None:
            if not assertion_failures:
                assertion_failures.append(
                    "could not extract challenge report for success_assertions evaluation"
                )

    if assertion_failures:
        task_outcome = "failed"

    result: dict[str, Any] = {
        "instruction_profile": profile.value,
        "task_outcome": task_outcome,
        "evaluation_validity": policy.validity.value,
        "prompt_hashes": {
            "base": rendered.base_sha256,
            "profile": rendered.profile_sha256,
            "challenge": rendered.challenge_sha256,
            "rendered": rendered.rendered_sha256,
        },
        "metrics": metrics_payload(metrics),
        "policy": {
            "validity": policy.validity.value,
            "disallowed_reads": list(policy.disallowed_reads),
            "escalated_to_product_code": policy.escalated_to_product_code,
            "opaque_shell_commands": list(policy.opaque_shell_commands),
        },
        "repository_commit": _get_git_commit(),
        "repository_dirty": _get_git_dirty(),
        "harness_version": "v2",
        "index": index,
        "model": model,
        "variant": variant,
        "duration_seconds": round(duration_seconds, 3),
        "returncode": returncode,
        "stdout": stdout,
        "stderr": stderr,
        "parsed": parsed_output,
    }

    if assertion_failures:
        result["assertion_failures"] = assertion_failures
    if parse_error is not None:
        result["parse_error"] = parse_error
    if report_parse_error is not None:
        result["report_parse_error"] = report_parse_error
    if challenge_report is not None:
        result["challenge_report"] = challenge_report

    results_dir.mkdir(parents=True, exist_ok=True)
    result_path = (
        results_dir
        / f"{model.replace('/', '_').replace(':', '_')}-trial-{index:03d}.json"
    )
    result_path.write_text(
        json.dumps(result, indent=2, sort_keys=True), encoding="utf-8"
    )

    return result
