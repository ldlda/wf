from __future__ import annotations

import json

from wf_cli.context import load_cli_context
from wf_transport_rpc_http import RpcWorkflowApiClient


def test_load_cli_context_uses_rpc_client_for_rpc_http_target(tmp_path) -> None:
    config_path = tmp_path / "wf.json"
    config_path.write_text(
        json.dumps(
            {
                "version": 1,
                "client": {
                    "target": {
                        "kind": "rpc_http",
                        "url": "http://127.0.0.1:8765/rpc",
                        "timeout_seconds": 9,
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    context = load_cli_context(config_path)

    assert isinstance(context.handlers, RpcWorkflowApiClient)
    assert context.handlers.url == "http://127.0.0.1:8765/rpc"
    assert context.handlers.timeout_seconds == 9
    assert context.service is None


def test_load_cli_context_local_override_beats_rpc_config(tmp_path) -> None:
    config_path = tmp_path / "wf.json"
    config_path.write_text(
        json.dumps(
            {
                "version": 1,
                "client": {
                    "target": {
                        "kind": "rpc_http",
                        "url": "http://127.0.0.1:8765/rpc",
                    }
                },
                "server": {
                    "store": {"kind": "filesystem", "root": ".wf_store"},
                },
            }
        ),
        encoding="utf-8",
    )

    context = load_cli_context(config_path, force_local=True)

    assert not isinstance(context.handlers, RpcWorkflowApiClient)
    assert context.service is None
    assert context.config_path == config_path
