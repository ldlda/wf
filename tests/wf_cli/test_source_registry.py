from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from wf_cli.app import app
from wf_cli.commands.source_registry import _read_json_arg
from wf_cli.context import CliContext

runner = CliRunner()


def _make_config(tmp_path: Path) -> dict[str, Any]:
    return {
        "version": 1,
        "client": {"target": {"kind": "local"}},
        "server": {"store": {"kind": "filesystem", "root": str(tmp_path / "store")}},
    }


def _fake_context_with_admin(
    mock_surface: MagicMock | None = None,
) -> CliContext:
    return CliContext(
        config_path=Path("dummy"),
        service=None,
        handlers=MagicMock(),
        source_admin=MagicMock(),
        admin=MagicMock(),
        source_registry_admin=mock_surface or MagicMock(),
    )


def _patch_load_cli_context(
    monkeypatch: pytest.MonkeyPatch, fake_ctx: CliContext
) -> None:
    monkeypatch.setattr(
        "wf_cli.commands.source_registry.load_cli_context_from_typer",
        lambda _ctx: fake_ctx,
    )


def _patch_asyncio_run(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "wf_cli.commands.source_registry.asyncio.run",
        lambda coro: coro,
    )


# --- help tests ---


def test_wf_admin_registry_help_exists() -> None:
    result = runner.invoke(app, ["admin", "registry", "--help"])

    assert result.exit_code == 0
    assert "list" in result.output
    assert "inspect" in result.output
    assert "add" in result.output
    assert "update" in result.output
    assert "enable" in result.output
    assert "disable" in result.output
    assert "remove" in result.output
    assert "apply" in result.output


def test_wf_admin_registry_list_help_exists() -> None:
    result = runner.invoke(app, ["admin", "registry", "list", "--help"])

    assert result.exit_code == 0
    assert "--limit" in result.output
    assert "--cursor" in result.output


def test_wf_admin_registry_inspect_help_exists() -> None:
    result = runner.invoke(app, ["admin", "registry", "inspect", "--help"])

    assert result.exit_code == 0
    assert "SOURCE_ID" in result.output


def test_wf_admin_registry_add_help_exists() -> None:
    result = runner.invoke(app, ["admin", "registry", "add", "--help"])

    assert result.exit_code == 0
    assert "--input" in result.output
    assert "--input-file" in result.output


def test_wf_admin_registry_update_help_exists() -> None:
    result = runner.invoke(app, ["admin", "registry", "update", "--help"])

    assert result.exit_code == 0
    assert "SOURCE_ID" in result.output
    assert "--patch" in result.output
    assert "--patch-file" in result.output


def test_wf_admin_registry_enable_help_exists() -> None:
    result = runner.invoke(app, ["admin", "registry", "enable", "--help"])

    assert result.exit_code == 0
    assert "SOURCE_ID" in result.output


def test_wf_admin_registry_disable_help_exists() -> None:
    result = runner.invoke(app, ["admin", "registry", "disable", "--help"])

    assert result.exit_code == 0
    assert "SOURCE_ID" in result.output


def test_wf_admin_registry_remove_help_exists() -> None:
    result = runner.invoke(app, ["admin", "registry", "remove", "--help"])

    assert result.exit_code == 0
    assert "SOURCE_ID" in result.output
    assert "--confirm" in result.output


# --- unavailability tests ---


def test_wf_admin_registry_list_local_static_returns_unavailable(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "wf_mcp.config.json"
    config_path.write_text(json.dumps(_make_config(tmp_path)), encoding="utf-8")

    result = runner.invoke(
        app,
        ["--config", str(config_path), "admin", "registry", "list"],
    )

    assert result.exit_code != 0
    assert "not available" in result.output


def test_wf_admin_registry_inspect_local_static_returns_unavailable(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "wf_mcp.config.json"
    config_path.write_text(json.dumps(_make_config(tmp_path)), encoding="utf-8")

    result = runner.invoke(
        app,
        ["--config", str(config_path), "admin", "registry", "inspect", "github.work"],
    )

    assert result.exit_code != 0
    assert "not available" in result.output


def test_wf_admin_registry_add_local_static_returns_unavailable(tmp_path: Path) -> None:
    config_path = tmp_path / "wf_mcp.config.json"
    config_path.write_text(json.dumps(_make_config(tmp_path)), encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "--config",
            str(config_path),
            "admin",
            "registry",
            "add",
            "--input",
            '{"id": "test.source"}',
        ],
    )

    assert result.exit_code != 0
    assert "not available" in result.output


def test_wf_admin_registry_update_local_static_returns_unavailable(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "wf_mcp.config.json"
    config_path.write_text(json.dumps(_make_config(tmp_path)), encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "--config",
            str(config_path),
            "admin",
            "registry",
            "update",
            "github.work",
            "--patch",
            '{"enabled": false}',
        ],
    )

    assert result.exit_code != 0
    assert "not available" in result.output


def test_wf_admin_registry_enable_local_static_returns_unavailable(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "wf_mcp.config.json"
    config_path.write_text(json.dumps(_make_config(tmp_path)), encoding="utf-8")

    result = runner.invoke(
        app,
        ["--config", str(config_path), "admin", "registry", "enable", "github.work"],
    )

    assert result.exit_code != 0
    assert "not available" in result.output


def test_wf_admin_registry_disable_local_static_returns_unavailable(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "wf_mcp.config.json"
    config_path.write_text(json.dumps(_make_config(tmp_path)), encoding="utf-8")

    result = runner.invoke(
        app,
        ["--config", str(config_path), "admin", "registry", "disable", "github.work"],
    )

    assert result.exit_code != 0
    assert "not available" in result.output


def test_wf_admin_registry_remove_local_static_returns_unavailable(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "wf_mcp.config.json"
    config_path.write_text(json.dumps(_make_config(tmp_path)), encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "--config",
            str(config_path),
            "admin",
            "registry",
            "remove",
            "github.work",
            "--confirm",
        ],
    )

    assert result.exit_code != 0
    assert "not available" in result.output


# --- validation tests ---


def test_wf_admin_registry_remove_without_confirm_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_admin = MagicMock()
    mock_admin.remove_registry_entry.return_value = {}
    fake_ctx = _fake_context_with_admin(mock_admin)
    _patch_load_cli_context(monkeypatch, fake_ctx)

    result = runner.invoke(app, ["admin", "registry", "remove", "github.work"])

    assert result.exit_code != 0
    assert "--confirm" in result.output
    mock_admin.remove_registry_entry.assert_not_called()


def test_wf_admin_registry_add_both_input_flags_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_ctx = _fake_context_with_admin()
    _patch_load_cli_context(monkeypatch, fake_ctx)

    result = runner.invoke(
        app,
        [
            "admin",
            "registry",
            "add",
            "--input",
            '{"id": "x"}',
            "--input-file",
            "dummy.json",
        ],
    )

    assert result.exit_code != 0


def test_wf_admin_registry_add_no_input_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_ctx = _fake_context_with_admin()
    _patch_load_cli_context(monkeypatch, fake_ctx)

    result = runner.invoke(app, ["admin", "registry", "add"])

    assert result.exit_code != 0


def test_wf_admin_registry_add_invalid_json_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_ctx = _fake_context_with_admin()
    _patch_load_cli_context(monkeypatch, fake_ctx)

    result = runner.invoke(
        app,
        ["admin", "registry", "add", "--input", "not json"],
    )

    assert result.exit_code != 0
    assert "invalid JSON" in result.output


def test_wf_admin_registry_update_both_patch_flags_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_ctx = _fake_context_with_admin()
    _patch_load_cli_context(monkeypatch, fake_ctx)

    result = runner.invoke(
        app,
        [
            "admin",
            "registry",
            "update",
            "x",
            "--patch",
            '{"a": 1}',
            "--patch-file",
            "dummy.json",
        ],
    )

    assert result.exit_code != 0


def test_wf_admin_registry_update_no_patch_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_ctx = _fake_context_with_admin()
    _patch_load_cli_context(monkeypatch, fake_ctx)

    result = runner.invoke(app, ["admin", "registry", "update", "x"])

    assert result.exit_code != 0


def test_wf_admin_registry_update_invalid_json_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_ctx = _fake_context_with_admin()
    _patch_load_cli_context(monkeypatch, fake_ctx)

    result = runner.invoke(
        app,
        ["admin", "registry", "update", "x", "--patch", "not json"],
    )

    assert result.exit_code != 0
    assert "invalid JSON" in result.output


# --- delegation tests ---


def test_wf_admin_registry_add_delegates_to_surface(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_surface = MagicMock()
    mock_surface.add_registry_entry.return_value = {"id": "new.source"}
    fake_ctx = _fake_context_with_admin(mock_surface)
    _patch_load_cli_context(monkeypatch, fake_ctx)
    _patch_asyncio_run(monkeypatch)

    result = runner.invoke(
        app,
        ["admin", "registry", "add", "--input", '{"id": "new.source"}'],
    )

    assert result.exit_code == 0
    mock_surface.add_registry_entry.assert_called_once_with(entry={"id": "new.source"})


def test_wf_admin_registry_update_delegates_to_surface(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_surface = MagicMock()
    mock_surface.update_registry_entry.return_value = {"id": "x", "enabled": False}
    fake_ctx = _fake_context_with_admin(mock_surface)
    _patch_load_cli_context(monkeypatch, fake_ctx)
    _patch_asyncio_run(monkeypatch)

    result = runner.invoke(
        app,
        ["admin", "registry", "update", "x", "--patch", '{"enabled": false}'],
    )

    assert result.exit_code == 0
    mock_surface.update_registry_entry.assert_called_once_with(
        source_id="x", patch={"enabled": False}
    )


def test_wf_admin_registry_enable_delegates_to_surface(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_surface = MagicMock()
    mock_surface.enable_registry_entry.return_value = {"id": "x", "enabled": True}
    fake_ctx = _fake_context_with_admin(mock_surface)
    _patch_load_cli_context(monkeypatch, fake_ctx)
    _patch_asyncio_run(monkeypatch)

    result = runner.invoke(app, ["admin", "registry", "enable", "x"])

    assert result.exit_code == 0
    mock_surface.enable_registry_entry.assert_called_once_with(source_id="x")


def test_wf_admin_registry_disable_delegates_to_surface(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_surface = MagicMock()
    mock_surface.disable_registry_entry.return_value = {"id": "x", "enabled": False}
    fake_ctx = _fake_context_with_admin(mock_surface)
    _patch_load_cli_context(monkeypatch, fake_ctx)
    _patch_asyncio_run(monkeypatch)

    result = runner.invoke(app, ["admin", "registry", "disable", "x"])

    assert result.exit_code == 0
    mock_surface.disable_registry_entry.assert_called_once_with(source_id="x")


def test_wf_admin_registry_remove_delegates_to_surface(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_surface = MagicMock()
    mock_surface.remove_registry_entry.return_value = {"id": "x", "removed": True}
    fake_ctx = _fake_context_with_admin(mock_surface)
    _patch_load_cli_context(monkeypatch, fake_ctx)
    _patch_asyncio_run(monkeypatch)

    result = runner.invoke(app, ["admin", "registry", "remove", "x", "--confirm"])

    assert result.exit_code == 0
    mock_surface.remove_registry_entry.assert_called_once_with(source_id="x")


# --- _read_json_arg unit tests ---


def test_read_json_arg_inline() -> None:
    assert _read_json_arg('{"a": 1}', None, "--input/--input-file") == {"a": 1}


def test_read_json_arg_file(tmp_path: Path) -> None:
    f = tmp_path / "data.json"
    f.write_text('{"b": 2}', encoding="utf-8")
    assert _read_json_arg(None, str(f), "--input/--input-file") == {"b": 2}


def test_read_json_arg_both_raises() -> None:
    with pytest.raises(Exception, match="provide exactly one"):
        _read_json_arg('{"a": 1}', "file.json", "--input/--input-file")


def test_read_json_arg_neither_raises() -> None:
    with pytest.raises(Exception, match="is required"):
        _read_json_arg(None, None, "--input/--input-file")


def test_read_json_arg_invalid_inline() -> None:
    with pytest.raises(Exception, match="invalid JSON"):
        _read_json_arg("not json", None, "--input/--input-file")


def test_read_json_arg_rejects_non_object_inline() -> None:
    with pytest.raises(Exception, match="must be a JSON object"):
        _read_json_arg("[1, 2]", None, "--input/--input-file")


def test_read_json_arg_rejects_non_object_file(tmp_path: Path) -> None:
    f = tmp_path / "array.json"
    f.write_text("[1, 2]", encoding="utf-8")
    with pytest.raises(Exception, match="must be a JSON object"):
        _read_json_arg(None, str(f), "--input/--input-file")


def test_read_json_arg_invalid_file(tmp_path: Path) -> None:
    f = tmp_path / "bad.json"
    f.write_text("not json", encoding="utf-8")
    with pytest.raises(Exception, match="invalid JSON in file"):
        _read_json_arg(None, str(f), "--input/--input-file")


def test_read_json_arg_missing_file() -> None:
    with pytest.raises(Exception, match="file not found"):
        _read_json_arg(None, "/nonexistent/file.json", "--input/--input-file")


# --- apply command tests ---


def test_wf_admin_registry_apply_help_exists() -> None:
    result = runner.invoke(app, ["admin", "registry", "apply", "--help"])

    assert result.exit_code == 0


def test_registry_apply_calls_surface(monkeypatch: pytest.MonkeyPatch) -> None:
    surface = MagicMock()
    surface.apply_registry_changes.return_value = {
        "applied": True,
        "registered": ["demo.new"],
        "updated": [],
        "removed": [],
        "connection_count": 1,
        "registry_entry_count": 1,
    }
    fake_ctx = _fake_context_with_admin(surface)
    _patch_load_cli_context(monkeypatch, fake_ctx)
    _patch_asyncio_run(monkeypatch)

    result = runner.invoke(app, ["admin", "registry", "apply"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["applied"] is True
    assert payload["registered"] == ["demo.new"]
