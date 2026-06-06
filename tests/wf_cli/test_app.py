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
    assert "source" in result.output
    assert "admin" in result.output
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


def test_wf_cap_list_help_exists() -> None:
    result = runner.invoke(app, ["cap", "list", "--help"])

    assert result.exit_code == 0
    assert "--format" in result.output
    assert "--source" in result.output


def test_wf_source_list_help_exists() -> None:
    result = runner.invoke(app, ["source", "list", "--help"])

    assert result.exit_code == 0
    assert "--format" in result.output
    assert "--limit" in result.output


def test_wf_admin_connections_help_exists() -> None:
    result = runner.invoke(app, ["admin", "connections", "--help"])

    assert result.exit_code == 0
    assert "--format" in result.output


def test_wf_artifact_list_help_exists() -> None:
    result = runner.invoke(app, ["artifact", "list", "--help"])

    assert result.exit_code == 0
    assert "--format" in result.output


def test_wf_deploy_save_help_exists() -> None:
    result = runner.invoke(app, ["deploy", "save", "--help"])

    assert result.exit_code == 0
    assert "--binding" in result.output


def test_wf_draft_create_from_capability_help_exists() -> None:
    result = runner.invoke(app, ["draft", "create-from-capability", "--help"])

    assert result.exit_code == 0
    assert "--title" in result.output
