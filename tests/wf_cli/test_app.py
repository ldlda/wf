from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
import typer
from typer.testing import CliRunner

from wf_cli.app import app
from wf_cli.commands.draft_options import parse_json_file, route_source

runner = CliRunner()


def test_draft_options_parse_json_file_reports_invalid_input(tmp_path) -> None:
    path = tmp_path / "invalid.json"
    path.write_text("{", encoding="utf-8")

    with pytest.raises(typer.BadParameter, match="--schema-file: invalid JSON"):
        parse_json_file(path, option_name="--schema-file")


def test_draft_options_route_source_requires_an_incoming_step() -> None:
    with pytest.raises(typer.BadParameter, match="--from-outcome requires --from-step"):
        route_source(None, "error")

    incoming = route_source("lookup", None)
    assert incoming is not None
    assert incoming.step_id == "lookup"
    assert incoming.outcome == "ok"


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


def test_wf_draft_create_help_accepts_capability_option() -> None:
    result = runner.invoke(app, ["draft", "create", "--help"])

    assert result.exit_code == 0
    output = " ".join(result.output.split())
    assert "--capability" in output
    assert "--name" in output
    assert "--title" in output
    assert "--input-schema-file" in output
    assert "--state-schema-file" in output
    assert "--output-schema-file" in output
    assert "--outcome" in output


def test_wf_draft_lifecycle_command_help() -> None:
    set_start = runner.invoke(app, ["draft", "set-start", "--help"])
    set_contract = runner.invoke(app, ["draft", "set-contract", "--help"])

    assert set_start.exit_code == 0
    assert "--revision" in set_start.output
    assert "--step" in set_start.output
    assert set_contract.exit_code == 0
    assert "--revision" in set_contract.output
    assert "--input-schema-file" in set_contract.output
    assert "--state-schema-file" in set_contract.output
    assert "--output-schema-file" in set_contract.output
    assert "--outcome" in set_contract.output


def test_wf_draft_lifecycle_commands_dispatch_exact_fields(
    monkeypatch,
    tmp_path,
) -> None:
    calls: list[tuple[str, dict[str, Any]]] = []

    class FakeHandlers:
        async def create_empty_draft_workspace(self, **kwargs: Any) -> dict[str, Any]:
            calls.append(("create_empty", kwargs))
            return {"revision": 1, "status": "invalid"}

        async def create_draft_workspace_from_capability(
            self, **kwargs: Any
        ) -> dict[str, Any]:
            calls.append(("create_capability", kwargs))
            return {"revision": 1, "status": "valid"}

        async def set_draft_start(self, **kwargs: Any) -> dict[str, Any]:
            calls.append(("set_start", kwargs))
            return {"revision": 2, "status": "invalid"}

        async def set_draft_contract(self, **kwargs: Any) -> dict[str, Any]:
            calls.append(("set_contract", kwargs))
            return {"revision": 3, "status": "invalid"}

    context = SimpleNamespace(handlers=FakeHandlers(), verbose=False)
    monkeypatch.setattr(
        "wf_cli.commands.drafts.load_cli_context",
        lambda _ctx: context,
    )
    input_schema = tmp_path / "input.json"
    state_schema = tmp_path / "state.json"
    output_schema = tmp_path / "output.json"
    input_schema.write_text('{"type":"object","properties":{}}', encoding="utf-8")
    state_schema.write_text(
        '{"type":"object","properties":{"items":{"type":"array",'
        '"reducer":"wf.std.append"}}}',
        encoding="utf-8",
    )
    output_schema.write_text(
        '{"type":"object","properties":{"result":{"type":"string"}}}',
        encoding="utf-8",
    )

    empty = runner.invoke(
        app,
        [
            "draft",
            "create",
            "control_ws",
            "--name",
            "control",
            "--title",
            "Control",
            "--input-schema-file",
            str(input_schema),
            "--state-schema-file",
            str(state_schema),
            "--output-schema-file",
            str(output_schema),
            "--outcome",
            "submitted",
            "--outcome",
            "cancelled",
        ],
    )
    capability = runner.invoke(
        app,
        [
            "draft",
            "create",
            "capability_ws",
            "--capability",
            "wf.std.constant",
            "--name",
            "constant",
        ],
    )
    started = runner.invoke(
        app,
        [
            "draft",
            "set-start",
            "control_ws",
            "--revision",
            "1",
            "--step",
            "gate",
        ],
    )
    contracted = runner.invoke(
        app,
        [
            "draft",
            "set-contract",
            "control_ws",
            "--revision",
            "2",
            "--state-schema-file",
            str(state_schema),
            "--outcome",
            "submitted",
            "--outcome",
            "cancelled",
        ],
    )

    assert empty.exit_code == 0, empty.output
    assert capability.exit_code == 0, capability.output
    assert started.exit_code == 0, started.output
    assert contracted.exit_code == 0, contracted.output
    assert calls == [
        (
            "create_empty",
            {
                "workspace_id": "control_ws",
                "name": "control",
                "title": "Control",
                "input_schema": {"type": "object", "properties": {}},
                "state_schema": {
                    "type": "object",
                    "properties": {
                        "items": {
                            "type": "array",
                            "reducer": "wf.std.append",
                        }
                    },
                },
                "output_schema": {
                    "type": "object",
                    "properties": {"result": {"type": "string"}},
                },
                "outcomes": ("submitted", "cancelled"),
            },
        ),
        (
            "create_capability",
            {
                "workspace_id": "capability_ws",
                "capability_name": "wf.std.constant",
                "name": "constant",
                "title": None,
            },
        ),
        (
            "set_start",
            {"workspace_id": "control_ws", "revision": 1, "step_id": "gate"},
        ),
        (
            "set_contract",
            {
                "workspace_id": "control_ws",
                "revision": 2,
                "input_schema": None,
                "state_schema": {
                    "type": "object",
                    "properties": {
                        "items": {
                            "type": "array",
                            "reducer": "wf.std.append",
                        }
                    },
                },
                "output_schema": None,
                "outcomes": ("submitted", "cancelled"),
            },
        ),
    ]


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        (["draft", "create", "ws"], "--name is required"),
        (
            [
                "draft",
                "create",
                "ws",
                "--capability",
                "wf.std.constant",
                "--outcome",
                "ok",
            ],
            "only valid without --capability",
        ),
        (
            ["draft", "set-contract", "ws", "--revision", "1"],
            "requires at least one contract field",
        ),
        (
            [
                "draft",
                "create",
                "ws",
                "--name",
                "ws",
                "--outcome",
                "ok",
                "--outcome",
                "ok",
            ],
            "outcomes must be unique",
        ),
        (
            [
                "draft",
                "set-contract",
                "ws",
                "--revision",
                "1",
                "--outcome",
                "",
            ],
            "outcomes must not be blank",
        ),
    ],
)
def test_wf_draft_lifecycle_rejects_invalid_options_before_loading_context(
    monkeypatch,
    arguments: list[str],
    message: str,
) -> None:
    monkeypatch.setattr(
        "wf_cli.commands.drafts.load_cli_context",
        lambda _ctx: (_ for _ in ()).throw(AssertionError("context loaded")),
    )

    result = runner.invoke(app, arguments)

    assert result.exit_code != 0
    assert message in result.output
    assert "context loaded" not in result.output


@pytest.mark.parametrize("value", ["[1]", '"schema"', "null"])
def test_wf_draft_create_rejects_non_object_schema_files(
    monkeypatch,
    tmp_path,
    value: str,
) -> None:
    schema = tmp_path / "schema.json"
    schema.write_text(value, encoding="utf-8")
    monkeypatch.setattr(
        "wf_cli.commands.drafts.load_cli_context",
        lambda _ctx: (_ for _ in ()).throw(AssertionError("context loaded")),
    )

    result = runner.invoke(
        app,
        [
            "draft",
            "create",
            "ws",
            "--name",
            "ws",
            "--input-schema-file",
            str(schema),
        ],
    )

    assert result.exit_code != 0
    assert "--input-schema-file: expected a JSON object" in result.output
    assert "context loaded" not in result.output


def test_wf_draft_create_rejects_malformed_schema_file(
    monkeypatch,
    tmp_path,
) -> None:
    schema = tmp_path / "schema.json"
    schema.write_text("{", encoding="utf-8")
    monkeypatch.setattr(
        "wf_cli.commands.drafts.load_cli_context",
        lambda _ctx: (_ for _ in ()).throw(AssertionError("context loaded")),
    )

    result = runner.invoke(
        app,
        [
            "draft",
            "create",
            "ws",
            "--name",
            "ws",
            "--input-schema-file",
            str(schema),
        ],
    )

    assert result.exit_code != 0
    assert "--input-schema-file: invalid JSON" in result.output
    assert "context loaded" not in result.output


def test_wf_draft_help_does_not_list_old_create_from_capability() -> None:
    result = runner.invoke(app, ["draft", "--help"])

    assert result.exit_code == 0
    assert "create-from-capability" not in result.output


def test_wf_draft_add_help_lists_typed_step_commands_and_removes_flat_command() -> None:
    result = runner.invoke(app, ["draft", "add", "--help"])

    assert result.exit_code == 0
    for name in (
        "capability",
        "interrupt",
        "foreach",
        "join",
        "end",
        "when",
        "choose",
        "match",
        "subgraph",
    ):
        assert name in result.output

    removed = runner.invoke(app, ["draft", "add-step", "--help"])
    assert removed.exit_code != 0


def test_wf_draft_map_help_explains_replace_merge_and_validate() -> None:
    input_result = runner.invoke(app, ["draft", "set-input", "--help"])
    output_result = runner.invoke(app, ["draft", "set-output", "--help"])
    workflow_output_result = runner.invoke(
        app, ["draft", "set-workflow-output", "--help"]
    )

    assert input_result.exit_code == 0
    assert output_result.exit_code == 0
    assert workflow_output_result.exit_code == 0
    input_help = " ".join(input_result.output.split())
    output_help = " ".join(output_result.output.split())
    workflow_output_help = " ".join(workflow_output_result.output.split())
    assert "replaces the full input map" in input_help
    assert "Use --merge only" in input_help
    assert "draft validate" in input_help
    assert "input.text=text" in input_help
    assert "input.text=local.text" in input_help
    assert "input.title=report.title" in input_help
    assert "replaces the full output map" in output_help
    assert "Use --merge only" in output_help
    assert "draft validate" in output_help
    assert "replaces the full workflow output map" in workflow_output_help
    assert "Use --merge only" in workflow_output_help
    assert "GRAPH_SOURCE=OUTPUT_FIELD" in workflow_output_help
    assert "output_schema fields are projected" in workflow_output_help
    assert "draft validate" in workflow_output_help


def test_wf_draft_bind_help_explains_direction() -> None:
    result = runner.invoke(app, ["draft", "bind", "--help"])

    assert result.exit_code == 0
    help_text = " ".join(result.output.split())
    assert "--from" in help_text
    assert "--to" in help_text
    assert "validate" in help_text
    assert "project missing schema" in help_text
    assert "set-input --merge" in help_text
    assert "local.report.title" in help_text


def test_wf_draft_add_capability_help_explains_explicit_wiring() -> None:
    result = runner.invoke(app, ["draft", "add", "capability", "--help"])

    assert result.exit_code == 0
    output = " ".join(result.output.split())
    assert "--capability" in output
    assert "--from-step" in output
    assert "--bind-output" in output
    assert "does not guess" in output
    assert "projects its schemas and bindings" in output
    assert "draft validate" in output
    assert "wf draft add capability report_ws" in output
    assert "Repeat the flag" in output
    assert "--input state.title=report.title" in output
    assert (
        "--bind-output title=state.title --bind-output summary=state.summary" in output
    )


def test_wf_draft_add_capability_calls_composed_local_handler(monkeypatch) -> None:
    calls: list[dict[str, Any]] = []

    class FakeHandlers:
        async def add_step_from_capability(self, **kwargs: Any) -> dict[str, Any]:
            calls.append(kwargs)
            return {"revision": 2, "status": "valid"}

    context = SimpleNamespace(handlers=FakeHandlers(), verbose=False)
    monkeypatch.setattr(
        "wf_cli.commands.draft_add.load_cli_context", lambda _ctx: context
    )

    result = runner.invoke(
        app,
        [
            "draft",
            "add",
            "capability",
            "workspace",
            "--revision",
            "1",
            "--step",
            "call",
            "--capability",
            "demo.call",
            "--from-step",
            "start",
            "--route",
            "ok=__end__",
            "--input",
            "input.text=report.text",
            "--bind-output",
            "value=state.value",
        ],
    )

    assert result.exit_code == 0, result.output
    call = calls[0]
    assert call["workspace_id"] == "workspace"
    assert call["revision"] == 1
    assert call["step_id"] == "call"
    assert call["capability_name"] == "demo.call"
    assert call["route_from_step"] == "start"
    assert call["route_from_outcome"] == "ok"
    assert call["routes"] == {"ok": "__end__"}
    assert call["input_map"] == {"input.text": "report.text"}
    assert call["bind_outputs"] == {"value": "state.value"}


def test_wf_draft_add_interrupt_builds_typed_contract(monkeypatch, tmp_path) -> None:
    calls: list[dict[str, Any]] = []

    class FakeHandlers:
        async def add_step(self, **kwargs: Any) -> dict[str, Any]:
            calls.append(kwargs)
            return {"revision": 2, "status": "valid"}

    request_schema = tmp_path / "request.json"
    request_schema.write_text(
        '{"type":"object","properties":{"issues":{"type":"array"}}}',
        encoding="utf-8",
    )
    resume_schema = tmp_path / "resume.json"
    resume_schema.write_text(
        '{"type":"object","properties":{"selected":{"type":"array"}}}',
        encoding="utf-8",
    )
    context = SimpleNamespace(handlers=FakeHandlers(), verbose=False)
    monkeypatch.setattr(
        "wf_cli.commands.draft_add.load_cli_context", lambda _ctx: context
    )

    result = runner.invoke(
        app,
        [
            "draft",
            "add",
            "interrupt",
            "workspace",
            "--revision",
            "1",
            "--step",
            "review",
            "--kind",
            "issue_review",
            "--from-step",
            "draft_issues",
            "--request-schema-file",
            str(request_schema),
            "--resume-schema-file",
            str(resume_schema),
            "--request",
            "state.issues=issues",
            "--resume",
            "selected=state.selected",
            "--outcome",
            "submitted",
            "--outcome",
            "cancelled",
            "--route",
            "submitted=create_issues",
            "--route",
            "cancelled=revise",
        ],
    )

    assert result.exit_code == 0, result.output
    call = calls[0]
    assert call["workspace_id"] == "workspace"
    assert call["incoming"].step_id == "draft_issues"
    assert call["incoming"].outcome == "ok"
    assert call["routes"] == {
        "submitted": "create_issues",
        "cancelled": "revise",
    }
    assert call["step"].model_dump(mode="json", by_alias=True) == {
        "interrupt": {
            "kind": "issue_review",
            "request": [{"target": "issues", "path": "state.issues"}],
            "resume": [{"source": "selected", "target": "state.selected"}],
            "request_schema": {
                "type": "object",
                "properties": {"issues": {"type": "array"}},
                "required": [],
            },
            "resume_schema": {
                "type": "object",
                "properties": {"selected": {"type": "array"}},
                "required": [],
            },
            "outcomes": ["submitted", "cancelled"],
        }
    }


def test_wf_draft_add_foreach_builds_concurrent_policy(monkeypatch) -> None:
    calls: list[dict[str, Any]] = []

    class FakeHandlers:
        async def add_step(self, **kwargs: Any) -> dict[str, Any]:
            calls.append(kwargs)
            return {"revision": 2, "status": "valid"}

    context = SimpleNamespace(handlers=FakeHandlers(), verbose=False)
    monkeypatch.setattr(
        "wf_cli.commands.draft_add.load_cli_context", lambda _ctx: context
    )

    result = runner.invoke(
        app,
        [
            "draft",
            "add",
            "foreach",
            "workspace",
            "--revision",
            "1",
            "--step",
            "each_issue",
            "--over",
            "state.issues",
            "--as",
            "issue",
            "--mode",
            "concurrent",
            "--item-error",
            "collect",
            "--collect-to",
            "state.errors",
            "--max-active",
            "2",
            "--max-outstanding",
            "5",
            "--route",
            "loop=process_issue",
            "--route",
            "done=finish",
            "--route",
            "completed_with_errors=finish",
        ],
    )

    assert result.exit_code == 0, result.output
    call = calls[0]
    assert call["step"].model_dump(mode="json", by_alias=True) == {
        "foreach": {
            "over": "state.issues",
            "as": "issue",
            "mode": "concurrent",
            "item_error": {"action": "collect", "collect_to": "state.errors"},
            "concurrent": {
                "max_active": 2,
                "max_outstanding": 5,
                "interrupt": "quiesce",
            },
        }
    }
    assert call["routes"] == {
        "loop": "process_issue",
        "done": "finish",
        "completed_with_errors": "finish",
    }

    defaults_result = runner.invoke(
        app,
        [
            "draft",
            "add",
            "foreach",
            "workspace",
            "--revision",
            "2",
            "--step",
            "each_default",
            "--over",
            "state.issues",
            "--as",
            "issue",
            "--mode",
            "concurrent",
        ],
    )
    assert defaults_result.exit_code == 0, defaults_result.output
    assert calls[1]["step"].foreach.concurrent is not None
    assert calls[1]["step"].foreach.concurrent.max_active == 4
    assert calls[1]["step"].foreach.concurrent.max_outstanding == 20


def test_wf_draft_add_join_and_end_build_concrete_steps(monkeypatch) -> None:
    calls: list[dict[str, Any]] = []

    class FakeHandlers:
        async def add_step(self, **kwargs: Any) -> dict[str, Any]:
            calls.append(kwargs)
            return {"revision": len(calls) + 1, "status": "valid"}

    context = SimpleNamespace(handlers=FakeHandlers(), verbose=False)
    monkeypatch.setattr(
        "wf_cli.commands.draft_add.load_cli_context", lambda _ctx: context
    )

    join_result = runner.invoke(
        app,
        [
            "draft",
            "add",
            "join",
            "workspace",
            "--revision",
            "1",
            "--step",
            "joined",
            "--from-step",
            "each_issue",
            "--from-outcome",
            "done",
            "--route",
            "done=finish",
        ],
    )
    end_result = runner.invoke(
        app,
        [
            "draft",
            "add",
            "end",
            "workspace",
            "--revision",
            "2",
            "--step",
            "finish",
            "--outcome",
            "completed",
        ],
    )

    assert join_result.exit_code == 0, join_result.output
    assert end_result.exit_code == 0, end_result.output
    assert calls[0]["step"].model_dump(mode="json") == {"join": {}}
    assert calls[0]["routes"] == {"done": "finish"}
    assert calls[1]["step"].model_dump(mode="json") == {"end": {"outcome": "completed"}}
    assert calls[1]["routes"] is None


def test_wf_draft_add_control_commands_reject_invalid_input_before_api_call(
    monkeypatch, tmp_path
) -> None:
    calls: list[dict[str, Any]] = []

    class FakeHandlers:
        async def add_step(self, **kwargs: Any) -> dict[str, Any]:
            calls.append(kwargs)
            return {}

    context = SimpleNamespace(handlers=FakeHandlers(), verbose=False)
    monkeypatch.setattr(
        "wf_cli.commands.draft_add.load_cli_context", lambda _ctx: context
    )
    malformed_schema = tmp_path / "bad.json"
    malformed_schema.write_text("{", encoding="utf-8")

    malformed = runner.invoke(
        app,
        [
            "draft",
            "add",
            "interrupt",
            "ws",
            "--revision",
            "1",
            "--step",
            "review",
            "--kind",
            "review",
            "--request-schema-file",
            str(malformed_schema),
        ],
    )
    serial_limits = runner.invoke(
        app,
        [
            "draft",
            "add",
            "foreach",
            "ws",
            "--revision",
            "1",
            "--step",
            "each",
            "--over",
            "state.items",
            "--as",
            "item",
            "--max-active",
            "2",
        ],
    )
    duplicate_request = runner.invoke(
        app,
        [
            "draft",
            "add",
            "interrupt",
            "ws",
            "--revision",
            "1",
            "--step",
            "review",
            "--kind",
            "review",
            "--request",
            "state.items=items",
            "--request",
            "state.items=other_items",
        ],
    )
    duplicate_resume = runner.invoke(
        app,
        [
            "draft",
            "add",
            "interrupt",
            "ws",
            "--revision",
            "1",
            "--step",
            "review",
            "--kind",
            "review",
            "--resume",
            "decision=state.decision",
            "--resume",
            "decision=state.other_decision",
        ],
    )
    missing_collect_target = runner.invoke(
        app,
        [
            "draft",
            "add",
            "foreach",
            "ws",
            "--revision",
            "1",
            "--step",
            "each",
            "--over",
            "state.items",
            "--as",
            "item",
            "--item-error",
            "collect",
        ],
    )
    end_route = runner.invoke(
        app,
        [
            "draft",
            "add",
            "end",
            "ws",
            "--revision",
            "1",
            "--step",
            "finish",
            "--route",
            "ok=__end__",
        ],
    )

    assert malformed.exit_code == 2
    assert "invalid JSON" in malformed.output
    assert "Traceback" not in malformed.output
    assert serial_limits.exit_code == 2
    assert "concurrent" in serial_limits.output
    assert "Traceback" not in serial_limits.output
    assert duplicate_request.exit_code == 2
    assert "duplicate --request" in duplicate_request.output
    assert "Traceback" not in duplicate_request.output
    assert duplicate_resume.exit_code == 2
    assert "duplicate --resume" in duplicate_resume.output
    assert "--bind-output" not in duplicate_resume.output
    assert "Traceback" not in duplicate_resume.output
    assert missing_collect_target.exit_code == 2
    assert (
        "collect item error policy requires collect_to" in missing_collect_target.output
    )
    assert "Traceback" not in missing_collect_target.output
    assert end_route.exit_code == 2
    assert "No such option" in end_route.output
    assert "--route" in end_route.output
    assert calls == []


def test_wf_draft_add_control_command_help_is_type_specific() -> None:
    interrupt = runner.invoke(app, ["draft", "add", "interrupt", "--help"])
    foreach = runner.invoke(app, ["draft", "add", "foreach", "--help"])
    join = runner.invoke(app, ["draft", "add", "join", "--help"])
    end = runner.invoke(app, ["draft", "add", "end", "--help"])

    assert (
        interrupt.exit_code == foreach.exit_code == join.exit_code == end.exit_code == 0
    )
    assert "--request-schema-file" in interrupt.output
    assert "--resume-schema-file" in interrupt.output
    assert "--request" in interrupt.output
    assert "--resume" in interrupt.output
    assert "--outcome" in interrupt.output
    assert "--max-active" not in interrupt.output
    assert "--mode" in foreach.output
    assert "--max-active" in foreach.output
    assert "--max-outstanding" in foreach.output
    assert "--item-error" in foreach.output
    assert "--collect-to" in foreach.output
    assert "--request-schema-file" not in foreach.output
    assert "--from-step" in join.output
    assert "--route" in join.output
    assert "--request-schema-file" not in join.output
    assert "--outcome" in end.output
    assert "--route" not in end.output


def test_wf_draft_add_decisions_build_ordered_typed_steps(
    monkeypatch, tmp_path
) -> None:
    calls: list[dict[str, Any]] = []

    class FakeHandlers:
        async def add_step(self, **kwargs: Any) -> dict[str, Any]:
            calls.append(kwargs)
            return {"revision": len(calls) + 1, "status": "valid"}

    context = SimpleNamespace(handlers=FakeHandlers(), verbose=False)
    monkeypatch.setattr(
        "wf_cli.commands.draft_add.load_cli_context", lambda _ctx: context
    )
    condition_file = tmp_path / "condition.json"
    condition_file.write_text('{"op":"exists","path":"state.report"}', encoding="utf-8")
    clauses_file = tmp_path / "clauses.json"
    clauses_file.write_text(
        '[{"if":{"op":"exists","path":"state.report"},"then":"publish"},'
        '{"if":{"op":"exists","path":"state.error"},"then":"revise"}]',
        encoding="utf-8",
    )
    cases_file = tmp_path / "cases.json"
    cases_file.write_text(
        '[{"equals":"ready","then":"publish"},{"equals":2,"then":"retry"},'
        '{"equals":true,"then":"approve"},{"equals":null,"then":"revise"}]',
        encoding="utf-8",
    )

    invocations = [
        [
            "when",
            "--condition-file",
            str(condition_file),
            "--then",
            "publish",
            "--otherwise",
            "revise",
        ],
        [
            "choose",
            "--clauses-file",
            str(clauses_file),
            "--default",
            "__end__",
        ],
        [
            "match",
            "--value",
            "state.status",
            "--cases-file",
            str(cases_file),
            "--default",
            "__end__",
        ],
    ]
    for revision, invocation in enumerate(invocations, start=1):
        result = runner.invoke(
            app,
            [
                "draft",
                "add",
                *invocation[:1],
                "workspace",
                "--revision",
                str(revision),
                "--step",
                invocation[0],
                "--from-step",
                "start",
                "--from-outcome",
                "ok",
                *invocation[1:],
            ],
        )
        assert result.exit_code == 0, result.output

    assert calls[0]["step"].model_dump(mode="json", by_alias=True) == {
        "when": {
            "if": {"op": "exists", "path": "state.report"},
            "then": "publish",
            "otherwise": "revise",
        }
    }
    assert calls[1]["step"].model_dump(mode="json", by_alias=True) == {
        "choose": {
            "clauses": [
                {
                    "if": {"op": "exists", "path": "state.report"},
                    "then": "publish",
                },
                {
                    "if": {"op": "exists", "path": "state.error"},
                    "then": "revise",
                },
            ],
            "default": "__end__",
        }
    }
    assert calls[2]["step"].model_dump(mode="json", by_alias=True) == {
        "match": {
            "value": "state.status",
            "cases": [
                {"equals": "ready", "then": "publish"},
                {"equals": 2, "then": "retry"},
                {"equals": True, "then": "approve"},
                {"equals": None, "then": "revise"},
            ],
            "default": "__end__",
        }
    }
    assert all(call["routes"] is None for call in calls)
    assert all(call["incoming"].step_id == "start" for call in calls)


def test_wf_draft_add_decisions_reject_bad_files_and_generic_routes(
    monkeypatch, tmp_path
) -> None:
    calls: list[dict[str, Any]] = []

    class FakeHandlers:
        async def add_step(self, **kwargs: Any) -> dict[str, Any]:
            calls.append(kwargs)
            return {}

    context = SimpleNamespace(handlers=FakeHandlers(), verbose=False)
    monkeypatch.setattr(
        "wf_cli.commands.draft_add.load_cli_context", lambda _ctx: context
    )
    empty_clauses = tmp_path / "empty.json"
    empty_clauses.write_text("[]", encoding="utf-8")
    object_cases = tmp_path / "object.json"
    object_cases.write_text("{}", encoding="utf-8")
    condition_file = tmp_path / "condition.json"
    condition_file.write_text('{"op":"exists","path":"state.report"}', encoding="utf-8")

    empty = runner.invoke(
        app,
        [
            "draft",
            "add",
            "choose",
            "ws",
            "--revision",
            "1",
            "--step",
            "choose",
            "--clauses-file",
            str(empty_clauses),
        ],
    )
    non_array = runner.invoke(
        app,
        [
            "draft",
            "add",
            "match",
            "ws",
            "--revision",
            "1",
            "--step",
            "match",
            "--value",
            "state.status",
            "--cases-file",
            str(object_cases),
        ],
    )
    generic_route = runner.invoke(
        app,
        [
            "draft",
            "add",
            "when",
            "ws",
            "--revision",
            "1",
            "--step",
            "when",
            "--condition-file",
            str(condition_file),
            "--then",
            "yes",
            "--route",
            "true=yes",
        ],
    )

    assert empty.exit_code == 2
    assert "Traceback" not in empty.output
    assert non_array.exit_code == 2
    assert "Traceback" not in non_array.output
    assert generic_route.exit_code == 2
    assert "--route" in generic_route.output
    assert calls == []


def test_wf_draft_add_subgraph_builds_name_and_artifact_contracts(
    monkeypatch, tmp_path
) -> None:
    calls: list[dict[str, Any]] = []

    class FakeHandlers:
        async def add_step(self, **kwargs: Any) -> dict[str, Any]:
            calls.append(kwargs)
            return {"revision": len(calls) + 1, "status": "valid"}

    context = SimpleNamespace(handlers=FakeHandlers(), verbose=False)
    monkeypatch.setattr(
        "wf_cli.commands.draft_add.load_cli_context", lambda _ctx: context
    )
    input_schema = tmp_path / "input.json"
    input_schema.write_text(
        '{"type":"object","properties":{"topic":{"type":"string"}}}',
        encoding="utf-8",
    )
    output_schema = tmp_path / "output.json"
    output_schema.write_text(
        '{"type":"object","properties":{"report":{"type":"string"}}}',
        encoding="utf-8",
    )

    named = runner.invoke(
        app,
        [
            "draft",
            "add",
            "subgraph",
            "workspace",
            "--revision",
            "1",
            "--step",
            "child",
            "--workflow-name",
            "child_workflow",
            "--description",
            "Generate the child report.",
            "--input-schema-file",
            str(input_schema),
            "--output-schema-file",
            str(output_schema),
            "--input",
            "state.topic=topic",
            "--bind-output",
            "report=state.report",
            "--outcome",
            "ok",
            "--outcome",
            "error",
            "--route",
            "ok=publish",
            "--route",
            "error=revise",
        ],
    )
    artifact = runner.invoke(
        app,
        [
            "draft",
            "add",
            "subgraph",
            "workspace",
            "--revision",
            "2",
            "--step",
            "saved_child",
            "--artifact-id",
            "child_report",
            "--artifact-version",
            "2",
        ],
    )

    assert named.exit_code == 0, named.output
    assert artifact.exit_code == 0, artifact.output
    named_payload = calls[0]["step"].model_dump(mode="json", by_alias=True)["subgraph"]
    assert named_payload["workflow"] == {"name": "child_workflow"}
    assert named_payload["desc"] == "Generate the child report."
    assert named_payload["input_schema"]["properties"] == {"topic": {"type": "string"}}
    assert named_payload["output_schema"]["properties"] == {
        "report": {"type": "string"}
    }
    assert named_payload["input"] == [{"target": "topic", "path": "state.topic"}]
    assert named_payload["output"] == [{"source": "report", "target": "state.report"}]
    assert named_payload["outcomes"] == ["ok", "error"]
    assert calls[0]["routes"] == {"ok": "publish", "error": "revise"}
    artifact_payload = calls[1]["step"].model_dump(mode="json", by_alias=True)[
        "subgraph"
    ]
    assert artifact_payload["workflow"] == {
        "artifact_id": "child_report",
        "version": 2,
    }
    assert artifact_payload["outcomes"] == ["ok"]


def test_wf_draft_add_subgraph_rejects_invalid_reference_combinations(
    monkeypatch,
) -> None:
    calls: list[dict[str, Any]] = []

    class FakeHandlers:
        async def add_step(self, **kwargs: Any) -> dict[str, Any]:
            calls.append(kwargs)
            return {}

    context = SimpleNamespace(handlers=FakeHandlers(), verbose=False)
    monkeypatch.setattr(
        "wf_cli.commands.draft_add.load_cli_context", lambda _ctx: context
    )
    invalid_refs = [
        [],
        ["--workflow-name", " "],
        [
            "--workflow-name",
            "child",
            "--artifact-id",
            "saved",
            "--artifact-version",
            "1",
        ],
        ["--artifact-id", "saved"],
        ["--artifact-version", "1"],
    ]

    for ref_args in invalid_refs:
        result = runner.invoke(
            app,
            [
                "draft",
                "add",
                "subgraph",
                "workspace",
                "--revision",
                "1",
                "--step",
                "child",
                *ref_args,
            ],
        )
        assert result.exit_code == 2
        assert "Traceback" not in result.output

    assert calls == []


def test_wf_draft_add_decision_and_subgraph_help_is_type_specific() -> None:
    when = runner.invoke(app, ["draft", "add", "when", "--help"])
    choose = runner.invoke(app, ["draft", "add", "choose", "--help"])
    match = runner.invoke(app, ["draft", "add", "match", "--help"])
    subgraph = runner.invoke(app, ["draft", "add", "subgraph", "--help"])

    assert (
        when.exit_code == choose.exit_code == match.exit_code == subgraph.exit_code == 0
    )
    assert "--condition-file" in when.output
    assert "--then" in when.output
    assert "--route" not in when.output
    assert "--clauses-file" in choose.output
    assert "--default" in choose.output
    assert "--route" not in choose.output
    assert "--value" in match.output
    assert "--cases-file" in match.output
    assert "--route" not in match.output
    assert "--workflow-name" in subgraph.output
    assert "--artifact-id" in subgraph.output
    assert "--artifact-version" in subgraph.output
    assert "--input-schema-file" in subgraph.output
    assert "--output-schema-file" in subgraph.output
    assert "--route" in subgraph.output

    for result in (when, choose, match, subgraph):
        assert "Example:" in result.output
        assert "draft validate WS" in result.output


def test_wf_draft_help_does_not_list_old_add_step_from_capability() -> None:
    result = runner.invoke(app, ["draft", "--help"])

    assert result.exit_code == 0
    assert "add-step-from-capability" not in result.output


def test_wf_draft_remove_commands_help_mentions_options() -> None:
    route_result = runner.invoke(app, ["draft", "remove-route", "--help"])
    step_result = runner.invoke(app, ["draft", "remove-step", "--help"])
    binding_result = runner.invoke(app, ["draft", "remove-binding", "--help"])

    assert route_result.exit_code == 0
    assert "--step" in route_result.output
    assert "--outcome" in route_result.output
    assert step_result.exit_code == 0
    assert "--step" in step_result.output
    assert binding_result.exit_code == 0
    assert "--input" in binding_result.output
    assert "--output" in binding_result.output
    assert "status: invalid" in binding_result.output


def test_wf_draft_route_flags_reject_duplicate_outcomes() -> None:
    add_result = runner.invoke(
        app,
        [
            "draft",
            "add",
            "capability",
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


def test_wf_run_resume_help_exists() -> None:
    result = runner.invoke(app, ["run", "resume", "--help"])

    assert result.exit_code == 0
    assert "resume payload" in result.output.lower()
    assert "schema" in result.output.lower()


def test_wf_draft_set_input_rejects_local_prefixed_target() -> None:
    result = runner.invoke(
        app,
        [
            "draft",
            "set-input",
            "report_ws",
            "--revision",
            "1",
            "--step",
            "render",
            "--map",
            "input.text=local.text",
        ],
    )

    assert result.exit_code == 2
    output = " ".join(result.output.split())
    assert "rootless node-local path" in output
    assert "input.text=text" in output
    assert "input.text=local.text" in output


def test_wf_draft_set_input_accepts_nested_rootless_target(monkeypatch) -> None:
    calls: list[dict[str, Any]] = []

    class FakeHandlers:
        async def set_step_input_map(self, **kwargs: Any) -> dict[str, Any]:
            calls.append(kwargs)
            return {"revision": 2, "status": "valid"}

    context = SimpleNamespace(handlers=FakeHandlers(), verbose=False)
    monkeypatch.setattr("wf_cli.commands.drafts.load_cli_context", lambda _ctx: context)

    result = runner.invoke(
        app,
        [
            "draft",
            "set-input",
            "report_ws",
            "--revision",
            "1",
            "--step",
            "render",
            "--map",
            "input.title=report.title",
        ],
    )

    assert result.exit_code == 0, result.output
    assert calls[0]["input_map"] == {"input.title": "report.title"}


def test_wf_draft_set_input_rejects_malformed_local_path(monkeypatch) -> None:
    monkeypatch.setattr(
        "wf_cli.commands.drafts.load_cli_context",
        lambda _ctx: (_ for _ in ()).throw(AssertionError("context loaded")),
    )

    result = runner.invoke(
        app,
        [
            "draft",
            "set-input",
            "report_ws",
            "--revision",
            "1",
            "--step",
            "render",
            "--map",
            "input.title=report..title",
        ],
    )

    assert result.exit_code == 2
    assert "rootless node-local path" in result.output
    assert "context loaded" not in result.output
