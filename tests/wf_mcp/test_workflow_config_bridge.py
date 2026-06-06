from __future__ import annotations

from pathlib import Path

from wf_config import WorkflowConfigFile
from wf_mcp.broker.config import broker_config_from_workflow_config
from wf_mcp.models import CatalogSnapshot


def test_broker_config_from_workflow_config_converts_mcp_sources(
    tmp_path: Path,
) -> None:
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


def test_broker_config_from_workflow_config_converts_mcp_http_source(
    tmp_path: Path,
) -> None:
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


def test_broker_config_from_workflow_config_ignores_non_mcp_sources(
    tmp_path: Path,
) -> None:
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


def test_broker_config_from_workflow_config_carries_role_store_roots() -> None:
    config = WorkflowConfigFile.model_validate(
        {
            "version": 1,
            "server": {
                "store": {"kind": "filesystem", "root": ".default"},
                "stores": {
                    "workflow": {"kind": "filesystem", "root": ".workflow"},
                    "auth": {"kind": "filesystem", "root": ".auth"},
                    "source_registry": {
                        "kind": "filesystem",
                        "root": ".sources",
                    },
                    "catalog_cache": {
                        "kind": "filesystem",
                        "root": ".catalog",
                    },
                },
            },
        }
    )

    broker = broker_config_from_workflow_config(config)

    assert broker.store_roots.workflow_root == Path(".workflow")
    assert broker.store_roots.auth_root == Path(".auth")
    assert broker.store_roots.source_registry_root == Path(".sources")
    assert broker.store_roots.catalog_cache_root == Path(".catalog")


def test_build_service_from_neutral_config_uses_role_store_roots(
    tmp_path: Path,
) -> None:
    config = WorkflowConfigFile.model_validate(
        {
            "version": 1,
            "server": {
                "store": {"kind": "filesystem", "root": str(tmp_path / "default")},
                "stores": {
                    "workflow": {
                        "kind": "filesystem",
                        "root": str(tmp_path / "workflow"),
                    },
                    "auth": {
                        "kind": "filesystem",
                        "root": str(tmp_path / "auth"),
                    },
                    "source_registry": {
                        "kind": "filesystem",
                        "root": str(tmp_path / "sources"),
                    },
                    "catalog_cache": {
                        "kind": "filesystem",
                        "root": str(tmp_path / "catalog"),
                    },
                },
                "sources": [
                    {
                        "kind": "mcp",
                        "id": "everything.default",
                        "provider": "everything",
                        "account": "default",
                        "transport": {
                            "kind": "stdio",
                            "command": "uvx",
                            "args": ["mcp-server-everything"],
                        },
                    }
                ],
            },
        }
    )

    from wf_mcp.broker.config import build_service_from_config

    broker = broker_config_from_workflow_config(config)
    service = build_service_from_config(broker)

    assert service.store.root == tmp_path / "auth"
    assert service.auth_store is not None
    assert service.catalog_store is not None
    assert service.auth_store.root == tmp_path / "auth"
    assert service.catalog_store.root == tmp_path / "catalog"
    assert service.artifact_store.root == tmp_path / "workflow"
    assert service.draft_workspace_store.root == tmp_path / "workflow"
    assert service.run_store.root == tmp_path / "workflow"
    assert (tmp_path / "sources").exists()

    service.source_catalog.store.save_catalog(
        CatalogSnapshot(
            connection_id="everything.default",
            fetched_at_epoch_ms=1,
            max_age_seconds=300,
            nodes=[],
            resources=[],
            prompts=[],
            metadata={},
        )
    )
    assert (tmp_path / "catalog" / "catalog" / "everything.default.json").exists()
    assert not (tmp_path / "auth" / "catalog" / "everything.default.json").exists()
