from __future__ import annotations

from typer.testing import CliRunner

from wf_cli.app import app


class FakeAdmin:
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


class FakeContext:
    admin = FakeAdmin()
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
