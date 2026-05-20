from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from wf_mcp.cli import build_parser, main
from wf_mcp.broker import load_broker_config

from .test_support import local_temp_root


def _write_config(path: Path) -> None:
    path.write_text(
        json.dumps({
            "store_root": ".wf_mcp_store",
            "connections": [
                {
                    "id": "demo.personal",
                    "server": "demo",
                    "account": "personal",
                }
            ],
        }),
        encoding="utf-8",
    )


def test_build_parser_accepts_serve_transport() -> None:
    parser = build_parser()
    args = parser.parse_args([
        "--config",
        "wf_mcp.config.json",
        "serve",
        "--transport",
        "streamable_http",
    ])

    assert args.command == "serve"
    assert args.transport == "streamable_http"
    assert args.resources_as_tools is False
    assert args.prompts_as_tools is False
    assert args.search_tools is False


def test_build_parser_accepts_proxy_compatibility_flags() -> None:
    parser = build_parser()
    args = parser.parse_args([
        "--config",
        "wf_mcp.config.json",
        "serve",
        "--resources-as-tools",
        "--prompts-as-tools",
        "--search-tools",
        "--safe-tool-names",
    ])

    assert args.command == "serve"
    assert args.resources_as_tools is True
    assert args.prompts_as_tools is True
    assert args.search_tools is True
    assert args.safe_tool_names is True


def test_build_parser_rejects_legacy_mode_flag() -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args([
            "--config",
            "wf_mcp.config.json",
            "serve",
            "--mode",
            "unified",
        ])


def test_build_parser_accepts_no_admin_tools_flag() -> None:
    parser = build_parser()
    args = parser.parse_args([
        "--config",
        "wf_mcp.config.json",
        "serve",
        "--no-admin-tools",
    ])

    assert args.command == "serve"
    assert args.admin_tools is False


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


def test_cli_status_prints_connection_statuses(capsys) -> None:
    tmp_path = local_temp_root() / "cli_status_test"
    tmp_path.mkdir(parents=True, exist_ok=True)
    config_path = tmp_path / "wf_mcp.config.json"
    _write_config(config_path)

    exit_code = main(["--config", str(config_path), "status"])
    captured = capsys.readouterr()

    assert exit_code == 0
    payload = json.loads(captured.out)
    assert payload == [
        {
            "connection_id": "demo.personal",
            "server": "demo",
            "account": "personal",
            "enabled": True,
            "has_snapshot": False,
            "fetched_at_epoch_ms": None,
            "max_age_seconds": None,
            "node_count": 0,
            "resource_count": 0,
            "prompt_count": 0,
        }
    ]


def test_load_broker_config_normalizes_typed_stdio_metadata() -> None:
    tmp_path = local_temp_root() / "cli_typed_stdio_config_test"
    tmp_path.mkdir(parents=True, exist_ok=True)
    config_path = tmp_path / "wf_mcp.config.json"
    config_path.write_text(
        json.dumps({
            "store_root": ".wf_mcp_store",
            "connections": [
                {
                    "id": "demo.personal",
                    "server": "demo",
                    "account": "personal",
                    "metadata": {
                        "command": "python",
                        "args": ["server.py"],
                        "env": {"TOKEN": "secret"},
                    },
                }
            ],
        }),
        encoding="utf-8",
    )

    config = load_broker_config(config_path)

    assert config.store_root == (tmp_path / ".wf_mcp_store").resolve()
    assert config.connections[0].metadata == {
        "transport": "stdio",
        "command": "python",
        "args": ["server.py"],
        "env": {"TOKEN": "secret"},
    }


def test_load_broker_config_rejects_bad_metadata_shape() -> None:
    tmp_path = local_temp_root() / "cli_bad_config_test"
    tmp_path.mkdir(parents=True, exist_ok=True)
    config_path = tmp_path / "wf_mcp.config.json"
    config_path.write_text(
        json.dumps({
            "connections": [
                {
                    "id": "demo.personal",
                    "server": "demo",
                    "account": "personal",
                    "metadata": {"transport": "stdio", "args": "server.py"},
                }
            ],
        }),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError):
        load_broker_config(config_path)
