from __future__ import annotations

import json
from pathlib import Path
from threading import RLock

from .models import WorkflowDraftWorkspace, ensure_workspace_id


class DraftWorkspaceConflictError(RuntimeError):
    """Raised when a workspace create/update loses an optimistic-concurrency race."""

    def __init__(self, workspace: WorkflowDraftWorkspace) -> None:
        self.workspace = workspace
        super().__init__(
            f"draft workspace {workspace.id!r} is at revision {workspace.revision}"
        )


class DraftWorkspaceStore:
    """Storage boundary for mutable workflow draft workspaces."""

    def create_workspace(self, workspace: WorkflowDraftWorkspace) -> None:
        """Save a new workspace, rejecting duplicate ids."""
        try:
            existing = self.get_workspace(workspace.id)
        except KeyError:
            self.save_workspace(workspace)
            return
        raise DraftWorkspaceConflictError(existing)

    def replace_workspace(
        self,
        workspace: WorkflowDraftWorkspace,
        *,
        expected_revision: int,
    ) -> None:
        """Replace a workspace only if the stored revision still matches."""
        current = self.get_workspace(workspace.id)
        if current.revision != expected_revision:
            raise DraftWorkspaceConflictError(current)
        self.save_workspace(workspace)

    def save_workspace(self, workspace: WorkflowDraftWorkspace) -> None:
        raise NotImplementedError

    def get_workspace(self, workspace_id: str) -> WorkflowDraftWorkspace:
        raise NotImplementedError

    def list_workspaces(self) -> list[WorkflowDraftWorkspace]:
        raise NotImplementedError

    def delete_workspace(self, workspace_id: str) -> bool:
        raise NotImplementedError


class FileDraftWorkspaceStore(DraftWorkspaceStore):
    """JSON file-backed draft workspace store for local development and tests.

    The internal lock protects optimistic writes inside one broker process. If
    multiple broker processes share a root, use a stronger store implementation.
    """

    def __init__(self, root: Path) -> None:
        self.root = root
        self._lock = RLock()
        self.workspaces_dir.mkdir(parents=True, exist_ok=True)

    @property
    def workspaces_dir(self) -> Path:
        return self.root / "draft_workspaces"

    def save_workspace(self, workspace: WorkflowDraftWorkspace) -> None:
        with self._lock:
            self._write_workspace(workspace)

    def create_workspace(self, workspace: WorkflowDraftWorkspace) -> None:
        with self._lock:
            path = self._workspace_path(workspace.id)
            if path.exists():
                raise DraftWorkspaceConflictError(self.get_workspace(workspace.id))
            self._write_workspace(workspace)

    def replace_workspace(
        self,
        workspace: WorkflowDraftWorkspace,
        *,
        expected_revision: int,
    ) -> None:
        with self._lock:
            current = self.get_workspace(workspace.id)
            if current.revision != expected_revision:
                raise DraftWorkspaceConflictError(current)
            self._write_workspace(workspace)

    def _write_workspace(self, workspace: WorkflowDraftWorkspace) -> None:
        path = self._workspace_path(workspace.id)
        temp_path = path.with_suffix(".json.tmp")
        temp_path.write_text(
            json.dumps(workspace.model_dump(mode="json"), indent=2),
            encoding="utf-8",
        )
        temp_path.replace(path)

    def get_workspace(self, workspace_id: str) -> WorkflowDraftWorkspace:
        path = self._workspace_path(workspace_id)
        if not path.exists():
            raise KeyError(f"unknown draft workspace {workspace_id!r}")
        return WorkflowDraftWorkspace.model_validate_json(
            path.read_text(encoding="utf-8")
        )

    def list_workspaces(self) -> list[WorkflowDraftWorkspace]:
        return [
            WorkflowDraftWorkspace.model_validate_json(path.read_text(encoding="utf-8"))
            for path in sorted(self.workspaces_dir.glob("*.json"))
        ]

    def delete_workspace(self, workspace_id: str) -> bool:
        with self._lock:
            path = self._workspace_path(workspace_id)
            if not path.exists():
                return False
            path.unlink()
            return True

    def _workspace_path(self, workspace_id: str) -> Path:
        safe_id = ensure_workspace_id(workspace_id)
        root = self.workspaces_dir.resolve()
        path = (self.workspaces_dir / f"{safe_id}.json").resolve()
        if path.parent != root:
            raise ValueError(f"workspace id escapes workspace store: {workspace_id!r}")
        return path
