from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

FINAL_REPORT_PROMPT = (
    "Your workflow attempt is over. Do not continue coding. Return only the "
    "final challenge report using the required challenge_report YAML schema. "
    "Include run_id, evidence, failed attempts, read flags, missed requirements, "
    "and whether the run succeeded."
)

CONTINUE_PROMPT = (
    "Continue this same trial from the current session. Do not restart in a new "
    "workspace. If the workflow is already complete, stop and return only the "
    "final challenge_report YAML using the required schema."
)


def _event_session_id(event: dict[str, Any]) -> str | None:
    session_id = event.get("sessionID")
    if isinstance(session_id, str) and session_id:
        return session_id
    part = event.get("part")
    if isinstance(part, dict):
        nested = part.get("sessionID")
        if isinstance(nested, str) and nested:
            return nested
    return None


def extract_session_id(stdout: str) -> str | None:
    """Return the first OpenCode session id found in JSONL stdout."""
    for line in stdout.splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        session_id = _event_session_id(event)
        if session_id is not None:
            return session_id
    return None


def resume_prompt_for_result(result: dict[str, object]) -> str:
    """Choose a continuation prompt from the result failure shape."""
    task_outcome = result.get("task_outcome")
    assertion_failures = result.get("assertion_failures")
    failures = assertion_failures if isinstance(assertion_failures, list) else []
    if task_outcome == "timeout":
        return CONTINUE_PROMPT
    if any("could not extract challenge report" in str(item) for item in failures):
        return FINAL_REPORT_PROMPT
    if result.get("parsed") is None and result.get("stdout"):
        return FINAL_REPORT_PROMPT
    return CONTINUE_PROMPT


def build_resume_command(
    *,
    session_id: str,
    attach_url: str | None,
    model: str,
    variant: str,
    prompt: str,
) -> list[str]:
    command = ["opencode", "run", "--session", session_id]
    if attach_url is not None:
        command.extend(["--attach", attach_url])
    command.extend(["--format", "json", "--model", model, "--variant", variant, prompt])
    return command


def display_resume_command(command: list[str]) -> str:
    """Render an argv list for copy-paste display without changing execution."""
    return subprocess.list2cmdline(command)


def resume_result_path(result_path: Path) -> Path:
    stem = result_path.with_suffix("")
    index = 1
    while True:
        candidate = stem.with_name(f"{stem.name}.resume-{index:03d}.json")
        if not candidate.exists():
            return candidate
        index += 1
