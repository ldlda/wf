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
