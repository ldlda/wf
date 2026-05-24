# Workflow Artifacts V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the first `wf_artifacts` package with immutable workflow artifact models, deployment bindings, dependency diagnostics, and a file-backed artifact store.

**Architecture:** `wf_artifacts` is a separate layer above `wf_core` and below future platform/MCP projections. It stores declarative workflow plans and dependency metadata, but does not execute workflows or import `wf_mcp`.

**Tech Stack:** Python 3.14, Pydantic v2 models, `pathlib`, JSON file storage, pytest.

---

## File Structure

- Create `src/wf_artifacts/__init__.py`: public facade for artifact models and stores.
- Create `src/wf_artifacts/models.py`: Pydantic models for artifacts, deployments, required capabilities, diagnostics, and drift policy.
- Create `src/wf_artifacts/store.py`: `WorkflowArtifactStore` protocol-like base class and `FileWorkflowArtifactStore`.
- Create `tests/artifacts/test_models.py`: serialization and validation tests for model shapes.
- Create `tests/artifacts/test_store.py`: file-store round-trip and latest-version tests.

## Task 1: Artifact Models

**Files:**

- Create: `src/wf_artifacts/models.py`
- Create: `src/wf_artifacts/__init__.py`
- Test: `tests/artifacts/test_models.py`

- [ ] **Step 1: Write failing model tests**

```python
from wf_artifacts import (
    DependencyDiagnostic,
    DiagnosticSeverity,
    DriftPolicy,
    RequiredCapability,
    WorkflowArtifact,
    WorkflowDeployment,
)


def test_workflow_artifact_serializes_required_capability_contract() -> None:
    capability = RequiredCapability(
        logical_source="context7",
        capability_name="query-docs",
        kind="tool",
        input_schema_hash="sha256:input",
        input_schema_snapshot={"type": "object", "properties": {}},
        output_schema_hash="sha256:output",
        output_schema_snapshot={"type": "object", "properties": {}},
        observed_concrete_source="context7.default",
        observed_at_epoch_ms=123,
    )
    artifact = WorkflowArtifact(
        id="summarize_docs",
        version=1,
        title="Summarize Docs",
        description="Summarize retrieved documentation.",
        input_schema={"type": "object", "properties": {}},
        output_schema={"type": "object", "properties": {}},
        outcomes=("done", "failed"),
        plan={"name": "summarize_docs", "nodes": [], "edges": []},
        required_capabilities={"context7.query-docs": capability},
        created_from_catalog_version="catalog-1",
    )

    dumped = artifact.model_dump(mode="json")

    assert dumped["id"] == "summarize_docs"
    assert dumped["version"] == 1
    assert dumped["outcomes"] == ["done", "failed"]
    assert dumped["required_capabilities"]["context7.query-docs"]["logical_source"] == "context7"
    assert dumped["required_capabilities"]["context7.query-docs"]["input_schema_hash"] == "sha256:input"


def test_workflow_deployment_binds_logical_sources_to_concrete_sources() -> None:
    deployment = WorkflowDeployment(
        id="summarize_docs.personal",
        artifact_id="summarize_docs",
        artifact_version=1,
        bindings={"context7": "context7.personal"},
        drift_policy=DriftPolicy.BLOCK,
    )

    dumped = deployment.model_dump(mode="json")

    assert dumped["id"] == "summarize_docs.personal"
    assert dumped["artifact_id"] == "summarize_docs"
    assert dumped["artifact_version"] == 1
    assert dumped["bindings"]["context7"] == "context7.personal"
    assert dumped["drift_policy"] == "block"


def test_dependency_diagnostic_is_structured() -> None:
    diagnostic = DependencyDiagnostic(
        severity=DiagnosticSeverity.ERROR,
        code="capability_missing",
        logical_ref="context7.query-docs",
        bound_source="context7.default",
        message="Bound source no longer exposes query-docs.",
        repair_hint="Refresh catalog or bind context7 to another compatible source.",
    )

    dumped = diagnostic.model_dump(mode="json")

    assert dumped["severity"] == "error"
    assert dumped["code"] == "capability_missing"
    assert dumped["logical_ref"] == "context7.query-docs"
    assert dumped["bound_source"] == "context7.default"
    assert dumped["repair_hint"].startswith("Refresh catalog")
```

- [ ] **Step 2: Run model tests to verify RED**

Run: `uv run --with pytest pytest tests\artifacts\test_models.py -q`

Expected: fail with `ModuleNotFoundError: No module named 'wf_artifacts'`.

- [ ] **Step 3: Implement minimal models**

```python
from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


JsonObject = dict[str, Any]


class DriftPolicy(StrEnum):
    BLOCK = "block"
    WARN = "warn"
    ALLOW = "allow"


class DiagnosticSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"


class RequiredCapability(BaseModel):
    logical_source: str
    capability_name: str
    kind: Literal["tool", "resource", "prompt", "node_spec", "workflow"]
    input_schema_hash: str | None = None
    input_schema_snapshot: JsonObject | None = None
    output_schema_hash: str | None = None
    output_schema_snapshot: JsonObject | None = None
    observed_concrete_source: str | None = None
    observed_at_epoch_ms: int | None = Field(default=None, ge=0)


class DependencyDiagnostic(BaseModel):
    severity: DiagnosticSeverity
    code: str
    logical_ref: str
    bound_source: str | None = None
    message: str
    repair_hint: str | None = None


class WorkflowArtifact(BaseModel):
    id: str
    version: int = Field(ge=1)
    title: str
    description: str | None = None
    input_schema: JsonObject
    output_schema: JsonObject
    outcomes: tuple[str, ...]
    plan: JsonObject
    required_capabilities: dict[str, RequiredCapability] = Field(default_factory=dict)
    workflow_dependencies: dict[str, int] = Field(default_factory=dict)
    created_from_catalog_version: str | None = None


class WorkflowDeployment(BaseModel):
    id: str
    artifact_id: str
    artifact_version: int = Field(ge=1)
    bindings: dict[str, str] = Field(default_factory=dict)
    drift_policy: DriftPolicy = DriftPolicy.BLOCK
```

- [ ] **Step 4: Export models**

```python
from .models import (
    DependencyDiagnostic,
    DiagnosticSeverity,
    DriftPolicy,
    RequiredCapability,
    WorkflowArtifact,
    WorkflowDeployment,
)

__all__ = [
    "DependencyDiagnostic",
    "DiagnosticSeverity",
    "DriftPolicy",
    "RequiredCapability",
    "WorkflowArtifact",
    "WorkflowDeployment",
]
```

- [ ] **Step 5: Run model tests to verify GREEN**

Run: `uv run --with pytest pytest tests\artifacts\test_models.py -q`

Expected: pass.

## Task 2: File Artifact Store

**Files:**

- Modify: `src/wf_artifacts/store.py`
- Modify: `src/wf_artifacts/__init__.py`
- Test: `tests/artifacts/test_store.py`

- [ ] **Step 1: Write failing store tests**

```python
from wf_artifacts import (
    FileWorkflowArtifactStore,
    WorkflowArtifact,
    WorkflowDeployment,
)


def artifact(version: int) -> WorkflowArtifact:
    return WorkflowArtifact(
        id="summarize_docs",
        version=version,
        title=f"Summarize Docs v{version}",
        description=None,
        input_schema={"type": "object", "properties": {}},
        output_schema={"type": "object", "properties": {}},
        outcomes=("done",),
        plan={"name": "summarize_docs", "nodes": [], "edges": []},
    )


def test_file_store_round_trips_artifact_versions(tmp_path) -> None:
    store = FileWorkflowArtifactStore(tmp_path)
    store.save_artifact(artifact(1))
    store.save_artifact(artifact(2))

    loaded = store.get_artifact("summarize_docs", 2)

    assert loaded.id == "summarize_docs"
    assert loaded.version == 2
    assert loaded.title == "Summarize Docs v2"


def test_file_store_resolves_latest_artifact_version(tmp_path) -> None:
    store = FileWorkflowArtifactStore(tmp_path)
    store.save_artifact(artifact(1))
    store.save_artifact(artifact(3))
    store.save_artifact(artifact(2))

    latest = store.resolve_latest("summarize_docs")

    assert latest.id == "summarize_docs"
    assert latest.version == 3


def test_file_store_round_trips_deployment(tmp_path) -> None:
    store = FileWorkflowArtifactStore(tmp_path)
    deployment = WorkflowDeployment(
        id="summarize_docs.personal",
        artifact_id="summarize_docs",
        artifact_version=1,
        bindings={"context7": "context7.personal"},
    )

    store.save_deployment(deployment)
    loaded = store.get_deployment("summarize_docs.personal")

    assert loaded.id == "summarize_docs.personal"
    assert loaded.artifact_id == "summarize_docs"
    assert loaded.bindings["context7"] == "context7.personal"
```

- [ ] **Step 2: Run store tests to verify RED**

Run: `uv run --with pytest pytest tests\artifacts\test_store.py -q`

Expected: fail importing `FileWorkflowArtifactStore`.

- [ ] **Step 3: Implement file store**

```python
from __future__ import annotations

import json
from pathlib import Path

from .models import WorkflowArtifact, WorkflowDeployment


class WorkflowArtifactStore:
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


class FileWorkflowArtifactStore(WorkflowArtifactStore):
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
```

- [ ] **Step 4: Export store types**

```python
from .store import FileWorkflowArtifactStore, WorkflowArtifactStore

__all__ = [
    ...
    "FileWorkflowArtifactStore",
    "WorkflowArtifactStore",
]
```

- [ ] **Step 5: Run store tests to verify GREEN**

Run: `uv run --with pytest pytest tests\artifacts -q`

Expected: pass.

## Task 3: Verification

**Files:**

- No production changes unless verification exposes issues.

- [ ] **Step 1: Run focused artifact tests**

Run: `uv run --with pytest pytest tests\artifacts -q`

Expected: all artifact tests pass.

- [ ] **Step 2: Run full test suite**

Run: `uv run --with pytest pytest -q`

Expected: existing tests and new artifact tests pass.

- [ ] **Step 3: Run lint/type checks**

Run: `uv run ruff check src tests examples main.py`

Expected: no lint errors.

Run: `uv run basedpyright src tests examples main.py --level error`

Expected: `0 errors`.

## Self-Review

- Spec coverage: implements the first artifact slice only: immutable models, deployments, dependency contracts, diagnostics, and file storage.
- Intentional gaps: no workflow execution, no dependency validation engine, no MCP projection, no native subgraph runtime.
- Placeholder scan: no TBD/TODO placeholders remain.
- Type consistency: tests and code use the same model names and fields.
