"""Stopped-run step budget migration tests (Task 4).

Pins the v1-to-v2 upgrade contract: a pre-budget interrupted checkpoint is
rewritten as v2 and persisted *before* resume dispatch (the runtime must
observe the upgraded checkpoint when it is called), while ordinary
inspection decodes v1 prospectively without touching the store.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from wf_api.models import RawWorkflowPlan
from wf_api.operation_context import WorkflowOperationContext
from wf_api.run_lifecycle import (
    create_pinned_environment,
    persist_stopped_run,
    restore_interrupted_run,
)
from wf_api.runs import WorkflowRunApi
from wf_api.saved_subgraphs import SavedSubgraphTree
from wf_artifacts import (
    FileRunStore,
    WorkflowArtifact,
    WorkflowDeployment,
)
from wf_authoring import NodeSpec
from wf_core import InterruptRequest, RunState, RunStatus
from wf_platform import CapabilitySource


class DummyEvents:
    def record_event(self, event: object) -> None:
        pass

    def record_workflow_event(
        self,
        event_type: str,
        *,
        capability_id: str,
        payload: dict[str, Any],
    ) -> None:
        pass


class EmptySpecProvider:
    @property
    def capability_sources(self) -> dict[str, CapabilitySource]:
        return {}

    def get_qualified_spec(self, qualified_name: str) -> NodeSpec[Any, Any]:
        raise KeyError(f"unknown capability {qualified_name!r}")


class UpgradeAssertingRuntime:
    """Resume-only fake proving the v1 upgrade persists before dispatch.

    When the API calls resume, the upgraded v2 checkpoint must already be
    the latest persisted checkpoint; otherwise resume dispatched work on top
    of unmigrated state.
    """

    def __init__(self, store: FileRunStore, run_id: str) -> None:
        self.store = store
        self.run_id = run_id
        self.resume_calls = 0

    async def run_workflow_from_plan(
        self,
        plan: RawWorkflowPlan,
        workflow_input: dict[str, Any],
        deployment: WorkflowDeployment | None = None,
        artifact: WorkflowArtifact | None = None,
        saved_subgraph_tree: SavedSubgraphTree | None = None,
        limits: Any | None = None,
    ) -> RunState:
        raise AssertionError("test must not start new workflow runs")

    async def resume_workflow_from_plan(
        self,
        plan: RawWorkflowPlan,
        run: RunState,
        *,
        resume_payload: dict[str, Any],
        resume_outcome: str,
        deployment: WorkflowDeployment | None = None,
        artifact: WorkflowArtifact | None = None,
        saved_subgraph_tree: SavedSubgraphTree | None = None,
    ) -> RunState:
        self.resume_calls += 1
        latest = self.store.get_latest_checkpoint(self.run_id)
        upgraded = latest.state.model_dump(mode="json")
        assert upgraded["version"] == 2
        assert upgraded["state"]["limits"] == {"max_steps": 10_000}
        assert upgraded["state"]["steps_executed"] == 0
        assert run.limits.max_steps == 10_000
        assert run.steps_executed == 0
        return RunState(
            workflow_name=plan.name,
            status=RunStatus.COMPLETED,
            workflow_input=run.workflow_input,
            state={"answer": resume_payload["answer"]},
            outcome=resume_outcome,
            output={"answer": resume_payload["answer"]},
        )


def _artifact() -> WorkflowArtifact:
    return WorkflowArtifact(
        id="pause",
        version=1,
        title="Pause",
        input_schema={"type": "object", "properties": {}},
        output_schema={"type": "object", "properties": {}},
        outcomes=("ok", "submitted"),
        plan={
            "name": "pause",
            "input_schema": {"type": "object", "properties": {}},
            "state_schema": {"type": "object", "properties": {}},
            "output_schema": {"type": "object", "properties": {}},
            "outcomes": ["ok", "submitted"],
            "start": "end_submitted",
            "nodes": [{"id": "end_submitted", "type": "end", "outcome": "submitted"}],
            "edges": [],
        },
    )


def _deployment(artifact: WorkflowArtifact) -> WorkflowDeployment:
    return WorkflowDeployment(
        id="pause.default",
        artifact_id=artifact.id,
        artifact_version=artifact.version,
        bindings=[],
    )


def _seed_interrupted_run(store: FileRunStore) -> str:
    artifact = _artifact()
    interrupted = RunState(
        workflow_name="pause",
        status=RunStatus.INTERRUPTED,
        workflow_input={"question": "continue?"},
        state={},
        interrupt=InterruptRequest(
            id="interrupt:approval",
            frame_id="root",
            node_id="approval",
            kind="approval",
            payload={"question": "continue?"},
        ),
    )
    record = persist_stopped_run(
        store=store,
        environment=create_pinned_environment(
            deployment=_deployment(artifact),
            artifact=artifact,
            tree=SavedSubgraphTree(artifacts_by_ref={}, diagnostics=[]),
        ),
        run=interrupted,
    )
    return record.id


def _checkpoint_path(store: FileRunStore, run_id: str, sequence: int) -> Path:
    return store.runs_dir / run_id / "checkpoints" / f"{sequence:06d}.json"


def _read_raw_checkpoint(
    store: FileRunStore, run_id: str, sequence: int
) -> dict[str, Any]:
    return json.loads(_checkpoint_path(store, run_id, sequence).read_text("utf-8"))


def _downgrade_latest_checkpoint_to_v1(store: FileRunStore, run_id: str) -> None:
    """Rewrite the latest checkpoint file as a pre-budget v1 envelope.

    Writes raw JSON directly so the file matches what a legacy (pre-budget)
    writer left on disk, bypassing current model validation.
    """
    path = _checkpoint_path(store, run_id, 1)
    payload: dict[str, Any] = json.loads(path.read_text("utf-8"))
    inner = payload["state"]["state"]
    inner.pop("limits", None)
    inner.pop("steps_executed", None)
    for frame in inner.get("frames", {}).values():
        frame.pop("step_number", None)
    for entry in inner.get("trace", []):
        entry.pop("step_number", None)
    if inner.get("interrupt") is not None:
        inner["interrupt"].pop("step_number", None)
    payload["state"] = {"version": 1, "state": inner}
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _api(store: FileRunStore, runtime: UpgradeAssertingRuntime) -> WorkflowRunApi:
    return WorkflowRunApi(
        WorkflowOperationContext(
            artifact_store=None,
            draft_workspace_store=None,
            run_store=store,
            events=DummyEvents(),
            specs=EmptySpecProvider(),
            runtime=runtime,
            live_sources=None,
        )
    )


def test_restore_interrupted_run_persists_v1_upgrade_before_returning(
    tmp_path: Path,
) -> None:
    store = FileRunStore(tmp_path / "runs")
    run_id = _seed_interrupted_run(store)
    _downgrade_latest_checkpoint_to_v1(store, run_id)

    record, run = restore_interrupted_run(store, run_id)

    assert record.id == run_id
    assert run.limits.max_steps == 10_000
    assert run.steps_executed == 0
    assert run.steps_remaining == 10_000
    assert [item.sequence for item in store.list_checkpoints(run_id)] == [1, 2]
    upgraded = _read_raw_checkpoint(store, run_id, 2)
    assert upgraded["state"]["version"] == 2
    assert upgraded["reason"] == "interrupted"


def test_restore_interrupted_run_leaves_v2_checkpoints_untouched(
    tmp_path: Path,
) -> None:
    store = FileRunStore(tmp_path / "runs")
    run_id = _seed_interrupted_run(store)

    record, run = restore_interrupted_run(store, run_id)

    assert record.id == run_id
    assert run.steps_executed == 0
    assert [item.sequence for item in store.list_checkpoints(run_id)] == [1]


async def test_resume_persists_v1_upgrade_before_runtime_dispatch(
    tmp_path: Path,
) -> None:
    store = FileRunStore(tmp_path / "runs")
    run_id = _seed_interrupted_run(store)
    _downgrade_latest_checkpoint_to_v1(store, run_id)
    runtime = UpgradeAssertingRuntime(store, run_id)
    api = _api(store, runtime)

    result = await api.resume_run(run_id=run_id, resume_payload={"answer": "yes"})

    assert runtime.resume_calls == 1
    assert result["status"] == "completed"
    assert result["max_steps"] == 10_000
    assert result["steps_executed"] == 0
    assert result["steps_remaining"] == 10_000
    assert [item.sequence for item in store.list_checkpoints(run_id)] == [1, 2, 3]
    upgraded = _read_raw_checkpoint(store, run_id, 2)
    assert upgraded["state"]["version"] == 2
    assert upgraded["state"]["state"]["steps_executed"] == 0


async def test_inspect_decodes_v1_without_mutation(tmp_path: Path) -> None:
    store = FileRunStore(tmp_path / "runs")
    run_id = _seed_interrupted_run(store)
    _downgrade_latest_checkpoint_to_v1(store, run_id)
    runtime = UpgradeAssertingRuntime(store, run_id)
    api = _api(store, runtime)

    summary = await api.inspect_run(run_id=run_id)

    assert summary["status"] == "interrupted"
    assert summary["max_steps"] == 10_000
    assert summary["steps_executed"] == 0
    assert summary["steps_remaining"] == 10_000
    assert runtime.resume_calls == 0
    assert [item.sequence for item in store.list_checkpoints(run_id)] == [1]
    untouched = _read_raw_checkpoint(store, run_id, 1)
    assert untouched["state"]["version"] == 1
