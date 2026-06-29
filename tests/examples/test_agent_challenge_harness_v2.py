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
        "debug",
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


def test_invalid_manifest_rejects_source_root_escape(tmp_path: Path) -> None:
    path = _write_manifest(tmp_path)
    text = path.read_text(encoding="utf-8").replace(
        "  root: source",
        "  root: ../source",
    )
    path.write_text(text, encoding="utf-8")

    with pytest.raises(ValueError, match="source.root"):
        load_challenge_manifest(path)


def test_invalid_manifest_rejects_server_config_escape(tmp_path: Path) -> None:
    path = _write_manifest(tmp_path)
    text = path.read_text(encoding="utf-8").replace(
        "  config: wf.config.json",
        "  config: ../wf.config.json",
    )
    path.write_text(text, encoding="utf-8")

    with pytest.raises(ValueError, match="server.config"):
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
    assert len({value.rendered_sha256 for value in rendered.values()}) == 4
    assert "report the exact blocker" in rendered[InstructionProfile.NONE].text.replace(
        "\n", " "
    )
    assert ".agent/skills" in rendered[InstructionProfile.SKILLS].text
    assert "inspect broader repository" in rendered[InstructionProfile.ALL].text
    assert "genuinely blocked" in rendered[InstructionProfile.DEBUG].text
    assert "ux_issues_found" in rendered[InstructionProfile.DEBUG].text


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


def test_extract_trial_metrics_accepts_missing_stdout() -> None:
    from examples.agent_challenges.metrics import extract_trial_metrics

    metrics = extract_trial_metrics(None)

    assert metrics.step_count == 0
    assert metrics.tool_call_count == 0


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


def test_extract_trial_metrics_handles_nested_step_finish_format() -> None:
    from examples.agent_challenges.metrics import extract_trial_metrics

    stdout = "\n".join(
        [
            json.dumps(
                {
                    "type": "step_finish",
                    "part": {
                        "tokens": {
                            "total": 100,
                            "input": 40,
                            "output": 30,
                            "reasoning": 10,
                            "cache": {"read": 20, "write": 0},
                        },
                        "cost": 0.005,
                    },
                }
            ),
            json.dumps(
                {
                    "type": "step_finish",
                    "part": {
                        "tokens": {
                            "total": 50,
                            "input": 20,
                            "output": 20,
                            "reasoning": 5,
                            "cache": {"read": 5, "write": 0},
                        },
                        "cost": 0.002,
                    },
                }
            ),
        ]
    )

    metrics = extract_trial_metrics(stdout)

    assert metrics.tokens.total == 150
    assert metrics.tokens.input == 60
    assert metrics.tokens.output == 50
    assert metrics.tokens.reasoning == 15
    assert metrics.tokens.cache_read == 25
    assert metrics.cost == 0.007


def test_opencode_text_results_preserve_report_before_later_summary() -> None:
    from examples.agent_challenges.opencode_io import opencode_text_results

    report = "```yaml\nchallenge_report:\n  run_failed: false\n```"
    stdout = "\n".join(
        [
            json.dumps({"type": "text", "part": {"text": report}}),
            json.dumps(
                {
                    "type": "text",
                    "part": {"text": "Challenge completed successfully."},
                }
            ),
        ]
    )

    results = opencode_text_results(stdout)

    assert [result["text"] for result in results] == [
        report,
        "Challenge completed successfully.",
    ]


def test_opencode_text_results_accept_json_array_output() -> None:
    from examples.agent_challenges.opencode_io import opencode_text_results

    stdout = json.dumps(
        [
            {"type": "text", "part": {"text": "first"}},
            {"type": "text", "part": {"text": "second"}},
        ]
    )

    results = opencode_text_results(stdout)

    assert [result["text"] for result in results] == ["first", "second"]


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
    repository_index_read = _tc("read", str(repository_root))
    skills_read = _tc(
        "read",
        str(workspace_root / ".agent" / "skills" / "wf-cli" / "SKILL.md"),
    )
    canonical_skills_read = _tc(
        "read",
        str(repository_root / "skills" / "wf-cli" / "SKILL.md"),
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

    none_skills_policy = evaluate_policy(
        "none",
        [repository_index_read, canonical_skills_read],
        workspace_root=workspace_root,
        repository_root=repository_root,
        workspaces_root=workspaces_root,
    )
    assert none_skills_policy.validity.value == "contaminated"

    skills_only_policy = evaluate_policy(
        "skills",
        [workspace_read, repository_index_read, skills_read, canonical_skills_read],
        workspace_root=workspace_root,
        repository_root=repository_root,
        workspaces_root=workspaces_root,
    )
    assert skills_only_policy.validity.value == "clean"
    assert not skills_only_policy.escalated_to_product_code

    skills_policy = evaluate_policy(
        "skills",
        [
            workspace_read,
            repository_index_read,
            skills_read,
            canonical_skills_read,
            source_read,
            test_read,
        ],
        workspace_root=workspace_root,
        repository_root=repository_root,
        workspaces_root=workspaces_root,
    )
    assert skills_policy.validity.value == "contaminated"
    assert not skills_policy.escalated_to_product_code
    assert skills_policy.reads_by_category["repository_index"] == (
        str(repository_root),
    )
    assert str(repository_root / "skills" / "wf-cli" / "SKILL.md") not in (
        skills_policy.disallowed_reads
    )

    all_policy = evaluate_policy(
        "all",
        [
            workspace_read,
            repository_index_read,
            skills_read,
            canonical_skills_read,
            source_read,
            test_read,
        ],
        workspace_root=workspace_root,
        repository_root=repository_root,
        workspaces_root=workspaces_root,
    )
    assert all_policy.validity.value == "clean"
    assert all_policy.escalated_to_product_code is True

    debug_policy = evaluate_policy(
        "debug",
        [
            workspace_read,
            repository_index_read,
            skills_read,
            canonical_skills_read,
            source_read,
            test_read,
        ],
        workspace_root=workspace_root,
        repository_root=repository_root,
        workspaces_root=workspaces_root,
    )
    assert debug_policy.validity.value == "clean"
    assert debug_policy.escalated_to_product_code is True

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
    assert bash_policy.validity.value == "clean"
    assert bash_policy.coverage.value == "partial"
    assert len(bash_policy.opaque_shell_commands) == 1

    wf_tc = ToolCallEvidence(
        ordinal=2,
        call_id="c2",
        tool="bash",
        status="success",
        title="run workflow",
        input={"command": "uv run wf --config trial/wf.config.json --local status"},
        metadata={},
        output_chars=100,
        output_preview="",
        output_sha256="ghi",
        failed=False,
    )
    wf_policy = evaluate_policy(
        "all",
        [wf_tc],
        workspace_root=workspace_root,
        repository_root=repository_root,
        workspaces_root=workspaces_root,
    )
    assert wf_policy.validity.value == "clean"
    assert wf_policy.coverage.value == "complete"
    assert wf_policy.opaque_shell_commands == ()


def test_policy_classifies_sibling_workspace_solution_reads(tmp_path: Path) -> None:
    from examples.agent_challenges.metrics import ToolCallEvidence
    from examples.agent_challenges.policy import evaluate_policy

    workspace_root = tmp_path / "workspaces" / "trial-002"
    workspace_root.mkdir(parents=True)
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    workspaces_root = tmp_path / "workspaces"
    solution_path = workspaces_root / "trial-001" / "workflow.plan.json"
    notes_path = workspaces_root / "trial-001" / "notes.txt"

    def _read(path: Path) -> ToolCallEvidence:
        return ToolCallEvidence(
            ordinal=1,
            call_id="c1",
            tool="read",
            status="success",
            title="read",
            input={"path": str(path)},
            metadata={},
            output_chars=100,
            output_preview="",
            output_sha256="abc",
            failed=False,
        )

    policy = evaluate_policy(
        "all",
        [_read(solution_path), _read(notes_path)],
        workspace_root=workspace_root,
        repository_root=repository_root,
        workspaces_root=workspaces_root,
    )

    assert policy.validity.value == "contaminated"
    assert policy.disallowed_reads == (str(solution_path),)
    assert policy.reads_by_category["existing_solution"] == (str(solution_path),)
    assert policy.reads_by_category["adjacent_attempts"] == (str(notes_path),)


def test_policy_reads_real_filepath_input(tmp_path: Path) -> None:
    from examples.agent_challenges.metrics import ToolCallEvidence
    from examples.agent_challenges.policy import evaluate_policy

    repository = tmp_path / "repo"
    workspace = repository / "examples" / "challenge" / "workspaces" / "trial"
    workspace.mkdir(parents=True)
    source_path = repository / "src" / "app.py"
    call = ToolCallEvidence(
        ordinal=1,
        call_id="read-1",
        tool="read",
        status="completed",
        title="Read source",
        input={"filePath": str(source_path)},
        metadata={},
        output_chars=10,
        output_preview="",
        output_sha256="abc",
        failed=False,
    )

    policy = evaluate_policy(
        "all",
        [call],
        workspace_root=workspace,
        repository_root=repository,
        workspaces_root=workspace.parent,
    )

    assert policy.escalated_to_product_code is True
    assert policy.reads_by_category["source"] == (str(source_path),)


def test_policy_allows_supplied_skill_globs_for_skills_profile(tmp_path: Path) -> None:
    from examples.agent_challenges.metrics import ToolCallEvidence
    from examples.agent_challenges.policy import evaluate_policy

    repository = tmp_path / "repo"
    workspace = repository / "examples" / "challenge" / "workspaces" / "trial"
    workspace.mkdir(parents=True)
    call = ToolCallEvidence(
        ordinal=1,
        call_id="glob-1",
        tool="glob",
        status="completed",
        title="Find supplied skills",
        input={"pattern": ".agent/skills/**/*"},
        metadata={},
        output_chars=10,
        output_preview="",
        output_sha256="abc",
        failed=False,
    )

    policy = evaluate_policy(
        "skills",
        [call],
        workspace_root=workspace,
        repository_root=repository,
        workspaces_root=workspace.parent,
    )

    assert policy.validity.value == "clean"
    assert policy.reads_by_category["supplied_skills"] == (".agent/skills/**/*",)
    assert policy.disallowed_reads == ()


def test_policy_treats_workspace_challenge_paths_as_workspace(tmp_path: Path) -> None:
    from examples.agent_challenges.metrics import ToolCallEvidence
    from examples.agent_challenges.policy import evaluate_policy

    repository = tmp_path / "repo"
    workspace = (
        repository
        / "examples"
        / "agent_challenges"
        / "report_workflow_challenge"
        / "workspaces"
        / "trial-001"
    )
    workspace.mkdir(parents=True)
    workspace_file = workspace / "rendered-prompt.md"
    call = ToolCallEvidence(
        ordinal=1,
        call_id="read-1",
        tool="read",
        status="completed",
        title="Read prompt",
        input={"filePath": str(workspace_file)},
        metadata={},
        output_chars=10,
        output_preview="",
        output_sha256="abc",
        failed=False,
    )

    policy = evaluate_policy(
        "skills",
        [call],
        workspace_root=workspace,
        repository_root=repository,
        workspaces_root=workspace.parent,
    )

    assert policy.validity.value == "clean"
    assert policy.reads_by_category["workspace"] == (str(workspace_file),)
    assert policy.disallowed_reads == ()


def test_policy_records_broad_globs_without_contaminating(tmp_path: Path) -> None:
    from examples.agent_challenges.metrics import ToolCallEvidence
    from examples.agent_challenges.policy import evaluate_policy

    repository = tmp_path / "repo"
    workspace = repository / "examples" / "challenge" / "workspaces" / "trial"
    workspace.mkdir(parents=True)
    call = ToolCallEvidence(
        ordinal=1,
        call_id="glob-1",
        tool="glob",
        status="completed",
        title="Search report workflow files",
        input={"pattern": "**/report_workflow/**"},
        metadata={},
        output_chars=10,
        output_preview="",
        output_sha256="abc",
        failed=False,
    )

    policy = evaluate_policy(
        "skills",
        [call],
        workspace_root=workspace,
        repository_root=repository,
        workspaces_root=workspace.parent,
    )

    assert policy.validity.value == "clean"
    assert policy.reads_by_category["search_intent"] == ("**/report_workflow/**",)
    assert policy.disallowed_reads == ()


def test_policy_none_records_broad_globs_without_contaminating(
    tmp_path: Path,
) -> None:
    from examples.agent_challenges.metrics import ToolCallEvidence
    from examples.agent_challenges.policy import evaluate_policy

    repository = tmp_path / "repo"
    workspace = repository / "examples" / "challenge" / "workspaces" / "trial"
    workspace.mkdir(parents=True)
    call = ToolCallEvidence(
        ordinal=1,
        call_id="glob-1",
        tool="glob",
        status="completed",
        title="Search workspace files",
        input={"pattern": "*.json"},
        metadata={},
        output_chars=10,
        output_preview="",
        output_sha256="abc",
        failed=False,
    )

    policy = evaluate_policy(
        "none",
        [call],
        workspace_root=workspace,
        repository_root=repository,
        workspaces_root=workspace.parent,
    )

    assert policy.validity.value == "clean"
    assert policy.reads_by_category["search_intent"] == ("*.json",)
    assert policy.disallowed_reads == ()


def test_policy_classifies_example_implementation_reads_separately(
    tmp_path: Path,
) -> None:
    from examples.agent_challenges.metrics import ToolCallEvidence
    from examples.agent_challenges.policy import evaluate_policy

    repository = tmp_path / "repo"
    workspace = repository / "examples" / "challenge" / "workspaces" / "trial"
    workspace.mkdir(parents=True)
    ops_path = repository / "examples" / "report_workflow" / "ops.py"
    call = ToolCallEvidence(
        ordinal=1,
        call_id="read-1",
        tool="read",
        status="completed",
        title="Read example implementation",
        input={"filePath": str(ops_path)},
        metadata={},
        output_chars=10,
        output_preview="",
        output_sha256="abc",
        failed=False,
    )

    policy = evaluate_policy(
        "skills",
        [call],
        workspace_root=workspace,
        repository_root=repository,
        workspaces_root=workspace.parent,
    )

    assert policy.validity.value == "contaminated"
    assert policy.escalated_to_product_code is True
    assert policy.reads_by_category["example_implementation"] == (str(ops_path),)
    assert policy.disallowed_reads == (str(ops_path),)


def test_policy_treats_current_workspace_store_as_store_access(
    tmp_path: Path,
) -> None:
    from examples.agent_challenges.metrics import ToolCallEvidence
    from examples.agent_challenges.policy import evaluate_policy

    repository = tmp_path / "repo"
    workspace = repository / "examples" / "challenge" / "workspaces" / "trial"
    store_file = (
        workspace / ".wf_browser_click_store" / "draft_workspaces" / "draft.json"
    )
    store_file.parent.mkdir(parents=True)
    store_file.write_text("{}", encoding="utf-8")
    call = ToolCallEvidence(
        ordinal=1,
        call_id="read-1",
        tool="read",
        status="completed",
        title="Read draft store internals",
        input={"filePath": str(store_file)},
        metadata={},
        output_chars=10,
        output_preview="",
        output_sha256="abc",
        failed=False,
    )

    none_policy = evaluate_policy(
        "none",
        [call],
        workspace_root=workspace,
        repository_root=repository,
        workspaces_root=workspace.parent,
    )
    assert none_policy.validity.value == "contaminated"
    assert none_policy.reads_by_category["prior_store"] == (str(store_file),)
    assert none_policy.disallowed_reads == (str(store_file),)

    skills_policy = evaluate_policy(
        "skills",
        [call],
        workspace_root=workspace,
        repository_root=repository,
        workspaces_root=workspace.parent,
    )
    assert skills_policy.validity.value == "contaminated"
    assert skills_policy.disallowed_reads == (str(store_file),)

    all_policy = evaluate_policy(
        "all",
        [call],
        workspace_root=workspace,
        repository_root=repository,
        workspaces_root=workspace.parent,
    )
    assert all_policy.validity.value == "clean"
    assert all_policy.disallowed_reads == ()


def test_policy_anchors_relative_paths_to_workspace(tmp_path: Path) -> None:
    from examples.agent_challenges.metrics import ToolCallEvidence
    from examples.agent_challenges.policy import evaluate_policy

    repository = tmp_path / "repo"
    workspace = repository / "examples" / "challenge" / "workspaces" / "trial"
    workspace.mkdir(parents=True)
    call = ToolCallEvidence(
        ordinal=1,
        call_id="read-1",
        tool="read",
        status="completed",
        title="Read workspace plan",
        input={"path": "workflow.plan.json"},
        metadata={},
        output_chars=10,
        output_preview="",
        output_sha256="abc",
        failed=False,
    )

    policy = evaluate_policy(
        "none",
        [call],
        workspace_root=workspace,
        repository_root=repository,
        workspaces_root=workspace.parent,
    )

    assert policy.validity.value == "clean"
    assert policy.reads_by_category["workspace"] == ("workflow.plan.json",)


def test_policy_classifies_ready_made_example_plans_as_existing_solution(
    tmp_path: Path,
) -> None:
    from examples.agent_challenges.metrics import ToolCallEvidence
    from examples.agent_challenges.policy import evaluate_policy

    repository = tmp_path / "repo"
    workspace = repository / "examples" / "challenge" / "workspaces" / "trial"
    workspace.mkdir(parents=True)
    plan_path = repository / "examples" / "report_workflow" / "workflow.plan.json"
    call = ToolCallEvidence(
        ordinal=1,
        call_id="read-1",
        tool="read",
        status="completed",
        title="Read ready-made plan",
        input={"filePath": str(plan_path)},
        metadata={},
        output_chars=10,
        output_preview="",
        output_sha256="abc",
        failed=False,
    )

    policy = evaluate_policy(
        "skills",
        [call],
        workspace_root=workspace,
        repository_root=repository,
        workspaces_root=workspace.parent,
    )

    assert policy.validity.value == "contaminated"
    assert policy.reads_by_category["existing_solution"] == (str(plan_path),)
    assert policy.disallowed_reads == (str(plan_path),)


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
    command = captured["command"]
    assert isinstance(command, list)
    assert command[command.index("--title") + 1] == "fixture test-model none 001"
    assert result["instruction_profile"] == "none"
    assert "prompt_hashes" in result
    assert "metrics" in result
    assert "policy" in result
    assert "repository_commit" in result


def test_safe_model_name_replaces_windows_path_separators() -> None:
    from examples.agent_challenges.workspace import _safe_model_name

    safe = _safe_model_name(r"..\bad/model:name")

    assert "\\" not in safe
    assert "/" not in safe
    assert ":" not in safe
    assert ".." not in safe


def test_opencode_trial_title_uses_short_matrix_labels() -> None:
    from examples.agent_challenges.runner import _opencode_trial_title

    assert (
        _opencode_trial_title(
            challenge_id="browser_click",
            model="opencode/deepseek-v4-flash-free",
            profile="skills",
            index=4,
        )
        == "browser deepseek skills 004"
    )
    assert (
        _opencode_trial_title(
            challenge_id="report_workflow",
            model="opencode/nemotron-3-ultra-free",
            profile="all",
            index=12,
        )
        == "report nemotron all 012"
    )


def test_instruction_bundle_rejects_path_traversal(tmp_path: Path) -> None:
    import yaml

    from examples.agent_challenges.workspace import _load_instruction_bundle

    bundle = tmp_path / "bundle.yaml"
    bundle.write_text(
        yaml.safe_dump(
            {
                "files": [
                    {
                        "source": "../outside.md",
                        "destination": "wf-cli/SKILL.md",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="escapes project root"):
        _load_instruction_bundle(bundle)


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
    assert result["returncode"] == -1
    assert "metrics" in result


def test_v2_runner_handles_missing_completed_stdout(tmp_path: Path) -> None:
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
        return type(
            "Result",
            (),
            {"returncode": 0, "stdout": None, "stderr": None},
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

    assert result["stdout"] == ""
    assert result["stderr"] == ""
    assert result["task_outcome"] == "failed"
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
        output_name=str(tmp_path / "manual-audit.yaml"),
    )

    assert workspace == tmp_path / "manual-audit.yaml"
    assert workspace.is_file()
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


def test_v2_runner_debug_profile_requires_ux_issues_found(
    tmp_path: Path,
) -> None:
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
        profile=InstructionProfile.DEBUG,
        model="test-model",
        variant="high",
        index=1,
        workspaces_dir=workspaces_dir,
        results_dir=results_dir,
        instruction_bundle=bundle,
        run_fn=fake_run,
    )

    assert result["task_outcome"] == "failed"
    assert any("ux_issues_found" in f for f in result["assertion_failures"])


def test_v2_runner_debug_profile_requires_challenge_report(tmp_path: Path) -> None:
    from examples.agent_challenges.runner import run_v2_trial

    manifest_path = _write_manifest(tmp_path / "challenge")
    manifest_path.write_text(
        manifest_path.read_text(encoding="utf-8").replace(
            "  required_fields: [value, run_failed]\n"
            "  success_assertions:\n"
            "    value: expected\n"
            "    run_failed: false\n",
            "  required_fields: []\n  success_assertions: {}\n",
        ),
        encoding="utf-8",
    )
    challenge = load_challenge_manifest(manifest_path)
    bundle = ROOT / "examples/agent_challenges/instruction_bundles/workflow_cli.yaml"
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
        return type(
            "Result",
            (),
            {
                "returncode": 0,
                "stdout": json.dumps({"text": "Completed without a report."}),
                "stderr": "",
            },
        )()

    result = run_v2_trial(
        challenge,
        profile=InstructionProfile.DEBUG,
        model="test-model",
        variant="high",
        index=1,
        workspaces_dir=tmp_path / "workspaces",
        results_dir=results_dir,
        instruction_bundle=bundle,
        run_fn=fake_run,
    )

    assert result["task_outcome"] == "failed"
    assert any("challenge_report" in f for f in result["assertion_failures"])


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

    assert result["task_outcome"] == "runner_error"
    assert result["returncode"] == -2
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
            json.dumps(
                {"text": "Challenge completed successfully after the full report."}
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


BROWSER_CHALLENGE = (
    ROOT
    / "examples"
    / "agent_challenges"
    / "browser_click_challenge"
    / "challenge.yaml"
)
REPORT_CHALLENGE = (
    ROOT
    / "examples"
    / "agent_challenges"
    / "report_workflow_challenge"
    / "challenge.yaml"
)
INSTRUCTION_BUNDLE = (
    ROOT / "examples" / "agent_challenges" / "instruction_bundles" / "workflow_cli.yaml"
)


@pytest.mark.parametrize(
    "manifest_path",
    [BROWSER_CHALLENGE, REPORT_CHALLENGE],
    ids=["browser_click", "report_workflow"],
)
def test_both_challenges_load_through_same_manifest(manifest_path: Path) -> None:
    loaded = load_challenge_manifest(manifest_path)

    assert loaded.manifest.version == 1
    assert loaded.prompt_path.is_file()
    assert loaded.workspace_template.is_dir()
    assert loaded.manifest.report.required_fields


@pytest.mark.parametrize(
    "manifest_path, expected_id, expected_source_id",
    [
        (BROWSER_CHALLENGE, "browser_click", "local.browser_click"),
        (REPORT_CHALLENGE, "report_workflow", "local.report"),
    ],
    ids=["browser_click", "report_workflow"],
)
def test_both_challenges_prepare_workspaces_under_each_profile(
    manifest_path: Path,
    expected_id: str,
    expected_source_id: str,
    tmp_path: Path,
) -> None:
    loaded = load_challenge_manifest(manifest_path)

    assert loaded.manifest.id == expected_id
    assert loaded.manifest.source.id == expected_source_id

    for profile in InstructionProfile:
        workspace = prepare_v2_trial_workspace(
            loaded,
            profile=profile,
            model="test-model",
            index=1,
            workspaces_dir=tmp_path / profile.value,
            instruction_bundle=INSTRUCTION_BUNDLE,
        )

        assert workspace.config_path.is_file()
        config = json.loads(workspace.config_path.read_text(encoding="utf-8"))
        assert config["client"]["target"] == {"kind": "local"}
        assert config["server"]["store"]["root"] == loaded.manifest.store_root

        if profile in (
            InstructionProfile.SKILLS,
            InstructionProfile.ALL,
            InstructionProfile.DEBUG,
        ):
            assert (workspace.root / ".agent/skills/wf-cli/SKILL.md").is_file()
        else:
            assert not (workspace.root / ".agent").exists()


def test_both_challenges_produce_different_challenge_hashes_but_same_base(
    tmp_path: Path,
) -> None:
    from examples.agent_challenges.prompts import compose_trial_prompt

    browser = load_challenge_manifest(BROWSER_CHALLENGE)
    report = load_challenge_manifest(REPORT_CHALLENGE)

    hashes: dict[str, str] = {}
    for name, challenge in [("browser", browser), ("report", report)]:
        for profile in InstructionProfile:
            rendered = compose_trial_prompt(
                challenge,
                profile=profile,
                wf_command_prefix="uv run wf --config wf.config.json --local",
                server_context="Local mode.",
                workspace_path=tmp_path / f"{name}_{profile.value}",
            )
            hashes[f"{name}_{profile.value}"] = rendered.challenge_sha256

    assert hashes["browser_none"] != hashes["report_none"]
    for profile in InstructionProfile:
        assert hashes[f"browser_{profile.value}"] != hashes[f"report_{profile.value}"]


def test_runner_to_report_success(tmp_path: Path) -> None:
    from examples.agent_challenges.runner import run_v2_trial

    challenge = load_challenge_manifest(_write_manifest(tmp_path / "challenge"))
    bundle = ROOT / "examples/agent_challenges/instruction_bundles/workflow_cli.yaml"
    workspaces_dir = tmp_path / "workspaces"
    results_dir = tmp_path / "results"
    results_dir.mkdir()

    agent_answer = "Deployment dep_abc created."
    stdout_jsonl = "\n".join(
        [
            json.dumps({"type": "step_start", "step": 1}),
            json.dumps(
                {
                    "type": "step_finish",
                    "tokens": {"total": 50, "input": 20, "output": 15},
                    "cost": 0.002,
                }
            ),
            json.dumps(
                {
                    "type": "text",
                    "part": {"text": f"Final answer: {agent_answer}"},
                }
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

    assert result["challenge_id"] == "fixture"
    assert isinstance(result["workspace_path"], str)
    assert isinstance(result["result_path"], str)
    assert isinstance(result["report_paths"], dict)
    assert "markdown" in result["report_paths"]
    assert "results_markdown" in result["report_paths"]
    assert "machine" in result["report_paths"]

    raw_path = Path(result["result_path"])
    md_path = Path(result["report_paths"]["markdown"])
    results_md_path = Path(result["report_paths"]["results_markdown"])
    machine_path = Path(result["report_paths"]["machine"])

    assert raw_path.is_file()
    assert md_path.is_file()
    assert results_md_path.is_file()
    assert machine_path.is_file()

    machine = json.loads(machine_path.read_text(encoding="utf-8"))
    assert machine["identity"]["challenge_id"] == "fixture"

    md = md_path.read_text(encoding="utf-8")
    assert agent_answer in md
    assert results_md_path.read_text(encoding="utf-8") == md


def test_runner_to_report_timeout(tmp_path: Path) -> None:
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
    assert result["returncode"] == -1
    assert isinstance(result.get("workspace_path"), str)
    assert isinstance(result.get("report_paths"), dict)


BASE_PROMPT = ROOT / "examples/agent_challenges/base-prompt.md"


def test_base_prompt_mentions_self_report_rules() -> None:
    text = BASE_PROMPT.read_text(encoding="utf-8")
    assert "tests/" in text or "tests" in text
    assert "examples/" in text or "examples" in text
    assert "read.product_code" in text
    assert "read.existing_solution" in text
    assert "read.adjacent_attempts" in text
