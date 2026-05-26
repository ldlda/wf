from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from wf_artifacts import (
    AvailableSource,
    CheckpointReason,
    DependencyDiagnostic,
    DiagnosticSeverity,
    PinnedRunEnvironment,
    ResumeReadiness,
    RunCheckpoint,
    RunStore,
    StoredRunStatus,
    WorkflowArtifact,
    WorkflowDeployment,
    WorkflowRunRecord,
    validate_deployment_dependencies,
)
from wf_core import (
    PersistedRunState,
    RunState,
    RunStatus,
    dump_run_state,
    load_run_state,
)

from .saved_subgraphs import SavedSubgraphTree


def create_pinned_environment(
    *,
    deployment: WorkflowDeployment,
    artifact: WorkflowArtifact,
    tree: SavedSubgraphTree,
) -> PinnedRunEnvironment:
    """Capture exact root, deployment, and child definitions for one run."""
    return PinnedRunEnvironment(
        deployment=deployment,
        root_artifact=artifact,
        child_artifacts=list(tree.artifacts_by_ref.values()),
    )


def persist_stopped_run(
    *,
    store: RunStore,
    environment: PinnedRunEnvironment,
    run: RunState,
    run_id: str | None = None,
) -> WorkflowRunRecord:
    """Persist one externally visible stopped state and its typed checkpoint."""
    if run.status not in {
        RunStatus.INTERRUPTED,
        RunStatus.COMPLETED,
        RunStatus.FAILED,
    }:
        raise ValueError(
            f"cannot persist active workflow run with status {run.status!s}"
        )

    key = run_id or f"run_{uuid4().hex}"
    now = datetime.now(UTC)
    sequence = 1
    created_at = now
    if run_id is not None:
        existing = store.get_run(run_id)
        created_at = existing.created_at
        sequence = store.get_latest_checkpoint(run_id).sequence + 1

    status = StoredRunStatus(run.status.value)
    readiness = (
        ResumeReadiness.READY
        if status is StoredRunStatus.INTERRUPTED
        else ResumeReadiness.NOT_APPLICABLE
    )
    checkpoint_id = f"{key}.{sequence:06d}"
    checkpoint = RunCheckpoint(
        id=checkpoint_id,
        run_id=key,
        sequence=sequence,
        reason=CheckpointReason(status.value),
        state=PersistedRunState.model_validate(dump_run_state(run)),
        created_at=now,
    )
    record = WorkflowRunRecord(
        id=key,
        status=status,
        resume_readiness=readiness,
        environment=environment,
        latest_checkpoint_id=checkpoint_id,
        created_at=created_at,
        updated_at=now,
    )
    store.save_checkpoint(checkpoint)
    store.save_run(record)
    return record


def restore_interrupted_run(
    store: RunStore, run_id: str
) -> tuple[WorkflowRunRecord, RunState]:
    """Load a persisted interrupted run and its latest typed runtime state."""
    record, run = load_stored_run(store, run_id)
    if record.status is not StoredRunStatus.INTERRUPTED:
        raise ValueError(f"workflow run {run_id!r} is not interrupted")
    return record, run


def load_stored_run(store: RunStore, run_id: str) -> tuple[WorkflowRunRecord, RunState]:
    """Load any stopped run record together with its latest typed checkpoint."""
    record = store.get_run(run_id)
    checkpoint = store.get_latest_checkpoint(run_id)
    return record, load_run_state(checkpoint.state.model_dump(mode="json"))


def validate_pinned_resume_environment(
    *,
    record: WorkflowRunRecord,
    sources: list[AvailableSource],
) -> list[DependencyDiagnostic]:
    """Revalidate exact stored graph definitions before a resume mutates state."""
    environment = record.environment
    diagnostics = validate_deployment_dependencies(
        artifact=environment.root_artifact,
        deployment=environment.deployment,
        sources=sources,
    )
    for child in environment.child_artifacts:
        diagnostics.extend(
            validate_deployment_dependencies(
                artifact=child,
                deployment=environment.deployment,
                sources=sources,
            )
        )
    return diagnostics


def has_blocking_diagnostics(diagnostics: list[DependencyDiagnostic]) -> bool:
    """Return whether dependency diagnostics prohibit executing a resume."""
    return any(item.severity is DiagnosticSeverity.ERROR for item in diagnostics)


def mark_resume_blocked(
    *,
    store: RunStore,
    record: WorkflowRunRecord,
    diagnostics: list[DependencyDiagnostic],
) -> WorkflowRunRecord:
    """Record blocked readiness without writing a new execution checkpoint."""
    blocked = record.model_copy(
        update={
            "resume_readiness": ResumeReadiness.BLOCKED,
            "diagnostics": diagnostics,
            "updated_at": datetime.now(UTC),
        }
    )
    store.save_run(blocked)
    return blocked
