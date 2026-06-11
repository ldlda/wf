from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

from typer import Context as TyperContext
from typer.testing import CliRunner

from tests.wf_mcp.test_support import echo_tool, input_binding
from tests.wf_mcp.workflow_surface.conftest import echo_artifact
from wf_artifacts import FileWorkflowArtifactStore, WorkflowArtifact, WorkflowDeployment
from wf_cli.app import app
from wf_cli.context import CliContext, config_path_from_context, load_cli_context

runner = CliRunner()


class PendingRunHandlers:
    async def inspect_run(self, *, run_id: str) -> dict[str, Any]:
        return {"run_id": run_id, "status": "running"}


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


def _seed_interrupt_deployment(root: Path) -> Path:
    config_path = _write_config(root)
    store_root = root / ".wf_mcp_store"
    artifact_store = FileWorkflowArtifactStore(store_root)
    artifact_store.save_artifact(_interrupt_artifact())
    artifact_store.save_deployment(
        WorkflowDeployment(
            id="approval.personal",
            artifact_id="approval",
            artifact_version=1,
            bindings=[],
        )
    )
    return config_path


def test_wf_deploy_validate_outputs_json(tmp_path: Path) -> None:
    root = tmp_path / "wf_cli_deploy_validate"
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


def test_wf_run_start_accepts_inline_json_input(tmp_path: Path) -> None:
    root = tmp_path / "wf_cli_run_start"
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


def test_wf_run_start_accepts_input_file(tmp_path: Path) -> None:
    root = tmp_path / "wf_cli_run_start_file"
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


def test_wf_run_inspect_and_trace_existing_run(tmp_path: Path) -> None:
    root = tmp_path / "wf_cli_run_inspect_trace"
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


def test_wf_run_watch_outputs_terminal_run_summary(tmp_path: Path) -> None:
    root = tmp_path / "wf_cli_run_watch_completed"
    root.mkdir()
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

        watched = runner.invoke(
            app,
            [
                "--config",
                str(config_path),
                "run",
                "watch",
                run_id,
                "--interval",
                "0",
            ],
        )

    assert watched.exit_code == 0, watched.output
    payload = json.loads(watched.output)
    assert payload["run_id"] == run_id
    assert payload["status"] == "completed"
    assert payload["outcome"] == "ok"


def test_wf_run_watch_stops_on_interrupted_run(tmp_path: Path) -> None:
    root = tmp_path / "wf_cli_run_watch_interrupted"
    root.mkdir()
    config_path = _seed_interrupt_deployment(root)

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
                "approval.personal",
                "--input",
                '{"message": "send?"}',
            ],
        )
        run_id = json.loads(start.output)["run_id"]

        watched = runner.invoke(
            app,
            [
                "--config",
                str(config_path),
                "run",
                "watch",
                run_id,
                "--interval",
                "0",
            ],
        )

    assert watched.exit_code == 0, watched.output
    payload = json.loads(watched.output)
    assert payload["run_id"] == run_id
    assert payload["status"] == "interrupted"
    assert payload["resume_readiness"] == "ready"


def test_wf_run_watch_can_include_trace_slice(tmp_path: Path) -> None:
    root = tmp_path / "wf_cli_run_watch_trace"
    root.mkdir()
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

        watched = runner.invoke(
            app,
            [
                "--config",
                str(config_path),
                "run",
                "watch",
                run_id,
                "--interval",
                "0",
                "--trace",
                "--trace-limit",
                "1",
            ],
        )

    assert watched.exit_code == 0, watched.output
    payload = json.loads(watched.output)
    assert payload["run_id"] == run_id
    assert payload["status"] == "completed"
    assert payload["outcome"] == "ok"
    assert payload["trace_limit"] == 1
    assert payload["trace"][0]["node_id"] == "echo"


def test_wf_run_watch_times_out_for_unstopped_run() -> None:
    fake_context = CliContext(
        config_path=Path("dummy"),
        service=None,
        handlers=cast(Any, PendingRunHandlers()),
        source_admin=cast(Any, None),
        admin=cast(Any, None),
    )

    with patch(
        "wf_cli.commands.runs.load_cli_context_from_typer",
        lambda _ctx: fake_context,
    ):
        result = runner.invoke(
            app,
            [
                "run",
                "watch",
                "run_pending",
                "--interval",
                "0",
                "--timeout",
                "0.1",
            ],
        )

    assert result.exit_code != 0
    assert "did not stop before timeout" in result.output


def test_wf_run_resume_interrupted_run(tmp_path: Path) -> None:
    root = tmp_path / "wf_cli_run_resume"
    root.mkdir(parents=True, exist_ok=True)
    config_path = _seed_interrupt_deployment(root)

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
                "approval.personal",
                "--input",
                '{"message": "send?"}',
            ],
        )
        run_id = json.loads(start.output)["run_id"]

        resumed = runner.invoke(
            app,
            [
                "--config",
                str(config_path),
                "run",
                "resume",
                run_id,
                "--payload",
                "{}",
            ],
        )

    assert resumed.exit_code == 0, resumed.output
    payload = json.loads(resumed.output)
    assert payload["run_id"] == run_id
    assert payload["status"] == "completed"
    assert payload["outcome"] == "submitted"
    assert payload["resume_readiness"] == "not_applicable"


def test_wf_run_start_reports_bad_json(tmp_path: Path) -> None:
    root = tmp_path / "wf_cli_run_bad_json"
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


def test_wf_run_list_emits_json(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeHandlers:
        async def list_runs(self, *, status=None, cursor=None, limit=50):
            captured["status"] = status
            captured["cursor"] = cursor
            captured["limit"] = limit
            return {
                "runs": [
                    {
                        "run_id": "run_1",
                        "deployment_id": "demo.default",
                        "artifact_id": "demo",
                        "artifact_version": 1,
                        "status": "completed",
                        "resume_readiness": "not_applicable",
                        "diagnostic_count": 0,
                        "created_at": "2026-06-11T00:00:00",
                        "updated_at": "2026-06-11T00:00:01",
                    }
                ],
                "total": 1,
                "cursor": None,
                "next_cursor": None,
                "limit": 25,
            }

    monkeypatch.setattr(
        "wf_cli.commands.runs.load_cli_context_from_typer",
        lambda ctx: type("Ctx", (), {"handlers": FakeHandlers(), "verbose": False})(),
    )

    result = CliRunner().invoke(
        app,
        ["run", "list", "--status", "completed", "--limit", "25"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["total"] == 1
    assert payload["runs"][0]["run_id"] == "run_1"
    assert captured == {"status": "completed", "cursor": None, "limit": 25}


def _interrupt_artifact() -> WorkflowArtifact:
    return WorkflowArtifact(
        id="approval",
        version=1,
        title="Approval",
        input_schema={
            "type": "object",
            "properties": {"message": {"type": "string"}},
            "required": ["message"],
        },
        output_schema={"type": "object", "properties": {}},
        outcomes=("submitted",),
        plan={
            "name": "approval",
            "input_schema": {
                "type": "object",
                "properties": {"message": {"type": "string"}},
                "required": ["message"],
            },
            "state_schema": {"fields": {}},
            "output_schema": {"type": "object", "properties": {}},
            "outcomes": ["submitted"],
            "start": "approval",
            "nodes": [
                {
                    "id": "approval",
                    "type": "interrupt",
                    "kind": "approval",
                    "request": [input_binding("input.message", "message")],
                    "resume": [],
                    "outcomes": ["submitted"],
                },
                {"id": "end_submitted", "type": "end", "outcome": "submitted"},
            ],
            "edges": [
                {"from": "approval", "outcome": "submitted", "to": "end_submitted"}
            ],
        },
    )
