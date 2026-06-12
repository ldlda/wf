from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from wf_config import (
    FilesystemStoreConfig,
    HttpSourceTransportConfig,
    LocalTargetConfig,
    McpSourceConfig,
    RpcHttpTargetConfig,
    RpcHttpTransportConfig,
    StdioSourceTransportConfig,
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
    assert str(config.client.target.url) == "http://127.0.0.1:8765/rpc"
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
    with pytest.raises(ValidationError):
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
    tmp_path: Path,
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


def test_load_workflow_config_preserves_absolute_filesystem_store(
    tmp_path: Path,
) -> None:
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


def test_workflow_config_parses_mcp_stdio_source() -> None:
    config = WorkflowConfigFile.model_validate(
        {
            "version": 1,
            "server": {
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
                ]
            },
        }
    )

    source = config.server.sources[0]
    assert isinstance(source, McpSourceConfig)
    assert source.id == "everything.default"
    assert source.enabled is True
    assert source.provider == "everything"
    assert source.account == "default"
    assert source.profile == "dev"
    assert source.ownership == "seed"
    assert isinstance(source.transport, StdioSourceTransportConfig)
    assert source.transport.command == "uvx"
    assert source.transport.args == ("mcp-server-everything",)
    assert source.transport.env == {"DEBUG": "1"}
    assert source.auth_ref == "auth.everything.default"
    assert source.metadata["description"] == "Everything test server"


def test_workflow_config_parses_mcp_http_source() -> None:
    config = WorkflowConfigFile.model_validate(
        {
            "version": 1,
            "server": {
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
                ]
            },
        }
    )

    source = config.server.sources[0]
    assert isinstance(source, McpSourceConfig)
    assert source.enabled is True
    assert source.ownership == "locked"
    assert isinstance(source.transport, HttpSourceTransportConfig)
    assert str(source.transport.url) == "http://127.0.0.1:3000/mcp"
    assert source.transport.headers == {"X-Test": "yes"}


def test_workflow_config_rejects_mcp_source_without_provider_account_shape() -> None:
    with pytest.raises(ValidationError, match="source id must look like"):
        WorkflowConfigFile.model_validate(
            {
                "version": 1,
                "server": {
                    "sources": [
                        {
                            "kind": "mcp",
                            "id": "everything",
                            "provider": "everything",
                            "account": "default",
                            "transport": {"kind": "stdio", "command": "uvx"},
                        }
                    ]
                },
            }
        )


def test_workflow_config_rejects_unsafe_mcp_source_id() -> None:
    with pytest.raises(ValidationError, match="source id must start"):
        WorkflowConfigFile.model_validate(
            {
                "version": 1,
                "server": {
                    "sources": [
                        {
                            "kind": "mcp",
                            "id": ".hidden.default",
                            "provider": "hidden",
                            "account": "default",
                            "transport": {"kind": "stdio", "command": "uvx"},
                        }
                    ]
                },
            }
        )


def test_workflow_config_parses_role_specific_store_overrides() -> None:
    config = WorkflowConfigFile.model_validate(
        {
            "version": 1,
            "server": {
                "store": {"kind": "filesystem", "root": ".wf_store"},
                "stores": {
                    "workflow": {"kind": "filesystem", "root": ".wf_workflow"},
                    "auth": {"kind": "filesystem", "root": ".wf_auth"},
                    "source_registry": {
                        "kind": "filesystem",
                        "root": ".wf_sources",
                    },
                    "catalog_cache": {
                        "kind": "filesystem",
                        "root": ".wf_catalog",
                    },
                },
            },
        }
    )

    assert isinstance(config.server.stores.workflow, FilesystemStoreConfig)
    assert config.server.stores.workflow.root.as_posix() == ".wf_workflow"
    assert isinstance(config.server.stores.auth, FilesystemStoreConfig)
    assert config.server.stores.auth.root.as_posix() == ".wf_auth"
    assert isinstance(config.server.stores.source_registry, FilesystemStoreConfig)
    assert config.server.stores.source_registry.root.as_posix() == ".wf_sources"
    assert isinstance(config.server.stores.catalog_cache, FilesystemStoreConfig)
    assert config.server.stores.catalog_cache.root.as_posix() == ".wf_catalog"


def test_workflow_config_rejects_duplicate_source_ids_across_kinds() -> None:
    with pytest.raises(ValidationError, match="duplicate source id"):
        WorkflowConfigFile.model_validate(
            {
                "version": 1,
                "server": {
                    "sources": [
                        {"kind": "stdlib", "id": "wf.std"},
                        {
                            "kind": "mcp",
                            "id": "wf.std",
                            "provider": "wf",
                            "account": "std",
                            "transport": {"kind": "stdio", "command": "uvx"},
                        },
                    ]
                },
            }
        )


def test_load_workflow_config_resolves_role_store_paths_relative_to_config(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "nested" / "wf.json"
    config_path.parent.mkdir()
    config_path.write_text(
        json.dumps(
            {
                "version": 1,
                "server": {
                    "store": {"kind": "filesystem", "root": ".default_store"},
                    "stores": {
                        "workflow": {
                            "kind": "filesystem",
                            "root": ".workflow_store",
                        },
                        "auth": {
                            "kind": "filesystem",
                            "root": ".auth_store",
                        },
                        "source_registry": {
                            "kind": "filesystem",
                            "root": ".source_store",
                        },
                        "catalog_cache": {
                            "kind": "filesystem",
                            "root": ".catalog_store",
                        },
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    config = load_workflow_config(config_path)

    assert config.server.store.root == (config_path.parent / ".default_store").resolve()
    assert config.server.stores.workflow is not None
    assert (
        config.server.stores.workflow.root
        == (config_path.parent / ".workflow_store").resolve()
    )
    assert config.server.stores.auth is not None
    assert (
        config.server.stores.auth.root == (config_path.parent / ".auth_store").resolve()
    )
    assert config.server.stores.source_registry is not None
    assert (
        config.server.stores.source_registry.root
        == (config_path.parent / ".source_store").resolve()
    )
    assert config.server.stores.catalog_cache is not None
    assert (
        config.server.stores.catalog_cache.root
        == (config_path.parent / ".catalog_store").resolve()
    )


def test_workflow_config_parses_python_source() -> None:
    config = WorkflowConfigFile.model_validate(
        {
            "version": 1,
            "server": {
                "sources": [
                    {
                        "kind": "python",
                        "id": "local.ops",
                        "module": "tests.fixtures.python_source_ops",
                        "registry": "registry",
                    }
                ]
            },
        }
    )

    source = config.server.sources[0]
    assert source.kind == "python"
    assert source.id == "local.ops"
    assert source.path == Path(".")
    assert source.module == "tests.fixtures.python_source_ops"
    assert source.registry == "registry"


def test_load_workflow_config_resolves_python_source_path(tmp_path: Path) -> None:
    config_path = tmp_path / "wf.json"
    config_path.write_text(
        json.dumps(
            {
                "version": 1,
                "server": {
                    "sources": [
                        {
                            "kind": "python",
                            "id": "local.ops",
                            "path": "src",
                            "module": "project_ops",
                        }
                    ]
                },
            }
        ),
        encoding="utf-8",
    )

    config = load_workflow_config(config_path)

    source = config.server.sources[0]
    assert source.kind == "python"
    assert source.path == (tmp_path / "src").resolve()


def test_server_config_resolves_missing_role_stores_to_default_store() -> None:
    config = WorkflowConfigFile.model_validate(
        {
            "version": 1,
            "server": {
                "store": {"kind": "filesystem", "root": ".default"},
                "stores": {
                    "auth": {"kind": "filesystem", "root": ".auth"},
                },
            },
        }
    )

    assert config.server.workflow_store.root.as_posix() == ".default"
    assert config.server.auth_store.root.as_posix() == ".auth"
    assert config.server.source_registry_store.root.as_posix() == ".default"
    assert config.server.catalog_cache_store.root.as_posix() == ".default"


def test_workflow_config_parses_oauth_provider_profile() -> None:
    config = WorkflowConfigFile.model_validate(
        {
            "auth": {
                "providers": {
                    "google": {
                        "kind": "oauth_authorization_code_pkce",
                        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
                        "token_url": "https://oauth2.googleapis.com/token",
                        "client_id_env": "GOOGLE_OAUTH_CLIENT_ID",
                        "client_secret_env": "GOOGLE_OAUTH_CLIENT_SECRET",
                        "scopes": [
                            "https://www.googleapis.com/auth/drive.readonly",
                        ],
                    }
                }
            }
        }
    )

    provider = config.auth.providers["google"]
    assert provider.kind == "oauth_authorization_code_pkce"
    assert provider.client_id_env == "GOOGLE_OAUTH_CLIENT_ID"
    assert provider.scopes == ("https://www.googleapis.com/auth/drive.readonly",)
