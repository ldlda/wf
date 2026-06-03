from __future__ import annotations

from typer.testing import CliRunner

from wf_transport_rpc_http.cli import app


def test_rpc_server_cli_help_mentions_store_root() -> None:
    result = CliRunner().invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "--store-root" in result.output
    assert "--host" in result.output
    assert "--port" in result.output
