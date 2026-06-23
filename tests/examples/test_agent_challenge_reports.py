from __future__ import annotations

import json
from pathlib import Path

import pytest


def _raw_result(tmp_path: Path) -> dict[str, object]:
    return {
        "instruction_profile": "none",
        "task_outcome": "success",
        "evaluation_validity": "clean",
        "challenge_id": "fixture",
        "model": "test-model",
        "variant": "high",
        "trial_index": 1,
        "prompt_hashes": {
            "base": "abc",
            "profile": "def",
            "challenge": "ghi",
            "rendered": "jkl",
        },
        "repository_commit": "abc123def",
        "repository_dirty": False,
        "result_path": str(tmp_path / "results" / "trial.json"),
        "workspace_path": str(tmp_path),
        "metrics": {
            "step_count": 2,
            "tool_call_count": 3,
            "failed_tool_call_count": 0,
            "tool_counts": {"bash": 2, "read": 1},
            "tokens": {
                "total": 500,
                "input": 200,
                "output": 200,
                "reasoning": 50,
                "cache_read": 50,
                "cache_write": 0,
            },
            "cost": 0.025,
            "unknown_event_count": 0,
            "tool_calls": [
                {
                    "ordinal": 1,
                    "call_id": "c1",
                    "tool": "read",
                    "status": "success",
                    "title": "Read workflow plan",
                    "input": {"path": str(tmp_path / "workflow.plan.json")},
                    "metadata": {},
                    "output_chars": 500,
                    "output_preview": "full tool output",
                    "output_sha256": "abc",
                    "failed": False,
                },
                {
                    "ordinal": 2,
                    "call_id": "c2",
                    "tool": "bash",
                    "status": "success",
                    "title": "Run workflow",
                    "input": {"command": "uv run wf status"},
                    "metadata": {},
                    "output_chars": 200,
                    "output_preview": "large raw stream",
                    "output_sha256": "def",
                    "failed": False,
                },
            ],
        },
        "policy": {
            "validity": "clean",
            "coverage": "complete",
            "disallowed_reads": [],
            "escalated_to_product_code": False,
            "opaque_shell_commands": [],
            "reads_by_category": {
                "workspace": [str(tmp_path / "workflow.plan.json")],
            },
        },
        "stdout": "large raw stdout content that should not appear in bounded report\n"
        * 1000,
        "stderr": "",
        "parsed": {"text": "The deployment succeeded with id dep_123."},
        "assertion_failures": [],
        "parse_errors": {},
    }


def test_trial_report_is_bounded_machine_projection(tmp_path: Path) -> None:
    from examples.agent_challenges.report_models import build_trial_report

    payload = build_trial_report(_raw_result(tmp_path), audit=None).model_dump(
        mode="json"
    )
    assert payload["schema_version"] == 1
    assert payload["identity"]["challenge_id"] == "fixture"
    assert payload["identity"]["raw_result_path"] == str(
        tmp_path / "results" / "trial.json"
    )
    assert payload["identity"]["workspace_path"] == str(tmp_path)
    assert payload["outcome"]["task_outcome"] == "success"
    assert payload["commands_and_tools"][0]["detail"].endswith("workflow.plan.json")
    serialized = json.dumps(payload)
    assert "large raw stream" not in serialized
    assert "full tool output" not in serialized
    assert payload["commands_and_tools"][0]["output_chars"] == 500
    assert payload["commands_and_tools"][0]["output_sha256"] == "abc"
    assert payload["manual_audit"]["status"] == "pending"


def test_command_brief_supports_filepath(tmp_path: Path) -> None:
    from examples.agent_challenges.report_models import build_trial_report

    result = _raw_result(tmp_path)
    metrics = result.get("metrics", {})
    if isinstance(metrics, dict):
        metrics["tool_calls"] = [
            {
                "ordinal": 1,
                "call_id": "c3",
                "tool": "read",
                "status": "success",
                "title": "Read source file",
                "input": {"filePath": str(tmp_path / "src" / "app.py")},
                "metadata": {},
                "output_chars": 100,
                "output_preview": "content",
                "output_sha256": "xyz",
                "failed": False,
            },
        ]

    payload = build_trial_report(result, audit=None).model_dump(mode="json")
    cmd = payload["commands_and_tools"][0]
    assert cmd["detail"] is not None
    assert cmd["detail"].endswith("app.py")


def test_markdown_projection_has_stable_headings(tmp_path: Path) -> None:
    from examples.agent_challenges.report_models import build_trial_report
    from examples.agent_challenges.reports import render_trial_report_markdown

    report = build_trial_report(_raw_result(tmp_path), audit=None)
    md = render_trial_report_markdown(report)

    expected_headings = [
        "# Trial Report",
        "## Outcome",
        "## Agent Self-Report",
        "## Commands And Tool Calls",
        "## Automatic Evidence",
        "## Policy Findings",
        "## Self-Report Discrepancies",
        "## Manual Audit",
        "## Follow-Up Notes",
    ]
    for heading in expected_headings:
        assert heading in md, f"Missing heading: {heading}"

    assert "Final agent answer" in md
    assert "The deployment succeeded" in md
    assert "large raw stream" not in md
    assert "full tool output" not in md


def test_markdown_command_items_indent_by_marker_width(tmp_path: Path) -> None:
    from examples.agent_challenges.report_models import (
        CommandToolBrief,
        build_trial_report,
    )
    from examples.agent_challenges.reports import render_trial_report_markdown

    report = build_trial_report(_raw_result(tmp_path), audit=None)
    command = report.commands_and_tools[0]
    report = report.model_copy(
        update={
            "commands_and_tools": [
                CommandToolBrief(**{**command.model_dump(), "ordinal": 9}),
                CommandToolBrief(**{**command.model_dump(), "ordinal": 10}),
            ]
        }
    )

    markdown = render_trial_report_markdown(report)

    assert "9. **read**" in markdown
    assert "\n   - Title:" in markdown
    assert "\n\n10. **read**" in markdown
    assert "\n    - Title:" in markdown


def test_projections_write_both_files(tmp_path: Path) -> None:
    from examples.agent_challenges.report_models import build_trial_report
    from examples.agent_challenges.reports import (
        TrialReportPaths,
        write_trial_report_projections,
    )

    report = build_trial_report(_raw_result(tmp_path), audit=None)
    markdown_path = tmp_path / "final-report.md"
    machine_path = tmp_path / "trial.report.json"

    paths = write_trial_report_projections(
        report,
        markdown_path=markdown_path,
        machine_path=machine_path,
    )

    assert isinstance(paths, TrialReportPaths)
    assert markdown_path.is_file()
    assert machine_path.is_file()

    md_content = markdown_path.read_text(encoding="utf-8")
    assert "# Trial Report" in md_content
    assert "## Outcome" in md_content

    machine_content = json.loads(machine_path.read_text(encoding="utf-8"))
    assert machine_content["schema_version"] == 1
    assert machine_content["manual_audit"]["status"] == "pending"

    assert list(tmp_path.iterdir()) == [markdown_path, machine_path]


def test_projections_exclude_raw_outputs(tmp_path: Path) -> None:
    from examples.agent_challenges.report_models import build_trial_report
    from examples.agent_challenges.reports import write_trial_report_projections

    report = build_trial_report(_raw_result(tmp_path), audit=None)
    markdown_path = tmp_path / "final-report.md"
    machine_path = tmp_path / "trial.report.json"

    write_trial_report_projections(
        report,
        markdown_path=markdown_path,
        machine_path=machine_path,
    )

    md = markdown_path.read_text(encoding="utf-8")
    assert "large raw stream" not in md
    assert "full tool output" not in md

    machine = json.loads(machine_path.read_text(encoding="utf-8"))
    serialized = json.dumps(machine)
    assert "large raw stream" not in serialized
    assert "full tool output" not in serialized


def _write_v2_result(tmp_path: Path) -> Path:
    result_dir = tmp_path / "results"
    result_dir.mkdir(parents=True)
    result = _raw_result(tmp_path)
    result["harness_version"] = "v2"
    result["result_path"] = str(tmp_path / "results" / "trial.json")
    result["workspace_path"] = str(tmp_path)
    path = result_dir / "trial.json"
    path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _write_v2_result_with_projections(tmp_path: Path) -> Path:
    result_path = _write_v2_result(tmp_path)
    from examples.agent_challenges.report_models import build_trial_report
    from examples.agent_challenges.reports import write_trial_report_projections

    result = json.loads(result_path.read_text(encoding="utf-8"))
    report = build_trial_report(result, audit=None)
    write_trial_report_projections(
        report,
        markdown_path=tmp_path / "final-report.md",
        machine_path=tmp_path / "results" / "trial.report.json",
    )
    return result_path


def test_manual_audit_regenerates_projections(tmp_path: Path) -> None:
    from examples.agent_challenges.audit import save_v2_manual_audit

    result_path = _write_v2_result(tmp_path)

    paths = save_v2_manual_audit(
        result_path,
        official_outcome="pass",
        auditor="reviewer",
        audited_at="2026-06-23T00:00:00Z",
        read_overrides={"existing_solution": True},
        corrections=["Agent inspected a ready-made workflow plan."],
        notes="Technical run passed; self-report corrected.",
    )

    assert paths.audit.is_file()
    assert paths.markdown.is_file()
    assert paths.machine.is_file()

    audit_yaml = paths.audit.read_text(encoding="utf-8")
    assert "official_outcome: pass" in audit_yaml
    assert "Agent inspected a ready-made workflow plan." in audit_yaml

    md = paths.markdown.read_text(encoding="utf-8")
    assert "Official outcome: pass" in md
    assert "Agent inspected a ready-made workflow plan." in md

    machine = json.loads(paths.machine.read_text(encoding="utf-8"))
    assert machine["manual_audit"]["official_outcome"] == "pass"
    assert machine["manual_audit"]["status"] == "complete"


def test_manual_audit_invalid_outcome_raises_and_preserves_projections(
    tmp_path: Path,
) -> None:
    from examples.agent_challenges.audit import save_v2_manual_audit

    result_path = _write_v2_result_with_projections(tmp_path)
    md_path = tmp_path / "final-report.md"
    machine_path = tmp_path / "results" / "trial.report.json"

    md_before = md_path.read_bytes()
    machine_before = machine_path.read_bytes()

    with pytest.raises(ValueError, match="official_outcome"):
        save_v2_manual_audit(
            result_path,
            official_outcome="maybe",
            auditor="reviewer",
        )

    assert md_path.read_bytes() == md_before
    assert machine_path.read_bytes() == machine_before


def test_discrepancy_detects_run_failed_contradiction(tmp_path: Path) -> None:
    from examples.agent_challenges.report_models import build_trial_report

    result = _raw_result(tmp_path)
    result["task_outcome"] = "failed"
    result["challenge_report"] = {"run_failed": False, "used_product_path": True}

    report = build_trial_report(result, audit=None)
    assert any(
        "run_failed=false" in d and "task_outcome is 'failed'" in d
        for d in report.self_report_discrepancies
    )


def test_discrepancy_detects_escalation_not_reported(tmp_path: Path) -> None:
    from examples.agent_challenges.report_models import build_trial_report

    result = _raw_result(tmp_path)
    result["task_outcome"] = "success"
    policy = result.get("policy", {})
    if isinstance(policy, dict):
        policy["escalated_to_product_code"] = True
    result["challenge_report"] = {
        "run_failed": False,
        "read": {"product_code": False},
    }

    report = build_trial_report(result, audit=None)
    assert any("read.product_code" in d for d in report.self_report_discrepancies)


def test_no_discrepancy_when_product_code_reported(tmp_path: Path) -> None:
    from examples.agent_challenges.report_models import build_trial_report

    result = _raw_result(tmp_path)
    result["task_outcome"] = "success"
    policy = result.get("policy", {})
    if isinstance(policy, dict):
        policy["escalated_to_product_code"] = True
    result["challenge_report"] = {
        "run_failed": False,
        "read": {"product_code": True},
    }

    report = build_trial_report(result, audit=None)
    assert not any("read.product_code" in d for d in report.self_report_discrepancies)


def test_example_read_does_not_create_discrepancy(tmp_path: Path) -> None:
    from examples.agent_challenges.report_models import build_trial_report

    result = _raw_result(tmp_path)
    policy = result.get("policy", {})
    if isinstance(policy, dict):
        policy["reads_by_category"] = {
            "examples": [str(tmp_path / "examples" / "solution.py")],
        }
    result["challenge_report"] = {
        "run_failed": False,
        "read": {"product_code": True, "existing_solution": False},
    }

    report = build_trial_report(result, audit=None)
    assert not any("existing solution" in d for d in report.self_report_discrepancies)
    assert any("example file(s)" in n for n in report.follow_up_notes)


def _policy_mut(result: dict[str, object]) -> dict[str, object]:
    p = result.get("policy", {})
    if not isinstance(p, dict):
        p = {}
        result["policy"] = p
    return p


def test_follow_up_notes_for_example_reads(tmp_path: Path) -> None:
    from examples.agent_challenges.report_models import build_trial_report

    result = _raw_result(tmp_path)
    _policy_mut(result)["reads_by_category"] = {
        "examples": [str(tmp_path / "examples" / "solution.py")],
    }

    report = build_trial_report(result, audit=None)
    assert any("example file(s)" in n for n in report.follow_up_notes)


def test_follow_up_notes_for_test_reads(tmp_path: Path) -> None:
    from examples.agent_challenges.report_models import build_trial_report

    result = _raw_result(tmp_path)
    _policy_mut(result)["reads_by_category"] = {
        "tests": [str(tmp_path / "tests" / "test_app.py")],
    }

    report = build_trial_report(result, audit=None)
    assert any("test file(s)" in n for n in report.follow_up_notes)


def test_follow_up_notes_for_example_implementation_reads(tmp_path: Path) -> None:
    from examples.agent_challenges.report_models import build_trial_report

    result = _raw_result(tmp_path)
    _policy_mut(result)["reads_by_category"] = {
        "example_implementation": [
            str(tmp_path / "examples" / "report_workflow" / "ops.py")
        ],
    }

    report = build_trial_report(result, audit=None)
    assert any("example implementation" in n for n in report.follow_up_notes)


def test_follow_up_notes_for_search_intent(tmp_path: Path) -> None:
    from examples.agent_challenges.report_models import build_trial_report

    result = _raw_result(tmp_path)
    _policy_mut(result)["reads_by_category"] = {
        "search_intent": ["**/report_workflow/**"],
    }

    report = build_trial_report(result, audit=None)
    assert any("search pattern" in n for n in report.follow_up_notes)


def test_build_report_raises_on_missing_paths(tmp_path: Path) -> None:
    from examples.agent_challenges.report_models import build_trial_report

    result = _raw_result(tmp_path)
    del result["result_path"]
    del result["workspace_path"]

    with pytest.raises(ValueError, match="raw_result_path"):
        build_trial_report(result, audit=None)
