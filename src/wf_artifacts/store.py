from __future__ import annotations

import json
import re
from pathlib import Path

from .models import WorkflowArtifact, WorkflowDeployment

STORE_ID_PATTERN = r"^[A-Za-z0-9_][A-Za-z0-9_.-]*$"


def ensure_store_id(value: str, *, field_name: str) -> str:
    """Reject ids that cannot safely map to one local store path component."""
    if not re.fullmatch(STORE_ID_PATTERN, value):
        raise ValueError(
            f"{field_name} must start with alphanumeric or underscore and contain "
            "only [A-Za-z0-9_.-]"
        )
    return value


class WorkflowArtifactStore:
    """Storage boundary for workflow artifacts and deployments."""

    def save_artifact(self, artifact: WorkflowArtifact) -> None:
        raise NotImplementedError

    def get_artifact(self, artifact_id: str, version: int) -> WorkflowArtifact:
        raise NotImplementedError

    def list_artifacts(self) -> list[WorkflowArtifact]:
        raise NotImplementedError

    def resolve_latest(self, artifact_id: str) -> WorkflowArtifact:
        raise NotImplementedError

    def save_deployment(self, deployment: WorkflowDeployment) -> None:
        raise NotImplementedError

    def get_deployment(self, deployment_id: str) -> WorkflowDeployment:
        raise NotImplementedError

    def list_deployments(self) -> list[WorkflowDeployment]:
        raise NotImplementedError

    def delete_artifact(self, artifact_id: str, version: int) -> None:
        raise NotImplementedError

    def deployments_for_artifact(
        self, artifact_id: str, version: int
    ) -> list[WorkflowDeployment]:
        raise NotImplementedError

    def delete_deployment(self, deployment_id: str) -> None:
        raise NotImplementedError


class FileWorkflowArtifactStore(WorkflowArtifactStore):
    """JSON file-backed artifact store for local development and tests."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.deployments_dir.mkdir(parents=True, exist_ok=True)

    @property
    def artifacts_dir(self) -> Path:
        return self.root / "workflows"

    @property
    def deployments_dir(self) -> Path:
        return self.root / "deployments"

    def save_artifact(self, artifact: WorkflowArtifact) -> None:
        artifact_dir = self._artifact_dir(artifact.id)
        artifact_dir.mkdir(parents=True, exist_ok=True)
        path = artifact_dir / self._artifact_filename(artifact.version)
        path.write_text(
            json.dumps(artifact.model_dump(mode="json"), indent=2),
            encoding="utf-8",
        )

    def get_artifact(self, artifact_id: str, version: int) -> WorkflowArtifact:
        path = self._artifact_dir(artifact_id) / self._artifact_filename(version)
        if not path.exists():
            raise KeyError(f"unknown workflow artifact {artifact_id}@{version}")
        return WorkflowArtifact.model_validate_json(path.read_text(encoding="utf-8"))

    def list_artifacts(self) -> list[WorkflowArtifact]:
        artifacts: list[WorkflowArtifact] = []
        for path in sorted(self.artifacts_dir.glob("*/*.json")):
            artifacts.append(
                WorkflowArtifact.model_validate_json(path.read_text(encoding="utf-8"))
            )
        return artifacts

    def resolve_latest(self, artifact_id: str) -> WorkflowArtifact:
        artifact_dir = self._artifact_dir(artifact_id)
        versions = [
            int(path.stem)
            for path in artifact_dir.glob("*.json")
            if path.stem.isdecimal()
        ]
        if not versions:
            raise KeyError(f"unknown workflow artifact {artifact_id!r}")
        return self.get_artifact(artifact_id, max(versions))

    def save_deployment(self, deployment: WorkflowDeployment) -> None:
        path = self._deployment_path(deployment.id)
        path.write_text(
            json.dumps(deployment.model_dump(mode="json"), indent=2),
            encoding="utf-8",
        )

    def get_deployment(self, deployment_id: str) -> WorkflowDeployment:
        path = self._deployment_path(deployment_id)
        if not path.exists():
            raise KeyError(f"unknown workflow deployment {deployment_id!r}")
        return WorkflowDeployment.model_validate_json(path.read_text(encoding="utf-8"))

    def list_deployments(self) -> list[WorkflowDeployment]:
        deployments: list[WorkflowDeployment] = []
        for path in sorted(self.deployments_dir.glob("*.json")):
            deployments.append(
                WorkflowDeployment.model_validate_json(path.read_text(encoding="utf-8"))
            )
        return deployments

    def delete_artifact(self, artifact_id: str, version: int) -> None:
        """Remove one immutable artifact version from the store."""
        path = self._artifact_dir(artifact_id) / self._artifact_filename(version)
        if not path.exists():
            raise KeyError(f"unknown workflow artifact {artifact_id}@{version}")
        path.unlink()

    def deployments_for_artifact(
        self, artifact_id: str, version: int
    ) -> list[WorkflowDeployment]:
        """Return deployments that currently reference one artifact version."""
        return [
            deployment
            for deployment in self.list_deployments()
            if deployment.artifact_id == artifact_id
            and deployment.artifact_version == version
        ]

    def delete_deployment(self, deployment_id: str) -> None:
        """Remove one mutable deployment binding record from the store."""
        path = self._deployment_path(deployment_id)
        if not path.exists():
            raise KeyError(f"unknown workflow deployment {deployment_id!r}")
        path.unlink()

    def _artifact_dir(self, artifact_id: str) -> Path:
        safe_id = ensure_store_id(artifact_id, field_name="artifact_id")
        root = self.artifacts_dir.resolve()
        path = (self.artifacts_dir / safe_id).resolve()
        if path.parent != root:
            raise ValueError(f"artifact_id escapes artifact store: {artifact_id!r}")
        return path

    @staticmethod
    def _artifact_filename(version: int) -> str:
        if version < 1:
            raise ValueError("artifact version must be >= 1")
        return f"{version}.json"

    def _deployment_path(self, deployment_id: str) -> Path:
        safe_id = ensure_store_id(deployment_id, field_name="deployment_id")
        root = self.deployments_dir.resolve()
        path = (self.deployments_dir / f"{safe_id}.json").resolve()
        if path.parent != root:
            raise ValueError(
                f"deployment_id escapes deployment store: {deployment_id!r}"
            )
        return path
