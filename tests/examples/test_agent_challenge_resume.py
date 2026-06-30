from __future__ import annotations

import json
from pathlib import Path

import pytest

from examples.agent_challenges.opencode_resume import (
    build_resume_command,
    display_resume_command,
    extract_session_id,
    resume_prompt_for_result,
    resume_result_path,
)


def _event(**payload: object) -> str:
    return json.dumps(payload, separators=(",", ":"))


def test_extract_session_id_reads_top_level_session_id() -> None:
    stdout = "\n".join(
        [
            _event(type="step_start", sessionID="ses_abc"),
            _event(type="text", sessionID="ses_def", text="later"),
        ]
    )

    assert extract_session_id(stdout) == "ses_abc"


def test_extract_session_id_reads_nested_part_session_id() -> None:
    stdout = _event(type="step_start", part={"sessionID": "ses_nested"})

    assert extract_session_id(stdout) == "ses_nested"


def test_extract_session_id_returns_none_for_empty_or_malformed_stdout() -> None:
    assert extract_session_id("") is None
    assert extract_session_id("not json\n{}") is None


def test_resume_prompt_asks_continue_for_timeout_with_partial_stdout() -> None:
    prompt = resume_prompt_for_result(
        {
            "task_outcome": "timeout",
            "stdout": _event(type="step_start", sessionID="ses_abc"),
        }
    )

    assert "continue" in prompt.lower()
    assert "do not restart" in prompt.lower()


def test_resume_prompt_asks_for_final_report_when_work_is_done_but_report_missing() -> (
    None
):
    prompt = resume_prompt_for_result(
        {
            "task_outcome": "failed",
            "assertion_failures": [
                "could not extract challenge report for required_fields evaluation"
            ],
            "stdout": _event(type="text", sessionID="ses_abc", text="run completed"),
        }
    )

    assert "do not continue coding" in prompt.lower()
    assert "challenge_report" in prompt


def test_build_resume_command_includes_attach_session_model_variant_and_prompt() -> (
    None
):
    command = build_resume_command(
        session_id="ses_abc",
        attach_url="http://127.0.0.1:8192/",
        model="opencode/deepseek-v4-flash-free",
        variant="max",
        prompt="continue?",
    )

    assert command == [
        "opencode",
        "run",
        "--session",
        "ses_abc",
        "--attach",
        "http://127.0.0.1:8192/",
        "--format",
        "json",
        "--model",
        "opencode/deepseek-v4-flash-free",
        "--variant",
        "max",
        "continue?",
    ]


def test_display_resume_command_quotes_prompt_with_spaces() -> None:
    rendered = display_resume_command(
        ["opencode", "run", "--session", "ses_cli", "continue this trial"]
    )

    assert rendered == 'opencode run --session ses_cli "continue this trial"'


def test_resume_result_path_uses_next_resume_index(tmp_path: Path) -> None:
    original = tmp_path / "trial.json"
    original.write_text("{}", encoding="utf-8")
    (tmp_path / "trial.resume-001.json").write_text("{}", encoding="utf-8")

    assert resume_result_path(original).name == "trial.resume-002.json"


def test_resume_trial_prints_resume_command(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from examples.agent_challenges.resume_trial import main

    result_path = tmp_path / "trial.json"
    result_path.write_text(
        json.dumps(
            {
                "model": "opencode/deepseek-v4-flash-free",
                "variant": "max",
                "opencode": {
                    "attach_url": "http://127.0.0.1:8192/",
                    "session_id": "ses_cli",
                    "resume_prompt": "continue?",
                    "resume_command": [
                        "opencode",
                        "run",
                        "--session",
                        "ses_cli",
                        "--attach",
                        "http://127.0.0.1:8192/",
                        "--format",
                        "json",
                        "--model",
                        "opencode/deepseek-v4-flash-free",
                        "--variant",
                        "max",
                        "continue?",
                    ],
                },
            }
        ),
        encoding="utf-8",
    )

    assert main(["--from-result", str(result_path), "--print-command"]) == 0
    output = capsys.readouterr().out
    assert "opencode run --session ses_cli" in output


def test_resume_trial_run_writes_resume_result(tmp_path: Path) -> None:
    from subprocess import CompletedProcess

    from examples.agent_challenges.resume_trial import resume_from_result

    result_path = tmp_path / "trial.json"
    result_path.write_text(
        json.dumps(
            {
                "model": "opencode/deepseek-v4-flash-free",
                "variant": "max",
                "opencode": {
                    "attach_url": None,
                    "session_id": "ses_cli",
                    "resume_prompt": "continue?",
                    "resume_command": [
                        "opencode",
                        "run",
                        "--session",
                        "ses_cli",
                        "--format",
                        "json",
                        "--model",
                        "opencode/deepseek-v4-flash-free",
                        "--variant",
                        "max",
                        "continue?",
                    ],
                },
            }
        ),
        encoding="utf-8",
    )

    calls: list[list[str]] = []

    def fake_run(command: list[str], **kwargs: object) -> CompletedProcess[str]:
        calls.append(command)
        return CompletedProcess(
            command, 0, stdout='{"type":"text","text":"done"}\n', stderr=""
        )

    output_path = resume_from_result(result_path, run_fn=fake_run)

    assert output_path.name == "trial.resume-001.json"
    assert calls[0][0:4] == ["opencode", "run", "--session", "ses_cli"]
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["source_result_path"] == str(result_path.resolve())
    assert payload["stdout"].strip()
