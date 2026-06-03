from __future__ import annotations

import json

from typer.testing import CliRunner

from wf_transport_rpc_http.cli import app


def test_rpc_server_cli_help_mentions_store_root() -> None:
    result = CliRunner().invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "--store-root" in result.output
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
