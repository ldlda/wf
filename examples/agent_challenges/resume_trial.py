from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

try:
    from .opencode_resume import (
        PromptMode,
        display_resume_command,
        resume_command_from_result,
        resume_result_path,
    )
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from examples.agent_challenges.opencode_resume import (
        PromptMode,
        display_resume_command,
        resume_command_from_result,
        resume_result_path,
    )


RunFn = Callable[..., subprocess.CompletedProcess[str]]


def _utf8_subprocess_env() -> dict[str, str]:
    env = dict(os.environ)
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    return env


def _load_command(
    result: dict[str, Any],
    *,
    session_id: str | None = None,
    attach_url: str | None = None,
    model: str | None = None,
    variant: str | None = None,
    prompt_mode: PromptMode = "auto",
) -> list[str]:
    return resume_command_from_result(
        result,
        session_id=session_id,
        attach_url=attach_url,
        model=model,
        variant=variant,
        prompt_mode=prompt_mode,
    )


def _display_command(command: list[str]) -> str:
    return display_resume_command(command)


def resume_from_result(
    result_path: Path,
    *,
    session_id: str | None = None,
    attach_url: str | None = None,
    model: str | None = None,
    variant: str | None = None,
    prompt_mode: PromptMode = "auto",
    run_fn: RunFn = subprocess.run,
) -> Path:
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if not isinstance(result, dict):
        raise ValueError("result file must contain a JSON object")
    command = _load_command(
        result,
        session_id=session_id,
        attach_url=attach_url,
        model=model,
        variant=variant,
        prompt_mode=prompt_mode,
    )
    workspace_path = result.get("workspace_path")
    cwd = str(workspace_path) if isinstance(workspace_path, str) else None
    started = time.monotonic()
    completed = run_fn(
        command,
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
        encoding="utf-8",
        errors="replace",
        env=_utf8_subprocess_env(),
    )
    payload = {
        "harness_version": "v2-resume",
        "source_result_path": str(result_path.resolve()),
        "command": command,
        "duration_seconds": round(time.monotonic() - started, 3),
        "returncode": completed.returncode,
        "stdout": completed.stdout or "",
        "stderr": completed.stderr or "",
    }
    output_path = resume_result_path(result_path)
    output_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )
    return output_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Print or run an OpenCode trial resume command."
    )
    parser.add_argument("--from-result", type=Path, required=True)
    parser.add_argument("--session")
    parser.add_argument("--attach", dest="attach_url")
    parser.add_argument("--model")
    parser.add_argument("--variant")
    parser.add_argument(
        "--prompt-mode",
        choices=("auto", "continue", "final-report"),
        default="auto",
        help="Choose the resume prompt instead of relying on auto detection.",
    )
    parser.add_argument("--print-command", action="store_true")
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args(argv)

    try:
        result = json.loads(args.from_result.read_text(encoding="utf-8"))
        if not isinstance(result, dict):
            raise ValueError("result file must contain a JSON object")
        command = _load_command(
            result,
            session_id=args.session,
            attach_url=args.attach_url,
            model=args.model,
            variant=args.variant,
            prompt_mode=args.prompt_mode,
        )
        if args.run:
            print(
                resume_from_result(
                    args.from_result,
                    session_id=args.session,
                    attach_url=args.attach_url,
                    model=args.model,
                    variant=args.variant,
                    prompt_mode=args.prompt_mode,
                ).as_posix()
            )
        else:
            print(_display_command(command))
    except ValueError as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
