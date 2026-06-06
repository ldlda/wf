from __future__ import annotations

import json

from typer.testing import CliRunner

from wf_cli.app import app


class FakeAdmin:
    def __init__(self) -> None:
        self._saved: dict[str, dict] = {}
        self._deleted: list[str] = []

    async def list_auth_records(self):
        return {
            "auth_records": [
                {
                    "id": "github.work",
                    "scheme": "bearer",
                    "metadata": {},
                    "payload_keys": ["token"],
                }
            ],
            "total": 1,
        }

    async def inspect_auth_record(self, auth_ref: str):
        return {
            "id": auth_ref,
            "scheme": "bearer",
            "metadata": {},
            "payload_keys": ["token"],
        }

    async def save_auth_record(self, *, auth_ref, scheme, payload, metadata=None):
        self._saved[auth_ref] = {
            "auth_ref": auth_ref,
            "scheme": scheme,
            "payload": payload,
            "metadata": metadata,
        }
        return {
            "id": auth_ref,
            "scheme": scheme,
            "metadata": metadata or {},
            "payload_keys": sorted(str(key) for key in payload),
        }

    async def delete_auth_record(self, auth_ref):
        self._deleted.append(auth_ref)
        return {"deleted": True, "id": auth_ref}


class FakeContext:
    def __init__(self) -> None:
        self.admin = FakeAdmin()
    verbose = False


def test_wf_admin_auth_list(monkeypatch) -> None:
    monkeypatch.setattr(
        "wf_cli.commands.auth_admin.load_cli_context_from_typer",
        lambda ctx: FakeContext(),
    )

    result = CliRunner().invoke(app, ["admin", "auth", "list"])

    assert result.exit_code == 0
    assert "github.work" in result.stdout
    assert "secret" not in result.stdout


def test_wf_admin_auth_inspect(monkeypatch) -> None:
    monkeypatch.setattr(
        "wf_cli.commands.auth_admin.load_cli_context_from_typer",
        lambda ctx: FakeContext(),
    )

    result = CliRunner().invoke(app, ["admin", "auth", "inspect", "github.work"])

    assert result.exit_code == 0
    assert "github.work" in result.stdout
    assert "payload_keys" in result.stdout
    assert "secret" not in result.stdout


def test_wf_admin_auth_save(monkeypatch) -> None:
    fake_ctx = FakeContext()
    monkeypatch.setattr(
        "wf_cli.commands.auth_admin.load_cli_context_from_typer",
        lambda ctx: fake_ctx,
    )

    result = CliRunner().invoke(
        app,
        [
            "admin",
            "auth",
            "save",
            "drive.work",
            "--scheme",
            "bearer",
            "--payload",
            '{"token":"secret"}',
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["id"] == "drive.work"
    assert payload["payload_keys"] == ["token"]
    assert "secret" not in result.stdout
    assert fake_ctx.admin._saved["drive.work"] == {
        "auth_ref": "drive.work",
        "scheme": "bearer",
        "payload": {"token": "secret"},
        "metadata": None,
    }


def test_wf_admin_auth_save_reads_payload_file(tmp_path, monkeypatch) -> None:
    fake_ctx = FakeContext()
    payload_file = tmp_path / "auth.json"
    payload_file.write_text('{"token":"secret"}', encoding="utf-8")
    monkeypatch.setattr(
        "wf_cli.commands.auth_admin.load_cli_context_from_typer",
        lambda ctx: fake_ctx,
    )

    result = CliRunner().invoke(
        app,
        [
            "admin",
            "auth",
            "save",
            "drive.work",
            "--scheme",
            "bearer",
            "--payload-file",
            str(payload_file),
        ],
    )

    assert result.exit_code == 0
    assert fake_ctx.admin._saved["drive.work"]["payload"] == {"token": "secret"}


def test_wf_admin_auth_delete_requires_confirm(monkeypatch) -> None:
    fake_ctx = FakeContext()
    monkeypatch.setattr(
        "wf_cli.commands.auth_admin.load_cli_context_from_typer",
        lambda ctx: fake_ctx,
    )

    result = CliRunner().invoke(app, ["admin", "auth", "delete", "drive.work"])

    assert result.exit_code != 0
    assert "confirm" in (result.stdout + result.output).lower()
    assert fake_ctx.admin._deleted == []


def test_wf_admin_auth_delete(monkeypatch) -> None:
    fake_ctx = FakeContext()
    monkeypatch.setattr(
        "wf_cli.commands.auth_admin.load_cli_context_from_typer",
        lambda ctx: fake_ctx,
    )

    result = CliRunner().invoke(
        app,
        ["admin", "auth", "delete", "drive.work", "--confirm"],
    )

    assert result.exit_code == 0
    assert json.loads(result.stdout) == {"deleted": True, "id": "drive.work"}
    assert fake_ctx.admin._deleted == ["drive.work"]
