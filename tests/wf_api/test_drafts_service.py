from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel

from tests.wf_mcp.test_support import echo_tool
from wf_api.draft_authoring import DraftOutcomeRef, WorkflowDraftAuthoringApi
from wf_api.drafts import WorkflowDraftApi
from wf_api.service import WorkflowApi
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


@node(name="snapshot_tool", outcomes=("ok", "skipped"))
def _snapshot_tool(payload: _SnapshotInput) -> _SnapshotOutput:
    return _SnapshotOutput(after=_Snapshot(clicked=True))


def _draft_api(
    artifact_store: FileWorkflowArtifactStore,
    *,
    register_echo: bool = False,
) -> tuple[WorkflowDraftApi, WfMcpService, WorkflowDraftAuthoringApi]:
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
    return (
        WorkflowDraftApi(context),
        service,
        WorkflowDraftAuthoringApi(context, WorkflowDraftApi(context)),
    )


@pytest.mark.asyncio
async def test_patch_draft_applies_json_patch(tmp_path: Path) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_patch")
    api, _service, _authoring = _draft_api(artifact_store, register_echo=True)

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

    assert result["status"] == "invalid"
    assert result["draft"]["steps"]["echo"]["input"][0]["target"] == {
        "root": "local",
        "parts": ["message"],
    }


@pytest.mark.asyncio
async def test_create_draft_workspace_creates_workspace(tmp_path: Path) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_create_workspace")
    api, _service, _authoring = _draft_api(artifact_store)

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
    api, _service, _authoring = _draft_api(artifact_store)
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
    api, _service, _authoring = _draft_api(artifact_store)
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
    api, _service, _authoring = _draft_api(artifact_store, register_echo=True)
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
    api, _service, _authoring = _draft_api(artifact_store)
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
            "target": "message",
            "path": "input.text",
        }
    ]
    assert fetched["draft"]["steps"]["echo"]["output"] == [
        {
            "source": "echoed",
            "target": "state.echoed",
        }
    ]


@pytest.mark.asyncio
async def test_step_map_helpers_merge_with_existing_bindings(tmp_path: Path) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_patch_helper_merge")
    api, _service, _authoring = _draft_api(artifact_store)
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
            "target": "final",
            "path": "input.final",
        }
    ]
    assert fetched["draft"]["steps"]["echo"]["output"] == [
        {
            "source": "echoed",
            "target": "state.echoed",
        },
        {
            "source": "extra",
            "target": "state.extra",
        },
    ]


@pytest.mark.asyncio
async def test_validate_draft_workspace_refreshes_status(tmp_path: Path) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_validate_workspace")
    api, service, authoring = _draft_api(artifact_store, register_echo=True)
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
    assert payload["diagnostics"][0]["code"] in (
        "unknown_outcome",
        "undeclared_edge_outcome",
    )
    assert fetched["status"] == "invalid"


@pytest.mark.asyncio
async def test_validate_draft_workspace_suggests_bind_output_to_state(
    tmp_path: Path,
) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_repair_hint")
    api, service, authoring = _draft_api(artifact_store)
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
                    "output": [
                        {
                            "source": {"root": "local", "parts": ["after"]},
                            "target": {"root": "state", "parts": ["after"]},
                        }
                    ],
                }
            },
            "routes": {"snap": {"ok": "__end__"}},
        },
    )

    payload = await api.validate_draft_workspace(workspace_id="snapshot_ws")

    diagnostic = payload["diagnostics"][0]
    assert diagnostic["code"] == "invalid_destination_path"
    assert diagnostic["step_id"] == "snap"
    assert diagnostic["repair_hint"] == (
        "wf draft bind-output-to-state snapshot_ws --revision 1 "
        "--step snap --output after --state state.after"
    )


@pytest.mark.asyncio
async def test_patch_draft_workspace_validates_new_use_step_with_context_specs(
    tmp_path: Path,
) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_patch_new_use")
    api, service, authoring = _draft_api(artifact_store, register_echo=True)
    service.register_specs("demo.personal", echo_tool, _snapshot_tool)
    await api.create_draft_workspace(
        workspace_id="echo_ws",
        draft=_echo_draft(),
    )

    patched = await api.patch_draft_workspace(
        workspace_id="echo_ws",
        revision=1,
        patch=[
            {
                "op": "add",
                "path": "/steps/snap",
                "value": {
                    "use": "demo.personal.snapshot_tool",
                    "input": [],
                    "output": [
                        {
                            "source": {"root": "local", "parts": ["after"]},
                            "target": {"root": "state", "parts": ["after"]},
                        }
                    ],
                },
            },
            {
                "op": "replace",
                "path": "/routes/echo/ok",
                "value": "snap",
            },
            {
                "op": "add",
                "path": "/routes/snap",
                "value": {"ok": "__end__"},
            },
        ],
    )

    diagnostic = patched["diagnostics"][0]
    assert patched["status"] == "invalid"
    assert diagnostic["code"] == "invalid_destination_path"
    assert diagnostic["step_id"] == "snap"
    assert diagnostic["details"] == {
        "output_field": "after",
        "state_path": "state.after",
    }


@pytest.mark.asyncio
async def test_create_minimal_draft_workspace_minimal_success_path(
    tmp_path: Path,
) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_minimal_workspace")
    api, _service, authoring = _draft_api(artifact_store, register_echo=True)

    result = await authoring.create_minimal_draft_workspace(
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
async def test_facade_delegates_semantic_authoring_to_authoring_service(
    tmp_path: Path,
) -> None:
    """WorkflowApi constructs a sibling WorkflowDraftAuthoringApi."""
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_facade_delegation")
    mcp_root = artifact_store.root / "facade_mcp"
    service = WfMcpService(
        store=FileStore(mcp_root),
        artifact_store=artifact_store,
        draft_workspace_store=FileDraftWorkspaceStore(mcp_root),
    )
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_specs("demo.personal", echo_tool, _snapshot_tool)

    context = context_from_service(service)
    facade = WorkflowApi(context)

    assert facade.draft_authoring is not None
    assert isinstance(facade.draft_authoring, WorkflowDraftAuthoringApi)

    await facade.create_draft_workspace(
        workspace_id="ws1",
        draft=_echo_draft(),
    )
    result = await facade.bind_draft(
        workspace_id="ws1",
        revision=1,
        step_id="echo",
        source_path="local.echoed",
        target_path="state.echoed",
    )
    assert result["revision"] == 2


@pytest.mark.asyncio
@pytest.mark.asyncio
async def test_bind_draft_workflow_input_to_step_input_projects_input_schema(
    tmp_path: Path,
) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_bind_input")
    api, service, authoring = _draft_api(artifact_store, register_echo=True)
    draft = {**_echo_draft(), "input_schema": {"type": "object", "properties": {}}}
    await api.create_draft_workspace(
        workspace_id="bind_ws",
        draft=draft,
    )

    result = await authoring.bind_draft(
        workspace_id="bind_ws",
        revision=1,
        step_id="echo",
        source_path="input.text",
        target_path="local.text",
    )
    workspace = await api.get_draft_workspace(workspace_id="bind_ws", include_draft=True)

    assert result["revision"] == 2
    assert workspace["draft"]["input_schema"]["properties"]["text"]["type"] == "string"
    assert workspace["draft"]["steps"]["echo"]["input"] == [
        {"target": "text", "path": "input.text"}
    ]


@pytest.mark.asyncio
async def test_bind_draft_output_to_nested_state_projects_state_schema(
    tmp_path: Path,
) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_bind_output_nested")
    api, service, authoring = _draft_api(artifact_store, register_echo=True)
    service.register_specs("demo.personal", _snapshot_tool)
    await api.create_draft_workspace(
        workspace_id="snapshot_ws",
        draft={
            "name": "snapshot",
            "input_schema": {"type": "object", "properties": {}},
            "state_schema": {"type": "object", "properties": {}},
            "output_schema": {"type": "object", "properties": {}},
            "start": "snap",
            "steps": {"snap": {"use": "demo.personal.snapshot_tool", "input": [], "output": []}},
            "routes": {"snap": {"ok": "__end__"}},
        },
    )

    result = await authoring.bind_draft(
        workspace_id="snapshot_ws",
        revision=1,
        step_id="snap",
        source_path="local.after",
        target_path="state.session.after",
    )
    workspace = await api.get_draft_workspace(workspace_id="snapshot_ws", include_draft=True)

    assert result["revision"] == 2
    assert (
        workspace["draft"]["state_schema"]["properties"]["session"]["properties"]["after"]["$ref"]
        == "#/$defs/_Snapshot"
    )
    assert workspace["draft"]["steps"]["snap"]["output"] == [
        {"source": "after", "target": "state.session.after"}
    ]


@pytest.mark.asyncio
async def test_bind_draft_rejects_unsupported_direction(tmp_path: Path) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_bind_bad_direction")
    api, _service, authoring = _draft_api(artifact_store, register_echo=True)
    await api.create_draft_workspace(workspace_id="bind_ws", draft=_echo_draft())

    with pytest.raises(ValueError, match="unsupported bind direction"):
        await authoring.bind_draft(
            workspace_id="bind_ws",
            revision=1,
            step_id="echo",
            source_path="input.message",
            target_path="state.message",
        )


@pytest.mark.asyncio
async def test_add_step_from_capability_wires_route_inputs_and_state_outputs(
    tmp_path: Path,
) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_add_step")
    api, service, authoring = _draft_api(artifact_store, register_echo=True)
    service.register_specs("demo.personal", echo_tool, _snapshot_tool)
    await api.create_draft_workspace(
        workspace_id="echo_ws",
        draft=_echo_draft(),
    )

    result = await authoring.add_step_from_capability(
        workspace_id="echo_ws",
        revision=1,
        step_id="snap",
        capability_name="demo.personal.snapshot_tool",
        route_from_step="echo",
        route_from_outcome="ok",
        routes={"ok": "__end__", "skipped": "__end__"},
        input_map={},
        bind_outputs={"after": "state.after"},
    )

    assert result["revision"] == 2
    assert result["status"] == "valid"
    fetched = await api.get_draft_workspace(workspace_id="echo_ws", include_draft=True)
    draft = fetched["draft"]
    assert draft["steps"]["snap"]["use"] == "demo.personal.snapshot_tool"
    assert draft["routes"]["echo"]["ok"] == "snap"
    assert draft["routes"]["snap"]["ok"] == "__end__"
    assert draft["steps"]["snap"]["output"] == [
        {
            "source": "after",
            "target": "state.after",
        }
    ]
    assert draft["state_schema"]["properties"]["after"]["$ref"] == "#/$defs/_Snapshot"
    assert draft["state_schema"]["$defs"]["_Snapshot"]["properties"]["clicked"] == {
        "title": "Clicked",
        "type": "boolean",
    }


@pytest.mark.asyncio
async def test_add_step_from_capability_rejects_existing_step_id(
    tmp_path: Path,
) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_add_step_duplicate")
    api, _service, authoring = _draft_api(artifact_store, register_echo=True)
    await api.create_draft_workspace(
        workspace_id="echo_ws",
        draft=_echo_draft(),
    )

    with pytest.raises(ValueError, match="draft step 'echo' already exists"):
        await authoring.add_step_from_capability(
            workspace_id="echo_ws",
            revision=1,
            step_id="echo",
            capability_name="demo.personal.echo_tool",
            route_from_step=None,
            route_from_outcome="ok",
            routes={"ok": "__end__"},
            input_map={},
            bind_outputs={},
        )


@pytest.mark.asyncio
async def test_branch_draft_updates_routes_atomically(tmp_path: Path) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_branch")
    api, _service, authoring = _draft_api(artifact_store, register_echo=True)
    await api.create_draft_workspace(
        workspace_id="branching",
        draft={
            "name": "branching",
            "input_schema": {"type": "object", "properties": {}},
            "state_schema": {"type": "object", "properties": {}},
            "output_schema": {"type": "object", "properties": {}},
            "start": "classify",
            "steps": {
                "classify": {
                    "use": "demo.personal.echo_tool",
                    "input": [],
                    "output": [],
                },
                "tool_error": {
                    "use": "demo.personal.echo_tool",
                    "input": [],
                    "output": [],
                },
            },
            "routes": {
                "classify": {"ok": "classify"},
                "tool_error": {"ok": "__end__"},
            },
        },
    )

    result = await authoring.branch_draft(
        workspace_id="branching",
        revision=1,
        step_id="classify",
        routes={"ok": "classify", "error": "tool_error"},
    )
    assert result["revision"] == 2
    workspace = await api.get_draft_workspace(
        workspace_id="branching", include_draft=True
    )
    assert workspace["draft"]["routes"]["classify"] == {
        "ok": "classify",
        "error": "tool_error",
    }
    assert "tool_error" in workspace["draft"]["steps"]


@pytest.mark.asyncio
async def test_handle_draft_updates_multiple_source_outcomes(tmp_path: Path) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_handle")
    api, _service, authoring = _draft_api(artifact_store, register_echo=True)
    await api.create_draft_workspace(
        workspace_id="handling",
        draft={
            "name": "handling",
            "input_schema": {"type": "object", "properties": {}},
            "state_schema": {"type": "object", "properties": {}},
            "output_schema": {"type": "object", "properties": {}},
            "start": "lookup",
            "steps": {
                "lookup": {
                    "use": "demo.personal.echo_tool",
                    "input": [],
                    "output": [],
                },
                "transform": {
                    "use": "demo.personal.echo_tool",
                    "input": [],
                    "output": [],
                },
            },
            "routes": {
                "lookup": {"ok": "transform", "error": "lookup"},
                "transform": {"ok": "__end__", "error": "transform"},
            },
        },
    )

    result = await authoring.handle_draft(
        workspace_id="handling",
        revision=1,
        branches=[
            DraftOutcomeRef(step_id="lookup", outcome="error"),
            DraftOutcomeRef(step_id="transform", outcome="error"),
        ],
        target="__end__",
    )
    assert result["revision"] == 2
    workspace = await api.get_draft_workspace(
        workspace_id="handling", include_draft=True
    )
    assert workspace["draft"]["routes"]["lookup"]["error"] == "__end__"
    assert workspace["draft"]["routes"]["transform"]["error"] == "__end__"
    assert workspace["draft"]["routes"]["lookup"]["ok"] == "transform"
    assert workspace["draft"]["routes"]["transform"]["ok"] == "__end__"


@pytest.mark.asyncio
async def test_branch_draft_no_change_when_routes_unchanged(tmp_path: Path) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_branch_noop")
    api, _service, authoring = _draft_api(artifact_store, register_echo=True)
    await api.create_draft_workspace(
        workspace_id="noop_ws",
        draft=_echo_draft(),
    )
    before = await api.get_draft_workspace(workspace_id="noop_ws", include_draft=True)

    result = await authoring.branch_draft(
        workspace_id="noop_ws",
        revision=1,
        step_id="echo",
        routes={"ok": "__end__"},
    )
    after = await api.get_draft_workspace(workspace_id="noop_ws", include_draft=True)
    assert result["revision"] == 1
    assert after == before


@pytest.mark.asyncio
async def test_branch_draft_no_change_still_checks_revision(tmp_path: Path) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_branch_noop_stale")
    api, _service, authoring = _draft_api(artifact_store, register_echo=True)
    await api.create_draft_workspace(
        workspace_id="noop_ws",
        draft=_echo_draft(),
    )

    result = await authoring.branch_draft(
        workspace_id="noop_ws",
        revision=2,
        step_id="echo",
        routes={"ok": "__end__"},
    )

    assert result["status"] == "conflict"
    assert result["diagnostics"][0]["code"] == "revision_conflict"


@pytest.mark.asyncio
async def test_handle_draft_empty_branches_noop(tmp_path: Path) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_handle_noop")
    api, _service, authoring = _draft_api(artifact_store, register_echo=True)
    await api.create_draft_workspace(
        workspace_id="noop_ws",
        draft=_echo_draft(),
    )
    before = await api.get_draft_workspace(workspace_id="noop_ws", include_draft=True)

    result = await authoring.handle_draft(
        workspace_id="noop_ws",
        revision=1,
        branches=[],
        target="fail",
    )
    after = await api.get_draft_workspace(workspace_id="noop_ws", include_draft=True)
    assert result["revision"] == 1
    assert after == before


@pytest.mark.asyncio
async def test_handle_draft_no_change_still_checks_revision(tmp_path: Path) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_handle_noop_stale")
    api, _service, authoring = _draft_api(artifact_store, register_echo=True)
    await api.create_draft_workspace(
        workspace_id="noop_ws",
        draft=_echo_draft(),
    )

    result = await authoring.handle_draft(
        workspace_id="noop_ws",
        revision=2,
        branches=[],
        target="fail",
    )

    assert result["status"] == "conflict"
    assert result["diagnostics"][0]["code"] == "revision_conflict"


@pytest.mark.asyncio
async def test_add_step_from_capability_infers_single_outcome_route(
    tmp_path: Path,
) -> None:
    """One declared outcome named 'done', no routes supplied -> routes to __end__."""
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_single_outcome")
    api, service, authoring = _draft_api(artifact_store, register_echo=True)
    service.register_specs("demo.personal", echo_tool)
    await api.create_draft_workspace(
        workspace_id="single",
        draft=_echo_draft(),
    )

    result = await authoring.add_step_from_capability(
        workspace_id="single",
        revision=1,
        step_id="done_step",
        capability_name="demo.personal.echo_tool",
    )
    assert result["revision"] == 2
    workspace = await api.get_draft_workspace(workspace_id="single", include_draft=True)
    assert workspace["draft"]["routes"]["done_step"] == {"ok": "__end__"}


@pytest.mark.asyncio
async def test_add_step_from_capability_requires_complete_routes_for_multi_outcome(
    tmp_path: Path,
) -> None:
    """Multiple declared outcomes with incomplete explicit routes raises ValueError."""
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_multi_outcome")
    api, service, authoring = _draft_api(artifact_store, register_echo=True)
    service.register_specs("demo.personal", echo_tool, _snapshot_tool)
    await api.create_draft_workspace(
        workspace_id="multi",
        draft=_echo_draft(),
    )

    with pytest.raises(ValueError, match="missing routes"):
        await authoring.add_step_from_capability(
            workspace_id="multi",
            revision=1,
            step_id="snap",
            capability_name="demo.personal.snapshot_tool",
            routes={"ok": "__end__"},
        )


@pytest.mark.asyncio
async def test_add_step_from_capability_rejects_unknown_routes_for_multi_outcome(
    tmp_path: Path,
) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_unknown_outcome")
    api, service, authoring = _draft_api(artifact_store, register_echo=True)
    service.register_specs("demo.personal", _snapshot_tool)
    await api.create_draft_workspace(
        workspace_id="unknown_multi",
        draft=_echo_draft(),
    )

    with pytest.raises(ValueError, match="unknown routes"):
        await authoring.add_step_from_capability(
            workspace_id="unknown_multi",
            revision=1,
            step_id="snap",
            capability_name="demo.personal.snapshot_tool",
            routes={"ok": "__end__", "skipped": "__end__", "typo": "__end__"},
        )


@pytest.mark.asyncio
async def test_compile_draft_workspace_returns_compiled_plan(tmp_path: Path) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_compile")
    api, _service, _authoring = _draft_api(artifact_store, register_echo=True)
    await api.create_draft_workspace(
        workspace_id="compile_me",
        draft=_echo_draft(),
    )
    before = await api.get_draft_workspace(
        workspace_id="compile_me", include_draft=True
    )
    result = await api.compile_draft_workspace(workspace_id="compile_me")
    after = await api.get_draft_workspace(workspace_id="compile_me", include_draft=True)
    assert result["compiled_plan"]["name"] == "echo"
    assert result["required_capabilities"]
    assert after == before


@pytest.mark.asyncio
async def test_compile_draft_workspace_invalid_returns_diagnostics(
    tmp_path: Path,
) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_compile_invalid")
    api, _service, _authoring = _draft_api(artifact_store, register_echo=True)
    draft = _echo_draft()
    draft["routes"]["echo"] = {"typo": "__end__"}
    await api.create_draft_workspace(
        workspace_id="invalid_ws",
        draft=draft,
    )
    result = await api.compile_draft_workspace(workspace_id="invalid_ws")
    assert result["status"] == "invalid"
    assert "compiled_plan" not in result
    assert result["diagnostics"]
