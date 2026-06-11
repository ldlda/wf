from __future__ import annotations

from pathlib import Path

from wf_config import FilesystemStoreConfig, PythonSourceConfig, WorkflowConfigFile
from wf_platform import CapabilitySource

from .context import WorkflowServer, build_local_static_workflow_server


def _has_mcp_sources(config: WorkflowConfigFile) -> bool:
    return any(
        getattr(source, "kind", None) == "mcp" for source in config.server.sources
    )


def _python_sources(config: WorkflowConfigFile) -> dict[str, CapabilitySource]:
    from wf_sources_python import load_python_source

    return {
        source.id: load_python_source(
            source_id=source.id,
            module=source.module,
            registry=source.registry,
            enabled=source.enabled,
        )
        for source in config.server.sources
        if isinstance(source, PythonSourceConfig)
    }


def _build_mcp_workflow_server_from_workflow_config(
    config: WorkflowConfigFile,
) -> WorkflowServer:
    """Build an MCP-backed server from neutral config.

    This import is intentionally isolated here: transport packages should not
    import MCP modules, while this server composition boundary is allowed to
    select source-provider implementations by source kind.
    """
    from wf_mcp.broker import build_workflow_server_from_workflow_config

    return build_workflow_server_from_workflow_config(config)


def _build_mcp_workflow_server_from_legacy_config(path: Path) -> WorkflowServer:
    """Build an MCP-backed server from legacy broker config."""
    from wf_mcp.broker import build_workflow_server_from_config, load_broker_config

    return build_workflow_server_from_config(load_broker_config(path))


def build_workflow_server_from_workflow_config(
    config: WorkflowConfigFile,
) -> WorkflowServer:
    """Build a WorkflowServer from neutral workflow config.

    Local/static configs use built-in sources. Configs with ``kind: "mcp"``
    sources delegate to the MCP provider adapter.
    """
    if _has_mcp_sources(config):
        return _build_mcp_workflow_server_from_workflow_config(config)
    store = config.server.workflow_store
    if not isinstance(store, FilesystemStoreConfig):
        # Roadmap: SQL/transactional stores are deferred until the remote server
        # storage boundary is proven with file-backed stores.
        raise ValueError("wf-rpc-server currently requires filesystem store")
    return build_local_static_workflow_server(
        store.root,
        extra_sources=_python_sources(config),
    )


def build_workflow_server_from_legacy_mcp_config(path: str | Path) -> WorkflowServer:
    """Build a WorkflowServer from legacy wf_mcp.config.json.

    Prefer neutral ``wf_config`` for new setups. This compatibility hook keeps the
    transport CLI free of direct MCP imports while existing users migrate.
    """
    return _build_mcp_workflow_server_from_legacy_config(Path(path))
