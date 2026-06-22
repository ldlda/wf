from __future__ import annotations

import json
from pathlib import Path

import pytest

from examples.agent_challenges.manifests import load_challenge_manifest
from examples.agent_challenges.models import InstructionProfile
from examples.agent_challenges.prompts import compose_trial_prompt
from examples.agent_challenges.workspace import prepare_v2_trial_workspace


def _write_manifest(root: Path) -> Path:
    (root / "workspace_template").mkdir(parents=True)
    (root / "challenge-prompt.md").write_text("Build it.\n", encoding="utf-8")
    path = root / "challenge.yaml"
    path.write_text(
        """\
version: 1
id: fixture
prompt: challenge-prompt.md
workspace_template: workspace_template
source:
  id: local.fixture
  root: source
  module: ops
  registry: registry
store_root: .wf_fixture_store
server:
  config: wf.config.json
  default_port: 8779
report:
  required_fields: [value, run_failed]
  success_assertions:
    value: expected
    run_failed: false
""",
        encoding="utf-8",
    )
    return path


def test_load_challenge_manifest_resolves_paths(tmp_path: Path) -> None:
    manifest_path = _write_manifest(tmp_path)

    loaded = load_challenge_manifest(manifest_path)

    assert loaded.manifest.id == "fixture"
    assert loaded.root == tmp_path.resolve()
    assert loaded.prompt_path == (tmp_path / "challenge-prompt.md").resolve()
    assert loaded.workspace_template == (tmp_path / "workspace_template").resolve()
    assert loaded.manifest.report.success_assertions == {
        "value": "expected",
        "run_failed": False,
    }


def test_instruction_profiles_are_exactly_the_supported_conditions() -> None:
    assert [profile.value for profile in InstructionProfile] == [
        "none",
        "skills",
        "all",
    ]


def test_invalid_manifest_rejects_parent_traversal(tmp_path: Path) -> None:
    path = _write_manifest(tmp_path)
    text = path.read_text(encoding="utf-8").replace(
        "workspace_template: workspace_template",
        "workspace_template: ../outside",
    )
    path.write_text(text, encoding="utf-8")

    with pytest.raises(ValueError, match="workspace_template"):
        load_challenge_manifest(path)


ROOT = Path(__file__).resolve().parents[2]


def test_challenge_prompt_is_identical_across_profiles(tmp_path: Path) -> None:
    challenge = load_challenge_manifest(_write_manifest(tmp_path / "challenge"))
    rendered = {
        profile: compose_trial_prompt(
            challenge,
            profile=profile,
            wf_command_prefix="uv run wf --config wf.config.json --local",
            server_context="Local mode.",
            workspace_path=tmp_path / profile.value,
        )
        for profile in InstructionProfile
    }

    assert {value.challenge_sha256 for value in rendered.values()} == {
        rendered[InstructionProfile.NONE].challenge_sha256
    }
    assert len({value.rendered_sha256 for value in rendered.values()}) == 3
    assert "report the exact blocker" in rendered[InstructionProfile.NONE].text.replace(
        "\n", " "
    )
    assert ".agent/skills" in rendered[InstructionProfile.SKILLS].text
    assert "inspect broader repository" in rendered[InstructionProfile.ALL].text


def test_skills_profile_copies_bundle_but_none_does_not(tmp_path: Path) -> None:
    challenge = load_challenge_manifest(_write_manifest(tmp_path / "challenge"))
    bundle = ROOT / "examples/agent_challenges/instruction_bundles/workflow_cli.yaml"

    none_workspace = prepare_v2_trial_workspace(
        challenge,
        profile=InstructionProfile.NONE,
        model="model",
        index=1,
        workspaces_dir=tmp_path / "workspaces",
        instruction_bundle=bundle,
    )
    skills_workspace = prepare_v2_trial_workspace(
        challenge,
        profile=InstructionProfile.SKILLS,
        model="model",
        index=2,
        workspaces_dir=tmp_path / "workspaces",
        instruction_bundle=bundle,
    )

    assert not (none_workspace.root / ".agent/skills").exists()
    assert (skills_workspace.root / ".agent/skills/wf-cli/SKILL.md").is_file()
    assert skills_workspace.instruction_files


def test_extract_trial_metrics_parses_jsonl_events() -> None:
    from examples.agent_challenges.metrics import extract_trial_metrics

    stdout = "\n".join(
        [
            json.dumps({"type": "step_start", "step": 1}),
            json.dumps(
                {
                    "type": "tool_use",
                    "tool": "read",
                    "status": "success",
                    "title": "Read file",
                    "input": {"path": "foo.py"},
                    "metadata": {},
                    "output": "x" * 4000,
                }
            ),
            json.dumps(
                {
                    "type": "tool_use",
                    "tool": "bash",
                    "status": "error",
                    "title": "Run command",
                    "input": {"command": "ls"},
                    "metadata": {},
                    "output": "error occurred",
                }
            ),
            json.dumps(
                {
                    "type": "step_finish",
                    "tokens": {
                        "total": 120,
                        "input": 20,
                        "output": 30,
                        "reasoning": 10,
                        "cache": {"read": 60, "write": 0},
                    },
                    "cost": 0.01,
                }
            ),
        ]
    )

    metrics = extract_trial_metrics(stdout)

    assert metrics.step_count == 1
    assert metrics.tool_call_count == 2
    assert metrics.failed_tool_call_count == 1
    assert metrics.tool_counts == {"bash": 1, "read": 1}
    assert metrics.tokens.total == 120
    assert metrics.tokens.input == 20
    assert metrics.tokens.output == 30
    assert metrics.tokens.reasoning == 10
    assert metrics.tokens.cache_read == 60
    assert metrics.cost == 0.01
    assert metrics.tool_calls[0].tool == "read"
    assert metrics.tool_calls[0].output_chars == 4000
    assert len(metrics.tool_calls[0].output_preview) <= 500


def test_extract_trial_metrics_sums_tokens_across_steps() -> None:
    from examples.agent_challenges.metrics import extract_trial_metrics

    stdout = "\n".join(
        [
            json.dumps({"type": "step_start", "step": 1}),
            json.dumps(
                {
                    "type": "step_finish",
                    "tokens": {
                        "total": 50,
                        "input": 20,
                        "output": 15,
                        "reasoning": 5,
                        "cache": {"read": 10, "write": 0},
                    },
                    "cost": 0.003,
                }
            ),
            json.dumps({"type": "step_start", "step": 2}),
            json.dumps(
                {
                    "type": "step_finish",
                    "tokens": {
                        "total": 70,
                        "input": 30,
                        "output": 25,
                        "reasoning": 10,
                        "cache": {"read": 5, "write": 0},
                    },
                    "cost": 0.004,
                }
            ),
        ]
    )

    metrics = extract_trial_metrics(stdout)

    assert metrics.step_count == 2
    assert metrics.tokens.total == 120
    assert metrics.tokens.input == 50
    assert metrics.tokens.output == 40
    assert metrics.tokens.reasoning == 15
    assert metrics.tokens.cache_read == 15
    assert metrics.cost == 0.007


def test_extract_trial_metrics_handles_nested_part_state_format() -> None:
    from examples.agent_challenges.metrics import extract_trial_metrics

    stdout = "\n".join(
        [
            json.dumps({"type": "step_start", "step": 1}),
            json.dumps(
                {
                    "type": "tool_use",
                    "part": {
                        "tool": "read",
                        "callID": "call-abc",
                        "state": {
                            "status": "success",
                            "title": "Read file",
                            "input": {"path": "src/app.py"},
                            "output": "file content here",
                            "metadata": {"size": 100},
                        },
                    },
                }
            ),
            json.dumps(
                {
                    "type": "tool_use",
                    "part": {
                        "tool": "bash",
                        "callID": "call-def",
                        "state": {
                            "status": "error",
                            "title": "Run command",
                            "input": {"command": "ls nonexistent"},
                            "output": "command failed",
                        },
                    },
                }
            ),
            json.dumps(
                {
                    "type": "step_finish",
                    "tokens": {
                        "total": 100,
                        "input": 50,
                        "output": 30,
                        "reasoning": 10,
                        "cache": {"read": 10, "write": 0},
                    },
                    "cost": 0.005,
                }
            ),
        ]
    )

    metrics = extract_trial_metrics(stdout)

    assert metrics.step_count == 1
    assert metrics.tool_call_count == 2
    assert metrics.failed_tool_call_count == 1
    assert metrics.tool_counts == {"bash": 1, "read": 1}
    assert metrics.tool_calls[0].tool == "read"
    assert metrics.tool_calls[0].status == "success"
    assert metrics.tool_calls[0].call_id == "call-abc"
    assert metrics.tool_calls[0].output_chars == 17
    assert metrics.tool_calls[0].input == {"path": "src/app.py"}
    assert metrics.tool_calls[1].tool == "bash"
    assert metrics.tool_calls[1].status == "error"
    assert metrics.tool_calls[1].failed is True
    assert metrics.tool_calls[1].input == {"command": "ls nonexistent"}
    assert metrics.tokens.total == 100
    assert metrics.cost == 0.005


def test_policy_evidence_classifies_reads(tmp_path: Path) -> None:
    from examples.agent_challenges.metrics import ToolCallEvidence
    from examples.agent_challenges.policy import evaluate_policy

    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    workspaces_root = tmp_path / "workspaces"
    workspaces_root.mkdir()

    def _tc(tool: str, path: str) -> ToolCallEvidence:
        return ToolCallEvidence(
            ordinal=1,
            call_id="c1",
            tool=tool,
            status="success",
            title="read",
            input={"path": path},
            metadata={},
            output_chars=100,
            output_preview="",
            output_sha256="abc",
            failed=False,
        )

    source_read = _tc("read", str(repository_root / "src" / "app.py"))
    skills_read = _tc(
        "read",
        str(workspace_root / ".agent" / "skills" / "wf-cli" / "SKILL.md"),
    )
    workspace_read = _tc("read", str(workspace_root / "attempt.md"))
    test_read = _tc("read", str(repository_root / "tests" / "test_app.py"))

    none_policy = evaluate_policy(
        "none",
        [workspace_read, source_read],
        workspace_root=workspace_root,
        repository_root=repository_root,
        workspaces_root=workspaces_root,
    )
    assert none_policy.validity.value == "contaminated"
    assert any("app.py" in p for p in none_policy.disallowed_reads)

    skills_policy = evaluate_policy(
        "skills",
        [workspace_read, skills_read, source_read, test_read],
        workspace_root=workspace_root,
        repository_root=repository_root,
        workspaces_root=workspaces_root,
    )
    assert skills_policy.validity.value == "contaminated"
    assert not skills_policy.escalated_to_product_code

    all_policy = evaluate_policy(
        "all",
        [workspace_read, skills_read, source_read, test_read],
        workspace_root=workspace_root,
        repository_root=repository_root,
        workspaces_root=workspaces_root,
    )
    assert all_policy.validity.value == "clean"
    assert all_policy.escalated_to_product_code is True

    bash_tc = ToolCallEvidence(
        ordinal=1,
        call_id="c1",
        tool="bash",
        status="success",
        title="run",
        input={"command": "cat /etc/passwd"},
        metadata={},
        output_chars=100,
        output_preview="",
        output_sha256="def",
        failed=False,
    )
    bash_policy = evaluate_policy(
        "none",
        [bash_tc],
        workspace_root=workspace_root,
        repository_root=repository_root,
        workspaces_root=workspaces_root,
    )
    assert bash_policy.validity.value == "unauditable"
    assert len(bash_policy.opaque_shell_commands) == 1


def test_v2_runner_default_timeout_and_workspace_cwd(tmp_path: Path) -> None:
    from examples.agent_challenges.runner import run_v2_trial

    challenge = load_challenge_manifest(_write_manifest(tmp_path / "challenge"))
    bundle = ROOT / "examples/agent_challenges/instruction_bundles/workflow_cli.yaml"
    workspaces_dir = tmp_path / "workspaces"
    results_dir = tmp_path / "results"
    results_dir.mkdir()

    captured: dict[str, object] = {}

    def fake_run(
        command: list[str],
        *,
        cwd: str,
        text: bool,
        capture_output: bool,
        timeout: float | None,
        check: bool,
    ) -> object:
        captured["cwd"] = cwd
        captured["timeout"] = timeout
        captured["command"] = command
        return type(
            "Result",
            (),
            {
                "returncode": 0,
                "stdout": json.dumps(
                    {
                        "type": "step_finish",
                        "tokens": {"total": 10, "input": 5, "output": 5},
                        "cost": 0.001,
                    }
                ),
                "stderr": "",
            },
        )()

    result = run_v2_trial(
        challenge,
        profile=InstructionProfile.NONE,
        model="test-model",
        variant="high",
        index=1,
        workspaces_dir=workspaces_dir,
        results_dir=results_dir,
        instruction_bundle=bundle,
        run_fn=fake_run,
    )

    assert captured["timeout"] == 3600
    assert isinstance(captured["cwd"], str)
    assert result["instruction_profile"] == "none"
    assert "prompt_hashes" in result
    assert "metrics" in result
    assert "policy" in result
    assert "repository_commit" in result


def test_v2_runner_timeout_preserves_partial_evidence(tmp_path: Path) -> None:
    import subprocess as sp

    from examples.agent_challenges.runner import run_v2_trial

    challenge = load_challenge_manifest(_write_manifest(tmp_path / "challenge"))
    bundle = ROOT / "examples/agent_challenges/instruction_bundles/workflow_cli.yaml"
    workspaces_dir = tmp_path / "workspaces"
    results_dir = tmp_path / "results"
    results_dir.mkdir()

    def fake_run(
        command: list[str],
        *,
        cwd: str,
        text: bool,
        capture_output: bool,
        timeout: float | None,
        check: bool,
    ) -> object:
        raise sp.TimeoutExpired(cmd=command, timeout=3600)

    result = run_v2_trial(
        challenge,
        profile=InstructionProfile.NONE,
        model="test-model",
        variant="high",
        index=1,
        workspaces_dir=workspaces_dir,
        results_dir=results_dir,
        instruction_bundle=bundle,
        run_fn=fake_run,
    )

    assert result["task_outcome"] == "timeout"
    assert "metrics" in result


def test_v2_report_contains_expected_sections(tmp_path: Path) -> None:
    from examples.agent_challenges.reports import report_from_v2_result

    result_payload = {
        "instruction_profile": "skills",
        "task_outcome": "success",
        "evaluation_validity": "contaminated",
        "prompt_hashes": {
            "base": "abc123",
            "profile": "def456",
            "challenge": "ghi789",
            "rendered": "jkl012",
        },
        "metrics": {
            "step_count": 1,
            "tool_call_count": 2,
            "failed_tool_call_count": 0,
            "tool_counts": {"bash": 1, "read": 1},
            "tokens": {
                "total": 100,
                "input": 50,
                "output": 30,
                "reasoning": 10,
                "cache_read": 10,
                "cache_write": 0,
            },
            "cost": 0.005,
            "unknown_event_count": 0,
            "tool_calls": [
                {
                    "ordinal": 1,
                    "call_id": "c1",
                    "tool": "read",
                    "status": "success",
                    "title": "Read file",
                    "input": {"path": "foo.py"},
                    "metadata": {},
                    "output_chars": 100,
                    "output_preview": "file content...",
                    "output_sha256": "abc",
                    "failed": False,
                },
            ],
        },
        "policy": {
            "validity": "contaminated",
            "disallowed_reads": ["src/app.py"],
            "escalated_to_product_code": False,
            "opaque_shell_commands": [],
        },
        "repository_commit": "abc123",
        "repository_dirty": False,
        "harness_version": "v2",
        "index": 1,
        "model": "test-model",
        "variant": "high",
        "duration_seconds": 10.5,
        "returncode": 0,
        "stdout": "test stdout",
        "stderr": "",
        "parsed": {"text": "Agent answer here"},
    }

    report_text = report_from_v2_result(result_payload)

    assert "Instruction profile: skills" in report_text
    assert "Task outcome: success" in report_text
    assert "Evaluation validity: contaminated" in report_text
    assert "Duration" in report_text
    assert "Observed token metrics" in report_text
    assert "Tool calls by tool" in report_text
    assert "Disallowed reads" in report_text
    assert "Agent self-report discrepancies" in report_text
    assert "Final agent answer" in report_text
    assert "Manual audit: pending" in report_text
    assert "file content..." in report_text
    assert "src/app.py" in report_text


def test_v2_manual_audit_includes_automatic_evidence(tmp_path: Path) -> None:
    from examples.agent_challenges.audit import manual_audit_from_v2_result

    result_payload = {
        "instruction_profile": "none",
        "task_outcome": "success",
        "evaluation_validity": "contaminated",
        "policy": {
            "validity": "contaminated",
            "disallowed_reads": ["src/app.py"],
            "escalated_to_product_code": False,
            "opaque_shell_commands": [],
        },
        "metrics": {"tokens": {"total": 100}},
    }

    workspace, audit = manual_audit_from_v2_result(
        result_payload,
        official_outcome="pass",
        auditor_notes="Reviewed and passed.",
    )

    assert audit["manual_audit"]["task_outcome"] == "success"
    assert audit["manual_audit"]["evaluation_validity"] == "contaminated"
    assert audit["manual_audit"]["official_outcome"] == "pass"
    assert audit["manual_audit"]["auditor_notes"] == "Reviewed and passed."
    assert "automatic_evidence" in audit["manual_audit"]


def test_v2_runner_assertions_pass_on_matching_report(tmp_path: Path) -> None:
    from examples.agent_challenges.runner import run_v2_trial

    challenge = load_challenge_manifest(_write_manifest(tmp_path / "challenge"))
    bundle = ROOT / "examples/agent_challenges/instruction_bundles/workflow_cli.yaml"
    workspaces_dir = tmp_path / "workspaces"
    results_dir = tmp_path / "results"
    results_dir.mkdir()

    report_yaml = (
        "```yaml\nchallenge_report:\n  value: expected\n  run_failed: false\n```\n"
    )
    stdout_jsonl = json.dumps({"text": report_yaml})

    def fake_run(
        command: list[str],
        *,
        cwd: str,
        text: bool,
        capture_output: bool,
        timeout: float | None,
        check: bool,
    ) -> object:
        return type(
            "Result",
            (),
            {"returncode": 0, "stdout": stdout_jsonl, "stderr": ""},
        )()

    result = run_v2_trial(
        challenge,
        profile=InstructionProfile.NONE,
        model="test-model",
        variant="high",
        index=1,
        workspaces_dir=workspaces_dir,
        results_dir=results_dir,
        instruction_bundle=bundle,
        run_fn=fake_run,
    )

    assert result["task_outcome"] == "success"
    assert "assertion_failures" not in result
    assert result.get("challenge_report") is not None


def test_v2_runner_assertions_fail_on_mismatched_report(tmp_path: Path) -> None:
    from examples.agent_challenges.runner import run_v2_trial

    challenge = load_challenge_manifest(_write_manifest(tmp_path / "challenge"))
    bundle = ROOT / "examples/agent_challenges/instruction_bundles/workflow_cli.yaml"
    workspaces_dir = tmp_path / "workspaces"
    results_dir = tmp_path / "results"
    results_dir.mkdir()

    report_yaml = (
        "```yaml\nchallenge_report:\n  value: wrong_value\n  run_failed: true\n```\n"
    )
    stdout_jsonl = json.dumps({"text": report_yaml})

    def fake_run(
        command: list[str],
        *,
        cwd: str,
        text: bool,
        capture_output: bool,
        timeout: float | None,
        check: bool,
    ) -> object:
        return type(
            "Result",
            (),
            {"returncode": 0, "stdout": stdout_jsonl, "stderr": ""},
        )()

    result = run_v2_trial(
        challenge,
        profile=InstructionProfile.NONE,
        model="test-model",
        variant="high",
        index=1,
        workspaces_dir=workspaces_dir,
        results_dir=results_dir,
        instruction_bundle=bundle,
        run_fn=fake_run,
    )

    assert result["task_outcome"] == "failed"
    assert "assertion_failures" in result
    assert len(result["assertion_failures"]) == 2
    assert any("value" in f for f in result["assertion_failures"])
    assert any("run_failed" in f for f in result["assertion_failures"])


def test_v2_runner_required_fields_missing(tmp_path: Path) -> None:
    from examples.agent_challenges.runner import run_v2_trial

    challenge = load_challenge_manifest(_write_manifest(tmp_path / "challenge"))
    bundle = ROOT / "examples/agent_challenges/instruction_bundles/workflow_cli.yaml"
    workspaces_dir = tmp_path / "workspaces"
    results_dir = tmp_path / "results"
    results_dir.mkdir()

    report_yaml = "```yaml\nchallenge_report:\n  other_field: true\n```\n"
    stdout_jsonl = json.dumps({"text": report_yaml})

    def fake_run(
        command: list[str],
        *,
        cwd: str,
        text: bool,
        capture_output: bool,
        timeout: float | None,
        check: bool,
    ) -> object:
        return type(
            "Result",
            (),
            {"returncode": 0, "stdout": stdout_jsonl, "stderr": ""},
        )()

    result = run_v2_trial(
        challenge,
        profile=InstructionProfile.NONE,
        model="test-model",
        variant="high",
        index=1,
        workspaces_dir=workspaces_dir,
        results_dir=results_dir,
        instruction_bundle=bundle,
        run_fn=fake_run,
    )

    assert result["task_outcome"] == "failed"
    assert "assertion_failures" in result
    assert any("required field missing" in f for f in result["assertion_failures"])


def test_v2_runner_preserves_evidence_on_parse_failure(tmp_path: Path) -> None:
    from examples.agent_challenges.runner import run_v2_trial

    challenge = load_challenge_manifest(_write_manifest(tmp_path / "challenge"))
    bundle = ROOT / "examples/agent_challenges/instruction_bundles/workflow_cli.yaml"
    workspaces_dir = tmp_path / "workspaces"
    results_dir = tmp_path / "results"
    results_dir.mkdir()

    def fake_run(
        command: list[str],
        *,
        cwd: str,
        text: bool,
        capture_output: bool,
        timeout: float | None,
        check: bool,
    ) -> object:
        raise RuntimeError("subprocess exploded")

    result = run_v2_trial(
        challenge,
        profile=InstructionProfile.NONE,
        model="test-model",
        variant="high",
        index=1,
        workspaces_dir=workspaces_dir,
        results_dir=results_dir,
        instruction_bundle=bundle,
        run_fn=fake_run,
    )

    assert result["task_outcome"] == "parse_error"
    assert "parse_error" in result
    assert result["parse_error"]["type"] == "RuntimeError"
    assert "subprocess exploded" in result["parse_error"]["message"]
    assert result["duration_seconds"] >= 0


def test_v2_runner_to_report_shows_final_answer(tmp_path: Path) -> None:
    from examples.agent_challenges.reports import report_from_v2_result
    from examples.agent_challenges.runner import run_v2_trial

    challenge = load_challenge_manifest(_write_manifest(tmp_path / "challenge"))
    bundle = ROOT / "examples/agent_challenges/instruction_bundles/workflow_cli.yaml"
    workspaces_dir = tmp_path / "workspaces"
    results_dir = tmp_path / "results"
    results_dir.mkdir()

    agent_answer = "The deployment succeeded with id dep_123."
    challenge_report_yaml = (
        "```yaml\nchallenge_report:\n  value: expected\n  run_failed: false\n```\n"
    )
    stdout_jsonl = "\n".join(
        [
            json.dumps({"type": "step_start", "step": 1}),
            json.dumps({"type": "step_finish", "tokens": {"total": 50}, "cost": 0.001}),
            json.dumps(
                {"text": f"Final answer: {agent_answer}\n\n{challenge_report_yaml}"}
            ),
        ]
    )

    def fake_run(
        command: list[str],
        *,
        cwd: str,
        text: bool,
        capture_output: bool,
        timeout: float | None,
        check: bool,
    ) -> object:
        return type(
            "Result",
            (),
            {"returncode": 0, "stdout": stdout_jsonl, "stderr": ""},
        )()

    result = run_v2_trial(
        challenge,
        profile=InstructionProfile.NONE,
        model="test-model",
        variant="high",
        index=1,
        workspaces_dir=workspaces_dir,
        results_dir=results_dir,
        instruction_bundle=bundle,
        run_fn=fake_run,
    )

    assert result["parsed"] is not None
    assert result["task_outcome"] == "success"

    report_text = report_from_v2_result(result)
    assert "Final agent answer" in report_text
    assert agent_answer in report_text


def test_v2_runner_preserves_report_parse_error_on_malformed_yaml(
    tmp_path: Path,
) -> None:
    from examples.agent_challenges.runner import run_v2_trial

    challenge = load_challenge_manifest(_write_manifest(tmp_path / "challenge"))
    bundle = ROOT / "examples/agent_challenges/instruction_bundles/workflow_cli.yaml"
    workspaces_dir = tmp_path / "workspaces"
    results_dir = tmp_path / "results"
    results_dir.mkdir()

    malformed_yaml = (
        "```yaml\nchallenge_report:\n  value: expected\n  run_failed: [unclosed\n```\n"
    )
    stdout_jsonl = "\n".join(
        [
            json.dumps({"type": "step_start", "step": 1}),
            json.dumps({"type": "step_finish", "tokens": {"total": 50}, "cost": 0.001}),
            json.dumps({"text": f"Some output.\n\n{malformed_yaml}"}),
        ]
    )

    def fake_run(
        command: list[str],
        *,
        cwd: str,
        text: bool,
        capture_output: bool,
        timeout: float | None,
        check: bool,
    ) -> object:
        return type(
            "Result",
            (),
            {"returncode": 0, "stdout": stdout_jsonl, "stderr": ""},
        )()

    result = run_v2_trial(
        challenge,
        profile=InstructionProfile.NONE,
        model="test-model",
        variant="high",
        index=1,
        workspaces_dir=workspaces_dir,
        results_dir=results_dir,
        instruction_bundle=bundle,
        run_fn=fake_run,
    )

    assert result["parsed"] is not None
    assert result.get("report_parse_error") is not None
    assert result["report_parse_error"]["type"] in (
        "ParserError",
        "ScannerError",
        "YAMLError",
    )
    assert result.get("challenge_report") is None
