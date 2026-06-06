from __future__ import annotations

import ast

import pytest

from wf_mcp.broker.config import build_service_from_config
from wf_mcp.broker.server import (
    build_workflow_server_from_config,
    workflow_server_from_service,
)
from wf_mcp.broker.service.core import WfMcpService
from wf_mcp.models import BrokerConfig, ConnectionConfig
from wf_mcp.source_registry import (
    FileSourceRegistryStore,
    McpSourceRegistryEntry,
    SourceRegistryFile,
)
from wf_mcp.storage import FileAuthStore, FileStore
from wf_server import WorkflowServer


def _registry_entry(source_id: str) -> McpSourceRegistryEntry:
    return McpSourceRegistryEntry.model_validate(
        {
            "id": source_id,
            "kind": "mcp",
            "enabled": True,
            "provider": "demo",
            "account": "registry",
            "transport": {"kind": "stdio", "command": "demo-server"},
        }
    )


def test_wf_server_package_stays_mcp_free() -> None:
    path = "src/wf_server/context.py"
    with open(path, encoding="utf-8") as file:
        tree = ast.parse(file.read(), filename=path)

    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module.startswith("wf_mcp"):
                violations.append(f"{node.lineno}: from {node.module} import ...")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("wf_mcp"):
                    violations.append(f"{node.lineno}: import {alias.name}")

    assert violations == []


def test_workflow_server_from_service_wires_neutral_surfaces(tmp_path) -> None:
    config = BrokerConfig(
        store_root=tmp_path / "store",
        connections=[
            ConnectionConfig(id="demo.default", server="demo", account="default")
        ],
    )
    service = build_service_from_config(config)

    server = workflow_server_from_service(
        service,
        config=config,
        source_registry_store=FileSourceRegistryStore(config.store_root),
    )

    assert isinstance(server, WorkflowServer)
    assert server.config.store_root == config.store_root
    assert server.api.context is server.context
    assert server.source_registry_admin is not None
    assert server.admin.connections is service.connection_service
    assert server.admin.events is service.events


def test_build_workflow_server_from_config_exposes_registry_admin(tmp_path) -> None:
    config = BrokerConfig(store_root=tmp_path / "store", connections=[])
    FileSourceRegistryStore(config.store_root).save_registry(
        SourceRegistryFile(sources=[_registry_entry("demo.registry")])
    )

    server = build_workflow_server_from_config(config)

    assert server.source_registry_admin is not None
    assert "demo.registry" in server.context.specs.capability_sources


def test_workflow_server_from_service_rejects_missing_stores(tmp_path) -> None:
    config = BrokerConfig(store_root=tmp_path / "store", connections=[])
    service = WfMcpService(store=FileStore(config.store_root))

    with pytest.raises(ValueError, match="requires workflow stores"):
        workflow_server_from_service(
            service,
            config=config,
            source_registry_store=FileSourceRegistryStore(config.store_root),
        )


async def test_workflow_server_from_service_exposes_auth_admin(tmp_path) -> None:
    from wf_mcp.models import AuthRecord

    config = BrokerConfig(
        store_root=tmp_path / "store",
        connections=[
            ConnectionConfig(id="demo.default", server="demo", account="default")
        ],
    )
    service = build_service_from_config(config)
    service.save_auth(
        AuthRecord(
            connection_id="github.work",
            scheme="bearer",
            payload={"token": "secret"},
        )
    )
    server = workflow_server_from_service(
        service,
        config=config,
        source_registry_store=FileSourceRegistryStore(config.store_root),
    )

    payload = await server.admin.list_auth_records()

    assert payload["auth_records"] == [
        {
            "id": "github.work",
            "scheme": "bearer",
            "metadata": {},
            "payload_keys": ["token"],
        }
    ]


async def test_workflow_server_from_service_uses_focused_auth_store(tmp_path) -> None:
    from wf_artifacts import (
        FileDraftWorkspaceStore,
        FileRunStore,
        FileWorkflowArtifactStore,
    )
    from wf_mcp.models import AuthRecord

    auth_store = FileAuthStore(tmp_path / "auth")
    service = WfMcpService(
        store=FileStore(tmp_path / "compat"),
        auth_store=auth_store,
        artifact_store=FileWorkflowArtifactStore(tmp_path / "workflow"),
        draft_workspace_store=FileDraftWorkspaceStore(tmp_path / "workflow"),
        run_store=FileRunStore(tmp_path / "workflow"),
    )
    auth_store.save_auth(AuthRecord(connection_id="drive.work", scheme="bearer"))

    config = BrokerConfig(
        store_root=tmp_path / "store",
        connections=[],
    )
    server = workflow_server_from_service(
        service,
        config=config,
        source_registry_store=FileSourceRegistryStore(tmp_path / "store"),
    )
    result = await server.admin.inspect_auth_record("drive.work")

    assert result["id"] == "drive.work"
