from __future__ import annotations

import json
from pathlib import Path
from threading import RLock

from .models import RunCheckpoint, WorkflowRunRecord, ensure_run_id


class RunStore:
    """Persistence boundary for stopped run summaries and checkpoints."""

    def save_run(self, run: WorkflowRunRecord) -> None:
        raise NotImplementedError

    def get_run(self, run_id: str) -> WorkflowRunRecord:
        raise NotImplementedError

    def list_runs(self) -> list[WorkflowRunRecord]:
        raise NotImplementedError

    def save_checkpoint(self, checkpoint: RunCheckpoint) -> None:
        raise NotImplementedError

    def get_latest_checkpoint(self, run_id: str) -> RunCheckpoint:
        raise NotImplementedError

    def list_checkpoints(self, run_id: str) -> list[RunCheckpoint]:
        raise NotImplementedError


class FileRunStore(RunStore):
    """JSON file-backed stopped-run store for local development and tests."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self._lock = RLock()
        self.runs_dir.mkdir(parents=True, exist_ok=True)

    @property
    def runs_dir(self) -> Path:
        return self.root / "runs"

    def save_run(self, run: WorkflowRunRecord) -> None:
        with self._lock:
            self._write_json(
                self._run_path(run.id),
                run.model_dump(mode="json"),
            )

    def get_run(self, run_id: str) -> WorkflowRunRecord:
        path = self._run_path(run_id)
        if not path.exists():
            raise KeyError(f"unknown workflow run {run_id!r}")
        return WorkflowRunRecord.model_validate_json(path.read_text(encoding="utf-8"))

    def list_runs(self) -> list[WorkflowRunRecord]:
        return [
            WorkflowRunRecord.model_validate_json(path.read_text(encoding="utf-8"))
            for path in sorted(self.runs_dir.glob("*/run.json"))
        ]

    def save_checkpoint(self, checkpoint: RunCheckpoint) -> None:
        with self._lock:
            self._write_json(
                self._checkpoint_path(checkpoint.run_id, checkpoint.sequence),
                checkpoint.model_dump(mode="json"),
            )

    def get_latest_checkpoint(self, run_id: str) -> RunCheckpoint:
        checkpoints = self.list_checkpoints(run_id)
        if not checkpoints:
            raise KeyError(f"workflow run {run_id!r} has no checkpoints")
        return checkpoints[-1]

    def list_checkpoints(self, run_id: str) -> list[RunCheckpoint]:
        directory = self._run_directory(run_id) / "checkpoints"
        if not directory.exists():
            return []
        return [
            RunCheckpoint.model_validate_json(path.read_text(encoding="utf-8"))
            for path in sorted(directory.glob("*.json"))
        ]

    def _write_json(self, path: Path, payload: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(".json.tmp")
        temp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        temp_path.replace(path)

    def _run_directory(self, run_id: str) -> Path:
        safe_id = ensure_run_id(run_id)
        root = self.runs_dir.resolve()
        path = (self.runs_dir / safe_id).resolve()
        if path.parent != root:
            raise ValueError(f"run id escapes run store: {run_id!r}")
        return path

    def _run_path(self, run_id: str) -> Path:
        return self._run_directory(run_id) / "run.json"

    def _checkpoint_path(self, run_id: str, sequence: int) -> Path:
        return self._run_directory(run_id) / "checkpoints" / f"{sequence:06d}.json"
