from __future__ import annotations

import json
from typing import Any

from examples.agent_challenges.browser_click_challenge.challenge import (
    TrialConfig,
    render_prompt,
)


def build_opencode_command(config: TrialConfig) -> list[str]:
    prompt_text = render_prompt(
        config.prompt_path,
        wf_command_prefix=config.wf_command_prefix,
        server_context=config.server_context,
    )
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


def _result_text(parsed: dict[str, Any]) -> str:
    for key in ("text", "message", "content", "output"):
        value = parsed.get(key)
        if isinstance(value, str):
            return value
    return json.dumps(parsed, sort_keys=True)
