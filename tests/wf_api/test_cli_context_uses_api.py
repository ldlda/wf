from __future__ import annotations

import json
from pathlib import Path

from wf_api import WorkflowApi
from wf_cli.context import load_cli_context


def test_load_cli_context_returns_workflow_api(tmp_path: Path) -> None:
    """CliContext.handlers must be WorkflowApi, not WorkflowSurfaceHandlers."""
    root = tmp_path / "wf_cli_api_check"
    root.mkdir()
    config_path = root / "wf_mcp.config.json"
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

    assert isinstance(context.handlers, WorkflowApi)
    assert hasattr(context.handlers, "backend")
