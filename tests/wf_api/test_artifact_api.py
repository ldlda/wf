"""Tests for wf_api.artifacts module."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from tests.wf_mcp.test_support import echo_tool
from wf_api import WorkflowApi
from wf_api.artifacts import WorkflowArtifactApi
from wf_artifacts import (
    FileDraftWorkspaceStore,
    FileWorkflowArtifactStore,
    RequiredCapability,
    WorkflowArtifact,
    WorkflowDeployment,
)
from wf_mcp.broker import WfMcpService
from wf_mcp.broker.service.workflow_operation_context import context_from_service
from wf_mcp.models import ConnectionConfig
from wf_mcp.storage import FileStore
from wf_mcp.workflow_surface import WorkflowSurfaceHandlers


def _echo_draft() -> dict[str, Any]:
    return {
        "name": "echo",
        "input_schema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
        "state_schema": {"fields": {"echoed": {"type": "string"}}},
        "output_schema": {
            "type": "object",
            "properties": {"echoed": {"type": "string"}},
            "required": ["echoed"],
        },
        "start": "echo",
        "steps": {
            "echo": {
                "use": "demo.personal.echo_tool",
                "input": [
                    {
                        "target": {"root": "local", "parts": ["text"]},
                        "path": {"root": "input", "parts": ["text"]},
                    }
                ],
                "output": [
                    {
                        "source": {"root": "local", "parts": ["echoed"]},
                        "target": {"root": "state", "parts": ["echoed"]},
                    }
                ],
            }
        },
        "routes": {"echo": {"ok": "__end__"}},
    }


def _echo_artifact() -> WorkflowArtifact:
    plan: dict[str, Any] = {
        "name": "echo",
        "input_schema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
        "state_schema": {"fields": {"echoed": {"type": "string"}}},
        "output_schema": {
            "type": "object",
            "properties": {"echoed": {"type": "string"}},
            "required": ["echoed"],
        },
        "start": "echo",
        "nodes": [
            {
                "id": "echo",
                "type": "node",
                "node": "demo.personal.echo_tool",
                "input": [
                    {
                        "path": {"root": "input", "parts": ["text"]},
                        "target": {"root": "local", "parts": ["text"]},
                    }
                ],
                "output": [
                    {
                        "source": {"root": "local", "parts": ["echoed"]},
                        "target": {"root": "state", "parts": ["echoed"]},
                    }
                ],
            }
        ],
        "edges": [{"from": "echo", "outcome": "ok", "to": "__end__"}],
    }
    return WorkflowArtifact(
        id="echo",
        version=1,
        title="Echo",
        input_schema=plan["input_schema"],
        output_schema=plan["output_schema"],
        outcomes=("completed",),
        plan=plan,
        required_capabilities={
            "demo.echo_tool": RequiredCapability(
                ref="demo.echo_tool",
                kind="node_spec",
            )
        },
    )


def _artifact_api(
    artifact_store: FileWorkflowArtifactStore,
    *,
    register_echo: bool = False,
) -> tuple[WorkflowArtifactApi, WfMcpService]:
    mcp_root = artifact_store.root / "artifacts_mcp" / str(id(artifact_store))
    service = WfMcpService(
        store=FileStore(mcp_root),
        artifact_store=artifact_store,
        draft_workspace_store=FileDraftWorkspaceStore(mcp_root),
    )
    if register_echo:
        service.register_connection(
            ConnectionConfig(id="demo.personal", server="demo", account="personal")
        )
        service.register_specs("demo.personal", echo_tool)
    context = context_from_service(service)
    return WorkflowArtifactApi(context), service


@pytest.mark.asyncio
async def test_save_artifact_stores_and_returns_saved(tmp_path: Path) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "artifacts_save")
    api, _service = _artifact_api(artifact_store)

    result = await api.save_artifact(_echo_artifact().model_dump(mode="json"))

    assert result["saved"] is True
    assert result["artifact_id"] == "echo"
    assert result["version"] == 1
    saved = artifact_store.get_artifact("echo", 1)
    assert saved.id == "echo"


@pytest.mark.asyncio
async def test_list_artifacts_returns_empty_page_without_artifact_store(
    tmp_path: Path,
) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "artifacts_no_store")
    _api, service = _artifact_api(artifact_store)
    context = replace(context_from_service(service), artifact_store=None)
    api = WorkflowArtifactApi(context)

    result = await api.list_artifacts()

    assert result["nodes"] == []
    assert result["next_cursor"] is None
    assert result["total"] == 0


@pytest.mark.asyncio
async def test_create_artifact_from_plan_saves_with_observed_node_specs(
    tmp_path: Path,
) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "artifacts_from_plan")
    api, _service = _artifact_api(artifact_store, register_echo=True)

    result = await api.create_artifact_from_plan(
        artifact_id="echo",
        version=1,
        title="Echo",
        plan=_echo_artifact().plan,
        outcomes=("completed",),
    )

    assert result["saved"] is True
    assert result["artifact_id"] == "echo"
    saved = artifact_store.get_artifact("echo", 1)
    assert saved.id == "echo"


@pytest.mark.asyncio
async def test_create_artifact_from_workspace_suggests_exact_available_source_binding(
    tmp_path: Path,
) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "artifacts_binding_hint")
    api, service = _artifact_api(artifact_store, register_echo=True)
    from wf_api.drafts import WorkflowDraftApi

    drafts_api = WorkflowDraftApi(context_from_service(service))
    await drafts_api.create_draft_workspace(
        workspace_id="echo_ws",
        draft=_echo_draft(),
    )

    result = await api.create_artifact_from_workspace(
        workspace_id="echo_ws",
        artifact_id="echo",
        version=1,
        title="Echo",
        outcomes=("completed",),
    )

    assert result["required_logical_sources"] == ["demo.personal"]
    assert result["suggested_bindings"] == {"demo.personal": "demo.personal"}


async def test_create_artifact_from_workspace_returns_saved_false_when_invalid(
    tmp_path: Path,
) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "artifacts_workspace_invalid")
    api, service = _artifact_api(artifact_store, register_echo=True)
    draft = _echo_draft()
    draft["routes"]["echo"] = {"typo": "__end__"}
    from wf_api.drafts import WorkflowDraftApi

    context = context_from_service(service)
    drafts_api = WorkflowDraftApi(context)
    await drafts_api.create_draft_workspace(
        workspace_id="echo_ws",
        draft=draft,
    )

    result = await api.create_artifact_from_workspace(
        workspace_id="echo_ws",
        artifact_id="echo",
        version=1,
        title="Echo",
        outcomes=("completed",),
    )

    assert result["saved"] is False
    assert result["status"] == "invalid"


@pytest.mark.asyncio
async def test_create_wrapper_from_workspace_saves_kind_wrapper(tmp_path: Path) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "artifacts_wrapper_workspace")
    api, service = _artifact_api(artifact_store, register_echo=True)
    from wf_api.drafts import WorkflowDraftApi

    context = context_from_service(service)
    drafts_api = WorkflowDraftApi(context)
    await drafts_api.create_draft_workspace(
        workspace_id="echo_ws",
        draft=_echo_draft(),
    )

    result = await api.create_wrapper_from_workspace(
        workspace_id="echo_ws",
        artifact_id="echo_wrapper",
        version=1,
        title="Echo Wrapper",
        outcomes=("completed",),
    )

    assert result["saved"] is True
    saved = artifact_store.get_artifact("echo_wrapper", 1)
    assert saved.kind == "wrapper"


@pytest.mark.asyncio
async def test_inspect_artifact_returns_stable_fields(tmp_path: Path) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "artifacts_inspect")
    api, _service = _artifact_api(artifact_store)
    artifact_store.save_artifact(_echo_artifact())

    result = await api.inspect_artifact(artifact_id="echo", version=1)

    assert result["id"] == "echo"
    assert result["version"] == 1
    assert result["title"] == "Echo"
    assert "plan" in result


@pytest.mark.asyncio
async def test_handler_delegation_for_inspect_artifact(tmp_path: Path) -> None:
    """WorkflowSurfaceHandlers.inspect_artifact delegates to WorkflowArtifactApi."""
    artifact_store = FileWorkflowArtifactStore(tmp_path / "artifacts_delegation")
    mcp_root = artifact_store.root / "delegation_mcp"
    service = WfMcpService(
        store=FileStore(mcp_root),
        artifact_store=artifact_store,
        draft_workspace_store=FileDraftWorkspaceStore(mcp_root),
    )
    artifact_store.save_artifact(_echo_artifact())

    h = WorkflowSurfaceHandlers(service)
    context = context_from_service(service)
    api = WorkflowArtifactApi(context)

    handler_result = await h.inspect_artifact(artifact_id="echo", version=1)
    api_result = await api.inspect_artifact(artifact_id="echo", version=1)

    assert handler_result["id"] == api_result["id"]
    assert handler_result["version"] == api_result["version"]
    assert handler_result["title"] == api_result["title"]


@pytest.mark.asyncio
async def test_delete_artifact_deletes_unreferenced_version(tmp_path: Path) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "artifacts_delete")
    api, _service = _artifact_api(artifact_store)
    artifact_store.save_artifact(_echo_artifact())

    result = await api.delete_artifact(artifact_id="echo", version=1)

    assert result["artifact_id"] == "echo"
    assert result["version"] == 1
    assert result["deleted"] is True
    assert result["blocked_by_deployments"] == []
    with pytest.raises(KeyError, match="unknown workflow artifact"):
        artifact_store.get_artifact("echo", 1)


@pytest.mark.asyncio
async def test_delete_artifact_rejects_referenced_version(tmp_path: Path) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "artifacts_delete_blocked")
    api, _service = _artifact_api(artifact_store)
    artifact_store.save_artifact(_echo_artifact())
    artifact_store.save_deployment(
        WorkflowDeployment(
            id="echo.default",
            artifact_id="echo",
            artifact_version=1,
        )
    )

    result = await api.delete_artifact(artifact_id="echo", version=1)

    assert result["artifact_id"] == "echo"
    assert result["version"] == 1
    assert result["deleted"] is False
    assert result["blocked_by_deployments"] == ["echo.default"]
    assert artifact_store.get_artifact("echo", 1).id == "echo"


def _api(root: Path) -> WorkflowApi:
    mcp_root = root / "mcp"
    service = WfMcpService(
        store=FileStore(mcp_root),
        artifact_store=FileWorkflowArtifactStore(root),
        draft_workspace_store=FileDraftWorkspaceStore(mcp_root),
    )
    return WorkflowApi(context_from_service(service))


@pytest.mark.asyncio
async def test_create_artifact_from_workspace_excludes_platform_sources_from_required_bindings(
    tmp_path: Path,
) -> None:
    api = _api(tmp_path)
    workspace = await api.create_draft_workspace_from_capability(
        workspace_id="constant_ws",
        capability_name="wf.std.constant",
        name="constant_value",
    )

    saved = await api.create_artifact_from_workspace(
        workspace_id=workspace["workspace_id"],
        artifact_id="constant_artifact",
        version=1,
        title="Constant Artifact",
        outcomes=["ok"],
    )

    assert saved["saved"] is True
    assert saved["required_logical_sources"] == []
    assert saved["suggested_bindings"] == {}
