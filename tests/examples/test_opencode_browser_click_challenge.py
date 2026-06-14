from __future__ import annotations

import json
from pathlib import Path

from examples.agent_challenges.browser_click_challenge.run_opencode_trials import (
    TrialConfig,
    build_opencode_command,
    classify_output,
    parse_opencode_output,
    trial_output_path,
)


def test_build_opencode_command_without_attach(tmp_path: Path) -> None:
    prompt = tmp_path / "prompt.md"
    prompt.write_text("hello", encoding="utf-8")
    config = TrialConfig(
        model="opencode/mimo-v2.5-free",
        variant="high",
        prompt_path=prompt,
        attach_url=None,
        timeout_seconds=120,
    )

    command = build_opencode_command(config)

    assert command[:2] == ["opencode", "run"]
    assert "--attach" not in command
    assert "--format" in command
    assert "json" in command
    assert "--model" in command
    assert "opencode/mimo-v2.5-free" in command
    assert "hello" in command


def test_build_opencode_command_with_attach(tmp_path: Path) -> None:
    prompt = tmp_path / "prompt.md"
    prompt.write_text("hello", encoding="utf-8")
    config = TrialConfig(
        model="opencode/deepseek-v3.1-free",
        variant="high",
        prompt_path=prompt,
        attach_url="http://127.0.0.1:4096",
        timeout_seconds=120,
    )

    command = build_opencode_command(config)

    assert "--attach" in command
    assert "http://127.0.0.1:4096" in command


def test_parse_opencode_output_reads_json_object() -> None:
    payload = {"text": "wf run start demo.default\nbefore.clicked false\nafter.clicked true"}

    parsed = parse_opencode_output(json.dumps(payload))

    assert parsed["text"] == payload["text"]


def test_parse_opencode_output_reads_last_jsonl_object() -> None:
    payload = "\n".join(
        [
            json.dumps({"type": "log", "text": "starting"}),
            json.dumps({"type": "message", "text": "final"}),
        ]
    )

    parsed = parse_opencode_output(payload)

    assert parsed["text"] == "final"


def test_parse_opencode_output_prefers_text_event_before_step_finish() -> None:
    payload = "\n".join(
        [
            json.dumps(
                {
                    "type": "text",
                    "part": {
                        "type": "text",
                        "text": "deployment id: demo.default\nbefore.clicked is false",
                    },
                }
            ),
            json.dumps({"type": "step_finish", "part": {"type": "step-finish"}}),
        ]
    )

    parsed = parse_opencode_output(payload)

    assert parsed["text"] == "deployment id: demo.default\nbefore.clicked is false"


def test_classify_output_success() -> None:
    result = classify_output(
        """
        uv run wf-rpc-server --config examples/browser_click_workflow/wf.config.json
        uv run wf run start browser_click_case_study.default
        deployment id: browser_click_case_study.default
        run id: run_123
        before.clicked is false
        after.clicked is true
        """
    )

    assert result == "success"


def test_classify_output_workflow_script() -> None:
    result = classify_output(
        """
        uv run python examples/browser_click_workflow/run_workflow.py
        Deployment id: browser_click_case_study.default
        Run id: run_123
        `before.clicked`: `False`
        `after.clicked`: `True`
        """
    )

    assert result == "workflow_script"


def test_classify_output_workflow_not_used() -> None:
    result = classify_output(
        """
        I wrote a Playwright script.
        before clicked false
        after clicked true
        """
    )

    assert result == "workflow_not_used"


def test_classify_output_run_failed() -> None:
    result = classify_output(
        """
        wf run start browser_click_case_study.default
        error: deployment validation failed
        """
    )

    assert result == "run_failed"


def test_trial_output_path_is_zero_padded(tmp_path: Path) -> None:
    path = trial_output_path(tmp_path, model="opencode/mimo-v2.5-free", index=3)

    assert path.name == "opencode_mimo-v2.5-free-trial-003.json"
