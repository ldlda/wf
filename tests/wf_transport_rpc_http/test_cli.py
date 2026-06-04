from __future__ import annotations

import json

from typer.testing import CliRunner

from wf_transport_rpc_http.cli import app


def test_rpc_server_cli_help_mentions_store_root() -> None:
    result = CliRunner().invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "--store-root" in result.output
    assert "--mcp-config" in result.output
    assert "--host" in result.output
    assert "--port" in result.output


def test_rpc_server_cli_accepts_config_file(tmp_path) -> None:
    config_path = tmp_path / "wf.json"
    config_path.write_text(
        json.dumps(
            {
                "version": 1,
                "server": {
                    "store": {"kind": "filesystem", "root": ".wf_store"},
                    "transports": [
                        {
                            "kind": "rpc_http",
                            "host": "127.0.0.1",
                            "port": 9999,
                            "path": "/rpc",
                        }
                    ],
                },
            }
        ),
        encoding="utf-8",
    )

    result = CliRunner().invoke(app, ["--config", str(config_path), "--help"])

    assert result.exit_code == 0
    assert "--config" in result.output


def test_rpc_server_cli_uses_configured_store_and_transport(
    monkeypatch, tmp_path
) -> None:
    config_path = tmp_path / "wf.json"
    config_path.write_text(
        json.dumps(
            {
                "version": 1,
                "server": {
                    "store": {"kind": "filesystem", "root": ".wf_store"},
                    "transports": [
                        {
                            "kind": "rpc_http",
                            "host": "127.0.0.2",
                            "port": 9999,
                            "path": "/workflow-rpc",
                        }
                    ],
                },
            }
        ),
        encoding="utf-8",
    )
    captured: dict[str, object] = {}

    def fake_build_server(root):
        captured["store_root"] = root
        return object()

    def fake_create_rpc_app(server, *, rpc_path="/rpc"):
        captured["server"] = server
        captured["rpc_path"] = rpc_path
        return object()

    def fake_uvicorn_run(app_obj, *, host, port, access_log):
        captured["app"] = app_obj
        captured["host"] = host
        captured["port"] = port
        captured["access_log"] = access_log

    monkeypatch.setattr(
        "wf_transport_rpc_http.cli.build_local_static_workflow_server",
        fake_build_server,
    )
    monkeypatch.setattr("wf_transport_rpc_http.cli.create_rpc_app", fake_create_rpc_app)
    monkeypatch.setattr("wf_transport_rpc_http.cli.uvicorn.run", fake_uvicorn_run)

    result = CliRunner().invoke(app, ["--config", str(config_path)])

    assert result.exit_code == 0, result.output
    assert captured["store_root"] == (tmp_path / ".wf_store").resolve()
    assert captured["rpc_path"] == "/workflow-rpc"
    assert captured["host"] == "127.0.0.2"
    assert captured["port"] == 9999
    assert captured["access_log"] is False


def test_rpc_server_cli_uses_mcp_config_server(monkeypatch, tmp_path) -> None:
    config_path = tmp_path / "wf_mcp.config.json"
    config_path.write_text(
        json.dumps(
            {
                "store_root": str(tmp_path / "store"),
                "connections": [],
            }
        ),
        encoding="utf-8",
    )
    captured: dict[str, object] = {}

    def fake_load_broker_config(path):
        captured["mcp_config_path"] = path
        return "broker-config"

    def fake_build_mcp_server(config):
        captured["mcp_config"] = config
        return object()

    def fake_create_rpc_app(server, *, rpc_path="/rpc"):
        captured["server"] = server
        captured["rpc_path"] = rpc_path
        return object()

    def fake_uvicorn_run(app_obj, *, host, port, access_log):
        captured["app"] = app_obj
        captured["host"] = host
        captured["port"] = port
        captured["access_log"] = access_log

    monkeypatch.setattr("wf_transport_rpc_http.cli.load_broker_config", fake_load_broker_config)
    monkeypatch.setattr(
        "wf_transport_rpc_http.cli.build_workflow_server_from_config",
        fake_build_mcp_server,
    )
    monkeypatch.setattr("wf_transport_rpc_http.cli.create_rpc_app", fake_create_rpc_app)
    monkeypatch.setattr("wf_transport_rpc_http.cli.uvicorn.run", fake_uvicorn_run)

    result = CliRunner().invoke(
        app,
        [
            "--mcp-config",
            str(config_path),
            "--host",
            "127.0.0.9",
            "--port",
            "9988",
        ],
    )

    assert result.exit_code == 0, result.output
    assert captured["mcp_config_path"] == config_path
    assert captured["mcp_config"] == "broker-config"
    assert captured["server"] is not None
    assert captured["rpc_path"] == "/rpc"
    assert captured["host"] == "127.0.0.9"
    assert captured["port"] == 9988
    assert captured["access_log"] is False


def test_rpc_server_cli_rejects_mcp_config_with_store_root(tmp_path) -> None:
    config_path = tmp_path / "wf_mcp.config.json"
    config_path.write_text(
        json.dumps({"store_root": str(tmp_path / "store"), "connections": []}),
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        app,
        [
            "--mcp-config",
            str(config_path),
            "--store-root",
            str(tmp_path / "other"),
        ],
    )

    assert result.exit_code != 0
    assert "--mcp-config cannot be combined with --store-root" in result.output


def test_rpc_server_cli_mcp_config_builds_registry_capable_server(monkeypatch, tmp_path) -> None:
    config_path = tmp_path / "wf_mcp.config.json"
    config_path.write_text(
        json.dumps(
            {
                "store_root": str(tmp_path / "store"),
                "connections": [],
            }
        ),
        encoding="utf-8",
    )
    captured: dict[str, object] = {}

    def fake_create_rpc_app(server, *, rpc_path="/rpc"):
        captured["source_registry_admin"] = server.source_registry_admin
        captured["rpc_path"] = rpc_path
        return object()

    def fake_uvicorn_run(app_obj, *, host, port, access_log):
        captured["host"] = host
        captured["port"] = port

    monkeypatch.setattr("wf_transport_rpc_http.cli.create_rpc_app", fake_create_rpc_app)
    monkeypatch.setattr("wf_transport_rpc_http.cli.uvicorn.run", fake_uvicorn_run)

    result = CliRunner().invoke(app, ["--mcp-config", str(config_path)])

    assert result.exit_code == 0, result.output
    assert captured["source_registry_admin"] is not None
    assert captured["rpc_path"] == "/rpc"
    assert captured["host"] == "127.0.0.1"
    assert captured["port"] == 8765


def test_rpc_server_cli_mcp_config_with_config_uses_transport_settings(monkeypatch, tmp_path) -> None:
    mcp_config_path = tmp_path / "wf_mcp.config.json"
    mcp_config_path.write_text(
        json.dumps(
            {
                "store_root": str(tmp_path / "store"),
                "connections": [],
            }
        ),
        encoding="utf-8",
    )
    neutral_config_path = tmp_path / "wf.json"
    neutral_config_path.write_text(
        json.dumps(
            {
                "version": 1,
                "server": {
                    "store": {"kind": "filesystem", "root": ".wf_store"},
                    "transports": [
                        {
                            "kind": "rpc_http",
                            "host": "127.0.0.3",
                            "port": 7777,
                            "path": "/custom-rpc",
                        }
                    ],
                },
            }
        ),
        encoding="utf-8",
    )
    captured: dict[str, object] = {}

    def fake_create_rpc_app(server, *, rpc_path="/rpc"):
        captured["server"] = server
        captured["rpc_path"] = rpc_path
        return object()

    def fake_uvicorn_run(app_obj, *, host, port, access_log):
        captured["host"] = host
        captured["port"] = port
        captured["access_log"] = access_log

    monkeypatch.setattr("wf_transport_rpc_http.cli.create_rpc_app", fake_create_rpc_app)
    monkeypatch.setattr("wf_transport_rpc_http.cli.uvicorn.run", fake_uvicorn_run)

    result = CliRunner().invoke(
        app,
        [
            "--mcp-config",
            str(mcp_config_path),
            "--config",
            str(neutral_config_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert captured["server"] is not None
    assert captured["rpc_path"] == "/custom-rpc"
    assert captured["host"] == "127.0.0.3"
    assert captured["port"] == 7777
    assert captured["access_log"] is False
