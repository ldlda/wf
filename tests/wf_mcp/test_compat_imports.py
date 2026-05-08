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
        create_transparent_proxy_client,
        load_broker_config,
    )

    assert AuthRecord.__name__ == "AuthRecord"
    assert BrokerConfig.__name__ == "BrokerConfig"
    assert ConnectionConfig.__name__ == "ConnectionConfig"
    assert DiscoveredTool.__name__ == "DiscoveredTool"
    assert FileStore.__name__ == "FileStore"
    assert McpSdkAdapter.__name__ == "McpSdkAdapter"
    assert WfMcpService.__name__ == "WfMcpService"
    assert callable(create_transparent_proxy_client)
    assert callable(load_broker_config)


def test_concern_package_imports_resolve() -> None:
    from wf_mcp.broker import WfMcpService, load_broker_config
    from wf_mcp.sdk import McpSdkAdapter
    from wf_mcp.storage import FileStore

    assert FileStore.__name__ == "FileStore"
    assert McpSdkAdapter.__name__ == "McpSdkAdapter"
    assert WfMcpService.__name__ == "WfMcpService"
    assert callable(load_broker_config)
