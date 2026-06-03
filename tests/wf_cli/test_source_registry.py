from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from wf_cli.app import app

runner = CliRunner()


def test_wf_admin_registry_help_exists() -> None:
    result = runner.invoke(app, ["admin", "registry", "--help"])

    assert result.exit_code == 0
    assert "list" in result.output
    assert "inspect" in result.output


def test_wf_admin_registry_list_help_exists() -> None:
    result = runner.invoke(app, ["admin", "registry", "list", "--help"])

    assert result.exit_code == 0
    assert "--limit" in result.output
    assert "--cursor" in result.output


def test_wf_admin_registry_inspect_help_exists() -> None:
    result = runner.invoke(app, ["admin", "registry", "inspect", "--help"])

    assert result.exit_code == 0
    assert "SOURCE_ID" in result.output


def test_wf_admin_registry_list_local_static_returns_unavailable(tmp_path: Path) -> None:
    config_path = tmp_path / "wf_mcp.config.json"
    config_path.write_text(
        json.dumps(
            {
                "version": 1,
                "client": {"target": {"kind": "local"}},
                "server": {"store": {"kind": "filesystem", "root": str(tmp_path / "store")}},
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        ["--config", str(config_path), "admin", "registry", "list"],
    )

    assert result.exit_code != 0
    assert "not available" in result.output


def test_wf_admin_registry_inspect_local_static_returns_unavailable(tmp_path: Path) -> None:
    config_path = tmp_path / "wf_mcp.config.json"
    config_path.write_text(
        json.dumps(
            {
                "version": 1,
                "client": {"target": {"kind": "local"}},
                "server": {"store": {"kind": "filesystem", "root": str(tmp_path / "store")}},
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        ["--config", str(config_path), "admin", "registry", "inspect", "github.work"],
    )

    assert result.exit_code != 0
    assert "not available" in result.output
