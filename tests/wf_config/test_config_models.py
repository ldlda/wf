from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from wf_config import (
    FilesystemStoreConfig,
    LocalTargetConfig,
    RpcHttpTargetConfig,
    RpcHttpTransportConfig,
    StdlibSourceConfig,
    WorkflowConfigFile,
    load_workflow_config,
)


def test_workflow_config_parses_local_target_and_filesystem_store() -> None:
    config = WorkflowConfigFile.model_validate(
        {
            "version": 1,
            "client": {"target": {"kind": "local"}},
            "server": {
                "store": {"kind": "filesystem", "root": ".wf_store"},
                "sources": [{"kind": "stdlib", "id": "wf.std"}],
            },
        }
    )

    assert isinstance(config.client.target, LocalTargetConfig)
    assert isinstance(config.server.store, FilesystemStoreConfig)
    assert config.server.store.root.as_posix() == ".wf_store"
    assert isinstance(config.server.sources[0], StdlibSourceConfig)
    assert config.server.sources[0].id == "wf.std"


def test_workflow_config_parses_rpc_http_target_and_transport() -> None:
    config = WorkflowConfigFile.model_validate(
        {
            "version": 1,
            "client": {
                "target": {
                    "kind": "rpc_http",
                    "url": "http://127.0.0.1:8765/rpc",
                    "timeout_seconds": 12,
                }
            },
            "server": {
                "transports": [
                    {
                        "kind": "rpc_http",
                        "host": "0.0.0.0",
                        "port": 9999,
                        "path": "/rpc",
                    }
                ]
            },
        }
    )

    assert isinstance(config.client.target, RpcHttpTargetConfig)
    assert config.client.target.url == "http://127.0.0.1:8765/rpc"
    assert config.client.target.timeout_seconds == 12
    assert isinstance(config.server.transports[0], RpcHttpTransportConfig)
    assert config.server.transports[0].host == "0.0.0.0"
    assert config.server.transports[0].port == 9999


def test_workflow_config_rejects_duplicate_source_ids() -> None:
    with pytest.raises(ValidationError, match="duplicate source id"):
        WorkflowConfigFile.model_validate(
            {
                "version": 1,
                "server": {
                    "sources": [
                        {"kind": "stdlib", "id": "wf.std"},
                        {"kind": "stdlib", "id": "wf.std"},
                    ]
                },
            }
        )


def test_workflow_config_rejects_unknown_target_kind() -> None:
    with pytest.raises(ValidationError):
        WorkflowConfigFile.model_validate(
            {
                "version": 1,
                "client": {"target": {"kind": "mcp"}},
            }
        )


def test_workflow_config_rejects_invalid_rpc_http_url() -> None:
    with pytest.raises(ValidationError, match="http:// or https://"):
        WorkflowConfigFile.model_validate(
            {
                "version": 1,
                "client": {"target": {"kind": "rpc_http", "url": "not-a-url"}},
            }
        )


def test_workflow_config_rejects_unwired_stdlib_source_id() -> None:
    with pytest.raises(ValidationError):
        WorkflowConfigFile.model_validate(
            {
                "version": 1,
                "server": {"sources": [{"kind": "stdlib", "id": "custom.id"}]},
            }
        )


def test_load_workflow_config_resolves_filesystem_store_relative_to_config(
    tmp_path,
) -> None:
    config_path = tmp_path / "wf.json"
    config_path.write_text(
        json.dumps(
            {
                "version": 1,
                "server": {
                    "store": {"kind": "filesystem", "root": ".wf_store"},
                },
            }
        ),
        encoding="utf-8",
    )

    config = load_workflow_config(config_path)

    assert config.server.store.root == (tmp_path / ".wf_store").resolve()


def test_load_workflow_config_preserves_absolute_filesystem_store(tmp_path) -> None:
    absolute_root = (tmp_path / "absolute-store").resolve()
    config_path = tmp_path / "wf.json"
    config_path.write_text(
        json.dumps(
            {
                "version": 1,
                "server": {
                    "store": {"kind": "filesystem", "root": str(absolute_root)},
                },
            }
        ),
        encoding="utf-8",
    )

    config = load_workflow_config(config_path)

    assert config.server.store.root == absolute_root
