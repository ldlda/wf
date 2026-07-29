from __future__ import annotations

import ast
import json
from pathlib import Path

from wf_api.operation_context import WorkflowOperationContext
from wf_cli.context import load_cli_context
from wf_mcp.broker import WfMcpService
from wf_mcp.broker.service.workflow_operation_context import context_from_service
from wf_mcp.storage import FileStore


def test_context_uses_source_catalog_mapping(tmp_path: Path) -> None:
    service = WfMcpService(store=FileStore(tmp_path / "context_sources"))
    context = context_from_service(service)

    assert context.specs.capability_sources is service.source_catalog.capability_sources


def test_wf_api_operation_context_imports_no_wf_mcp() -> None:
    path = (
        Path(__file__).resolve().parents[2] / "src" / "wf_api" / "operation_context.py"
    )
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            if node.module.startswith("wf_mcp"):
                violations.append(f"{node.lineno}: from {node.module} import ...")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("wf_mcp"):
                    violations.append(f"{node.lineno}: import {alias.name}")

    assert violations == []


def test_context_from_service_exposes_existing_store_objects(tmp_path: Path) -> None:
    config_path = tmp_path / "wf_mcp.config.json"
    config_path.write_text(
        json.dumps(
            {
                "store_root": ".wf_mcp_store",
                "connections": [
                    {
                        "id": "demo.personal",
                        "server": "demo",
                        "account": "personal",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    cli_context = load_cli_context(config_path)
    service = cli_context.service
    assert service is not None

    operation_context = context_from_service(service)

    assert isinstance(operation_context, WorkflowOperationContext)
    assert operation_context.artifact_store is service.artifact_store
    assert operation_context.draft_workspace_store is service.draft_workspace_store
    assert operation_context.run_store is service.run_store
    assert operation_context.specs.capability_sources is service.capability_sources


def test_context_from_service_delegates_specs_and_events(tmp_path: Path) -> None:
    config_path = tmp_path / "wf_mcp.config.json"
    config_path.write_text(
        json.dumps({"store_root": ".wf_mcp_store", "connections": []}),
        encoding="utf-8",
    )
    cli_context = load_cli_context(config_path)
    service = cli_context.service
    assert service is not None
    operation_context = context_from_service(service)

    event = object()
    operation_context.events.record_event(event)

    assert service.list_events()[-1] is event


def test_context_from_service_record_workflow_event(tmp_path: Path) -> None:
    config_path = tmp_path / "wf_mcp.config.json"
    config_path.write_text(
        json.dumps({"store_root": ".wf_mcp_store", "connections": []}),
        encoding="utf-8",
    )
    cli_context = load_cli_context(config_path)
    service = cli_context.service
    assert service is not None
    operation_context = context_from_service(service)

    operation_context.events.record_workflow_event(
        "workflow_artifact_saved",
        capability_id="workflow.demo.v1",
        payload={"artifact_id": "demo", "version": 1},
    )

    recorded = service.events.list_events()[-1]
    assert recorded.kind == "workflow_artifact_saved"
    assert recorded.capability_id == "workflow.demo.v1"
    assert recorded.payload["artifact_id"] == "demo"
    assert recorded.payload["version"] == 1


def test_context_runtime_runner_uses_workflow_runtime_service(tmp_path: Path) -> None:
    service = WfMcpService(store=FileStore(tmp_path / "context_runtime"))
    context = context_from_service(service)

    assert getattr(context.runtime, "runtime") is service.workflow_runtime
