from __future__ import annotations

import json

from wf_cli.context import load_cli_context

from ..wf_mcp.test_support import local_temp_root


def test_load_cli_context_builds_service_and_handlers() -> None:
    tmp_path = local_temp_root() / "wf_cli_context"
    tmp_path.mkdir(parents=True, exist_ok=True)
    config_path = tmp_path / "wf_mcp.config.json"
    config_path.write_text(
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

    context = load_cli_context(config_path)

    assert context.config_path == config_path
    assert context.service.connections.list_all()[0].id == "demo.personal"
    assert context.handlers.service is context.service
