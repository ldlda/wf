from __future__ import annotations

import re
from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from wf_core import PersistedRunState

from ..models import DependencyDiagnostic, WorkflowArtifact, WorkflowDeployment

RUN_ID_PATTERN = r"^[A-Za-z0-9_][A-Za-z0-9_.-]*$"


def ensure_run_id(run_id: str) -> str:
    """Reject ids that cannot safely identify one local run directory."""
    if not re.fullmatch(RUN_ID_PATTERN, run_id):
        raise ValueError(
            "run_id must start with alphanumeric or underscore and contain only "
            "[A-Za-z0-9_.-]"
        )
    return run_id


class StoredRunStatus(StrEnum):
    """Stopped runtime statuses supported by durable run persistence."""

    INTERRUPTED = "interrupted"
    COMPLETED = "completed"
    FAILED = "failed"


class ResumeReadiness(StrEnum):
    """Whether an interrupted stored run may currently continue."""

    READY = "ready"
    BLOCKED = "blocked"
    NOT_APPLICABLE = "not_applicable"


class CheckpointReason(StrEnum):
    """Why a stopped-state checkpoint was written."""

    INTERRUPTED = "interrupted"
    COMPLETED = "completed"
    FAILED = "failed"


class PinnedRunEnvironment(BaseModel):
    """Exact execution definitions captured when a run starts."""

    model_config = ConfigDict(extra="forbid")

    deployment: WorkflowDeployment
    root_artifact: WorkflowArtifact
    child_artifacts: list[WorkflowArtifact] = Field(default_factory=list)


class WorkflowRunRecord(BaseModel):
    """Durable summary and pinned environment for one started workflow run."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=RUN_ID_PATTERN)
    status: StoredRunStatus
    resume_readiness: ResumeReadiness
    environment: PinnedRunEnvironment
    latest_checkpoint_id: str = Field(pattern=RUN_ID_PATTERN)
    diagnostics: list[DependencyDiagnostic] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class VersionedCheckpointState(BaseModel):
    """Lenient read envelope for stopped-run checkpoints.

    Writes always produce version 2 via ``wf_core.dump_run_state``; reads
    accept version 1 so pre-budget checkpoints reach
    ``load_run_state_with_upgrade`` instead of failing checkpoint validation
    with a ``version == 2`` literal error first. The inner state stays an
    untyped dict because core owns strict budget validation there.
    """

    model_config = ConfigDict(extra="forbid")

    version: Literal[1, 2] = 2
    state: dict[str, Any]


class RunCheckpoint(BaseModel):
    """One stopped-state snapshot persisted at an external run boundary."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=RUN_ID_PATTERN)
    run_id: str = Field(pattern=RUN_ID_PATTERN)
    sequence: int = Field(ge=1)
    reason: CheckpointReason
    state: PersistedRunState | VersionedCheckpointState
    created_at: datetime
