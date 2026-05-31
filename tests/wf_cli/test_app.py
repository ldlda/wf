from __future__ import annotations

from typer.testing import CliRunner

from wf_cli.app import app


runner = CliRunner()


def test_wf_help_lists_lifecycle_groups() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "cap" in result.output
    assert "draft" in result.output
    assert "artifact" in result.output
    assert "deploy" in result.output
    assert "run" in result.output
    assert "docs" in result.output
    assert "schema" in result.output
    assert "explain" in result.output


def test_wf_run_group_help_exists() -> None:
    result = runner.invoke(app, ["run", "--help"])

    assert result.exit_code == 0
    assert "Run workflow deployments" in result.output


def test_root_config_flag_accepted_before_subcommand() -> None:
    result = runner.invoke(app, ["--config", "custom.json", "run", "--help"])

    assert result.exit_code == 0
    assert "Run workflow deployments" in result.output


def test_wf_deploy_validate_help_exists() -> None:
    result = runner.invoke(app, ["deploy", "validate", "--help"])

    assert result.exit_code == 0
    assert "Validate one saved workflow deployment" in result.output


def test_wf_run_start_help_exists() -> None:
    result = runner.invoke(app, ["run", "start", "--help"])

    assert result.exit_code == 0
    assert "--input-file" in result.output


def test_wf_explain_help_shows_input_modes() -> None:
    result = runner.invoke(app, ["explain", "--help"])

    assert result.exit_code == 0
    assert "--input-file" in result.output
    assert "--stdin" in result.output
    assert "--list" in result.output
