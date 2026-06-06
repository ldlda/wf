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

    def fake_build_server(config):
        captured["store_root"] = config.server.store.root
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
        "wf_transport_rpc_http.cli.build_workflow_server_from_workflow_config",
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

    def fake_build_mcp_server(path):
        captured["mcp_config_path"] = path
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
        "wf_transport_rpc_http.cli.build_workflow_server_from_legacy_mcp_config",
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


def test_rpc_server_cli_mcp_config_builds_registry_capable_server(
    monkeypatch, tmp_path
) -> None:
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


def test_rpc_server_cli_mcp_config_with_config_uses_transport_settings(
    monkeypatch, tmp_path
) -> None:
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


def test_rpc_server_cli_config_with_mcp_source_uses_mcp_builder(
    monkeypatch, tmp_path
) -> None:
    captured = {}

    def fake_build_from_workflow_config(config):
        captured["source_kinds"] = [source.kind for source in config.server.sources]
        return object()

    def fake_create_rpc_app(server, *, rpc_path="/rpc"):
        captured["server"] = server
        captured["rpc_path"] = rpc_path
        return "app"

    def fake_run(app, *, host, port, access_log):
        captured["run"] = {
            "app": app,
            "host": host,
            "port": port,
            "access_log": access_log,
        }

    monkeypatch.setattr(
        "wf_transport_rpc_http.cli.build_workflow_server_from_workflow_config",
        fake_build_from_workflow_config,
    )
    monkeypatch.setattr("wf_transport_rpc_http.cli.create_rpc_app", fake_create_rpc_app)
    monkeypatch.setattr("wf_transport_rpc_http.cli.uvicorn.run", fake_run)

    config_path = tmp_path / "wf.json"
    config_path.write_text(
        """
{
  "version": 1,
  "server": {
    "store": {"kind": "filesystem", "root": ".wf_store"},
    "transports": [{"kind": "rpc_http", "host": "127.0.0.1", "port": 8765}],
    "sources": [
      {
        "kind": "mcp",
        "id": "everything.default",
        "provider": "everything",
        "account": "default",
        "transport": {"kind": "stdio", "command": "uvx"}
      }
    ]
  }
}
""",
        encoding="utf-8",
    )

    from typer.testing import CliRunner

    from wf_transport_rpc_http.cli import app

    result = CliRunner().invoke(app, ["--config", str(config_path)])

    assert result.exit_code == 0, result.output
    assert captured["source_kinds"] == ["mcp"]
    assert captured["run"]["app"] == "app"


def test_rpc_server_cli_rejects_store_root_with_mcp_source_config(tmp_path) -> None:
    config_path = tmp_path / "wf.json"
    config_path.write_text(
        json.dumps(
            {
                "version": 1,
                "server": {
                    "store": {"kind": "filesystem", "root": ".wf_store"},
                    "sources": [
                        {
                            "kind": "mcp",
                            "id": "everything.default",
                            "provider": "everything",
                            "account": "default",
                            "transport": {"kind": "stdio", "command": "uvx"},
                        }
                    ],
                },
            }
        ),
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        app,
        ["--config", str(config_path), "--store-root", str(tmp_path / "override")],
    )

    assert result.exit_code != 0
    assert "--store-root cannot override MCP-source config" in result.output


def test_rpc_server_cli_config_uses_workflow_store_override(
    tmp_path,
    monkeypatch,
) -> None:
    config_path = tmp_path / "wf.json"
    config_path.write_text(
        json.dumps(
            {
                "version": 1,
                "server": {
                    "store": {"kind": "filesystem", "root": ".default"},
                    "stores": {
                        "workflow": {
                            "kind": "filesystem",
                            "root": ".workflow",
                        }
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    captured: dict[str, object] = {}

    def fake_build_server(config):
        captured["workflow_store_root"] = config.server.workflow_store.root
        return object()

    def fake_create_rpc_app(server, *, rpc_path="/rpc"):
        captured["server"] = server
        captured["rpc_path"] = rpc_path
        return object()

    def fake_uvicorn_run(app_obj, *, host, port, access_log):
        captured["app"] = app_obj

    monkeypatch.setattr(
        "wf_transport_rpc_http.cli.build_workflow_server_from_workflow_config",
        fake_build_server,
    )
    monkeypatch.setattr("wf_transport_rpc_http.cli.create_rpc_app", fake_create_rpc_app)
    monkeypatch.setattr("wf_transport_rpc_http.cli.uvicorn.run", fake_uvicorn_run)

    result = CliRunner().invoke(app, ["--config", str(config_path)])

    assert result.exit_code == 0, result.output
    assert captured["workflow_store_root"] == (tmp_path / ".workflow").resolve()
