from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from wf_artifacts import (
    CheckpointReason,
    FileRunStore,
    PinnedRunEnvironment,
    ResumeReadiness,
    RunCheckpoint,
    StoredRunStatus,
    WorkflowArtifact,
    WorkflowDeployment,
    WorkflowRunRecord,
)
from wf_core import PersistedRunState, RunState, RunStatus, dump_run_state


def artifact(artifact_id: str = "parent") -> WorkflowArtifact:
    return WorkflowArtifact(
        id=artifact_id,
        version=1,
        title=artifact_id.title(),
        input_schema={"type": "object", "properties": {}},
        output_schema={"type": "object", "properties": {}},
        outcomes=("ok",),
        plan={"name": artifact_id, "nodes": [], "edges": []},
    )


def deployment() -> WorkflowDeployment:
    return WorkflowDeployment(
        id="parent.personal",
        artifact_id="parent",
        artifact_version=1,
        bindings=[{"logical_source": "demo", "concrete_source": "demo.personal"}],
    )


def run_record(run_id: str, checkpoint_id: str) -> WorkflowRunRecord:
    now = datetime.now(UTC)
    return WorkflowRunRecord(
        id=run_id,
        status=StoredRunStatus.INTERRUPTED,
        resume_readiness=ResumeReadiness.READY,
        environment=PinnedRunEnvironment(
            deployment=deployment(),
            root_artifact=artifact(),
            child_artifacts=[artifact("child")],
        ),
        latest_checkpoint_id=checkpoint_id,
        created_at=now,
        updated_at=now,
    )


def checkpoint(run_id: str, sequence: int) -> RunCheckpoint:
    return RunCheckpoint(
        id=f"{run_id}.{sequence:06d}",
        run_id=run_id,
        sequence=sequence,
        reason=CheckpointReason.INTERRUPTED,
        state=PersistedRunState.model_validate(
            dump_run_state(
                RunState(
                    workflow_name="parent",
                    status=RunStatus.INTERRUPTED,
                    workflow_input={},
                    state={},
                )
            )
        ),
        created_at=datetime.now(UTC),
    )


def test_file_run_store_round_trips_pinned_environment_and_checkpoint(tmp_path) -> None:
    store = FileRunStore(tmp_path)
    run = run_record("run_123", "run_123.000001")
    stored_checkpoint = checkpoint("run_123", 1)

    store.save_run(run)
    store.save_checkpoint(stored_checkpoint)

    restored_run = store.get_run("run_123")
    restored_checkpoint = store.get_latest_checkpoint("run_123")

    assert restored_run.environment.root_artifact.id == "parent"
    assert restored_run.environment.child_artifacts[0].id == "child"
    assert restored_checkpoint.sequence == 1


def test_file_run_store_lists_runs_and_checkpoints_in_order(tmp_path) -> None:
    store = FileRunStore(tmp_path)
    store.save_run(run_record("run_b", "run_b.000001"))
    store.save_run(run_record("run_a", "run_a.000002"))
    store.save_checkpoint(checkpoint("run_a", 2))
    store.save_checkpoint(checkpoint("run_a", 1))

    assert [record.id for record in store.list_runs()] == ["run_a", "run_b"]
    assert [item.sequence for item in store.list_checkpoints("run_a")] == [1, 2]


def test_file_run_store_rejects_unsafe_run_id(tmp_path) -> None:
    store = FileRunStore(tmp_path)

    with pytest.raises(ValueError, match="run_id must start"):
        store.get_run("../outside")

    with pytest.raises(ValueError, match="run_id must start"):
        store.get_run(".hidden_run")


def test_workflow_run_record_validates_latest_checkpoint_id() -> None:
    with pytest.raises(ValidationError):
        run_record("run_123", "../outside")
