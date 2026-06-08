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


def test_wf_mcp_capabilities_shim_reexports_wf_sources_mcp_catalog_entries() -> None:
    from wf_mcp.capabilities import CatalogNodeEntry as CompatCatalogNodeEntry
    from wf_mcp.capabilities import DiscoveredTool as CompatDiscoveredTool
    from wf_sources_mcp.catalog import CatalogNodeEntry, DiscoveredTool

    assert CompatCatalogNodeEntry is CatalogNodeEntry
    assert CompatDiscoveredTool is DiscoveredTool


def test_wf_mcp_catalog_models_shim_reexports_wf_sources_mcp_catalog_models() -> None:
    from wf_mcp.catalog.models import CatalogSnapshot as CompatCatalogSnapshot
    from wf_mcp.catalog.models import dump_catalog_snapshot as compat_dump
    from wf_sources_mcp.catalog import CatalogSnapshot, dump_catalog_snapshot

    assert CompatCatalogSnapshot is CatalogSnapshot
    assert compat_dump is dump_catalog_snapshot


def test_wf_mcp_sdk_protocol_shims_reexport_wf_sources_mcp_sdk() -> None:
    from wf_mcp.sdk import BackendAdapter as CompatBackendAdapter
    from wf_mcp.sdk import StatefulMcpRuntime as CompatStatefulMcpRuntime
    from wf_mcp.sdk import ToolCallResult as CompatToolCallResult
    from wf_mcp.sdk.base import BackendAdapter as CompatBaseBackendAdapter
    from wf_mcp.sdk.base import StatefulMcpRuntime as CompatBaseStatefulMcpRuntime
    from wf_mcp.sdk.base import ToolCallResult as CompatBaseToolCallResult
    from wf_sources_mcp.sdk import BackendAdapter, StatefulMcpRuntime, ToolCallResult

    assert CompatBackendAdapter is BackendAdapter
    assert CompatToolCallResult is ToolCallResult
    assert CompatStatefulMcpRuntime is StatefulMcpRuntime
    assert CompatBaseBackendAdapter is BackendAdapter
    assert CompatBaseToolCallResult is ToolCallResult
    assert CompatBaseStatefulMcpRuntime is StatefulMcpRuntime

    from wf_mcp.sdk import PromptRuntime as CompatPromptRuntime
    from wf_mcp.sdk import ResourceRuntime as CompatResourceRuntime
    from wf_mcp.sdk import ToolRuntime as CompatToolRuntime
    from wf_mcp.sdk.base import PromptRuntime as CompatBasePromptRuntime
    from wf_mcp.sdk.base import ResourceRuntime as CompatBaseResourceRuntime
    from wf_mcp.sdk.base import ToolRuntime as CompatBaseToolRuntime
    from wf_sources_mcp.sdk import PromptRuntime, ResourceRuntime, ToolRuntime

    assert CompatPromptRuntime is PromptRuntime
    assert CompatResourceRuntime is ResourceRuntime
    assert CompatToolRuntime is ToolRuntime
    assert CompatBasePromptRuntime is PromptRuntime
    assert CompatBaseResourceRuntime is ResourceRuntime
    assert CompatBaseToolRuntime is ToolRuntime


def test_wf_mcp_runtime_protocol_shim_reexports_wf_sources_mcp_tool_executor() -> None:
    from wf_mcp.runtime import ToolExecutor as CompatRuntimeToolExecutor
    from wf_mcp.runtime.protocols import ToolExecutor as CompatProtocolToolExecutor
    from wf_sources_mcp.sdk import ToolExecutor

    assert CompatRuntimeToolExecutor is ToolExecutor
    assert CompatProtocolToolExecutor is ToolExecutor


def test_wf_mcp_sdk_converter_shim_reexports_wf_sources_mcp_converters() -> None:
    from wf_mcp.sdk.converters import prompt_to_discovered as compat_prompt
    from wf_mcp.sdk.converters import resource_to_discovered as compat_resource
    from wf_mcp.sdk.converters import tool_result_to_call_result as compat_tool_result
    from wf_mcp.sdk.converters import tool_to_discovered as compat_tool_to_discovered
    from wf_mcp.sdk.converters import (
        workflow_output_schema_from_mcp_tool_schema as compat_output_schema,
    )
    from wf_sources_mcp.sdk.converters import (
        prompt_to_discovered,
        resource_to_discovered,
        tool_result_to_call_result,
        tool_to_discovered,
        workflow_output_schema_from_mcp_tool_schema,
    )

    assert compat_prompt is prompt_to_discovered
    assert compat_resource is resource_to_discovered
    assert compat_tool_result is tool_result_to_call_result
    assert compat_tool_to_discovered is tool_to_discovered
    assert compat_output_schema is workflow_output_schema_from_mcp_tool_schema


def test_wf_mcp_sdk_adapter_shim_reexports_wf_sources_mcp_adapter() -> None:
    from wf_mcp.sdk import McpSdkAdapter as CompatPackageAdapter
    from wf_mcp.sdk.adapter import McpSdkAdapter as CompatModuleAdapter
    from wf_sources_mcp.sdk import McpSdkAdapter
    from wf_sources_mcp.sdk.adapter import McpSdkAdapter as CanonicalModuleAdapter

    assert CompatPackageAdapter is McpSdkAdapter
    assert CompatModuleAdapter is McpSdkAdapter
    assert CanonicalModuleAdapter is McpSdkAdapter


def test_runtime_shims_reexport_wf_sources_mcp_runtime() -> None:
    from wf_mcp.runtime import (
        McpRuntimePool as OldMcpRuntimePool,
    )
    from wf_mcp.runtime import (
        PersistentMcpSession as OldPersistentMcpSession,
    )
    from wf_mcp.runtime import (
        PersistentSessionFactory as OldPersistentSessionFactory,
    )
    from wf_mcp.runtime import (
        connection_runtime_fingerprint as old_connection_runtime_fingerprint,
    )
    from wf_sources_mcp.runtime import (
        McpRuntimePool,
        PersistentMcpSession,
        PersistentSessionFactory,
        connection_runtime_fingerprint,
    )

    assert OldMcpRuntimePool is McpRuntimePool
    assert OldPersistentMcpSession is PersistentMcpSession
    assert OldPersistentSessionFactory is PersistentSessionFactory
    assert old_connection_runtime_fingerprint is connection_runtime_fingerprint


def test_wf_mcp_broker_catalog_shim_reexports_wf_sources_mcp_catalog() -> None:
    from wf_mcp.broker.catalog import CombinedCatalog as CompatCombinedCatalog
    from wf_mcp.broker.catalog import snapshot_from_specs as compat_snapshot_from_specs
    from wf_sources_mcp.catalog import CombinedCatalog, snapshot_from_specs

    assert CompatCombinedCatalog is CombinedCatalog
    assert compat_snapshot_from_specs is snapshot_from_specs
