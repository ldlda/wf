from __future__ import annotations

import json
from pathlib import Path

from wf_api import file_workflow_stores
from wf_config import WorkflowConfigFile
from wf_config.models import FilesystemStoreConfig, McpSourceConfig, ServerConfig
from wf_sources_mcp.runtime import McpRuntimePool, PersistentSessionFactory
from wf_sources_mcp.sdk import McpSdkAdapter
from wf_sources_mcp.source_registry import (
    FileSourceRegistryStore,
    workflow_mcp_source_to_connection_config,
)
from wf_sources_mcp.storage import FileAuthStore, FileCatalogStore, FileStore

from ..control import BrokerConfigFile, ConnectionConfigFile
from ..models import BrokerConfig
from .models import BrokerStoreRoots
from .service import WfMcpService

_HTTP_TRANSPORTS = {"http", "streamable-http", "streamable_http", "sse"}


def _source_metadata_without_transport(
    metadata: dict[str, object],
) -> dict[str, object]:
    return {
        key: value
        for key, value in metadata.items()
        if key
        not in {
            "transport",
            "command",
            "args",
            "env",
            "cwd",
            "url",
            "headers",
            "profile",
            "auth_ref",
        }
    }


def _mcp_source_from_connection(connection: ConnectionConfigFile) -> McpSourceConfig:
    metadata = dict(connection.metadata)
    transport_kind = str(metadata.get("transport", "stdio"))
    profile = metadata.get("profile")
    auth_ref = metadata.get("auth_ref")
    source_metadata = _source_metadata_without_transport(metadata)
    if transport_kind == "stdio":
        command = metadata.get("command")
        if not isinstance(command, str) or not command:
            raise ValueError(
                f"legacy stdio connection {connection.id!r} requires metadata.command"
            )
        transport = {
            "kind": "stdio",
            "command": command,
            "args": list(metadata.get("args", [])),
            "env": dict(metadata.get("env", {})),
        }
        cwd = metadata.get("cwd")
        if cwd is not None:
            source_metadata["cwd"] = cwd
    elif transport_kind in _HTTP_TRANSPORTS:
        url = metadata.get("url")
        if not isinstance(url, str) or not url:
            raise ValueError(
                f"legacy HTTP connection {connection.id!r} requires metadata.url"
            )
        transport = {
            "kind": "http",
            "url": url,
            "headers": dict(metadata.get("headers", {})),
        }
        source_metadata["legacy_transport"] = transport_kind
    else:
        raise ValueError(
            f"legacy connection {connection.id!r} uses unsupported transport "
            f"{transport_kind!r}"
        )

    return McpSourceConfig.model_validate(
        {
            "kind": "mcp",
            "id": connection.id,
            "enabled": connection.enabled,
            "provider": connection.server,
            "account": connection.account,
            "profile": profile if isinstance(profile, str) else None,
            "ownership": connection.source_config_ownership,
            "transport": transport,
            "auth_ref": auth_ref if isinstance(auth_ref, str) else None,
            "metadata": source_metadata,
        }
    )


def load_broker_config(path: str | Path) -> BrokerConfig:
    """Load a file-backed broker config into runtime config objects."""
    config_path = Path(path)
    data = json.loads(config_path.read_text(encoding="utf-8"))
    return BrokerConfigFile.model_validate(data).to_runtime(config_path=config_path)


def _filesystem_store_root(store: object, *, role: str) -> Path:
    if not isinstance(store, FilesystemStoreConfig):
        raise ValueError(f"MCP-backed workflow server requires filesystem {role} store")
    return store.root


def broker_config_from_workflow_config(config: WorkflowConfigFile) -> BrokerConfig:
    """Create MCP broker runtime config from neutral workflow server config."""
    return BrokerConfig(
        store_root=config.server.store.root,
        store_roots=BrokerStoreRoots(
            default_root=config.server.store.root,
            workflow_root=_filesystem_store_root(
                config.server.workflow_store,
                role="workflow",
            ),
            auth_root=_filesystem_store_root(config.server.auth_store, role="auth"),
            source_registry_root=_filesystem_store_root(
                config.server.source_registry_store,
                role="source_registry",
            ),
            catalog_cache_root=_filesystem_store_root(
                config.server.catalog_cache_store,
                role="catalog_cache",
            ),
        ),
        connections=[
            workflow_mcp_source_to_connection_config(source)
            for source in config.server.sources
            if getattr(source, "kind", None) == "mcp"
        ],
    )


def migrate_broker_config_file(path: str | Path) -> WorkflowConfigFile:
    """Convert legacy wf_mcp.config.json into neutral workflow config.

    This does not write files. Callers choose whether to serialize the returned
    config to disk or inspect it first.
    """
    config_path = Path(path)
    data = json.loads(config_path.read_text(encoding="utf-8"))
    legacy = BrokerConfigFile.model_validate(data)
    return WorkflowConfigFile(
        server=ServerConfig(
            store=FilesystemStoreConfig(root=legacy.store_root),
            sources=[
                _mcp_source_from_connection(connection)
                for connection in legacy.connections
            ],
        )
    )


def build_service_from_config(config: BrokerConfig) -> WfMcpService:
    """Create a broker service with SDK adapters for configured connections."""
    runtime_factory = PersistentSessionFactory()
    store_roots = config.store_roots or BrokerStoreRoots.from_default(config.store_root)
    workflow_stores = file_workflow_stores(store_roots.workflow_root)
    # Keep FileStore as the compatibility facade on WfMcpService.store while
    # focused services receive role-specific stores.
    auth_store = FileAuthStore(store_roots.auth_root)
    catalog_store = FileCatalogStore(store_roots.catalog_cache_root)
    service = WfMcpService(
        store=FileStore(store_roots.auth_root),
        auth_store=auth_store,
        catalog_store=catalog_store,
        artifact_store=workflow_stores.artifact_store,
        draft_workspace_store=workflow_stores.draft_workspace_store,
        run_store=workflow_stores.run_store,
        # Discovery can use short-lived SDK sessions. Workflow execution needs
        # a persistent runtime so stateful MCP servers keep session/page state
        # across sequential workflow nodes.
        tool_executor=McpRuntimePool(runtime_factory.create),
    )
    source_registry_store = FileSourceRegistryStore(store_roots.source_registry_root)
    service.sync_connections_from_config(
        config,
        source_registry_store=source_registry_store,
    )
    for connection in service.connections.list_all():
        if connection.server not in service.adapters:
            service.register_adapter(connection.server, McpSdkAdapter())
    return service


__all__ = [
    "broker_config_from_workflow_config",
    "build_service_from_config",
    "load_broker_config",
    "migrate_broker_config_file",
]
