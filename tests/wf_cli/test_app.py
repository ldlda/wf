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


def test_wf_main_loads_dotenv_before_invoking_app(monkeypatch) -> None:
    import wf_cli.app as mod

    calls: list[str] = []

    monkeypatch.setattr(mod, "load_dotenv", lambda: calls.append("dotenv"))
    monkeypatch.setattr(mod, "app", lambda: calls.append("app"))

    mod.main()

    assert calls == ["dotenv", "app"]


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


def test_wf_schema_help_describes_catalog_and_verbose_output() -> None:
    result = runner.invoke(app, ["schema", "--help"])

    assert result.exit_code == 0
    output = result.output.lower()
    assert "compact workflow schema outline" in output
    assert "--verbose" in output
    assert "draft" in output
    assert "raw" in output
    assert "core" in output


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


def test_wf_draft_map_help_explains_replace_merge_and_validate() -> None:
    input_result = runner.invoke(app, ["draft", "set-input", "--help"])
    output_result = runner.invoke(app, ["draft", "set-output", "--help"])

    assert input_result.exit_code == 0
    assert output_result.exit_code == 0
    input_help = " ".join(input_result.output.split())
    output_help = " ".join(output_result.output.split())
    assert "replaces the full input map" in input_help
    assert "Use --merge only" in input_help
    assert "draft validate" in input_help
    assert "replaces the full output map" in output_help
    assert "Use --merge only" in output_help
    assert "draft validate" in output_help


def test_wf_draft_bind_output_to_state_help_explains_composed_edit() -> None:
    result = runner.invoke(app, ["draft", "bind-output-to-state", "--help"])

    assert result.exit_code == 0
    output = " ".join(result.output.split())
    assert "state schema" in output
    assert "output binding" in output
    assert "validate" in output


def test_wf_draft_add_step_from_capability_help_explains_explicit_wiring() -> None:
    result = runner.invoke(app, ["draft", "add-step-from-capability", "--help"])

    assert result.exit_code == 0
    output = " ".join(result.output.split())
    assert "--from-step" in output
    assert "--bind-output" in output
    assert "does not guess" in output


def test_wf_draft_route_flags_reject_duplicate_outcomes() -> None:
    add_result = runner.invoke(
        app,
        [
            "draft",
            "add-step-from-capability",
            "ws",
            "--revision",
            "1",
            "--step",
            "call",
            "--capability",
            "demo.call",
            "--route",
            "ok=call",
            "--route",
            "ok=__end__",
        ],
    )
    branch_result = runner.invoke(
        app,
        [
            "draft",
            "branch",
            "ws",
            "--revision",
            "1",
            "--step",
            "call",
            "--route",
            "ok=call",
            "--route",
            "ok=__end__",
        ],
    )

    assert add_result.exit_code == 2
    assert branch_result.exit_code == 2
    assert "duplicate --route for 'ok'" in add_result.output
    assert "duplicate --route for 'ok'" in branch_result.output
