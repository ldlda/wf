from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from wf_artifacts import FileWorkflowArtifactStore, WorkflowDeployment
from wf_cli.app import app
from typer import Context as TyperContext

from wf_cli.context import CliContext, config_path_from_context, load_cli_context

from tests.wf_mcp.test_support import echo_tool, local_temp_root
from tests.wf_mcp.workflow_surface.conftest import echo_artifact


runner = CliRunner()


def _load_cli_context_with_specs(ctx: TyperContext | str | Path) -> CliContext:
    """Test-only hook: seed executable demo specs for CLI integration tests.

    ``build_service_from_config`` registers connections, adapters, and
    file-backed stores, but not in-memory node specs.  Production code does
    not auto-register specs; this helper exists solely so CLI tests can
    exercise the full command path with a runnable deployment.
    """
    if isinstance(ctx, (str, Path)):
        config_path = ctx
    else:
        config_path = config_path_from_context(ctx)
    context = load_cli_context(config_path)
    service = context.service
    assert service is not None
    service.register_specs("demo.personal", echo_tool)
    return context


def _write_config(root: Path) -> Path:
    config_path = root / "wf_mcp.config.json"
    config_path.write_text(
        json.dumps(
            {
                "store_root": ".wf_mcp_store",
                "connections": [
                    {
                        "id": "demo.personal",
                        "server": "demo",
                        "account": "personal",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return config_path


def _seed_echo_deployment(root: Path) -> Path:
    config_path = _write_config(root)
    store_root = root / ".wf_mcp_store"
    artifact_store = FileWorkflowArtifactStore(store_root)
    artifact_store.save_artifact(echo_artifact())
    artifact_store.save_deployment(
        WorkflowDeployment(
            id="echo.personal",
            artifact_id="echo",
            artifact_version=1,
            bindings=[{"logical_source": "demo", "concrete_source": "demo.personal"}],
        )
    )
    return config_path


def test_wf_deploy_validate_outputs_json() -> None:
    root = local_temp_root() / "wf_cli_deploy_validate"
    root.mkdir(parents=True, exist_ok=True)
    config_path = _seed_echo_deployment(root)

    with patch(
        "wf_cli.commands.deployments.load_cli_context", _load_cli_context_with_specs
    ):
        result = runner.invoke(
            app,
            ["--config", str(config_path), "deploy", "validate", "echo.personal"],
        )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["deployment_id"] == "echo.personal"
    assert payload["status"] == "runnable"
    assert payload["next_actions"]["recommended_next_tool"] == (
        "wf.workflow.run_deployment"
    )


def test_wf_run_start_accepts_inline_json_input() -> None:
    root = local_temp_root() / "wf_cli_run_start"
    root.mkdir(parents=True, exist_ok=True)
    config_path = _seed_echo_deployment(root)

    with patch(
        "wf_cli.commands.runs.load_cli_context_from_typer", _load_cli_context_with_specs
    ):
        result = runner.invoke(
            app,
            [
                "--config",
                str(config_path),
                "run",
                "start",
                "echo.personal",
                "--input",
                '{"text": "hello"}',
            ],
        )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["status"] == "completed"
    assert payload["output"]["echoed"] == "hello"
    assert isinstance(payload["run_id"], str)
    assert payload["next_actions"]["can_continue"] is False


def test_wf_run_start_accepts_input_file() -> None:
    root = local_temp_root() / "wf_cli_run_start_file"
    root.mkdir(parents=True, exist_ok=True)
    config_path = _seed_echo_deployment(root)
    input_path = root / "input.json"
    input_path.write_text('{"text": "from file"}', encoding="utf-8")

    with patch(
        "wf_cli.commands.runs.load_cli_context_from_typer", _load_cli_context_with_specs
    ):
        result = runner.invoke(
            app,
            [
                "--config",
                str(config_path),
                "run",
                "start",
                "echo.personal",
                "--input-file",
                str(input_path),
            ],
        )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["status"] == "completed"
    assert payload["output"]["echoed"] == "from file"


def test_wf_run_inspect_and_trace_existing_run() -> None:
    root = local_temp_root() / "wf_cli_run_inspect_trace"
    root.mkdir(parents=True, exist_ok=True)
    config_path = _seed_echo_deployment(root)

    with patch(
        "wf_cli.commands.runs.load_cli_context_from_typer", _load_cli_context_with_specs
    ):
        start = runner.invoke(
            app,
            [
                "--config",
                str(config_path),
                "run",
                "start",
                "echo.personal",
                "--input",
                '{"text": "hello"}',
            ],
        )
        run_id = json.loads(start.output)["run_id"]

        inspected = runner.invoke(
            app,
            ["--config", str(config_path), "run", "inspect", run_id],
        )
        traced = runner.invoke(
            app,
            [
                "--config",
                str(config_path),
                "run",
                "trace",
                run_id,
                "--from",
                "0",
                "--limit",
                "1",
            ],
        )

    assert inspected.exit_code == 0
    inspected_payload = json.loads(inspected.output)
    assert inspected_payload["run_id"] == run_id
    assert inspected_payload["status"] == "completed"
    assert "trace" not in inspected_payload

    assert traced.exit_code == 0
    traced_payload = json.loads(traced.output)
    assert traced_payload["run_id"] == run_id
    assert traced_payload["trace_start"] == 0
    assert traced_payload["trace_limit"] == 1
    assert traced_payload["trace"][0]["node_id"] == "echo"


def test_wf_run_start_reports_bad_json() -> None:
    root = local_temp_root() / "wf_cli_run_bad_json"
    root.mkdir(parents=True, exist_ok=True)
    config_path = _seed_echo_deployment(root)

    with patch(
        "wf_cli.commands.runs.load_cli_context_from_typer", _load_cli_context_with_specs
    ):
        result = runner.invoke(
            app,
            [
                "--config",
                str(config_path),
                "run",
                "start",
                "echo.personal",
                "--input",
                "{",
            ],
        )

    assert result.exit_code != 0
    assert "invalid JSON" in result.stderr
