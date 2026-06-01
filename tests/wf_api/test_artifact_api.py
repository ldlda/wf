"""Tests for wf_api.artifacts module."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from typing import Any

from wf_artifacts import FileWorkflowArtifactStore, RequiredCapability, WorkflowArtifact
from wf_api.artifacts import WorkflowArtifactApi
from wf_mcp.broker import WfMcpService
from wf_mcp.models import ConnectionConfig
from wf_mcp.storage import FileStore
from wf_mcp.workflow_surface import WorkflowSurfaceHandlers
from wf_mcp.broker.service.workflow_operation_context import context_from_service

from tests.wf_mcp.test_support import echo_tool, local_temp_root


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
    service = WfMcpService(
        store=FileStore(artifact_store.root / "artifacts_mcp" / str(id(artifact_store))),
        artifact_store=artifact_store,
    )
    if register_echo:
        service.register_connection(
            ConnectionConfig(id="demo.personal", server="demo", account="personal")
        )
        service.register_specs("demo.personal", echo_tool)
    context = context_from_service(service)
    return WorkflowArtifactApi(context), service


def test_save_artifact_stores_and_returns_saved() -> None:
    artifact_store = FileWorkflowArtifactStore(local_temp_root() / "artifacts_save")
    api, _service = _artifact_api(artifact_store)

    result = asyncio.run(api.save_artifact(_echo_artifact().model_dump(mode="json")))

    assert result["saved"] is True
    assert result["artifact_id"] == "echo"
    assert result["version"] == 1
    saved = artifact_store.get_artifact("echo", 1)
    assert saved.id == "echo"


def test_list_artifacts_returns_empty_page_without_artifact_store() -> None:
    artifact_store = FileWorkflowArtifactStore(local_temp_root() / "artifacts_no_store")
    _api, service = _artifact_api(artifact_store)
    context = replace(context_from_service(service), artifact_store=None)
    api = WorkflowArtifactApi(context)

    result = asyncio.run(api.list_artifacts())

    assert result["nodes"] == []
    assert result["next_cursor"] is None
    assert result["total"] == 0


def test_create_artifact_from_plan_saves_with_observed_node_specs() -> None:
    artifact_store = FileWorkflowArtifactStore(
        local_temp_root() / "artifacts_from_plan"
    )
    api, _service = _artifact_api(artifact_store, register_echo=True)

    result = asyncio.run(
        api.create_artifact_from_plan(
            artifact_id="echo",
            version=1,
            title="Echo",
            plan=_echo_artifact().plan,
            outcomes=("completed",),
        )
    )

    assert result["saved"] is True
    assert result["artifact_id"] == "echo"
    saved = artifact_store.get_artifact("echo", 1)
    assert saved.id == "echo"


def test_create_artifact_from_workspace_returns_saved_false_when_invalid() -> None:
    artifact_store = FileWorkflowArtifactStore(
        local_temp_root() / "artifacts_workspace_invalid"
    )
    api, service = _artifact_api(artifact_store, register_echo=True)
    draft = _echo_draft()
    draft["routes"]["echo"] = {"typo": "__end__"}
    from wf_api.drafts import WorkflowDraftApi

    context = context_from_service(service)
    drafts_api = WorkflowDraftApi(context)
    asyncio.run(
        drafts_api.create_draft_workspace(
            workspace_id="echo_ws",
            draft=draft,
        )
    )

    result = asyncio.run(
        api.create_artifact_from_workspace(
            workspace_id="echo_ws",
            artifact_id="echo",
            version=1,
            title="Echo",
            outcomes=("completed",),
        )
    )

    assert result["saved"] is False
    assert result["status"] == "invalid"


def test_create_wrapper_from_workspace_saves_kind_wrapper() -> None:
    artifact_store = FileWorkflowArtifactStore(
        local_temp_root() / "artifacts_wrapper_workspace"
    )
    api, service = _artifact_api(artifact_store, register_echo=True)
    from wf_api.drafts import WorkflowDraftApi

    context = context_from_service(service)
    drafts_api = WorkflowDraftApi(context)
    asyncio.run(
        drafts_api.create_draft_workspace(
            workspace_id="echo_ws",
            draft=_echo_draft(),
        )
    )

    result = asyncio.run(
        api.create_wrapper_from_workspace(
            workspace_id="echo_ws",
            artifact_id="echo_wrapper",
            version=1,
            title="Echo Wrapper",
            outcomes=("completed",),
        )
    )

    assert result["saved"] is True
    saved = artifact_store.get_artifact("echo_wrapper", 1)
    assert saved.kind == "wrapper"


def test_inspect_artifact_returns_stable_fields() -> None:
    artifact_store = FileWorkflowArtifactStore(
        local_temp_root() / "artifacts_inspect"
    )
    api, _service = _artifact_api(artifact_store)
    artifact_store.save_artifact(_echo_artifact())

    result = asyncio.run(api.inspect_artifact(artifact_id="echo", version=1))

    assert result["id"] == "echo"
    assert result["version"] == 1
    assert result["title"] == "Echo"
    assert "plan" in result


def test_handler_delegation_for_inspect_artifact() -> None:
    """WorkflowSurfaceHandlers.inspect_artifact delegates to WorkflowArtifactApi."""
    artifact_store = FileWorkflowArtifactStore(
        local_temp_root() / "artifacts_delegation"
    )
    service = WfMcpService(
        store=FileStore(artifact_store.root / "delegation_mcp"),
        artifact_store=artifact_store,
    )
    artifact_store.save_artifact(_echo_artifact())

    h = WorkflowSurfaceHandlers(service)
    context = context_from_service(service)
    api = WorkflowArtifactApi(context)

    handler_result = asyncio.run(h.inspect_artifact(artifact_id="echo", version=1))
    api_result = asyncio.run(api.inspect_artifact(artifact_id="echo", version=1))

    assert handler_result["id"] == api_result["id"]
    assert handler_result["version"] == api_result["version"]
    assert handler_result["title"] == api_result["title"]
