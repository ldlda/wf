from __future__ import annotations

import asyncio
from typing import Any

from wf_artifacts import FileWorkflowArtifactStore
from wf_api.drafts import WorkflowDraftApi
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


def _draft_api(
    artifact_store: FileWorkflowArtifactStore,
    *,
    register_echo: bool = False,
) -> tuple[WorkflowDraftApi, WfMcpService]:
    service = WfMcpService(
        store=FileStore(artifact_store.root / "drafts_mcp" / str(id(artifact_store))),
        artifact_store=artifact_store,
    )
    if register_echo:
        service.register_connection(
            ConnectionConfig(id="demo.personal", server="demo", account="personal")
        )
        service.register_specs("demo.personal", echo_tool)
    context = context_from_service(service)
    return WorkflowDraftApi(context), service


def test_patch_draft_applies_json_patch() -> None:
    artifact_store = FileWorkflowArtifactStore(local_temp_root() / "drafts_patch")
    api, _service = _draft_api(artifact_store)

    result = asyncio.run(
        api.patch_draft(
            draft=_echo_draft(),
            patch=[
                {
                    "op": "replace",
                    "path": "/steps/echo/input/0/target/parts/0",
                    "value": "message",
                }
            ],
        )
    )

    assert result["status"] == "valid"
    assert result["draft"]["steps"]["echo"]["input"][0]["target"] == {
        "root": "local",
        "parts": ["message"],
    }


def test_create_draft_workspace_creates_workspace() -> None:
    artifact_store = FileWorkflowArtifactStore(
        local_temp_root() / "drafts_create_workspace"
    )
    api, _service = _draft_api(artifact_store)

    result = asyncio.run(
        api.create_draft_workspace(
            workspace_id="echo_ws",
            title="Echo Workspace",
            draft=_echo_draft(),
        )
    )

    assert result["workspace_id"] == "echo_ws"
    assert result["revision"] == 1


def test_patch_draft_workspace_updates_revision() -> None:
    artifact_store = FileWorkflowArtifactStore(
        local_temp_root() / "drafts_patch_workspace"
    )
    api, _service = _draft_api(artifact_store)
    asyncio.run(
        api.create_draft_workspace(
            workspace_id="echo_ws",
            draft=_echo_draft(),
        )
    )

    patched = asyncio.run(
        api.patch_draft_workspace(
            workspace_id="echo_ws",
            revision=1,
            patch=[{"op": "replace", "path": "/name", "value": "echo_v2"}],
        )
    )

    assert patched["revision"] == 2
    assert patched["status"] == "valid"


def test_validate_draft_workspace_refreshes_status() -> None:
    artifact_store = FileWorkflowArtifactStore(
        local_temp_root() / "drafts_validate_workspace"
    )
    api, service = _draft_api(artifact_store, register_echo=True)
    draft = _echo_draft()
    draft["routes"]["echo"] = {"typo": "__end__"}
    asyncio.run(
        api.create_draft_workspace(
            workspace_id="echo_ws",
            draft=draft,
        )
    )

    payload = asyncio.run(api.validate_draft_workspace(workspace_id="echo_ws"))
    fetched = asyncio.run(api.get_draft_workspace(workspace_id="echo_ws"))

    assert payload["revision"] == 1
    assert payload["status"] == "invalid"
    assert payload["diagnostics"][0]["code"] == "unknown_outcome"
    assert fetched["status"] == "invalid"


def test_create_minimal_draft_workspace_with_error_route() -> None:
    artifact_store = FileWorkflowArtifactStore(
        local_temp_root() / "drafts_minimal_workspace"
    )
    api, _service = _draft_api(artifact_store, register_echo=True)

    result = asyncio.run(
        api.create_minimal_draft_workspace(
            workspace_id="echo_minimal",
            name="echo",
            capability_name="demo.personal.echo_tool",
            input_schema={
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
            state_schema={"fields": {"echoed": {"type": "string"}}},
            output_schema={
                "type": "object",
                "properties": {"echoed": {"type": "string"}},
                "required": ["echoed"],
            },
            input_map={"input.text": "text"},
            output_map={"echoed": "state.echoed"},
        )
    )

    assert result["workspace_id"] == "echo_minimal"
    fetched = asyncio.run(
        api.get_draft_workspace(workspace_id="echo_minimal", include_draft=True)
    )
    assert fetched["draft"]["routes"]["call"]["ok"] == "__end__"
    assert fetched["draft"]["steps"]["call"]["use"] == "demo.personal.echo_tool"


def test_delegation_smoke_validate_draft_equivalence() -> None:
    """WorkflowSurfaceHandlers.validate_draft delegates to WorkflowDraftApi."""
    artifact_store = FileWorkflowArtifactStore(
        local_temp_root() / "drafts_delegation_smoke"
    )
    service = WfMcpService(
        store=FileStore(artifact_store.root / "delegation_mcp"),
        artifact_store=artifact_store,
    )
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_specs("demo.personal", echo_tool)

    h = WorkflowSurfaceHandlers(service)
    context = context_from_service(service)
    api = WorkflowDraftApi(context)
    draft = _echo_draft()

    handler_result = asyncio.run(h.validate_draft(draft=draft))
    api_result = asyncio.run(api.validate_draft(draft=draft))

    assert handler_result["status"] == api_result["status"]
    assert handler_result["diagnostics"] == api_result["diagnostics"]
    assert (
        handler_result["compiled_plan"]["nodes"] == api_result["compiled_plan"]["nodes"]
    )
