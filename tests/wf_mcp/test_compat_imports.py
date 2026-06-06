from __future__ import annotations


def test_root_facade_exports_core_entrypoints() -> None:
    from wf_mcp import (
        AuthRecord,
        BrokerConfig,
        ConnectionConfig,
        DiscoveredTool,
        FileStore,
        McpSdkAdapter,
        WfMcpService,
        create_proxy_client,
        load_broker_config,
    )

    assert AuthRecord.__name__ == "AuthRecord"
    assert BrokerConfig.__name__ == "BrokerConfig"
    assert ConnectionConfig.__name__ == "ConnectionConfig"
    assert DiscoveredTool.__name__ == "DiscoveredTool"
    assert FileStore.__name__ == "FileStore"
    assert McpSdkAdapter.__name__ == "McpSdkAdapter"
    assert WfMcpService.__name__ == "WfMcpService"
    assert callable(create_proxy_client)
    assert callable(load_broker_config)


def test_concern_package_imports_resolve() -> None:
    from wf_mcp.broker import WfMcpService, load_broker_config
    from wf_mcp.proxy import ProxyRuntime
    from wf_mcp.sdk import McpSdkAdapter
    from wf_mcp.storage import FileStore

    assert FileStore.__name__ == "FileStore"
    assert McpSdkAdapter.__name__ == "McpSdkAdapter"
    assert WfMcpService.__name__ == "WfMcpService"
    assert ProxyRuntime.__name__ == "ProxyRuntime"
    assert callable(load_broker_config)


def test_models_module_reexports_canonical_model_owners() -> None:
    from wf_mcp.auth import AuthRecord
    from wf_mcp.broker.models import BrokerConfig, ConnectionConfig
    from wf_mcp.catalog.models import CatalogSnapshot
    from wf_mcp.models import AuthRecord as CompatAuthRecord
    from wf_mcp.models import BrokerConfig as CompatBrokerConfig
    from wf_mcp.models import CatalogSnapshot as CompatCatalogSnapshot
    from wf_mcp.models import ConnectionConfig as CompatConnectionConfig

    assert CompatAuthRecord is AuthRecord
    assert CompatBrokerConfig is BrokerConfig
    assert CompatCatalogSnapshot is CatalogSnapshot
    assert CompatConnectionConfig is ConnectionConfig


def test_wf_mcp_auth_shim_reexports_wf_sources_mcp_auth() -> None:
    from wf_mcp.auth import AuthRecord as CompatAuthRecord
    from wf_sources_mcp.auth import AuthRecord

    assert CompatAuthRecord is AuthRecord


def test_wf_mcp_storage_shim_reexports_wf_sources_mcp_storage() -> None:
    from wf_mcp.storage import FileAuthStore as CompatFileAuthStore
    from wf_mcp.storage import FileCatalogStore as CompatFileCatalogStore
    from wf_mcp.storage import FileStore as CompatFileStore
    from wf_sources_mcp.storage import FileAuthStore, FileCatalogStore, FileStore

    assert CompatFileAuthStore is FileAuthStore
    assert CompatFileCatalogStore is FileCatalogStore
    assert CompatFileStore is FileStore


def test_wf_mcp_source_registry_shim_reexports_wf_sources_mcp_registry() -> None:
    from wf_mcp.source_registry import FileSourceRegistryStore as CompatFileStore
    from wf_mcp.source_registry import McpSourceRegistryEntry as CompatEntry
    from wf_mcp.source_registry import SourceRegistryFile as CompatFile
    from wf_sources_mcp.source_registry import (
        FileSourceRegistryStore,
        McpSourceRegistryEntry,
        SourceRegistryFile,
    )

    assert CompatFileStore is FileSourceRegistryStore
    assert CompatEntry is McpSourceRegistryEntry
    assert CompatFile is SourceRegistryFile
