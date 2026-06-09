from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from wf_api.models import RawWorkflowPlan
from wf_api.operation_context import WorkflowOperationContext
from wf_api.run_lifecycle import create_pinned_environment, persist_stopped_run
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


class BlockingResumeRuntime:
    def __init__(self) -> None:
        self.entered = 0
        self.first_entered = asyncio.Event()
        self.release_first = asyncio.Event()

    async def run_workflow_from_plan(
        self,
        plan: RawWorkflowPlan,
        workflow_input: dict[str, Any],
        deployment: WorkflowDeployment | None = None,
        artifact: WorkflowArtifact | None = None,
        saved_subgraph_tree: SavedSubgraphTree | None = None,
    ) -> RunState:
        raise AssertionError("test should not start new workflow runs")

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
        self.entered += 1
        self.first_entered.set()
        await self.release_first.wait()
        return RunState(
            workflow_name=plan.name,
            status=RunStatus.COMPLETED,
            workflow_input=run.workflow_input,
            state={"answer": resume_payload["answer"]},
            outcome=resume_outcome,
            output={"answer": resume_payload["answer"]},
        )


async def test_resume_run_serializes_same_run_attempts(tmp_path: Path) -> None:
    store = FileRunStore(tmp_path / "runs")
    runtime = BlockingResumeRuntime()
    run_id = _seed_interrupted_run(store)
    api = WorkflowRunApi(
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

    first = asyncio.create_task(
        api.resume_run(run_id=run_id, resume_payload={"answer": "first"})
    )
    await runtime.first_entered.wait()

    second = asyncio.create_task(
        api.resume_run(run_id=run_id, resume_payload={"answer": "second"})
    )
    await asyncio.sleep(0)

    assert runtime.entered == 1

    runtime.release_first.set()
    first_payload = await first

    assert first_payload["status"] == "completed"
    assert first_payload["output"] == {"answer": "first"}

    with pytest.raises(ValueError, match="is not interrupted"):
        await second

    assert runtime.entered == 1
    assert store.get_latest_checkpoint(run_id).sequence == 2
    assert len(store.list_checkpoints(run_id)) == 2


def _seed_interrupted_run(store: FileRunStore) -> str:
    artifact = _artifact()
    deployment = WorkflowDeployment(
        id="pause.default",
        artifact_id=artifact.id,
        artifact_version=artifact.version,
        bindings=[],
    )
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
            deployment=deployment,
            artifact=artifact,
            tree=SavedSubgraphTree(artifacts_by_ref={}, diagnostics=[]),
        ),
        run=interrupted,
    )
    return record.id


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
