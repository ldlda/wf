from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from typer import Context as TyperContext
from typer.testing import CliRunner

from tests.wf_mcp.test_support import echo_tool, local_temp_root
from tests.wf_mcp.workflow_surface.conftest import echo_artifact
from wf_artifacts import FileWorkflowArtifactStore, WorkflowDeployment
from wf_cli.app import app
from wf_cli.context import CliContext, config_path_from_context, load_cli_context
from wf_cli.formats import ListOutputFormat, render_list_payload
from wf_cli.io import CliInputError, parse_bindings, parse_json_value


def _load_cli_context_with_specs(ctx: TyperContext | str | Path) -> CliContext:
    if isinstance(ctx, (str, Path)):
        config_path = ctx
    else:
        config_path = config_path_from_context(ctx)
    context = load_cli_context(config_path)
    service = context.service
    assert service is not None
    service.register_specs("demo.personal", echo_tool)
    return context


def test_render_list_payload_ids_uses_requested_id_field() -> None:
    payload = {"capabilities": [{"name": "wf.std.truthy"}, {"name": "wf.std.add"}]}

    rendered = render_list_payload(
        payload,
        collection_key="capabilities",
        output_format=ListOutputFormat.IDS,
        id_field="name",
    )

    assert rendered == "wf.std.truthy\nwf.std.add"


def test_render_list_payload_compact_includes_summary_fields() -> None:
    payload = {
        "nodes": [
            {
                "name": "workflow.echo.v1",
                "kind": "workflow",
                "display_name": "Echo",
            }
        ]
    }

    rendered = render_list_payload(
        payload,
        collection_key="nodes",
        output_format=ListOutputFormat.COMPACT,
        id_field="name",
        summary_fields=("kind", "display_name"),
    )

    assert rendered == "workflow.echo.v1\tkind=workflow\tdisplay_name=Echo"


def test_render_list_payload_json_returns_pretty_json() -> None:
    payload = {"deployments": [{"id": "echo.personal"}]}

    rendered = render_list_payload(
        payload,
        collection_key="deployments",
        output_format=ListOutputFormat.JSON,
        id_field="id",
    )

    parsed = json.loads(rendered)
    assert parsed["deployments"][0]["id"] == "echo.personal"


def test_render_list_payload_rejects_missing_collection_key() -> None:
    with pytest.raises(ValueError, match="missing required field 'nodes'"):
        render_list_payload(
            {"capabilities": []},
            collection_key="nodes",
            output_format=ListOutputFormat.IDS,
            id_field="name",
        )


def test_render_list_payload_rejects_non_array_collection() -> None:
    with pytest.raises(ValueError, match="field 'nodes' must be an array"):
        render_list_payload(
            {"nodes": {}},
            collection_key="nodes",
            output_format=ListOutputFormat.IDS,
            id_field="name",
        )


def test_parse_json_value_accepts_arrays_for_json_patch() -> None:
    value = parse_json_value(
        input_json='[{"op":"replace","path":"/name","value":"x"}]', input_file=None
    )

    assert isinstance(value, list)
    assert value[0]["op"] == "replace"


def test_parse_json_value_rejects_both_input_modes(tmp_path) -> None:
    payload = tmp_path / "payload.json"
    payload.write_text("{}", encoding="utf-8")

    with pytest.raises(CliInputError, match="mutually exclusive"):
        parse_json_value(input_json="{}", input_file=payload)


def test_parse_bindings_rejects_invalid_shape() -> None:
    with pytest.raises(CliInputError, match="logical=concrete"):
        parse_bindings(["demo.personal"])


def test_parse_bindings_rejects_duplicate_logical_source() -> None:
    with pytest.raises(CliInputError, match="duplicate --binding"):
        parse_bindings(["demo=demo.personal", "demo=demo.work"])


runner = CliRunner()


def _write_cli_config(root: Path) -> Path:
    config_path = root / "wf_mcp.config.json"
    config_path.write_text(
        json.dumps(
            {
                "store_root": ".wf_mcp_store",
                "connections": [
                    {"id": "demo.personal", "server": "demo", "account": "personal"}
                ],
            }
        ),
        encoding="utf-8",
    )
    return config_path


def test_wf_cap_list_outputs_json() -> None:
    root = local_temp_root() / "wf_cli_cap_list"
    root.mkdir(parents=True, exist_ok=True)
    config_path = _write_cli_config(root)

    with patch(
        "wf_cli.commands.caps.load_cli_context_from_typer", _load_cli_context_with_specs
    ):
        result = runner.invoke(
            app,
            ["--config", str(config_path), "cap", "list", "--source", "demo.personal"],
        )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["capabilities"][0]["name"] == "demo.personal.echo_tool"
    assert payload["capabilities"][0]["source_id"] == "demo.personal"


def test_wf_cap_list_ids_format() -> None:
    root = local_temp_root() / "wf_cli_cap_list_ids"
    root.mkdir(parents=True, exist_ok=True)
    config_path = _write_cli_config(root)

    with patch(
        "wf_cli.commands.caps.load_cli_context_from_typer", _load_cli_context_with_specs
    ):
        result = runner.invoke(
            app,
            [
                "--config",
                str(config_path),
                "cap",
                "list",
                "--source",
                "demo.personal",
                "--format",
                "ids",
            ],
        )

    assert result.exit_code == 0
    assert result.output.strip() == "demo.personal.echo_tool"


def test_wf_cap_inspect_outputs_detail() -> None:
    root = local_temp_root() / "wf_cli_cap_inspect"
    root.mkdir(parents=True, exist_ok=True)
    config_path = _write_cli_config(root)

    with patch(
        "wf_cli.commands.caps.load_cli_context_from_typer", _load_cli_context_with_specs
    ):
        result = runner.invoke(
            app,
            ["--config", str(config_path), "cap", "inspect", "demo.personal.echo_tool"],
        )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["name"] == "demo.personal.echo_tool"
    assert payload["wrapper_hints"]["input_map"] == {"input.text": "text"}


def _seed_echo_artifact(root: Path) -> Path:
    config_path = _write_cli_config(root)
    store = FileWorkflowArtifactStore(root / ".wf_mcp_store")
    store.save_artifact(echo_artifact())
    return config_path


def _seed_echo_deployment(root: Path) -> Path:
    config_path = _seed_echo_artifact(root)
    store = FileWorkflowArtifactStore(root / ".wf_mcp_store")
    store.save_deployment(
        WorkflowDeployment(
            id="echo.personal",
            artifact_id="echo",
            artifact_version=1,
            bindings=[{"logical_source": "demo", "concrete_source": "demo.personal"}],
        )
    )
    return config_path


def test_wf_artifact_list_and_inspect() -> None:
    root = local_temp_root() / "wf_cli_artifacts"
    root.mkdir(parents=True, exist_ok=True)
    config_path = _seed_echo_artifact(root)

    listed = runner.invoke(
        app, ["--config", str(config_path), "artifact", "list", "--format", "ids"]
    )
    inspected = runner.invoke(
        app, ["--config", str(config_path), "artifact", "inspect", "echo", "1"]
    )

    assert listed.exit_code == 0
    assert listed.output.strip() == "workflow.echo.v1"
    assert inspected.exit_code == 0
    payload = json.loads(inspected.output)
    assert payload["id"] == "echo"
    assert payload["version"] == 1


def test_wf_deploy_list_inspect_save_delete() -> None:
    root = local_temp_root() / "wf_cli_deploy_lifecycle"
    root.mkdir(parents=True, exist_ok=True)
    config_path = _seed_echo_deployment(root)

    listed = runner.invoke(
        app, ["--config", str(config_path), "deploy", "list", "--format", "ids"]
    )
    inspected = runner.invoke(
        app, ["--config", str(config_path), "deploy", "inspect", "echo.personal"]
    )
    saved = runner.invoke(
        app,
        [
            "--config",
            str(config_path),
            "deploy",
            "save",
            "echo.copy",
            "--artifact",
            "echo",
            "--version",
            "1",
            "--binding",
            "demo=demo.personal",
        ],
    )
    deleted = runner.invoke(
        app, ["--config", str(config_path), "deploy", "delete", "echo.copy"]
    )

    assert listed.exit_code == 0
    assert listed.output.strip() == "echo.personal"
    assert inspected.exit_code == 0
    assert json.loads(inspected.output)["id"] == "echo.personal"
    assert saved.exit_code == 0
    assert json.loads(saved.output)["deployment_id"] == "echo.copy"
    assert deleted.exit_code == 0
    assert json.loads(deleted.output)["deleted"] is True


def test_wf_draft_create_patch_validate_save() -> None:
    root = local_temp_root() / "wf_cli_draft_lifecycle"
    root.mkdir(parents=True, exist_ok=True)
    config_path = _write_cli_config(root)

    with patch("wf_cli.commands.drafts.load_cli_context", _load_cli_context_with_specs):
        created = runner.invoke(
            app,
            [
                "--config",
                str(config_path),
                "draft",
                "create-from-capability",
                "echo_workspace",
                "demo.personal.echo_tool",
                "--name",
                "echo_workspace",
            ],
        )
        listed = runner.invoke(
            app, ["--config", str(config_path), "draft", "list", "--format", "ids"]
        )
        inspected = runner.invoke(
            app,
            [
                "--config",
                str(config_path),
                "draft",
                "inspect",
                "echo_workspace",
                "--include-draft",
            ],
        )
        revision = json.loads(created.output)["revision"]
        patched = runner.invoke(
            app,
            [
                "--config",
                str(config_path),
                "draft",
                "patch",
                "echo_workspace",
                "--revision",
                str(revision),
                "--input",
                '[{"op":"replace","path":"/name","value":"echo_workspace_renamed"}]',
            ],
        )
        validated = runner.invoke(
            app, ["--config", str(config_path), "draft", "validate", "echo_workspace"]
        )
        saved = runner.invoke(
            app,
            [
                "--config",
                str(config_path),
                "draft",
                "save",
                "echo_workspace",
                "--artifact",
                "echo_workspace",
                "--version",
                "1",
                "--title",
                "Echo Workspace",
                "--outcome",
                "completed",
                "--binding",
                "demo=demo.personal",
            ],
        )

    assert created.exit_code == 0
    assert json.loads(created.output)["workspace_id"] == "echo_workspace"
    assert listed.exit_code == 0
    assert listed.output.strip() == "echo_workspace"
    assert inspected.exit_code == 0
    assert "draft" in json.loads(inspected.output)
    assert patched.exit_code == 0
    assert json.loads(patched.output)["revision"] == revision + 1
    assert validated.exit_code == 0
    assert json.loads(validated.output)["status"] == "valid"
    assert saved.exit_code == 0
    assert json.loads(saved.output)["saved"] is True
