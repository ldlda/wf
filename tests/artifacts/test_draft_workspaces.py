from __future__ import annotations

from typing import Any

from wf_artifacts import (
    FileDraftWorkspaceStore,
    WorkflowDraftWorkspace,
    create_draft_workspace,
    get_draft_workspace,
    patch_draft_workspace,
    summarize_draft_workspace,
)


def test_draft_workspace_stores_mutable_draft_with_revision() -> None:
    workspace = WorkflowDraftWorkspace(
        id="echo_draft",
        revision=1,
        title="Echo Draft",
        draft=_draft(),
        status="valid",
        diagnostics=[],
        created_at_epoch_ms=100,
        updated_at_epoch_ms=100,
    )

    assert workspace.id == "echo_draft"
    assert workspace.revision == 1
    assert workspace.draft["steps"]["echo"]["use"] == "demo.echo"


def test_draft_workspace_summary_is_compact() -> None:
    workspace = WorkflowDraftWorkspace(
        id="echo_draft",
        revision=3,
        draft=_draft(),
        status="valid",
        diagnostics=[],
        created_at_epoch_ms=100,
        updated_at_epoch_ms=200,
    )

    summary = summarize_draft_workspace(workspace)

    assert summary["workspace_id"] == "echo_draft"
    assert summary["revision"] == 3
    assert summary["status"] == "valid"
    assert summary["summary"]["name"] == "echo"
    assert summary["summary"]["steps"] == ["echo"]
    assert "draft" not in summary


def test_file_draft_workspace_store_round_trips_workspace(tmp_path) -> None:
    store = FileDraftWorkspaceStore(tmp_path)
    workspace = WorkflowDraftWorkspace(
        id="echo_draft",
        revision=1,
        draft=_draft(),
        status="valid",
        diagnostics=[],
        created_at_epoch_ms=100,
        updated_at_epoch_ms=100,
    )

    store.save_workspace(workspace)
    loaded = store.get_workspace("echo_draft")

    assert loaded == workspace


def test_file_draft_workspace_store_lists_workspaces(tmp_path) -> None:
    store = FileDraftWorkspaceStore(tmp_path)
    store.save_workspace(
        WorkflowDraftWorkspace(
            id="b",
            revision=1,
            draft=_draft(),
            status="valid",
            diagnostics=[],
            created_at_epoch_ms=100,
            updated_at_epoch_ms=100,
        )
    )
    store.save_workspace(
        WorkflowDraftWorkspace(
            id="a",
            revision=1,
            draft=_draft(),
            status="valid",
            diagnostics=[],
            created_at_epoch_ms=100,
            updated_at_epoch_ms=100,
        )
    )

    assert [workspace.id for workspace in store.list_workspaces()] == ["a", "b"]


def test_file_draft_workspace_store_deletes_workspace(tmp_path) -> None:
    store = FileDraftWorkspaceStore(tmp_path)
    store.save_workspace(
        WorkflowDraftWorkspace(
            id="echo_draft",
            revision=1,
            draft=_draft(),
            status="valid",
            diagnostics=[],
            created_at_epoch_ms=100,
            updated_at_epoch_ms=100,
        )
    )

    deleted = store.delete_workspace("echo_draft")
    deleted_again = store.delete_workspace("echo_draft")

    assert deleted is True
    assert deleted_again is False
    assert store.list_workspaces() == []


def test_file_draft_workspace_store_rejects_path_traversal_ids(tmp_path) -> None:
    store = FileDraftWorkspaceStore(tmp_path)

    try:
        store.get_workspace("../outside")
    except ValueError as exc:
        assert "path separators are not allowed" in str(exc)
    else:
        raise AssertionError("expected unsafe workspace id to be rejected")


def test_create_draft_workspace_validates_and_saves(tmp_path) -> None:
    store = FileDraftWorkspaceStore(tmp_path)

    result = create_draft_workspace(
        store,
        workspace_id="echo_draft",
        draft=_draft(),
        title="Echo Draft",
    )

    loaded = store.get_workspace("echo_draft")
    assert result["workspace_id"] == "echo_draft"
    assert result["status"] == "valid"
    assert loaded.revision == 1
    assert loaded.status == "valid"


def test_create_draft_workspace_rejects_duplicate_id(tmp_path) -> None:
    store = FileDraftWorkspaceStore(tmp_path)
    create_draft_workspace(store, workspace_id="echo_draft", draft=_draft())

    result = create_draft_workspace(
        store,
        workspace_id="echo_draft",
        draft=_draft(),
        title="Replacement",
    )

    loaded = store.get_workspace("echo_draft")
    assert result["status"] == "conflict"
    assert result["diagnostics"][0]["code"] == "workspace_exists"
    assert loaded.revision == 1
    assert loaded.title is None


def test_patch_draft_workspace_applies_patch_and_increments_revision(tmp_path) -> None:
    store = FileDraftWorkspaceStore(tmp_path)
    create_draft_workspace(store, workspace_id="echo_draft", draft=_draft())

    result = patch_draft_workspace(
        store,
        workspace_id="echo_draft",
        revision=1,
        patch=[
            {
                "op": "replace",
                "path": "/name",
                "value": "echo_v2",
            }
        ],
    )

    loaded = store.get_workspace("echo_draft")
    assert result["revision"] == 2
    assert result["status"] == "valid"
    assert loaded.revision == 2
    assert loaded.draft["name"] == "echo_v2"


def test_patch_draft_workspace_rejects_stale_revision(tmp_path) -> None:
    store = FileDraftWorkspaceStore(tmp_path)
    create_draft_workspace(store, workspace_id="echo_draft", draft=_draft())
    patch_draft_workspace(
        store,
        workspace_id="echo_draft",
        revision=1,
        patch=[],
    )

    result = patch_draft_workspace(
        store,
        workspace_id="echo_draft",
        revision=1,
        patch=[],
    )

    assert result["status"] == "conflict"
    assert result["diagnostics"][0]["code"] == "revision_conflict"
    assert store.get_workspace("echo_draft").revision == 2


def test_patch_draft_workspace_rejects_duplicate_revision_patch(tmp_path) -> None:
    store = FileDraftWorkspaceStore(tmp_path)
    create_draft_workspace(store, workspace_id="echo_draft", draft=_draft())

    first = patch_draft_workspace(
        store,
        workspace_id="echo_draft",
        revision=1,
        patch=[{"op": "replace", "path": "/name", "value": "first"}],
    )
    second = patch_draft_workspace(
        store,
        workspace_id="echo_draft",
        revision=1,
        patch=[{"op": "replace", "path": "/name", "value": "second"}],
    )

    loaded = store.get_workspace("echo_draft")
    assert first["revision"] == 2
    assert second["status"] == "conflict"
    assert second["diagnostics"][0]["code"] == "revision_conflict"
    assert loaded.draft["name"] == "first"


def test_patch_draft_workspace_rejects_invalid_patch_without_revision_bump(
    tmp_path,
) -> None:
    store = FileDraftWorkspaceStore(tmp_path)
    create_draft_workspace(store, workspace_id="echo_draft", draft=_draft())

    result = patch_draft_workspace(
        store,
        workspace_id="echo_draft",
        revision=1,
        patch=[{"op": "remove", "path": "/missing"}],
    )

    assert result["status"] == "invalid"
    assert result["diagnostics"][0]["code"] == "patch_invalid"
    assert store.get_workspace("echo_draft").revision == 1


def test_get_draft_workspace_includes_full_draft_only_when_requested(tmp_path) -> None:
    store = FileDraftWorkspaceStore(tmp_path)
    create_draft_workspace(store, workspace_id="echo_draft", draft=_draft())

    compact = get_draft_workspace(store, workspace_id="echo_draft")
    full = get_draft_workspace(
        store,
        workspace_id="echo_draft",
        include_draft=True,
    )

    assert "draft" not in compact
    assert full["draft"]["steps"]["echo"]["use"] == "demo.echo"


def _draft() -> dict[str, Any]:
    return {
        "name": "echo",
        "input_schema": {"type": "object", "properties": {}},
        "state_schema": {"fields": {"echoed": {"type": "string"}}},
        "output_schema": {"type": "object", "properties": {}},
        "start": "echo",
        "steps": {
            "echo": {
                "use": "demo.echo",
                "in": {},
                "out": {"echoed": "state.echoed"},
            }
        },
        "routes": {"echo": {"ok": "__end__"}},
    }
