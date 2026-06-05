from __future__ import annotations

from pathlib import Path

import pytest

from wf_config import WorkflowConfigFile
from wf_server.config import (
    build_workflow_server_from_legacy_mcp_config,
    build_workflow_server_from_workflow_config,
)
from wf_server.context import WorkflowServer


def test_build_workflow_server_from_workflow_config_uses_local_static_for_no_mcp_sources(
    tmp_path: Path,
) -> None:
    config = WorkflowConfigFile.model_validate(
        {
            "version": 1,
            "server": {
                "store": {"kind": "filesystem", "root": str(tmp_path / "store")},
                "sources": [{"kind": "stdlib", "id": "wf.std"}],
            },
        }
    )

    server = build_workflow_server_from_workflow_config(config)

    assert isinstance(server, WorkflowServer)
    assert server.config.store_root == tmp_path / "store"
    assert server.source_registry_admin is None


def test_build_workflow_server_from_workflow_config_uses_mcp_builder_for_mcp_sources(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    captured = {}

    def fake_builder(config):
        captured["source_kinds"] = [source.kind for source in config.server.sources]
        return "mcp-server"

    monkeypatch.setattr(
        "wf_server.config._build_mcp_workflow_server_from_workflow_config",
        fake_builder,
    )
    config = WorkflowConfigFile.model_validate(
        {
            "version": 1,
            "server": {
                "store": {"kind": "filesystem", "root": str(tmp_path / "store")},
                "sources": [
                    {
                        "kind": "mcp",
                        "id": "everything.default",
                        "provider": "everything",
                        "account": "default",
                        "transport": {"kind": "stdio", "command": "uvx"},
                    }
                ],
            },
        }
    )

    server = build_workflow_server_from_workflow_config(config)

    assert server == "mcp-server"
    assert captured["source_kinds"] == ["mcp"]


def test_build_workflow_server_from_legacy_mcp_config_delegates_to_mcp_builder(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    captured = {}

    def fake_builder(path):
        captured["path"] = path
        return "legacy-mcp-server"

    monkeypatch.setattr(
        "wf_server.config._build_mcp_workflow_server_from_legacy_config",
        fake_builder,
    )
    legacy_path = tmp_path / "wf_mcp.config.json"
    legacy_path.write_text('{"store_root": "store", "connections": []}', encoding="utf-8")

    server = build_workflow_server_from_legacy_mcp_config(legacy_path)

    assert server == "legacy-mcp-server"
    assert captured["path"] == legacy_path
