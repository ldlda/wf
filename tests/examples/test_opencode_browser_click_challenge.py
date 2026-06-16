from __future__ import annotations

import json
import subprocess
from pathlib import Path

import yaml

from examples.agent_challenges import reports as generic_reports
from examples.agent_challenges.browser_click_challenge import (
    run_opencode_trials,
)
from examples.agent_challenges.browser_click_challenge.challenge import (
    BROWSER_CLICK_DEF,
    LOCAL_WF_COMMAND_PREFIX,
    render_prompt,
    server_command,
)
from examples.agent_challenges.browser_click_challenge.classification import (
    challenge_report_schema_errors,
    classify_challenge_report,
    classify_output,
    extract_challenge_report,
)
from examples.agent_challenges.browser_click_challenge.opencode_io import (
    build_opencode_command,
    parse_opencode_output,
)
from examples.agent_challenges.browser_click_challenge.reports import (
    report_from_result,
    save_report,
)
from examples.agent_challenges.browser_click_challenge.run_opencode_trials import (
    prepare_trial_workspace,
    run_trial,
    starting_trial_index,
    trial_output_path,
    wf_command_prefix_for_config,
)
from examples.agent_challenges.browser_click_challenge.save_manual_audit import (
    main as save_manual_audit_main,
)
from examples.agent_challenges.browser_click_challenge.save_trial_report import (
    main as save_trial_report_main,
)
from examples.agent_challenges.workspace import (
    ChallengeDef,
    TrialConfig,
    write_trial_config,
)
from examples.agent_challenges.workspace import (
    prepare_trial_workspace as generic_prepare_trial_workspace,
)


def _valid_challenge_report(**overrides: object) -> dict[str, object]:
    report: dict[str, object] = {
        "used_product_path": True,
        "used_helper_script": False,
        "workflow_file": "browser-click.workflow.yaml",
        "deployment_id": "browser_click_case_study.default",
        "run_id": "run_123",
        "before_clicked": False,
        "after_clicked": True,
        "run_failed": False,
        "leftover_processes": False,
        "read": {
            "skills": True,
            "docs": True,
            "product_code": False,
            "adjacent_attempts": False,
            "prior_store": False,
            "existing_solution": False,
        },
        "attempts": {"total": 1, "failed": 0},
        "missed_requirements": ["none"],
        "notes": "ok",
    }
    report.update(overrides)
    return report


def test_build_opencode_command_without_attach(tmp_path: Path) -> None:
    prompt = tmp_path / "prompt.md"
    prompt.write_text("hello", encoding="utf-8")
    config = TrialConfig(
        model="opencode/mimo-v2.5-free",
        variant="high",
        prompt_path=prompt,
        attach_url=None,
        timeout_seconds=120,
        wf_command_prefix=LOCAL_WF_COMMAND_PREFIX,
        server_context="Use local CLI mode.",
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
        wf_command_prefix=LOCAL_WF_COMMAND_PREFIX,
        server_context="Use local CLI mode.",
    )

    command = build_opencode_command(config)

    assert "--attach" in command
    assert "http://127.0.0.1:4096" in command


def test_run_opencode_trials_script_supports_direct_execution() -> None:
    result = subprocess.run(
        [
            "uv",
            "run",
            "python",
            "examples/agent_challenges/browser_click_challenge/run_opencode_trials.py",
            "--help",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "--model" in result.stdout


def test_run_trial_saves_final_report_from_successful_result(
    tmp_path: Path,
    monkeypatch,
) -> None:
    workspace = tmp_path / "trial"
    workspace.mkdir()
    prompt = workspace / "prompt.md"
    prompt.write_text("hello", encoding="utf-8")
    workflow_file = workspace / "workflow.plan.json"
    report = "\n".join(
        [
            "## Report",
            "",
            "```yaml",
            "challenge_report:",
            "  used_product_path: true",
            "  used_helper_script: false",
            f'  workflow_file: "{workflow_file.as_posix()}"',
            '  deployment_id: "browser_click_case_study.default"',
            '  run_id: "run_123"',
            "  before_clicked: false",
            "  after_clicked: true",
            "  run_failed: false",
            "  leftover_processes: false",
            "  read:",
            "    skills: true",
            "    docs: true",
            "    product_code: false",
            "    adjacent_attempts: false",
            "    prior_store: false",
            "    existing_solution: false",
            "  attempts:",
            "    total: 1",
            "    failed: 0",
            "  missed_requirements:",
            '    - "none"',
            '  notes: "ok"',
            "```",
            "",
        ]
    )

    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=["opencode"],
            returncode=0,
            stdout=json.dumps({"text": report}),
            stderr="",
        )

    from examples.agent_challenges import runner as generic_runner

    monkeypatch.setattr(generic_runner.subprocess, "run", fake_run)
    config = TrialConfig(
        model="opencode/mimo-v2.5-free",
        variant="high",
        prompt_path=prompt,
        attach_url=None,
        timeout_seconds=120,
        wf_command_prefix=LOCAL_WF_COMMAND_PREFIX,
        server_context="Use local CLI mode.",
    )

    result = run_trial(config, index=1, results_dir=tmp_path / "results")

    assert result["classification"] == "success"
    assert result["report_path"] == (workspace / "final-report.md").as_posix()
    assert (workspace / "final-report.md").read_text(encoding="utf-8") == (
        report.rstrip() + "\n"
    )
    saved_result = json.loads(
        (tmp_path / "results" / "opencode_mimo-v2.5-free-trial-001.json").read_text(
            encoding="utf-8"
        )
    )
    assert saved_result["report_path"] == (workspace / "final-report.md").as_posix()


def test_run_trial_records_report_save_error_for_timeout(
    tmp_path: Path,
    monkeypatch,
) -> None:
    prompt = tmp_path / "prompt.md"
    prompt.write_text("hello", encoding="utf-8")

    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(cmd=["opencode"], timeout=120)

    from examples.agent_challenges import runner as generic_runner

    monkeypatch.setattr(generic_runner.subprocess, "run", fake_run)
    config = TrialConfig(
        model="opencode/mimo-v2.5-free",
        variant="high",
        prompt_path=prompt,
        attach_url=None,
        timeout_seconds=120,
        wf_command_prefix=LOCAL_WF_COMMAND_PREFIX,
        server_context="Use local CLI mode.",
    )

    result = run_trial(config, index=1, results_dir=tmp_path / "results")

    assert result["classification"] == "timeout"
    assert result["report_save_error"] == "result file is missing parsed output"
    saved_result = json.loads(
        (tmp_path / "results" / "opencode_mimo-v2.5-free-trial-001.json").read_text(
            encoding="utf-8"
        )
    )
    assert saved_result["report_save_error"] == "result file is missing parsed output"


def test_run_trial_records_parse_error_details(
    tmp_path: Path,
    monkeypatch,
) -> None:
    prompt = tmp_path / "prompt.md"
    prompt.write_text("hello", encoding="utf-8")

    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=["opencode"],
            returncode=0,
            stdout="not-json",
            stderr="",
        )

    from examples.agent_challenges import runner as generic_runner

    monkeypatch.setattr(generic_runner.subprocess, "run", fake_run)
    config = TrialConfig(
        model="opencode/mimo-v2.5-free",
        variant="high",
        prompt_path=prompt,
        attach_url=None,
        timeout_seconds=120,
        wf_command_prefix=LOCAL_WF_COMMAND_PREFIX,
        server_context="Use local CLI mode.",
    )

    result = run_trial(config, index=1, results_dir=tmp_path / "results")

    assert result["classification"] == "parse_error"
    assert result["parse_error"]["type"] == "JSONDecodeError"
    assert "Expecting value" in result["parse_error"]["message"]
    saved_result = json.loads(
        (tmp_path / "results" / "opencode_mimo-v2.5-free-trial-001.json").read_text(
            encoding="utf-8"
        )
    )
    assert saved_result["parse_error"] == result["parse_error"]


def test_parse_opencode_output_reads_json_object() -> None:
    payload = {
        "text": "wf run start demo.default\nbefore.clicked false\nafter.clicked true"
    }

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


def test_extract_challenge_report_from_yaml_block() -> None:
    text = """
    The run worked.

    ```yaml
    challenge_report:
      used_product_path: true
      used_helper_script: false
      workflow_file: "browser-click.workflow.yaml"
      deployment_id: "browser_click_case_study.default"
      run_id: "run_123"
      before_clicked: false
      after_clicked: true
      run_failed: false
      leftover_processes: false
      read:
        skills: true
        docs: true
        product_code: false
        adjacent_attempts: false
        prior_store: false
        existing_solution: false
      attempts:
        total: 1
        failed: 0
      missed_requirements:
        - "none"
      notes: "ok"
    ```
    """

    report = extract_challenge_report(text)

    assert report is not None
    assert report["used_product_path"] is True
    assert report["before_clicked"] is False
    assert report["after_clicked"] is True


def test_classify_challenge_report_success() -> None:
    result = classify_challenge_report(_valid_challenge_report())

    assert result == "success"


def test_challenge_report_schema_errors_reject_missing_read_block() -> None:
    report = _valid_challenge_report()
    report.pop("read")

    assert challenge_report_schema_errors(report) == ["missing challenge_report.read"]
    assert classify_challenge_report(report) == "unknown"


def test_classify_output_prefers_yaml_report() -> None:
    result = classify_output(
        """
        Some prose that would otherwise be ambiguous.

        ```yaml
        challenge_report:
          used_product_path: true
          used_helper_script: false
          workflow_file: "browser-click.workflow.yaml"
          deployment_id: "browser_click_case_study.default"
          run_id: "run_123"
          before_clicked: false
          after_clicked: true
          run_failed: false
          leftover_processes: false
          read:
            skills: true
            docs: true
            product_code: false
            adjacent_attempts: false
            prior_store: false
            existing_solution: false
          attempts:
            total: 1
            failed: 0
          missed_requirements:
            - "none"
          notes: "ok"
        ```
        """
    )

    assert result == "success"


def test_classify_challenge_report_detects_helper_script() -> None:
    result = classify_challenge_report(
        _valid_challenge_report(
            used_product_path=False,
            used_helper_script=True,
            workflow_file="",
        )
    )

    assert result == "workflow_script"


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


def test_prepare_trial_workspace_copies_template_to_model_trial_dir(
    tmp_path: Path,
) -> None:
    template = tmp_path / "template"
    template.mkdir()
    (template / "prompt.md").write_text("prompt", encoding="utf-8")
    (template / ".gitignore").write_text(".wf_store/\n", encoding="utf-8")
    workspaces = tmp_path / "workspaces"
    source_root = tmp_path / "browser_click_workflow"
    source_root.mkdir()

    prepared = prepare_trial_workspace(
        model="opencode/mimo-v2.5-free",
        index=7,
        workspaces_dir=workspaces,
        template_dir=template,
        source_root=source_root,
    )

    assert prepared.root == workspaces / "opencode_mimo-v2.5-free-trial-007"
    config = json.loads(prepared.config_path.read_text(encoding="utf-8"))
    assert config["client"]["target"] == {"kind": "local"}
    assert config["server"]["store"] == {
        "kind": "filesystem",
        "root": ".wf_browser_click_store",
    }
    assert config["server"]["sources"][0] == {
        "kind": "python",
        "id": "local.browser_click",
        "path": "../../browser_click_workflow",
        "module": "ops",
        "registry": "registry",
    }
    assert prepared.prompt_path.read_text(encoding="utf-8") == "prompt"
    assert (prepared.root / ".gitignore").read_text(encoding="utf-8") == ".wf_store/\n"


def test_save_trial_report_copies_report_into_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "trial"
    workspace.mkdir()

    output = save_report(workspace=workspace, report_text="# Report\n\nok\n")

    assert output == workspace / "final-report.md"
    assert output.read_text(encoding="utf-8") == "# Report\n\nok\n"


def test_report_from_result_infers_workspace_from_prompt_path(tmp_path: Path) -> None:
    workspace = tmp_path / "trial"
    workspace.mkdir()
    result_path = tmp_path / "result.json"
    result_path.write_text(
        json.dumps(
            {
                "config": {"prompt_path": str(workspace / "prompt.md")},
                "parsed": {"text": "# Report\n\nok"},
            }
        ),
        encoding="utf-8",
    )

    inferred_workspace, report_text = report_from_result(result_path)

    assert inferred_workspace == workspace
    assert report_text == "# Report\n\nok"


def test_report_from_result_recovers_text_from_stdout_when_parsed_is_null(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "trial"
    workspace.mkdir()
    result_path = tmp_path / "result.json"
    result_path.write_text(
        json.dumps(
            {
                "config": {"prompt_path": str(workspace / "prompt.md")},
                "parsed": None,
                "stdout": json.dumps({"type": "message", "text": "# Partial report"}),
            }
        ),
        encoding="utf-8",
    )

    inferred_workspace, report_text = report_from_result(result_path)

    assert inferred_workspace == workspace
    assert report_text == "# Partial report"


def test_save_trial_report_from_result_writes_inferred_workspace(
    tmp_path: Path,
    capsys,
) -> None:
    workspace = tmp_path / "trial"
    workspace.mkdir()
    result_path = tmp_path / "result.json"
    result_path.write_text(
        json.dumps(
            {
                "config": {"prompt_path": str(workspace / "prompt.md")},
                "parsed": {"text": "# Report\n\nok"},
            }
        ),
        encoding="utf-8",
    )

    assert save_trial_report_main(["--from-result", str(result_path)]) == 0

    assert (workspace / "final-report.md").read_text(encoding="utf-8") == (
        "# Report\n\nok\n"
    )
    assert (workspace / "final-report.md").as_posix() in capsys.readouterr().out


def test_save_trial_report_requires_input_when_workspace_only(
    tmp_path: Path,
    monkeypatch,
) -> None:
    class _InteractiveStdin:
        def isatty(self) -> bool:
            return True

        def read(self) -> str:
            raise AssertionError("should not block on interactive stdin")

    workspace = tmp_path / "trial"
    workspace.mkdir()
    monkeypatch.setattr(generic_reports.sys, "stdin", _InteractiveStdin())

    try:
        save_trial_report_main([str(workspace)])
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("expected argparse failure")


def test_save_manual_audit_from_result_infers_report_and_applies_overrides(
    tmp_path: Path,
    capsys,
) -> None:
    workspace = tmp_path / "trial"
    workspace.mkdir()
    report_text = "\n".join(
        [
            "## Report",
            "",
            "```yaml",
            "challenge_report:",
            "  used_product_path: true",
            "  used_helper_script: false",
            '  workflow_file: "workflow.plan.json"',
            '  deployment_id: "browser_click_case_study.default"',
            '  run_id: "run_123"',
            "  before_clicked: false",
            "  after_clicked: true",
            "  run_failed: false",
            "  leftover_processes: false",
            "  read:",
            "    skills: true",
            "    docs: true",
            "    product_code: false",
            "    adjacent_attempts: false",
            "    prior_store: false",
            "    existing_solution: false",
            "  attempts:",
            "    total: 1",
            "    failed: 0",
            "  missed_requirements:",
            '    - "none"',
            '  notes: "agent said clean"',
            "```",
            "",
        ]
    )
    result_path = tmp_path / "result.json"
    result_path.write_text(
        json.dumps(
            {
                "classification": "success",
                "duration_seconds": 42.5,
                "returncode": 0,
                "config": {"prompt_path": str(workspace / "prompt.md")},
                "parsed": {"text": report_text},
            }
        ),
        encoding="utf-8",
    )

    assert (
        save_manual_audit_main(
            [
                "--from-result",
                str(result_path),
                "--manual-classification",
                "success_code_assisted",
                "--audited-at",
                "2026-06-16T00:00:00Z",
                "--set-read",
                "product_code=true",
                "--set-evidence",
                "trace_count=3",
                "--correction",
                "read.product_code: agent reported false, audited true",
                "--notes",
                "Valid product run, but code-assisted.",
            ]
        )
        == 0
    )

    audit_path = workspace / "manual-audit.yaml"
    audit = yaml.safe_load(audit_path.read_text(encoding="utf-8"))["manual_audit"]
    assert audit["auto_classification"] == "success"
    assert audit["manual_classification"] == "success_code_assisted"
    assert audit["audited_at"] == "2026-06-16T00:00:00Z"
    assert audit["valid_product_run"] is True
    assert audit["product_path_used"] is True
    assert audit["helper_script_used"] is False
    assert audit["run_succeeded"] is True
    assert audit["evidence"]["deployment_id"] == "browser_click_case_study.default"
    assert audit["evidence"]["run_id"] == "run_123"
    assert audit["evidence"]["before_clicked"] is False
    assert audit["evidence"]["after_clicked"] is True
    assert audit["evidence"]["trace_count"] == 3
    assert audit["read_flags"]["product_code"] is True
    assert audit["read_flags"]["adjacent_attempts"] is False
    assert audit["attempts"] == {"total": 1, "failed": 0}
    assert audit["corrections"] == [
        "read.product_code: agent reported false, audited true"
    ]
    assert audit["notes"] == "Valid product run, but code-assisted."
    assert audit_path.as_posix() in capsys.readouterr().out


def test_save_manual_audit_from_report_overrides_timeout_result_stream(
    tmp_path: Path,
    capsys,
) -> None:
    workspace = tmp_path / "trial"
    workspace.mkdir()
    report_path = workspace / "final-report.md"
    report_path.write_text(
        "\n".join(
            [
                "```yaml",
                "challenge_report:",
                "  used_product_path: true",
                "  used_helper_script: false",
                '  workflow_file: "workflow.plan.json"',
                '  deployment_id: "browser_click_deployment"',
                '  run_id: "run_123"',
                "  before_clicked: false",
                "  after_clicked: true",
                "  run_failed: false",
                "  leftover_processes: false",
                "  read:",
                "    skills: false",
                "    docs: true",
                "    product_code: true",
                "    adjacent_attempts: false",
                "    prior_store: false",
                "    existing_solution: true",
                "  attempts:",
                "    total: 1",
                "    failed: 0",
                "  missed_requirements:",
                '    - "none"',
                '  notes: "manual UI recovery"',
                "```",
                "",
            ]
        ),
        encoding="utf-8",
    )
    result_path = tmp_path / "result.json"
    result_path.write_text(
        json.dumps(
            {
                "classification": "timeout",
                "duration_seconds": 1000,
                "returncode": None,
                "config": {"prompt_path": str(workspace / "prompt.md")},
                "parsed": {"text": "stale event stream, no final report"},
            }
        ),
        encoding="utf-8",
    )

    assert (
        save_manual_audit_main(
            [
                "--from-result",
                str(result_path),
                "--from-report",
                str(report_path),
                "--manual-classification",
                "success_code_assisted",
                "--audited-at",
                "2026-06-16T00:00:00Z",
            ]
        )
        == 0
    )

    audit_path = workspace / "manual-audit.yaml"
    audit = yaml.safe_load(audit_path.read_text(encoding="utf-8"))["manual_audit"]
    assert audit["auto_classification"] == "timeout"
    assert audit["manual_classification"] == "success_code_assisted"
    assert audit["valid_product_run"] is True
    assert audit["product_path_used"] is True
    assert audit["run_succeeded"] is True
    assert audit["evidence"]["deployment_id"] == "browser_click_deployment"
    assert audit["evidence"]["run_id"] == "run_123"
    assert audit["read_flags"]["product_code"] is True
    assert audit["agent_notes"] == "manual UI recovery"
    assert audit_path.as_posix() in capsys.readouterr().out


def test_save_manual_audit_rejects_non_boolean_read_override(tmp_path: Path) -> None:
    workspace = tmp_path / "trial"
    workspace.mkdir()
    result_path = tmp_path / "result.json"
    result_path.write_text(
        json.dumps(
            {
                "classification": "unknown",
                "config": {"prompt_path": str(workspace / "prompt.md")},
                "parsed": {"text": "no yaml"},
            }
        ),
        encoding="utf-8",
    )

    try:
        save_manual_audit_main(
            [
                "--from-result",
                str(result_path),
                "--manual-classification",
                "invalid",
                "--set-read",
                "product_code=maybe",
            ]
        )
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("expected argparse failure")


def test_prepare_trial_workspace_uses_next_available_directory(
    tmp_path: Path,
) -> None:
    template = tmp_path / "template"
    template.mkdir()
    (template / "prompt.md").write_text("prompt", encoding="utf-8")
    source_root = tmp_path / "browser_click_workflow"
    source_root.mkdir()
    workspaces = tmp_path / "workspaces"
    first = workspaces / "opencode_mimo-v2.5-free-trial-001"
    stale = first / "old-answer.json"
    first.mkdir(parents=True)
    stale.write_text("stale", encoding="utf-8")

    next_index = starting_trial_index(
        model="opencode/mimo-v2.5-free",
        results_dir=tmp_path / "results",
        workspaces_dir=workspaces,
    )
    prepared = prepare_trial_workspace(
        model="opencode/mimo-v2.5-free",
        index=next_index,
        workspaces_dir=workspaces,
        template_dir=template,
        source_root=source_root,
    )

    assert prepared.root == workspaces / "opencode_mimo-v2.5-free-trial-002"
    assert prepared.root.exists()
    assert stale.read_text(encoding="utf-8") == "stale"


def test_main_uses_custom_workspace_template_and_source_root(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    template = tmp_path / "template"
    template.mkdir()
    (template / "prompt.md").write_text("custom prompt", encoding="utf-8")
    source_root = tmp_path / "source"
    source_root.mkdir()
    workspaces = tmp_path / "workspaces"
    results = tmp_path / "results"

    def fake_run_trial(
        config: TrialConfig,
        *,
        index: int,
        results_dir: Path,
        classify_fn: object = None,
    ) -> dict[str, object]:
        return {
            "index": index,
            "classification": "success",
            "returncode": 0,
            "duration_seconds": 1.0,
            "report_path": config.prompt_path.parent / "final-report.md",
        }

    from examples.agent_challenges import runner as generic_runner

    monkeypatch.setattr(generic_runner, "run_trial", fake_run_trial)

    assert (
        run_opencode_trials.main(
            [
                "--model",
                "check/model",
                "--trials",
                "1",
                "--workspace-template",
                str(template),
                "--source-root",
                str(source_root),
                "--workspaces-dir",
                str(workspaces),
                "--results-dir",
                str(results),
            ]
        )
        == 0
    )

    workspace = workspaces / "check_model-trial-001"
    assert workspace.exists()
    assert (workspace / "prompt.md").read_text(encoding="utf-8") == "custom prompt"
    config = json.loads((workspace / "wf.config.json").read_text(encoding="utf-8"))
    assert config["server"]["sources"][0]["path"] == "../../source"
    assert '"success_count": 1' in capsys.readouterr().out


def test_starting_trial_index_accounts_for_existing_results_and_workspaces(
    tmp_path: Path,
) -> None:
    results = tmp_path / "results"
    workspaces = tmp_path / "workspaces"
    results.mkdir()
    workspaces.mkdir()
    (results / "opencode_mimo-v2.5-free-trial-003.json").write_text(
        "{}",
        encoding="utf-8",
    )
    (workspaces / "opencode_mimo-v2.5-free-trial-005").mkdir()
    (workspaces / "other_model-trial-099").mkdir()

    assert (
        starting_trial_index(
            model="opencode/mimo-v2.5-free",
            results_dir=results,
            workspaces_dir=workspaces,
        )
        == 6
    )


def test_wf_command_prefix_for_config_uses_repo_relative_path() -> None:
    config_path = (
        Path("examples")
        / "agent_challenges"
        / "browser_click_challenge"
        / "workspaces"
        / "opencode_mimo-v2.5-free-trial-001"
        / "wf.config.json"
    )

    prefix = wf_command_prefix_for_config(config_path)

    assert prefix == (
        "uv run wf --config "
        "examples/agent_challenges/browser_click_challenge/workspaces/"
        "opencode_mimo-v2.5-free-trial-001/wf.config.json --local"
    )


def test_render_prompt_injects_command_prefix_and_server_context(
    tmp_path: Path,
) -> None:
    prompt = tmp_path / "prompt.md"
    prompt.write_text(
        "Use {{wf_command_prefix}}. {{server_context}}",
        encoding="utf-8",
    )

    rendered = render_prompt(
        prompt,
        wf_command_prefix=LOCAL_WF_COMMAND_PREFIX,
        server_context="No RPC server is staged.",
    )

    assert LOCAL_WF_COMMAND_PREFIX in rendered
    assert "No RPC server is staged." in rendered


def test_server_command_uses_example_config_and_requested_port() -> None:
    command = server_command(
        port=8765, config_arg="examples/browser_click_workflow/wf.config.json"
    )

    assert command[:3] == ["uv", "run", "wf-rpc-server"]
    assert "--config" in command
    assert "examples/browser_click_workflow/wf.config.json" in command
    assert "--port" in command
    assert "8765" in command


# --- New generic-module tests ---


def test_generic_workspace_preparation_writes_config_for_arbitrary_challenge_def(
    tmp_path: Path,
) -> None:
    template = tmp_path / "template"
    template.mkdir()
    (template / "prompt.md").write_text("test prompt", encoding="utf-8")
    workspaces = tmp_path / "workspaces"
    source_root = tmp_path / "my_source"
    source_root.mkdir()

    defn = ChallengeDef(
        name="custom_challenge",
        source_root=source_root,
        source_id="local.custom",
        source_module="custom_ops",
        source_registry="custom_registry",
        store_root=".custom_store",
        default_workspace_template=template,
        default_workspaces_dir=workspaces,
        default_results_dir=tmp_path / "results",
        default_prompt=template / "prompt.md",
        default_server_port=9999,
        server_config_arg="examples/custom/wf.config.json",
    )

    ws = generic_prepare_trial_workspace(
        defn,
        model="test-model",
        index=1,
    )

    assert ws.root == workspaces / "test-model-trial-001"
    config = json.loads(ws.config_path.read_text(encoding="utf-8"))
    assert config["client"]["target"] == {"kind": "local"}
    assert config["server"]["store"] == {"kind": "filesystem", "root": ".custom_store"}
    assert config["server"]["sources"][0] == {
        "kind": "python",
        "id": "local.custom",
        "path": "../../my_source",
        "module": "custom_ops",
        "registry": "custom_registry",
    }
    assert (ws.root / "prompt.md").read_text(encoding="utf-8") == "test prompt"


def test_browser_click_wrapper_produces_expected_paths_and_command_prefix() -> None:
    assert BROWSER_CLICK_DEF.name == "browser_click"
    assert BROWSER_CLICK_DEF.source_id == "local.browser_click"
    assert BROWSER_CLICK_DEF.server_config_arg == (
        "examples/browser_click_workflow/wf.config.json"
    )
    assert LOCAL_WF_COMMAND_PREFIX == (
        "uv run wf --config examples/browser_click_workflow/wf.config.json --local"
    )
    assert BROWSER_CLICK_DEF.default_prompt.name == "prompt.md"
    assert BROWSER_CLICK_DEF.default_prompt.parent.name == "workspace_template"


def test_generic_runner_can_be_configured_with_fake_challenge_and_fake_opencode(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from examples.agent_challenges.runner import main as generic_main

    template = tmp_path / "template"
    template.mkdir()
    (template / "prompt.md").write_text("fake {{wf_command_prefix}}", encoding="utf-8")
    source_root = tmp_path / "source"
    source_root.mkdir()
    workspaces = tmp_path / "workspaces"
    results = tmp_path / "results"

    defn = ChallengeDef(
        name="fake_challenge",
        source_root=source_root,
        source_id="local.fake",
        source_module="fake_ops",
        source_registry="fake_registry",
        store_root=".fake_store",
        default_workspace_template=template,
        default_workspaces_dir=workspaces,
        default_results_dir=results,
        default_prompt=template / "prompt.md",
        default_server_port=9000,
        server_config_arg="fake/config.json",
    )

    def classify_fn(text: str) -> str:
        if "success" in text.lower():
            return "success"
        return "unknown"

    sent_text = json.dumps({"text": "success!"})

    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=["opencode"],
            returncode=0,
            stdout=sent_text,
            stderr="",
        )

    from examples.agent_challenges import runner as generic_runner

    monkeypatch.setattr(generic_runner.subprocess, "run", fake_run)

    exit_code = generic_main(
        defn,
        classify_fn,
        [
            "--model",
            "fake/model",
            "--trials",
            "1",
        ],
    )

    assert exit_code == 0
    assert (workspaces / "fake_model-trial-001").exists()
    assert (results / "fake_model-trial-001.json").exists()


def test_generic_write_trial_config_with_custom_source_root(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "wf.config.json"
    source_root = tmp_path / "custom_root"
    source_root.mkdir()

    defn = ChallengeDef(
        name="test",
        source_root=source_root,
        source_id="local.test",
        source_module="test_mod",
        source_registry="test_reg",
        store_root=".test_store",
        default_workspace_template=tmp_path / "template",
        default_workspaces_dir=tmp_path / "workspaces",
        default_results_dir=tmp_path / "results",
        default_prompt=tmp_path / "template" / "prompt.md",
        default_server_port=8000,
        server_config_arg="test/config.json",
    )

    write_trial_config(config_path, defn=defn)
    config = json.loads(config_path.read_text(encoding="utf-8"))

    assert config["server"]["sources"][0] == {
        "kind": "python",
        "id": "local.test",
        "path": "custom_root",
        "module": "test_mod",
        "registry": "test_reg",
    }
