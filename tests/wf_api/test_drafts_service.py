from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel

from tests.wf_mcp.test_support import echo_tool
from wf_api.drafts import WorkflowDraftApi
from wf_artifacts import FileDraftWorkspaceStore, FileWorkflowArtifactStore
from wf_authoring import node
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


class _Snapshot(BaseModel):
    clicked: bool


class _SnapshotOutput(BaseModel):
    after: _Snapshot


class _SnapshotInput(BaseModel):
    pass


@node(name="snapshot_tool")
def _snapshot_tool(payload: _SnapshotInput) -> _SnapshotOutput:
    return _SnapshotOutput(after=_Snapshot(clicked=True))


def _draft_api(
    artifact_store: FileWorkflowArtifactStore,
    *,
    register_echo: bool = False,
) -> tuple[WorkflowDraftApi, WfMcpService]:
    mcp_root = artifact_store.root / "drafts_mcp" / str(id(artifact_store))
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
    return WorkflowDraftApi(context), service


@pytest.mark.asyncio
async def test_patch_draft_applies_json_patch(tmp_path: Path) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_patch")
    api, _service = _draft_api(artifact_store)

    result = await api.patch_draft(
        draft=_echo_draft(),
        patch=[
            {
                "op": "replace",
                "path": "/steps/echo/input/0/target/parts/0",
                "value": "message",
            }
        ],
    )

    assert result["status"] == "valid"
    assert result["draft"]["steps"]["echo"]["input"][0]["target"] == {
        "root": "local",
        "parts": ["message"],
    }


@pytest.mark.asyncio
async def test_create_draft_workspace_creates_workspace(tmp_path: Path) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_create_workspace")
    api, _service = _draft_api(artifact_store)

    result = await api.create_draft_workspace(
        workspace_id="echo_ws",
        title="Echo Workspace",
        draft=_echo_draft(),
    )

    assert result["workspace_id"] == "echo_ws"
    assert result["revision"] == 1
    fetched = await api.get_draft_workspace(workspace_id="echo_ws", include_draft=True)

    assert fetched["workspace_id"] == "echo_ws"
    assert fetched["title"] == "Echo Workspace"
    assert fetched["draft"]["steps"]["echo"]["use"] == "demo.personal.echo_tool"


@pytest.mark.asyncio
async def test_list_draft_workspaces_returns_sorted_summaries_without_drafts(
    tmp_path: Path,
) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_list_workspaces")
    api, _service = _draft_api(artifact_store)
    await api.create_draft_workspace(
        workspace_id="b_draft",
        title="B Draft",
        draft=_echo_draft(),
    )

    await api.create_draft_workspace(
        workspace_id="a_draft",
        title="A Draft",
        draft=_echo_draft(),
    )

    result = await api.list_draft_workspaces()

    assert [workspace["workspace_id"] for workspace in result["workspaces"]] == [
        "a_draft",
        "b_draft",
    ]
    assert result["workspaces"][0]["title"] == "A Draft"
    assert "draft" not in result["workspaces"][0]


@pytest.mark.asyncio
async def test_delete_draft_workspace_is_idempotent(tmp_path: Path) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_delete_workspace")
    api, _service = _draft_api(artifact_store)
    await api.create_draft_workspace(
        workspace_id="echo_ws",
        draft=_echo_draft(),
    )

    deleted = await api.delete_draft_workspace(workspace_id="echo_ws")
    deleted_again = await api.delete_draft_workspace(workspace_id="echo_ws")
    listed = await api.list_draft_workspaces()

    assert deleted["workspace_id"] == "echo_ws"
    assert deleted["deleted"] is True
    assert deleted["status"] == "deleted"
    assert deleted_again["workspace_id"] == "echo_ws"
    assert deleted_again["deleted"] is False
    assert deleted_again["status"] == "not_found"
    assert listed["workspaces"] == []


@pytest.mark.asyncio
async def test_patch_draft_workspace_updates_revision(tmp_path: Path) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_patch_workspace")
    api, _service = _draft_api(artifact_store)
    await api.create_draft_workspace(
        workspace_id="echo_ws",
        draft=_echo_draft(),
    )

    patched = await api.patch_draft_workspace(
        workspace_id="echo_ws",
        revision=1,
        patch=[{"op": "replace", "path": "/name", "value": "echo_v2"}],
    )

    assert patched["revision"] == 2
    assert patched["status"] == "valid"


@pytest.mark.asyncio
async def test_draft_workspace_patch_helpers_update_revision_and_bindings(
    tmp_path: Path,
) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_patch_helpers")
    api, _service = _draft_api(artifact_store)
    await api.create_draft_workspace(
        workspace_id="echo_ws",
        draft=_echo_draft(),
    )

    named = await api.set_draft_name(
        workspace_id="echo_ws",
        revision=1,
        name="echo_v2",
    )
    routed = await api.set_draft_route(
        workspace_id="echo_ws",
        revision=2,
        step_id="echo",
        outcome="error",
        target="__end__",
    )
    input_mapped = await api.set_step_input_map(
        workspace_id="echo_ws",
        revision=3,
        step_id="echo",
        input_map={"input.text": "message"},
    )

    output_mapped = await api.set_step_output_map(
        workspace_id="echo_ws",
        revision=4,
        step_id="echo",
        output_map={"echoed": "state.echoed"},
    )
    fetched = await api.get_draft_workspace(workspace_id="echo_ws", include_draft=True)

    assert named["revision"] == 2
    assert routed["revision"] == 3
    assert input_mapped["revision"] == 4
    assert output_mapped["revision"] == 5
    assert fetched["draft"]["name"] == "echo_v2"
    assert fetched["draft"]["routes"]["echo"]["error"] == "__end__"
    assert fetched["draft"]["steps"]["echo"]["input"] == [
        {
            "target": {"root": "local", "parts": ["message"]},
            "path": {"root": "input", "parts": ["text"]},
        }
    ]
    assert fetched["draft"]["steps"]["echo"]["output"] == [
        {
            "source": {"root": "local", "parts": ["echoed"]},
            "target": {"root": "state", "parts": ["echoed"]},
        }
    ]


@pytest.mark.asyncio
async def test_step_map_helpers_merge_with_existing_bindings(tmp_path: Path) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_patch_helper_merge")
    api, _service = _draft_api(artifact_store)
    await api.create_draft_workspace(
        workspace_id="echo_ws",
        draft=_echo_draft(),
    )

    input_mapped = await api.set_step_input_map(
        workspace_id="echo_ws",
        revision=1,
        step_id="echo",
        input_map={"input.extra": "extra"},
        merge=True,
    )
    output_mapped = await api.set_step_output_map(
        workspace_id="echo_ws",
        revision=2,
        step_id="echo",
        output_map={"extra": "state.extra"},
        merge=True,
    )
    replaced = await api.set_step_input_map(
        workspace_id="echo_ws",
        revision=3,
        step_id="echo",
        input_map={"input.final": "final"},
    )
    fetched = await api.get_draft_workspace(workspace_id="echo_ws", include_draft=True)

    assert input_mapped["revision"] == 2
    assert output_mapped["revision"] == 3
    assert replaced["revision"] == 4
    assert fetched["draft"]["steps"]["echo"]["input"] == [
        {
            "target": {"root": "local", "parts": ["final"]},
            "path": {"root": "input", "parts": ["final"]},
        }
    ]
    assert fetched["draft"]["steps"]["echo"]["output"] == [
        {
            "source": {"root": "local", "parts": ["echoed"]},
            "target": {"root": "state", "parts": ["echoed"]},
        },
        {
            "source": {"root": "local", "parts": ["extra"]},
            "target": {"root": "state", "parts": ["extra"]},
        },
    ]


@pytest.mark.asyncio
async def test_validate_draft_workspace_refreshes_status(tmp_path: Path) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_validate_workspace")
    api, service = _draft_api(artifact_store, register_echo=True)
    draft = _echo_draft()
    draft["routes"]["echo"] = {"typo": "__end__"}
    await api.create_draft_workspace(
        workspace_id="echo_ws",
        draft=draft,
    )

    payload = await api.validate_draft_workspace(workspace_id="echo_ws")
    fetched = await api.get_draft_workspace(workspace_id="echo_ws")

    assert payload["revision"] == 1
    assert payload["status"] == "invalid"
    assert payload["diagnostics"][0]["code"] == "unknown_outcome"
    assert fetched["status"] == "invalid"


@pytest.mark.asyncio
async def test_create_minimal_draft_workspace_minimal_success_path(
    tmp_path: Path,
) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_minimal_workspace")
    api, _service = _draft_api(artifact_store, register_echo=True)

    result = await api.create_minimal_draft_workspace(
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

    assert result["workspace_id"] == "echo_minimal"
    fetched = await api.get_draft_workspace(
        workspace_id="echo_minimal", include_draft=True
    )
    assert fetched["draft"]["routes"]["call"]["ok"] == "__end__"
    assert fetched["draft"]["steps"]["call"]["use"] == "demo.personal.echo_tool"


@pytest.mark.asyncio
async def test_delegation_smoke_validate_draft_equivalence(tmp_path: Path) -> None:
    """WorkflowSurfaceHandlers.validate_draft delegates to WorkflowDraftApi."""
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_delegation_smoke")
    mcp_root = artifact_store.root / "delegation_mcp"
    service = WfMcpService(
        store=FileStore(mcp_root),
        artifact_store=artifact_store,
        draft_workspace_store=FileDraftWorkspaceStore(mcp_root),
    )
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_specs("demo.personal", echo_tool)

    h = WorkflowSurfaceHandlers(service)
    context = context_from_service(service)
    api = WorkflowDraftApi(context)
    draft = _echo_draft()

    handler_result = await h.validate_draft(draft=draft)
    api_result = await api.validate_draft(draft=draft)

    assert handler_result["status"] == api_result["status"]
    assert handler_result["diagnostics"] == api_result["diagnostics"]
    assert (
        handler_result["compiled_plan"]["nodes"] == api_result["compiled_plan"]["nodes"]
    )


@pytest.mark.asyncio
async def test_add_state_schema_from_output_copies_output_property_defs(
    tmp_path: Path,
) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_state_from_output")
    api, service = _draft_api(artifact_store)
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_specs("demo.personal", _snapshot_tool)
    await api.create_draft_workspace(
        workspace_id="snapshot_ws",
        draft={
            "name": "snapshot",
            "input_schema": {"type": "object", "properties": {}},
            "state_schema": {"type": "object", "properties": {}},
            "output_schema": {"type": "object", "properties": {}},
            "start": "snap",
            "steps": {
                "snap": {
                    "use": "demo.personal.snapshot_tool",
                    "input": [],
                    "output": [],
                }
            },
            "routes": {"snap": {"ok": "__end__"}},
        },
    )

    updated = await api.add_state_schema_from_output(
        workspace_id="snapshot_ws",
        revision=1,
        step_id="snap",
        output_field="after",
        state_path="state.after",
    )
    fetched = await api.get_draft_workspace(
        workspace_id="snapshot_ws",
        include_draft=True,
    )

    state_schema = fetched["draft"]["state_schema"]
    assert updated["revision"] == 2
    assert state_schema["properties"]["after"]["$ref"] == "#/$defs/_Snapshot"
    assert state_schema["$defs"]["_Snapshot"]["properties"]["clicked"] == {
        "title": "Clicked",
        "type": "boolean",
    }


@pytest.mark.asyncio
async def test_add_state_schema_from_output_rejects_nested_state_path(
    tmp_path: Path,
) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_nested_state_output")
    api, service = _draft_api(artifact_store)
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_specs("demo.personal", _snapshot_tool)
    await api.create_draft_workspace(
        workspace_id="snapshot_ws",
        draft={
            "name": "snapshot",
            "input_schema": {"type": "object", "properties": {}},
            "state_schema": {"type": "object", "properties": {}},
            "output_schema": {"type": "object", "properties": {}},
            "start": "snap",
            "steps": {
                "snap": {
                    "use": "demo.personal.snapshot_tool",
                    "input": [],
                    "output": [],
                }
            },
            "routes": {"snap": {"ok": "__end__"}},
        },
    )

    with pytest.raises(ValueError, match="state_path must name one root field"):
        await api.add_state_schema_from_output(
            workspace_id="snapshot_ws",
            revision=1,
            step_id="snap",
            output_field="after",
            state_path="state.after.clicked",
        )
