from __future__ import annotations

import json
from pathlib import Path

from wf_artifacts import FileDraftWorkspaceStore, FileWorkflowArtifactStore

from ..control import BrokerConfigFile
from ..models import BrokerConfig
from ..runtime import McpRuntimePool, PersistentSessionFactory
from ..sdk import McpSdkAdapter
from ..storage import FileStore
from .service import WfMcpService


def load_broker_config(path: str | Path) -> BrokerConfig:
    """Load a file-backed broker config into runtime config objects."""
    config_path = Path(path)
    data = json.loads(config_path.read_text(encoding="utf-8"))
    return BrokerConfigFile.model_validate(data).to_runtime(config_path=config_path)


def build_service_from_config(config: BrokerConfig) -> WfMcpService:
    """Create a broker service with SDK adapters for configured connections."""
    runtime_factory = PersistentSessionFactory()
    service = WfMcpService(
        store=FileStore(config.store_root),
        artifact_store=FileWorkflowArtifactStore(config.store_root),
        draft_workspace_store=FileDraftWorkspaceStore(config.store_root),
        # Discovery can use short-lived SDK sessions. Workflow execution needs
        # a persistent runtime so stateful MCP servers keep session/page state
        # across sequential workflow nodes.
        tool_executor=McpRuntimePool(runtime_factory.create),
    )
    for connection in config.connections:
        service.register_connection(connection)
        if connection.server not in service.adapters:
            service.register_adapter(connection.server, McpSdkAdapter())
    return service
