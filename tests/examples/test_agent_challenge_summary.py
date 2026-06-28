from __future__ import annotations

import json
import os
from pathlib import Path


def _write_report(
    path: Path,
    *,
    challenge: str = "browser_click",
    model: str = "opencode/deepseek-v4-flash-free",
    profile: str = "skills",
    trial: int = 4,
    manual: str | None = "pass",
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "identity": {
                    "challenge_id": challenge,
                    "model": model,
                    "variant": "high",
                    "instruction_profile": profile,
                    "trial_index": trial,
                    "raw_result_path": str(path.with_suffix(".json")),
                    "workspace_path": str(
                        path.parent.parent / "workspaces" / path.stem
                    ),
                },
                "outcome": {
                    "task_outcome": "success",
                    "evaluation_validity": "clean",
                    "duration_seconds": 125.0,
                    "returncode": 0,
                },
                "automatic_evidence": {
                    "tokens": {"total": 12345},
                },
                "agent_self_report": {
                    "attempts": {"failed": 1, "total": 2},
                    "read": {
                        "skills": True,
                        "docs": False,
                        "product_code": False,
                    },
                },
                "manual_audit": {
                    "official_outcome": manual,
                    "notes": "Pass | with newline\nand spacing.",
                },
            }
        ),
        encoding="utf-8",
    )
    return path


def test_load_trial_summary_uses_short_labels_and_manual_outcome(
    tmp_path: Path,
) -> None:
    from examples.agent_challenges.summarize_trials import load_trial_summary

    report = _write_report(tmp_path / "results" / "trial.report.json")

    summary = load_trial_summary(report)

    assert summary.challenge == "browser"
    assert summary.model == "deepseek"
    assert summary.profile == "skills"
    assert summary.trial == 4
    assert summary.manual == "pass"
    assert summary.duration_seconds == 125.0
    assert summary.tokens_total == 12345
    assert summary.attempts == "1/2"
    assert summary.read_flags == "skills"
    assert summary.notes == "Pass | with newline and spacing."


def test_load_trial_summary_prefers_manual_attempt_evidence(
    tmp_path: Path,
) -> None:
    from examples.agent_challenges.summarize_trials import load_trial_summary

    report = _write_report(tmp_path / "results" / "trial.report.json")
    payload = json.loads(report.read_text(encoding="utf-8"))
    payload["manual_audit"]["evidence"] = {
        "attempts_total": 3,
        "attempts_failed": 2,
    }
    report.write_text(json.dumps(payload), encoding="utf-8")

    summary = load_trial_summary(report)

    assert summary.attempts == "2/3"


def test_render_markdown_escapes_table_cells(tmp_path: Path) -> None:
    from examples.agent_challenges.summarize_trials import (
        load_trial_summary,
        render_markdown,
    )

    summary = load_trial_summary(_write_report(tmp_path / "one.report.json"))

    markdown = render_markdown([summary])

    assert "| browser | deepseek | skills | 004 | pass |" in markdown
    assert "Pass \\| with newline and spacing." in markdown


def test_find_report_files_accepts_challenge_and_results_dirs(tmp_path: Path) -> None:
    from examples.agent_challenges.summarize_trials import find_report_files

    challenge = tmp_path / "browser_click_challenge"
    report = _write_report(challenge / "results" / "trial.report.json")

    assert find_report_files([challenge]) == [report]
    assert find_report_files([challenge / "results"]) == [report]


def test_find_report_files_can_select_newest_with_padding(tmp_path: Path) -> None:
    from examples.agent_challenges.summarize_trials import find_report_files

    challenge = tmp_path / "browser_click_challenge"
    reports = [
        _write_report(challenge / "results" / f"trial-{index}.report.json")
        for index in range(4)
    ]
    for index, report in enumerate(reports):
        timestamp = 1000 + index
        os.utime(report, (timestamp, timestamp))

    before_mtimes = {path: path.stat().st_mtime for path in reports}

    selected = find_report_files([challenge], last=1, over_list=2)

    assert [path.name for path in selected] == [
        "trial-1.report.json",
        "trial-2.report.json",
        "trial-3.report.json",
    ]
    assert {path: path.stat().st_mtime for path in reports} == before_mtimes


def test_find_report_files_prefers_raw_result_mtime_for_last(tmp_path: Path) -> None:
    from examples.agent_challenges.summarize_trials import find_report_files

    challenge = tmp_path / "browser_click_challenge"
    old_report = _write_report(challenge / "results" / "old.report.json")
    new_report = _write_report(challenge / "results" / "new.report.json")
    old_raw = challenge / "results" / "old.json"
    new_raw = challenge / "results" / "new.json"
    old_raw.write_text("{}", encoding="utf-8")
    new_raw.write_text("{}", encoding="utf-8")

    os.utime(old_raw, (1000, 1000))
    os.utime(new_raw, (2000, 2000))
    os.utime(old_report, (3000, 3000))
    os.utime(new_report, (1500, 1500))

    selected = find_report_files([challenge], last=1)

    assert selected == [new_report]
    assert find_report_files([challenge], last=1, sort_by="report") == [old_report]


def test_summarize_trials_direct_script_execution_smoke(tmp_path: Path) -> None:
    import subprocess
    import sys

    report = _write_report(tmp_path / "results" / "trial.report.json")

    completed = subprocess.run(
        [
            sys.executable,
            "examples/agent_challenges/summarize_trials.py",
            str(report),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "| browser | deepseek | skills | 004 | pass |" in completed.stdout
