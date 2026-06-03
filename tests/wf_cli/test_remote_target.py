from __future__ import annotations

import json

import httpx
from typer.testing import CliRunner

from wf_api.models import RawWorkflowPlan
from wf_cli.app import app
from wf_cli.context import load_cli_context, load_local_cli_context
from wf_core import END
from wf_server import build_local_static_workflow_server
from wf_transport_rpc_http import RpcWorkflowApiClient, create_rpc_app


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


def test_wf_cap_commands_use_rpc_url_override(monkeypatch, tmp_path) -> None:
    server = build_local_static_workflow_server(tmp_path / "store")
    rpc_app = create_rpc_app(server)
    transport = httpx.ASGITransport(app=rpc_app)
    original_client = httpx.AsyncClient
    monkeypatch.setattr(
        "wf_transport_rpc_http.client.httpx.AsyncClient",
        lambda *args, **kwargs: original_client(
            transport=transport, base_url="http://test"
        ),
    )
    config_path = tmp_path / "wf.json"
    config_path.write_text('{"version": 1}', encoding="utf-8")

    result = CliRunner().invoke(
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
    assert result.exit_code == 0, result.output
    assert '"name": "wf.std.constant"' in result.output
