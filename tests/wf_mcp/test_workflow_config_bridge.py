from __future__ import annotations

from wf_config import WorkflowConfigFile
from wf_mcp.broker.config import broker_config_from_workflow_config


def test_broker_config_from_workflow_config_converts_mcp_sources(tmp_path) -> None:
    workflow_config = WorkflowConfigFile.model_validate(
        {
            "version": 1,
            "server": {
                "store": {"kind": "filesystem", "root": str(tmp_path / "store")},
                "sources": [
                    {
                        "kind": "mcp",
                        "id": "everything.default",
                        "enabled": True,
                        "provider": "everything",
                        "account": "default",
                        "profile": "dev",
                        "ownership": "seed",
                        "transport": {
                            "kind": "stdio",
                            "command": "uvx",
                            "args": ["mcp-server-everything"],
                            "env": {"DEBUG": "1"},
                        },
                        "auth_ref": "auth.everything.default",
                        "metadata": {"description": "Everything test server"},
                    }
                ],
            },
        }
    )

    broker_config = broker_config_from_workflow_config(workflow_config)

    assert broker_config.store_root == tmp_path / "store"
    assert len(broker_config.connections) == 1
    connection = broker_config.connections[0]
    assert connection.id == "everything.default"
    assert connection.server == "everything"
    assert connection.account == "default"
    assert connection.enabled is True
    assert connection.source_config_ownership == "seed"
    assert connection.metadata["profile"] == "dev"
    assert connection.metadata["auth_ref"] == "auth.everything.default"
    assert connection.metadata["transport"] == "stdio"
    assert connection.metadata["command"] == "uvx"
    assert connection.metadata["args"] == ["mcp-server-everything"]
    assert connection.metadata["env"] == {"DEBUG": "1"}
    assert connection.metadata["description"] == "Everything test server"


def test_broker_config_from_workflow_config_converts_mcp_http_source(tmp_path) -> None:
    workflow_config = WorkflowConfigFile.model_validate(
        {
            "version": 1,
            "server": {
                "store": {"kind": "filesystem", "root": str(tmp_path / "store")},
                "sources": [
                    {
                        "kind": "mcp",
                        "id": "context7.default",
                        "provider": "context7",
                        "account": "default",
                        "transport": {
                            "kind": "http",
                            "url": "http://127.0.0.1:3000/mcp",
                            "headers": {"X-Test": "yes"},
                        },
                    }
                ],
            },
        }
    )

    broker_config = broker_config_from_workflow_config(workflow_config)

    connection = broker_config.connections[0]
    assert connection.metadata["transport"] == "streamable_http"
    assert connection.metadata["url"] == "http://127.0.0.1:3000/mcp"
    assert connection.metadata["headers"] == {"X-Test": "yes"}


def test_broker_config_from_workflow_config_ignores_non_mcp_sources(tmp_path) -> None:
    workflow_config = WorkflowConfigFile.model_validate(
        {
            "version": 1,
            "server": {
                "store": {"kind": "filesystem", "root": str(tmp_path / "store")},
                "sources": [{"kind": "stdlib", "id": "wf.std"}],
            },
        }
    )

    broker_config = broker_config_from_workflow_config(workflow_config)

    assert broker_config.store_root == tmp_path / "store"
    assert broker_config.connections == []
