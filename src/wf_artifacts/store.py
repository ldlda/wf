from __future__ import annotations

import json
from pathlib import Path

from .models import WorkflowArtifact, WorkflowDeployment


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
        artifact_dir = self.artifacts_dir / artifact.id
        artifact_dir.mkdir(parents=True, exist_ok=True)
        path = artifact_dir / f"{artifact.version}.json"
        path.write_text(
            json.dumps(artifact.model_dump(mode="json"), indent=2),
            encoding="utf-8",
        )

    def get_artifact(self, artifact_id: str, version: int) -> WorkflowArtifact:
        path = self.artifacts_dir / artifact_id / f"{version}.json"
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
        versions = [
            int(path.stem)
            for path in (self.artifacts_dir / artifact_id).glob("*.json")
            if path.stem.isdecimal()
        ]
        if not versions:
            raise KeyError(f"unknown workflow artifact {artifact_id!r}")
        return self.get_artifact(artifact_id, max(versions))

    def save_deployment(self, deployment: WorkflowDeployment) -> None:
        path = self.deployments_dir / f"{deployment.id}.json"
        path.write_text(
            json.dumps(deployment.model_dump(mode="json"), indent=2),
            encoding="utf-8",
        )

    def get_deployment(self, deployment_id: str) -> WorkflowDeployment:
        path = self.deployments_dir / f"{deployment_id}.json"
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
