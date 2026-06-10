from __future__ import annotations


def test_rpc_server_cli_compat_import_matches_server_cli() -> None:
    from wf_server import cli as server_cli
    from wf_transport_rpc_http import cli as transport_cli

    assert transport_cli.app is server_cli.app
    assert transport_cli.main is server_cli.main
