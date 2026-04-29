from __future__ import annotations

import json
from pathlib import Path

from wf_mcp.cli import build_parser, main

from test_wf_mcp_support import local_temp_root


def _write_config(path: Path) -> None:
    path.write_text(
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


def test_build_parser_accepts_serve_transport() -> None:
    parser = build_parser()
    args = parser.parse_args(
        ["--config", "wf_mcp.config.json", "serve", "--transport", "streamable_http"]
    )

    assert args.command == "serve"
    assert args.transport == "streamable_http"


def test_cli_connections_prints_configured_connections(capsys) -> None:
    tmp_path = local_temp_root() / "cli_connections_test"
    tmp_path.mkdir(parents=True, exist_ok=True)
    config_path = tmp_path / "wf_mcp.config.json"
    _write_config(config_path)

    exit_code = main(["--config", str(config_path), "connections"])
    captured = capsys.readouterr()

    assert exit_code == 0
    payload = json.loads(captured.out)
    assert payload[0]["id"] == "demo.personal"


def test_cli_catalog_prints_empty_catalog_when_not_refreshed(
    capsys,
) -> None:
    tmp_path = local_temp_root() / "cli_catalog_test"
    tmp_path.mkdir(parents=True, exist_ok=True)
    config_path = tmp_path / "wf_mcp.config.json"
    _write_config(config_path)

    exit_code = main(["--config", str(config_path), "catalog"])
    captured = capsys.readouterr()

    assert exit_code == 0
    payload = json.loads(captured.out)
    assert payload["nodes"] == []
    assert payload["resources"] == []
    assert payload["prompts"] == []
