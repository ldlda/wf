from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, cast

import httpx
from typer.testing import CliRunner

import wf_cli.context as cli_context
from wf_api.models import RawWorkflowPlan
from wf_cli.app import app
from wf_cli.context import CliContext, load_cli_context, load_local_cli_context
from wf_core import END
from wf_server import build_local_static_workflow_server
from wf_transport_rpc_http import RpcWorkflowApiClient, create_rpc_app
from wf_transport_rpc_http.client.sources import RpcSourceAdminClientMixin


class BrokenSourceAdmin:
    async def list_sources(
        self,
        *,
        cursor: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        return {"sources": [], "next_cursor": None, "total": 0}

    async def inspect_source(self, *, source_id: str) -> dict[str, Any]:
        raise RuntimeError(f"broken source admin for {source_id}")


def test_load_cli_context_uses_rpc_client_for_rpc_http_target(tmp_path) -> None:
    config_path = tmp_path / "wf.json"
    config_path.write_text(
        json.dumps(
            {
                "version": 1,
                "client": {
                    "target": {
                        "kind": "rpc_http",
                        "url": "http://127.0.0.1:8765/rpc",
                        "timeout_seconds": 9,
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    context = load_cli_context(config_path)

    assert isinstance(context.handlers, RpcWorkflowApiClient)
    assert context.handlers.url == "http://127.0.0.1:8765/rpc"
    assert context.handlers.timeout_seconds == 9
    assert context.service is None


def test_load_cli_context_local_override_beats_rpc_config(tmp_path) -> None:
    config_path = tmp_path / "wf.json"
    config_path.write_text(
        json.dumps(
            {
                "version": 1,
                "client": {
                    "target": {
                        "kind": "rpc_http",
                        "url": "http://127.0.0.1:8765/rpc",
                    }
                },
                "server": {
                    "store": {"kind": "filesystem", "root": ".wf_store"},
                },
            }
        ),
        encoding="utf-8",
    )

    context = load_cli_context(config_path, force_local=True)

    assert not isinstance(context.handlers, RpcWorkflowApiClient)
    assert context.service is None
    assert context.config_path == config_path


def test_load_cli_context_rejects_local_and_url_conflict(tmp_path) -> None:
    config_path = tmp_path / "wf.json"
    config_path.write_text('{"version": 1}', encoding="utf-8")

    try:
        load_cli_context(
            config_path,
            force_local=True,
            rpc_url="http://127.0.0.1:8765/rpc",
        )
    except ValueError as exc:
        message = str(exc)
    else:
        raise AssertionError("expected ValueError")

    assert "--local and --url are mutually exclusive" in message


def test_load_cli_context_uses_workflow_shape_not_filename(tmp_path) -> None:
    config_path = tmp_path / "wf_mcp.config.json"
    config_path.write_text(
        json.dumps(
            {
                "version": 1,
                "client": {
                    "target": {
                        "kind": "rpc_http",
                        "url": "http://127.0.0.1:8765/rpc",
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    context = load_cli_context(config_path)

    assert isinstance(context.handlers, RpcWorkflowApiClient)


def test_load_cli_context_uses_broker_shape_not_filename(tmp_path) -> None:
    config_path = tmp_path / "wf.json"
    config_path.write_text(
        json.dumps({"store_root": ".wf_mcp_store", "connections": []}),
        encoding="utf-8",
    )

    context = load_cli_context(config_path)

    assert context.service is not None
    assert not isinstance(context.handlers, RpcWorkflowApiClient)


def test_load_cli_context_url_override_reuses_config_timeout(tmp_path) -> None:
    config_path = tmp_path / "wf.json"
    config_path.write_text(
        json.dumps(
            {
                "version": 1,
                "client": {
                    "target": {
                        "kind": "rpc_http",
                        "url": "http://127.0.0.1:8765/rpc",
                        "timeout_seconds": 77,
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    context = load_cli_context(config_path, rpc_url="http://127.0.0.1:9999/rpc")

    assert isinstance(context.handlers, RpcWorkflowApiClient)
    assert context.handlers.url == "http://127.0.0.1:9999/rpc"
    assert context.handlers.timeout_seconds == 77


def test_local_cli_context_rejects_rpc_target_for_local_only_commands(tmp_path) -> None:
    config_path = tmp_path / "wf.json"
    config_path.write_text(
        json.dumps(
            {
                "version": 1,
                "client": {
                    "target": {
                        "kind": "rpc_http",
                        "url": "http://127.0.0.1:8765/rpc",
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    try:
        load_local_cli_context(config_path)
    except ValueError as exc:
        message = str(exc)
    else:
        raise AssertionError("expected ValueError")

    assert "not available for rpc_http targets yet" in message


def _constant_plan() -> RawWorkflowPlan:
    return RawWorkflowPlan.model_validate(
        {
            "name": "remote_cli_constant",
            "input_schema": {"type": "object", "properties": {}},
            "state_schema": {
                "type": "object",
                "properties": {
                    "result": {"type": "string", "reducer": "wf.std.replace"}
                },
            },
            "output_schema": {
                "type": "object",
                "properties": {"result": {"type": "string"}},
                "required": ["result"],
            },
            "outcomes": ["ok"],
            "start": "constant",
            "nodes": [
                {
                    "id": "constant",
                    "type": "node",
                    "node": "wf.std.constant",
                    "input": [
                        {
                            "value": "hello remote cli",
                            "target": {"root": "local", "parts": ["value"]},
                        }
                    ],
                    "output": [
                        {
                            "source": {"root": "local", "parts": ["value"]},
                            "target": {"root": "state", "parts": ["result"]},
                        }
                    ],
                }
            ],
            "edges": [{"from": "constant", "outcome": "ok", "to": END}],
            "output": [
                {
                    "path": {"root": "state", "parts": ["result"]},
                    "target": {"root": "local", "parts": ["result"]},
                }
            ],
        }
    )


def _interrupt_plan() -> RawWorkflowPlan:
    return RawWorkflowPlan.model_validate(
        {
            "name": "remote_approval",
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
                    "request": [
                        {
                            "path": {"root": "input", "parts": ["message"]},
                            "target": {"root": "local", "parts": ["message"]},
                        }
                    ],
                    "resume": [],
                    "outcomes": ["submitted"],
                },
                {"id": "end_submitted", "type": "end", "outcome": "submitted"},
            ],
            "edges": [
                {"from": "approval", "outcome": "submitted", "to": "end_submitted"}
            ],
        }
    )


def _patch_rpc_client_to_server(monkeypatch, server) -> None:
    """Route CLI-created RPC clients to an in-process ASGI test server."""

    def fake_rpc_client_from_target(
        *,
        url: str,
        timeout_seconds: float,
    ) -> RpcWorkflowApiClient:
        return RpcWorkflowApiClient(
            url=url,
            timeout_seconds=timeout_seconds,
            http_client=httpx.AsyncClient(
                transport=httpx.ASGITransport(app=create_rpc_app(server)),
                base_url="http://test",
            ),
        )

    monkeypatch.setattr(cli_context, "rpc_client_from_target", fake_rpc_client_from_target)


def test_wf_cap_commands_use_rpc_url_override(monkeypatch, tmp_path) -> None:
    server = build_local_static_workflow_server(tmp_path / "store")
    _patch_rpc_client_to_server(monkeypatch, server)
    config_path = tmp_path / "wf.json"
    config_path.write_text('{"version": 1}', encoding="utf-8")

    runner = CliRunner()
    inspected = runner.invoke(
        app,
        [
            "--config",
            str(config_path),
            "--url",
            "http://test/rpc",
            "cap",
            "inspect",
            "wf.std.constant",
        ],
    )
    listed = runner.invoke(
        app,
        [
            "--config",
            str(config_path),
            "--url",
            "http://test/rpc",
            "cap",
            "list",
            "--source",
            "wf.std",
            "--limit",
            "100",
        ],
    )
    called = runner.invoke(
        app,
        [
            "--config",
            str(config_path),
            "--url",
            "http://test/rpc",
            "cap",
            "call",
            "wf.std.constant",
            "--input",
            '{"value": "hello cap call"}',
        ],
    )

    assert inspected.exit_code == 0, inspected.output
    assert '"name": "wf.std.constant"' in inspected.output
    assert listed.exit_code == 0, listed.output
    listed_payload = json.loads(listed.output)
    assert listed_payload["capabilities"]
    assert {
        capability["source_id"] for capability in listed_payload["capabilities"]
    } == {"wf.std"}
    assert called.exit_code == 0, called.output
    called_payload = json.loads(called.output)
    assert called_payload["qualified_name"] == "wf.std.constant"
    assert called_payload["outcome"] == "ok"
    assert called_payload["output"] == {"value": "hello cap call"}


def test_wf_source_commands_use_rpc_url_override(monkeypatch, tmp_path) -> None:
    server = build_local_static_workflow_server(tmp_path / "store")
    _patch_rpc_client_to_server(monkeypatch, server)
    config_path = tmp_path / "wf.json"
    config_path.write_text('{"version": 1}', encoding="utf-8")
    runner = CliRunner()
    base_args = ["--config", str(config_path), "--url", "http://test/rpc"]

    listed = runner.invoke(app, [*base_args, "source", "list", "--limit", "10"])
    inspected = runner.invoke(app, [*base_args, "source", "inspect", "wf.std"])

    assert listed.exit_code == 0, listed.output
    assert '"id": "wf.std"' in listed.output
    assert inspected.exit_code == 0, inspected.output
    assert '"id": "wf.std"' in inspected.output


def test_wf_remote_source_inspect_formats_expected_rpc_error(
    monkeypatch,
    tmp_path,
) -> None:
    server = build_local_static_workflow_server(tmp_path / "store")
    _patch_rpc_client_to_server(monkeypatch, server)
    config_path = tmp_path / "wf.json"
    config_path.write_text('{"version": 1}', encoding="utf-8")
    runner = CliRunner()
    base_args = ["--config", str(config_path), "--url", "http://test/rpc"]

    result = runner.invoke(app, [*base_args, "source", "inspect", "missing.source"])

    assert result.exit_code != 0
    assert "Error" in result.output
    assert "Workflow operation failed" in result.output
    assert "missing.source" in result.output
    assert "Traceback" not in result.output
    assert "RuntimeError" not in result.output


def test_wf_remote_source_list_formats_transport_error(monkeypatch, tmp_path) -> None:
    async def connection_failed(*args: Any, **kwargs: Any) -> dict[str, Any]:
        raise httpx.ConnectError(
            "connection refused",
            request=httpx.Request("POST", "http://test/rpc"),
        )

    monkeypatch.setattr(RpcSourceAdminClientMixin, "list_sources", connection_failed)
    config_path = tmp_path / "wf.json"
    config_path.write_text('{"version": 1}', encoding="utf-8")
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "--config",
            str(config_path),
            "--url",
            "http://test/rpc",
            "source",
            "list",
        ],
    )

    assert result.exit_code != 0
    assert "Error" in result.output
    assert "connection refused" in result.output
    assert "Traceback" not in result.output
    assert "ConnectError" not in result.output


def test_wf_unexpected_error_uses_short_traceback_by_default(
    monkeypatch,
    tmp_path,
) -> None:
    fake_context = CliContext(
        config_path=Path("dummy"),
        service=cast(Any, object()),
        handlers=build_local_static_workflow_server(tmp_path / "store").api,
        source_admin=BrokenSourceAdmin(),
        admin=cast(Any, object()),
    )
    monkeypatch.setattr(
        "wf_cli.commands.sources.load_cli_context_from_typer",
        lambda _ctx: fake_context,
    )

    result = CliRunner().invoke(app, ["source", "inspect", "wf.std"])

    assert result.exit_code != 0
    assert "broken source admin for wf.std" in result.output
    assert "tests/wf_cli/test_remote_target.py" not in result.output


def test_wf_verbose_shows_full_traceback_for_unexpected_error(
    monkeypatch,
    tmp_path,
) -> None:
    fake_context = CliContext(
        config_path=Path("dummy"),
        service=cast(Any, object()),
        handlers=build_local_static_workflow_server(tmp_path / "store").api,
        source_admin=BrokenSourceAdmin(),
        admin=cast(Any, object()),
        verbose=True,
    )
    monkeypatch.setattr(
        "wf_cli.commands.sources.load_cli_context_from_typer",
        lambda _ctx: fake_context,
    )

    result = CliRunner().invoke(app, ["--verbose", "source", "inspect", "wf.std"])

    assert result.exit_code != 0
    assert isinstance(result.exception, RuntimeError)
    assert str(result.exception) == "broken source admin for wf.std"


def test_wf_admin_commands_use_rpc_url_override(monkeypatch, tmp_path) -> None:
    server = build_local_static_workflow_server(tmp_path / "store")
    server.events.record_workflow_event(
        "workflow_test_event",
        capability_id="workflow.demo.v1",
        payload={"ok": True},
    )
    _patch_rpc_client_to_server(monkeypatch, server)
    config_path = tmp_path / "wf.json"
    config_path.write_text('{"version": 1}', encoding="utf-8")
    runner = CliRunner()
    base_args = ["--config", str(config_path), "--url", "http://test/rpc"]

    connections = runner.invoke(app, [*base_args, "admin", "connections"])
    statuses = runner.invoke(app, [*base_args, "admin", "statuses"])
    events = runner.invoke(app, [*base_args, "admin", "events"])

    assert connections.exit_code == 0, connections.output
    assert '"connections": []' in connections.output
    assert statuses.exit_code == 0, statuses.output
    assert '"statuses": []' in statuses.output
    assert events.exit_code == 0, events.output
    assert '"kind": "workflow_test_event"' in events.output


def test_wf_remote_draft_artifact_deploy_lifecycle(monkeypatch, tmp_path) -> None:
    server = build_local_static_workflow_server(tmp_path / "store")
    _patch_rpc_client_to_server(monkeypatch, server)
    config_path = tmp_path / "wf.json"
    config_path.write_text('{"version": 1}', encoding="utf-8")
    runner = CliRunner()
    base_args = ["--config", str(config_path), "--url", "http://test/rpc"]

    created = runner.invoke(
        app,
        [
            *base_args,
            "draft",
            "create-from-capability",
            "remote_ws",
            "wf.std.constant",
            "--name",
            "remote_constant",
            "--title",
            "Remote Constant",
        ],
    )
    assert created.exit_code == 0, created.output
    assert '"workspace_id": "remote_ws"' in created.output

    validated = runner.invoke(
        app,
        [*base_args, "draft", "validate", "remote_ws"],
    )
    assert validated.exit_code == 0, validated.output
    assert '"status": "valid"' in validated.output

    saved_artifact = runner.invoke(
        app,
        [
            *base_args,
            "draft",
            "save",
            "remote_ws",
            "--artifact",
            "remote_artifact",
            "--version",
            "1",
            "--title",
            "Remote Artifact",
            "--outcome",
            "ok",
            "--binding",
            "wf.std=wf.std",
        ],
    )
    assert saved_artifact.exit_code == 0, saved_artifact.output
    assert '"artifact_id": "remote_artifact"' in saved_artifact.output

    inspected_artifact = runner.invoke(
        app,
        [*base_args, "artifact", "inspect", "remote_artifact", "1"],
    )
    assert inspected_artifact.exit_code == 0, inspected_artifact.output
    assert '"id": "remote_artifact"' in inspected_artifact.output

    saved_deployment = runner.invoke(
        app,
        [
            *base_args,
            "deploy",
            "save",
            "remote_artifact.default",
            "--artifact",
            "remote_artifact",
            "--version",
            "1",
            "--binding",
            "wf.std=wf.std",
        ],
    )
    assert saved_deployment.exit_code == 0, saved_deployment.output
    assert '"deployment_id": "remote_artifact.default"' in saved_deployment.output

    validated_deployment = runner.invoke(
        app,
        [*base_args, "deploy", "validate", "remote_artifact.default"],
    )
    assert validated_deployment.exit_code == 0, validated_deployment.output
    assert '"status": "runnable"' in validated_deployment.output


def test_wf_remote_run_resume_interrupted_deployment(monkeypatch, tmp_path) -> None:
    server = build_local_static_workflow_server(tmp_path / "store")
    asyncio.run(
        server.api.create_artifact_from_plan(
            artifact_id="remote_approval",
            version=1,
            title="Remote Approval",
            plan=_interrupt_plan(),
            outcomes=("submitted",),
        )
    )
    asyncio.run(
        server.api.save_deployment(
            {
                "id": "remote_approval.default",
                "artifact_id": "remote_approval",
                "artifact_version": 1,
                "bindings": [],
            }
        )
    )
    _patch_rpc_client_to_server(monkeypatch, server)
    config_path = tmp_path / "wf.json"
    config_path.write_text('{"version": 1}', encoding="utf-8")
    runner = CliRunner()
    base_args = ["--config", str(config_path), "--url", "http://test/rpc"]

    started = runner.invoke(
        app,
        [
            *base_args,
            "run",
            "start",
            "remote_approval.default",
            "--input",
            '{"message": "approve?"}',
        ],
    )
    assert started.exit_code == 0, started.output
    started_payload = json.loads(started.output)
    assert started_payload["status"] == "interrupted"

    resumed = runner.invoke(
        app,
        [
            *base_args,
            "run",
            "resume",
            started_payload["run_id"],
            "--payload",
            "{}",
        ],
    )
    assert resumed.exit_code == 0, resumed.output
    resumed_payload = json.loads(resumed.output)
    assert resumed_payload["run_id"] == started_payload["run_id"]
    assert resumed_payload["status"] == "completed"
    assert resumed_payload["outcome"] == "submitted"


def test_wf_status_uses_rpc_url_override(monkeypatch, tmp_path) -> None:
    server = build_local_static_workflow_server(tmp_path / "store")
    _patch_rpc_client_to_server(monkeypatch, server)
    config_path = tmp_path / "wf.json"
    config_path.write_text('{"version": 1}', encoding="utf-8")

    result = CliRunner().invoke(
        app,
        [
            "--config",
            str(config_path),
            "--url",
            "http://test/rpc",
            "status",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["target"]["mode"] == "remote"
    assert payload["target"]["url"] == "http://test/rpc"
    assert payload["workflow"]["capability_count"] >= 1
    assert payload["sources"]["available"] is True
    assert payload["admin"]["available"] is True
    assert payload["registry"]["available"] is False


def test_wf_status_reports_rpc_config_target(monkeypatch, tmp_path) -> None:
    server = build_local_static_workflow_server(tmp_path / "store")
    _patch_rpc_client_to_server(monkeypatch, server)
    config_path = tmp_path / "wf.json"
    config_path.write_text(
        json.dumps(
            {
                "version": 1,
                "client": {
                    "target": {
                        "kind": "rpc_http",
                        "url": "http://test/rpc",
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        app,
        [
            "--config",
            str(config_path),
            "status",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["target"]["mode"] == "remote"
    assert payload["target"]["url"] == "http://test/rpc"
    assert payload["workflow"]["capability_count"] >= 1


def test_wf_draft_delete_requires_confirm(monkeypatch, tmp_path) -> None:
    server = build_local_static_workflow_server(tmp_path / "store")
    _patch_rpc_client_to_server(monkeypatch, server)
    config_path = tmp_path / "wf.json"
    config_path.write_text('{"version": 1}', encoding="utf-8")
    runner = CliRunner()
    base_args = ["--config", str(config_path), "--url", "http://test/rpc"]

    result = runner.invoke(app, [*base_args, "draft", "delete", "delete-me"])

    assert result.exit_code != 0
    assert "confirm" in (result.output).lower()


def test_wf_draft_delete_succeeds_with_confirm(monkeypatch, tmp_path) -> None:
    server = build_local_static_workflow_server(tmp_path / "store")
    _patch_rpc_client_to_server(monkeypatch, server)
    config_path = tmp_path / "wf.json"
    config_path.write_text('{"version": 1}', encoding="utf-8")
    runner = CliRunner()
    base_args = ["--config", str(config_path), "--url", "http://test/rpc"]

    runner.invoke(
        app,
        [
            *base_args,
            "draft",
            "create-from-capability",
            "delete-me",
            "wf.std.constant",
            "--name",
            "delete_me_ws",
        ],
    )

    result = runner.invoke(app, [*base_args, "draft", "delete", "delete-me", "--confirm"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["workspace_id"] == "delete-me"
    assert payload["deleted"] is True
