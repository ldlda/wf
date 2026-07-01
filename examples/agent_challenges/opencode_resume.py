from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Literal

PromptMode = Literal["auto", "continue", "final-report"]

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


def resume_prompt_for_mode(result: dict[str, object], mode: PromptMode) -> str:
    """Return the operator-selected resume prompt, falling back to auto detection."""
    if mode == "continue":
        return CONTINUE_PROMPT
    if mode == "final-report":
        return FINAL_REPORT_PROMPT
    return resume_prompt_for_result(result)


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


def resume_command_from_result(
    result: dict[str, Any],
    *,
    session_id: str | None = None,
    attach_url: str | None = None,
    model: str | None = None,
    variant: str | None = None,
    prompt_mode: PromptMode = "auto",
) -> list[str]:
    """Rebuild a resume command from validated metadata or old raw results."""
    opencode = result.get("opencode")

    stdout = result.get("stdout")
    stdout_text = stdout if isinstance(stdout, str) else ""
    if isinstance(opencode, dict):
        metadata_session_id = opencode.get("session_id")
        metadata_model = opencode.get("model")
        metadata_variant = opencode.get("variant")
        metadata_attach_url = opencode.get("attach_url")
    else:
        metadata_session_id = None
        metadata_model = None
        metadata_variant = None
        metadata_attach_url = None

    recovered_session_id = (
        session_id
        or (metadata_session_id if isinstance(metadata_session_id, str) else None)
        or extract_session_id(stdout_text)
    )
    if not recovered_session_id:
        raise ValueError("result has no opencode session id; pass --session")

    result_model = result.get("model")
    result_variant = result.get("variant")
    resolved_model = (
        model
        or (metadata_model if isinstance(metadata_model, str) else None)
        or (result_model if isinstance(result_model, str) else None)
    )
    resolved_variant = (
        variant
        or (metadata_variant if isinstance(metadata_variant, str) else None)
        or (result_variant if isinstance(result_variant, str) else None)
    )
    resolved_attach_url = attach_url or (
        metadata_attach_url if isinstance(metadata_attach_url, str) else None
    )

    if not resolved_model:
        raise ValueError("result has no opencode model; pass --model")
    if not resolved_variant:
        raise ValueError("result has no opencode variant; pass --variant")

    return build_resume_command(
        session_id=recovered_session_id,
        attach_url=resolved_attach_url,
        model=resolved_model,
        variant=resolved_variant,
        prompt=resume_prompt_for_mode(result, prompt_mode),
    )


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
