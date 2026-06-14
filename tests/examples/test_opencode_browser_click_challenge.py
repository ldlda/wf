from __future__ import annotations

import json
from pathlib import Path

from examples.agent_challenges.browser_click_challenge.run_opencode_trials import (
    LOCAL_WF_COMMAND_PREFIX,
    TrialConfig,
    build_opencode_command,
    classify_challenge_report,
    classify_output,
    extract_challenge_report,
    parse_opencode_output,
    prepare_trial_workspace,
    render_prompt,
    server_command,
    trial_output_path,
    wf_command_prefix_for_config,
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
      notes: "ok"
    ```
    """

    report = extract_challenge_report(text)

    assert report is not None
    assert report["used_product_path"] is True
    assert report["before_clicked"] is False
    assert report["after_clicked"] is True


def test_classify_challenge_report_success() -> None:
    result = classify_challenge_report(
        {
            "used_product_path": True,
            "used_helper_script": False,
            "workflow_file": "browser-click.workflow.yaml",
            "deployment_id": "browser_click_case_study.default",
            "run_id": "run_123",
            "before_clicked": False,
            "after_clicked": True,
            "run_failed": False,
        }
    )

    assert result == "success"


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
          notes: "ok"
        ```
        """
    )

    assert result == "success"


def test_classify_challenge_report_detects_helper_script() -> None:
    result = classify_challenge_report(
        {
            "used_product_path": False,
            "used_helper_script": True,
            "workflow_file": "",
            "deployment_id": "browser_click_case_study.default",
            "run_id": "run_123",
            "before_clicked": False,
            "after_clicked": True,
            "run_failed": False,
        }
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
    (template / "wf.config.json").write_text('{"version": 1}', encoding="utf-8")
    (template / "prompt.md").write_text("prompt", encoding="utf-8")
    (template / ".gitignore").write_text(".wf_store/\n", encoding="utf-8")
    workspaces = tmp_path / "workspaces"

    prepared = prepare_trial_workspace(
        model="opencode/mimo-v2.5-free",
        index=7,
        workspaces_dir=workspaces,
        template_dir=template,
    )

    assert prepared.root == workspaces / "opencode_mimo-v2.5-free-trial-007"
    assert prepared.config_path.read_text(encoding="utf-8") == '{"version": 1}'
    assert prepared.prompt_path.read_text(encoding="utf-8") == "prompt"
    assert (prepared.root / ".gitignore").read_text(encoding="utf-8") == ".wf_store/\n"


def test_prepare_trial_workspace_removes_stale_previous_attempt(
    tmp_path: Path,
) -> None:
    template = tmp_path / "template"
    template.mkdir()
    (template / "wf.config.json").write_text('{"version": 1}', encoding="utf-8")
    (template / "prompt.md").write_text("prompt", encoding="utf-8")
    workspaces = tmp_path / "workspaces"
    stale = workspaces / "opencode_mimo-v2.5-free-trial-001" / "old-answer.json"
    stale.parent.mkdir(parents=True)
    stale.write_text("stale", encoding="utf-8")

    prepared = prepare_trial_workspace(
        model="opencode/mimo-v2.5-free",
        index=1,
        workspaces_dir=workspaces,
        template_dir=template,
    )

    assert prepared.root.exists()
    assert not stale.exists()


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
    command = server_command(port=8765)

    assert command[:3] == ["uv", "run", "wf-rpc-server"]
    assert "--config" in command
    assert "examples/browser_click_workflow/wf.config.json" in command
    assert "--port" in command
    assert "8765" in command
