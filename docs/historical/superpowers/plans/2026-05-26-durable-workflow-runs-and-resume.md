# Durable Workflow Runs and Resume Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist stopped workflow executions so interrupted deployments can resume after process restart, while completed and failed runs become inspectable history.

**Architecture:** Add a versioned storage codec around the existing `wf_core.RunState` dataclass using Pydantic `TypeAdapter`, rather than duplicating runtime models. Add typed run/checkpoint records and a file-backed store under `wf_artifacts.runs`: `wf_platform` cannot own these models yet because `wf_artifacts` already depends on it for capability/source refs, and run records must strongly type pinned artifact/deployment snapshots. Replace the workflow surface's in-memory active-run dictionary with durable retrieval and pin the resolved saved-child artifact tree used by each run.

**Tech Stack:** Python 3.14, Pydantic v2 `TypeAdapter`, existing `wf_core` runtime dataclasses, existing `wf_artifacts` Pydantic models, file-backed JSON storage, FastMCP workflow tools, pytest, basedpyright, Ruff.

---

## Scope And Decisions

- V1 persists one checkpoint whenever `run_deployment` or `resume_run` stops as `interrupted`, `completed`, or `failed`.
- V1 does not persist mid-tool-call or per-node checkpoints.
- `unrunnable` remains a pre-start response and does not create a run record.
- Only an explicit `InterruptNode` produces resumable execution.
- A live MCP/tool transport failure persists a failed run; it is not converted into an interrupt.
- Resumed runs use pinned deployment/artifact/saved-child snapshots captured at start, then revalidate the external capabilities those pinned definitions require.
- A paused run with missing/disabled/incompatible dependencies remains `interrupted` with blocked resume readiness and diagnostics.
- Existing `retry`, `timeout_seconds`, and `retry_count` declarations remain unsupported runtime policy.

## Target File Layout

```text
src/wf_core/
  run_codec.py                       # versioned RunState JSON storage boundary

src/wf_artifacts/runs/
  __init__.py
  models.py                          # WorkflowRunRecord, RunCheckpoint, pinned environment
  store.py                           # RunStore protocol and FileRunStore

src/wf_mcp/workflow_surface/
  run_lifecycle.py                   # workflow-surface persistence/resume helpers
  handlers.py                        # thin delegation and payload assembly
  tools.py                           # inspect_run/read_run_trace MCP exposure
  saved_subgraphs.py                 # reconstruct prepared tree from pinned snapshots

src/wf_mcp/broker/
  config.py                          # configure FileRunStore
  service/core.py                    # accept pinned saved-child tree during execution/resume

tests/core/
  test_run_codec.py

tests/artifacts/
  test_run_store.py

tests/wf_mcp/
  test_durable_runs.py
  test_saved_subgraphs.py
  test_server.py
```

`handlers.py` is already large. Add lifecycle-specific logic to
`run_lifecycle.py`; retain public methods on `WorkflowSurfaceHandlers` only as
thin MCP-facing delegation points.

---

### Task 1: Add A Versioned `RunState` Storage Codec

**Files:**

- Create: `src/wf_core/run_codec.py`
- Modify: `src/wf_core/__init__.py`
- Create: `tests/core/test_run_codec.py`

- [ ] **Step 1: Write failing round-trip tests for terminal and interrupted child-scope state**

Create tests that prove the codec preserves typed values rather than returning
loose dictionaries:

```python
from wf_core import RunState, RunStatus, dump_run_state, load_run_state
from wf_core.models.reducers import ReducerRef
from wf_core.models.workflow_refs import WorkflowRef
from wf_core.paths import StatePath
from wf_core.run_state import (
    InterruptRequest,
    InterruptRoute,
    LineageState,
    RuntimeScope,
    StateWrite,
)


def test_run_state_codec_round_trips_completed_output() -> None:
    run = RunState(
        workflow_name="echo",
        status=RunStatus.COMPLETED,
        workflow_input={"text": "hi"},
        state={"echoed": "hi"},
        outcome="ok",
        output={"echoed": "hi"},
    )

    stored = dump_run_state(run)
    restored = load_run_state(stored)

    assert stored["version"] == 1
    assert restored.status is RunStatus.COMPLETED
    assert restored.output["echoed"] == "hi"


def test_run_state_codec_round_trips_child_interrupt_lineage_types() -> None:
    run = RunState(
        workflow_name="parent",
        status=RunStatus.INTERRUPTED,
        workflow_input={},
        state={},
    )
    run.scopes["child"] = RuntimeScope(
        id="child",
        workflow_name="child",
        workflow_ref=WorkflowRef(name="child"),
    )
    run.lineages["child-lineage"] = LineageState(
        id="child-lineage",
        scope_id="child",
        writes=[
            StateWrite(
                path=StatePath(("count",)),
                incoming_value=1,
                visible_value=2,
                reducer=ReducerRef.model_validate("wf.std.add"),
            )
        ],
    )
    run.interrupt = InterruptRequest(
        id="interrupt:child",
        frame_id="parent-step",
        node_id="child_step",
        kind="approval",
        route=InterruptRoute(
            frame_id="child-frame",
            node_id="ask",
            scope_id="child",
            lineage_id="child-lineage",
            parent_frame_id="parent-step",
            workflow_ref=WorkflowRef(name="child"),
        ),
    )

    restored = load_run_state(dump_run_state(run))

    assert isinstance(restored.lineages["child-lineage"].writes[0].path, StatePath)
    assert str(restored.lineages["child-lineage"].writes[0].reducer.ref) == "wf.std.add"
    assert isinstance(restored.interrupt.route.workflow_ref, WorkflowRef)
```

- [ ] **Step 2: Run tests and verify codec symbols are missing**

Run:

```bash
uv run pytest -q tests/core/test_run_codec.py
```

Expected: FAIL because `dump_run_state` / `load_run_state` do not exist.

- [ ] **Step 3: Implement the versioned envelope using `TypeAdapter(RunState)`**

Create `src/wf_core/run_codec.py`:

```python
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, TypeAdapter, ValidationError

from .run_state import RunState


class PersistedRunState(BaseModel):
    """Versioned JSON storage envelope for a stopped runtime snapshot."""

    model_config = ConfigDict(extra="forbid")

    version: Literal[1] = 1
    state: dict[str, Any]


_RUN_STATE_ADAPTER = TypeAdapter(RunState)


def dump_run_state(run: RunState) -> dict[str, object]:
    """Serialize one stopped `RunState` into the durable v1 envelope."""
    return PersistedRunState(
        state=_RUN_STATE_ADAPTER.dump_python(run, mode="json")
    ).model_dump(mode="json")


def load_run_state(payload: object) -> RunState:
    """Validate and restore a durable v1 runtime snapshot."""
    envelope = PersistedRunState.model_validate(payload)
    try:
        return _RUN_STATE_ADAPTER.validate_python(envelope.state)
    except ValidationError as exc:
        raise ValueError("invalid persisted workflow run state") from exc
```

Export `PersistedRunState`, `dump_run_state`, and `load_run_state` from
`src/wf_core/__init__.py`.

This intentionally uses the runtime dataclasses as the single execution model.
Do not create duplicate Pydantic copies of every frame/scope/lineage type.

- [ ] **Step 4: Run codec tests and static checks**

Run:

```bash
uv run pytest -q tests/core/test_run_codec.py
uvx ruff check src/wf_core/run_codec.py src/wf_core/__init__.py tests/core/test_run_codec.py
uv run basedpyright --level error src/wf_core tests/core/test_run_codec.py
```

Expected: PASS and `0 errors`.

---

### Task 2: Add Typed Run Records And A File-Backed Run Store

**Files:**

- Create: `src/wf_artifacts/runs/__init__.py`
- Create: `src/wf_artifacts/runs/models.py`
- Create: `src/wf_artifacts/runs/store.py`
- Modify: `src/wf_artifacts/__init__.py`
- Create: `tests/artifacts/test_run_store.py`

- [ ] **Step 1: Write failing tests for run/checkpoint persistence**

Create tests using existing artifact/deployment helper style from
`tests/artifacts/test_store.py`:

```python
def test_file_run_store_round_trips_pinned_environment_and_checkpoint() -> None:
    store = FileRunStore(local_temp_root() / "run_store")
    environment = PinnedRunEnvironment(
        deployment=_deployment(),
        root_artifact=_artifact(),
        child_artifacts=[_child_artifact()],
    )
    now = datetime.now(UTC)
    run = WorkflowRunRecord(
        id="run_123",
        environment=environment,
        status=StoredRunStatus.INTERRUPTED,
        resume_readiness=ResumeReadiness.READY,
        latest_checkpoint_id="run_123.000001",
        created_at=now,
        updated_at=now,
    )
    checkpoint = RunCheckpoint(
        id="run_123.000001",
        run_id=run.id,
        sequence=1,
        reason=CheckpointReason.INTERRUPTED,
        state=dump_run_state(_interrupted_run_state()),
    )

    store.save_run(run)
    store.save_checkpoint(checkpoint)

    restored_run = store.get_run("run_123")
    restored_checkpoint = store.get_latest_checkpoint("run_123")
    assert restored_run.environment.root_artifact.id == "parent"
    assert restored_run.environment.child_artifacts[0].id == "child"
    assert restored_checkpoint.sequence == 1


def test_file_run_store_lists_runs_and_reads_bounded_checkpoints() -> None:
    store = FileRunStore(local_temp_root() / "run_listing")
    first = _run_record("run_a", latest_checkpoint_id="run_a.000002")
    second = _run_record("run_b", latest_checkpoint_id="run_b.000001")
    store.save_run(second)
    store.save_run(first)
    store.save_checkpoint(_checkpoint("run_a", sequence=1))
    store.save_checkpoint(_checkpoint("run_a", sequence=2))

    assert [record.id for record in store.list_runs()] == ["run_a", "run_b"]
    assert [item.sequence for item in store.list_checkpoints("run_a")] == [1, 2]
```

- [ ] **Step 2: Run tests and verify the run package is absent**

Run:

```bash
uv run pytest -q tests/artifacts/test_run_store.py
```

Expected: FAIL on missing `wf_artifacts.runs`.

- [ ] **Step 3: Implement typed run models**

Create `src/wf_artifacts/runs/models.py`:

```python
from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from wf_core import PersistedRunState
from ..models import DependencyDiagnostic, WorkflowArtifact, WorkflowDeployment


class StoredRunStatus(StrEnum):
    INTERRUPTED = "interrupted"
    COMPLETED = "completed"
    FAILED = "failed"


class ResumeReadiness(StrEnum):
    READY = "ready"
    BLOCKED = "blocked"
    NOT_APPLICABLE = "not_applicable"


class CheckpointReason(StrEnum):
    INTERRUPTED = "interrupted"
    COMPLETED = "completed"
    FAILED = "failed"


class PinnedRunEnvironment(BaseModel):
    """Immutable execution definitions captured when a run starts."""

    model_config = ConfigDict(extra="forbid")

    deployment: WorkflowDeployment
    root_artifact: WorkflowArtifact
    child_artifacts: list[WorkflowArtifact] = Field(default_factory=list)


class WorkflowRunRecord(BaseModel):
    """Durable summary and pinned environment for one started run."""

    model_config = ConfigDict(extra="forbid")

    id: str
    status: StoredRunStatus
    resume_readiness: ResumeReadiness
    environment: PinnedRunEnvironment
    latest_checkpoint_id: str
    diagnostics: list[DependencyDiagnostic] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class RunCheckpoint(BaseModel):
    """One stopped-state checkpoint written at a public run boundary."""

    model_config = ConfigDict(extra="forbid")

    id: str
    run_id: str
    sequence: int = Field(ge=1)
    reason: CheckpointReason
    state: PersistedRunState
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

Use a small factory function or classmethod for timestamp initialization only
if later lifecycle implementation demonstrates repeated construction
boilerplate. Do not invent mutable state transitions inside the Pydantic
models.

- [ ] **Step 4: Implement `RunStore` and `FileRunStore`**

Create `src/wf_artifacts/runs/store.py` with:

```python
class RunStore:
    """Persistence boundary for execution run summaries and checkpoints."""

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
    """JSON file-backed stopped-run store for local execution."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.runs_dir.mkdir(parents=True, exist_ok=True)

    @property
    def runs_dir(self) -> Path:
        return self.root / "runs"
```

Store each run at `runs/<safe_run_id>/run.json` and each checkpoint at
`runs/<safe_run_id>/checkpoints/<sequence:06d>.json`. Reuse or add the same
safe identifier validation discipline used for draft workspaces; reject path
separators and traversal before writing.

- [ ] **Step 5: Export the package and verify store tests**

Export the run models/store from `src/wf_artifacts/runs/__init__.py` and
`src/wf_artifacts/__init__.py`.

Run:

```bash
uv run pytest -q tests/artifacts/test_run_store.py
uvx ruff check src/wf_artifacts tests/artifacts/test_run_store.py
uv run basedpyright --level error src/wf_artifacts tests/artifacts/test_run_store.py
```

Expected: PASS and `0 errors`.

---

### Task 3: Pin The Resolved Saved-Child Environment Used By A Run

**Files:**

- Modify: `src/wf_mcp/workflow_surface/saved_subgraphs.py`
- Modify: `src/wf_mcp/broker/service/core.py`
- Test: `tests/wf_mcp/test_saved_subgraphs.py`
- Test: `tests/wf_mcp/test_durable_runs.py`

- [ ] **Step 1: Write failing tests proving resume uses saved snapshots rather than overwritten artifact files**

Add a durable run integration test:

```python
def test_interrupted_run_resumes_against_pinned_child_snapshot_after_store_overwrite() -> None:
    store = FileWorkflowArtifactStore(local_temp_root() / "pinned_children")
    run_store = FileRunStore(local_temp_root() / "pinned_children")
    store.save_artifact(_parent_artifact())
    store.save_artifact(_interrupting_child_artifact(output_field="echoed"))
    store.save_deployment(_deployment())
    first_handlers = _handlers(store, run_store=run_store)

    paused = asyncio.run(
        first_handlers.run_deployment(
            deployment_id="parent.personal",
            workflow_input={"text": "hello"},
        )
    )

    # The current file store permits replacement of one artifact version.
    store.save_artifact(_interrupting_child_artifact(output_field="changed"))
    second_handlers = _handlers(store, run_store=run_store)
    resumed = asyncio.run(
        second_handlers.resume_run(
            run_id=paused["run_id"],
            resume_payload={"answer": "world"},
        )
    )

    assert resumed["status"] == "completed"
    assert resumed["output"]["echoed"] == "world"
```

This test is deliberately about pinning; it must not be changed to expect the
overwritten child definition.

- [ ] **Step 2: Run the new test and verify current process-local storage cannot pass it**

Run:

```bash
uv run pytest -q tests/wf_mcp/test_durable_runs.py::test_interrupted_run_resumes_against_pinned_child_snapshot_after_store_overwrite
```

Expected: FAIL because the run is not durable and/or resume reloads child
definitions from the artifact store.

- [ ] **Step 3: Add reconstruction from pinned child artifact snapshots**

In `src/wf_mcp/workflow_surface/saved_subgraphs.py`, add a constructor that
does not read the mutable artifact store:

```python
def saved_subgraph_tree_from_snapshots(
    child_artifacts: list[WorkflowArtifact],
) -> SavedSubgraphTree:
    """Restore a previously resolved child tree from pinned run snapshots."""
    return SavedSubgraphTree(
        artifacts_by_ref={
            str(workflow_ref_from_artifact(artifact)): artifact
            for artifact in child_artifacts
        },
        diagnostics=[],
    )
```

Use the actual existing reference display helper if its spelling differs; do
not create a new dotted-string parser.

- [ ] **Step 4: Let service execution accept an already-pinned tree**

Extend `_prepare_workflow_runtime`, `run_workflow_from_plan`, and
`resume_workflow_from_plan` with an optional `saved_subgraph_tree` parameter.
When supplied, compile/prepare from it rather than resolving descendants again
through `artifact_store`.

Keep the comment explicit:

```python
# Durable resumes must execute the saved child definitions captured when the
# run started; the file artifact store can otherwise be overwritten in place.
```

- [ ] **Step 5: Verify saved-child and pinning tests**

Run:

```bash
uv run pytest -q tests/wf_mcp/test_saved_subgraphs.py tests/wf_mcp/test_durable_runs.py
uv run basedpyright --level error src/wf_mcp tests/wf_mcp/test_saved_subgraphs.py tests/wf_mcp/test_durable_runs.py
```

Expected: PASS and `0 errors`.

---

### Task 4: Replace Process-Local Active Runs With Durable Lifecycle Helpers

**Files:**

- Modify: `src/wf_core/runtime/engine.py`
- Create: `src/wf_mcp/workflow_surface/run_lifecycle.py`
- Modify: `src/wf_mcp/workflow_surface/handlers.py`
- Modify: `src/wf_mcp/broker/service/core.py`
- Modify: `src/wf_mcp/broker/config.py`
- Test: `tests/wf_mcp/test_durable_runs.py`
- Create: `tests/core/test_execution_results.py`

- [ ] **Step 1: Write failing tests for completed, failed, and restart-resumable run persistence**

Create `tests/wf_mcp/test_durable_runs.py` with cases:

```python
def test_completed_deployment_creates_durable_run_and_checkpoint() -> None:
    handlers, run_store = _completed_handlers_with_run_store()
    payload = asyncio.run(
        handlers.run_deployment(
            deployment_id="echo.personal",
            workflow_input={"text": "hello"},
        )
    )

    stored = run_store.get_run(payload["run_id"])
    checkpoint = run_store.get_latest_checkpoint(payload["run_id"])
    assert stored.status == StoredRunStatus.COMPLETED
    assert stored.resume_readiness == ResumeReadiness.NOT_APPLICABLE
    assert load_run_state(checkpoint.state.model_dump()).output["echoed"] == "hello"


def test_interrupted_run_resumes_after_handler_recreation() -> None:
    first_handlers, run_store = _interrupting_handlers_with_run_store()
    paused = asyncio.run(
        first_handlers.run_deployment(
            deployment_id="parent.personal",
            workflow_input={"text": "hello"},
        )
    )
    second_handlers, _ = _interrupting_handlers_with_run_store(run_store=run_store)

    resumed = asyncio.run(second_handlers.resume_run(
        run_id=paused["run_id"],
        resume_payload={"answer": "world"},
    ))

    assert resumed["status"] == "completed"
    assert run_store.get_latest_checkpoint(paused["run_id"]).sequence == 2


def test_runtime_failure_is_persisted_as_failed_not_interrupted() -> None:
    handlers, run_store = _failing_handlers_with_run_store()
    payload = asyncio.run(
        handlers.run_deployment(
            deployment_id="explode.personal",
            workflow_input={},
        )
    )
    assert payload["status"] == "failed"
    assert run_store.get_run(payload["run_id"]).status == StoredRunStatus.FAILED


def test_failure_after_resume_is_persisted_as_failed_not_interrupted() -> None:
    handlers, run_store = _interrupt_then_fail_handlers_with_run_store()
    paused = asyncio.run(
        handlers.run_deployment(
            deployment_id="approval.personal",
            workflow_input={},
        )
    )
    failed = asyncio.run(
        handlers.resume_run(
            run_id=paused["run_id"],
            resume_payload={"approved": True},
        )
    )
    assert failed["status"] == "failed"
    assert run_store.get_run(paused["run_id"]).status == StoredRunStatus.FAILED
```

Also add a core regression test for a new captured-result API:

```python
def test_execute_workflow_result_async_returns_failed_state_without_changing_strict_execute() -> None:
    workflow = Workflow(
        name="failing",
        input_schema=_schema({}),
        state_schema=StateSchema.from_field_map({}),
        output_schema=_schema({}),
        outcomes=["ok"],
        start="explode",
        node_defs=[
            NodeDef(
                name="explode",
                input_schema=_schema({}),
                output_schema=_schema({}),
                outcomes=["ok"],
            )
        ],
        nodes=[NodeUse(id="explode", type="node", node="explode")],
        edges=[Edge.model_validate({"from": "explode", "outcome": "ok", "to": END})],
    )

    def explode(_payload: dict[str, object], _context: RuntimeContext) -> dict[str, object]:
        raise ValueError("boom")

    async def explode_async(
        payload: dict[str, object], context: RuntimeContext
    ) -> dict[str, object]:
        return explode(payload, context)

    failed = asyncio.run(
        execute_workflow_result_async(workflow, {}, {"explode": explode_async})
    )
    assert failed.status is RunStatus.FAILED
    assert "boom" in failed.error

    with pytest.raises(ValueError, match="boom"):
        asyncio.run(execute_workflow_async(workflow, {}, {"explode": explode_async}))


def test_resume_workflow_result_async_returns_failed_state_without_changing_strict_resume() -> None:
    interrupted = _interrupted_run_before_explode()

    failed = asyncio.run(
        resume_workflow_result_async(
            _interrupt_then_explode_workflow(),
            interrupted,
            {"explode": _explode_async},
            resume_payload={"approved": True},
        )
    )

    assert failed.status is RunStatus.FAILED
    assert "boom" in failed.error
```

This preserves the existing strict core execution API for direct callers while
giving the platform a failed `RunState` it can persist.

- [ ] **Step 2: Run tests and verify process-local behavior fails restart resume**

Run:

```bash
uv run pytest -q tests/wf_mcp/test_durable_runs.py
```

Expected: FAIL because no run store is wired and `_active_runs` is process-local.

- [ ] **Step 3: Add a core result-returning execution entrypoint for the platform**

In `src/wf_core/runtime/engine.py`, add a sibling entrypoint such as:

```python
async def execute_workflow_result_async(
    workflow: Workflow,
    workflow_input: dict[str, Any],
    registry: Mapping[str, AsyncNodeHandler],
    *,
    reducers: Mapping[str, ReducerDefinition] | None = None,
    subgraphs: Mapping[str, PreparedSubgraph[AsyncNodeHandler]] | None = None,
) -> RunState:
    """Execute and return terminal failed state rather than raising node failures."""
    run = create_run_state(workflow, workflow_input)
    try:
        prepare_new_run(workflow, workflow_input, run)
        return await resume_workflow_async(
            workflow,
            run,
            registry,
            reducers=reducers,
            subgraphs=subgraphs,
        )
    except Exception as exc:
        run.status = RunStatus.FAILED
        run.error = str(exc)
        return run


async def resume_workflow_result_async(
    workflow: Workflow,
    run: RunState,
    registry: Mapping[str, AsyncNodeHandler],
    *,
    resume_payload: dict[str, Any] | None = None,
    resume_outcome: str = "submitted",
    reducers: Mapping[str, ReducerDefinition] | None = None,
    subgraphs: Mapping[str, PreparedSubgraph[AsyncNodeHandler]] | None = None,
) -> RunState:
    """Resume and return terminal failed state rather than raising node failures."""
    try:
        return await resume_workflow_async(
            workflow,
            run,
            registry,
            resume_payload=resume_payload,
            resume_outcome=resume_outcome,
            reducers=reducers,
            subgraphs=subgraphs,
        )
    except Exception as exc:
        run.status = RunStatus.FAILED
        run.error = str(exc)
        return run
```

Export it through `wf_core.__init__`. Use this new result-oriented entrypoint
from `WfMcpService.run_workflow_from_plan`, and use
`resume_workflow_result_async` from `resume_workflow_from_plan`; do not change
existing strict raise-on-failure APIs.

- [ ] **Step 4: Add lifecycle helper functions outside `handlers.py`**

Create `src/wf_mcp/workflow_surface/run_lifecycle.py` with focused helpers:

```python
def create_pinned_environment(
    *,
    deployment: WorkflowDeployment,
    artifact: WorkflowArtifact,
    tree: SavedSubgraphTree,
) -> PinnedRunEnvironment:
    """Capture the exact graph definitions and bindings used for one run."""


def persist_stopped_run(
    *,
    store: RunStore,
    environment: PinnedRunEnvironment,
    run: RunState,
    run_id: str | None = None,
) -> WorkflowRunRecord:
    """Write one run summary and its next stopped-state checkpoint."""


def restore_interrupted_run(
    store: RunStore, run_id: str
) -> tuple[WorkflowRunRecord, RunState]:
    """Load the latest typed checkpoint for a resumable interrupted run."""
```

`persist_stopped_run` must reject a `RunState` still marked `PENDING` or
`RUNNING`; V1 stores stopped boundaries only.

- [ ] **Step 5: Add `run_store` dependency to `WfMcpService`**

In `src/wf_mcp/broker/service/core.py`, add:

```python
run_store: RunStore | None = None
```

In `__post_init__`, default it to:

```python
if self.run_store is None:
    self.run_store = FileRunStore(_store_root(self.store))
```

In `src/wf_mcp/broker/config.py`, pass
`run_store=FileRunStore(config.store_root)` alongside existing stores.

- [ ] **Step 6: Replace `_active_runs` use in the workflow surface**

In `handlers.py`:

- remove `ActiveWorkflowRun`
- remove `self._active_runs`
- on successful start execution, call `persist_stopped_run(...)`
- on resume, load `WorkflowRunRecord` plus checkpoint through
  `restore_interrupted_run(...)`
- reconstruct the pinned saved-child tree and run from its stored environment
- persist the new stopped snapshot under the existing `run_id`

Do not embed file-store knowledge in handlers. It receives only `RunStore`.

- [ ] **Step 7: Verify durable lifecycle tests**

Run:

```bash
uv run pytest -q tests/core/test_execution_results.py tests/wf_mcp/test_durable_runs.py tests/wf_mcp/test_saved_subgraphs.py tests/wf_mcp/test_workflow_surface.py
uvx ruff check src/wf_core src/wf_mcp src/wf_artifacts tests/wf_mcp/test_durable_runs.py
uv run basedpyright --level error src/wf_core src/wf_mcp src/wf_artifacts tests/wf_mcp
```

Expected: PASS and `0 errors`.

---

### Task 5: Block Resume When Pinned External Dependencies Are No Longer Ready

**Files:**

- Modify: `src/wf_mcp/workflow_surface/run_lifecycle.py`
- Modify: `src/wf_mcp/workflow_surface/handlers.py`
- Test: `tests/wf_mcp/test_durable_runs.py`

- [ ] **Step 1: Write failing tests for blocked and restored resume readiness**

```python
def test_resume_keeps_interrupted_run_blocked_when_pinned_source_is_disabled() -> None:
    handlers, run_store, service = _paused_run_fixture()
    paused = asyncio.run(
        handlers.run_deployment(
            deployment_id="parent.personal",
            workflow_input={"text": "hello"},
        )
    )
    service.connections.get("demo.personal").enabled = False

    blocked = asyncio.run(handlers.resume_run(
        run_id=paused["run_id"],
        resume_payload={"answer": "world"},
    ))

    stored = run_store.get_run(paused["run_id"])
    checkpoint = run_store.get_latest_checkpoint(paused["run_id"])
    assert blocked["status"] == "interrupted"
    assert blocked["resume_readiness"] == "blocked"
    assert blocked["diagnostics"][0]["severity"] == "error"
    assert stored.resume_readiness == ResumeReadiness.BLOCKED
    assert checkpoint.sequence == 1


def test_blocked_interrupted_run_can_resume_after_pinned_source_returns() -> None:
    handlers, _run_store, service = _paused_run_fixture()
    paused = asyncio.run(
        handlers.run_deployment(
            deployment_id="parent.personal",
            workflow_input={"text": "hello"},
        )
    )
    service.connections.get("demo.personal").enabled = False
    asyncio.run(
        handlers.resume_run(
            run_id=paused["run_id"],
            resume_payload={"answer": "world"},
        )
    )
    service.connections.get("demo.personal").enabled = True
    resumed = asyncio.run(
        handlers.resume_run(
            run_id=paused["run_id"],
            resume_payload={"answer": "world"},
        )
    )
    assert resumed["status"] == "completed"
    assert resumed["resume_readiness"] == "not_applicable"
```

- [ ] **Step 2: Run tests and confirm current resume proceeds without durable readiness**

Run:

```bash
uv run pytest -q tests/wf_mcp/test_durable_runs.py -k 'blocked or returns'
```

Expected: FAIL.

- [ ] **Step 3: Revalidate the pinned environment before mutation**

Add a lifecycle function:

```python
def validate_pinned_resume_environment(
    *,
    record: WorkflowRunRecord,
    sources: dict[str, CapabilitySource],
) -> list[DependencyDiagnostic]:
    """Validate the stored graph contract against current external sources."""
```

It must validate `record.environment.root_artifact` and each stored child
artifact against `record.environment.deployment`; it must not load replacement
artifact definitions from the current artifact store.

In `resume_run`, perform this before applying resume payload or executing core.
If blocking diagnostics exist:

- update only run summary readiness/diagnostics
- keep `status="interrupted"`
- do not append a checkpoint, because execution state did not change
- return a compact blocked response

- [ ] **Step 4: Verify blocked-resume behavior**

Run:

```bash
uv run pytest -q tests/wf_mcp/test_durable_runs.py tests/wf_mcp/test_saved_subgraphs.py
uv run basedpyright --level error src/wf_mcp tests/wf_mcp/test_durable_runs.py
```

Expected: PASS and `0 errors`.

---

### Task 6: Expose Inspect And Bounded Trace Tools

**Files:**

- Modify: `src/wf_mcp/workflow_surface/handlers.py`
- Modify: `src/wf_mcp/workflow_surface/tools.py`
- Modify: `src/wf_mcp/broker/artifact_tools.py`
- Test: `tests/wf_mcp/test_server.py`
- Test: `tests/wf_mcp/test_durable_runs.py`

- [ ] **Step 1: Write failing public-surface tests**

Add tests asserting:

```python
def test_inspect_run_returns_summary_without_trace_payload() -> None:
    payload = asyncio.run(handlers.inspect_run(run_id=run_id))
    assert payload["run_id"] == run_id
    assert payload["status"] == "completed"
    assert payload["trace_count"] == 1
    assert "trace" not in payload


def test_read_run_trace_returns_bounded_slice_and_total_count() -> None:
    payload = asyncio.run(handlers.read_run_trace(
        run_id=run_id,
        trace_range=TraceRange(start=1, limit=1),
    ))
    assert payload["trace_start"] == 1
    assert payload["trace_limit"] == 1
    assert payload["trace_count"] == 3
    assert len(payload["trace"]) == 1
    assert payload["trace_truncated"] is True
```

In server schema tests, assert field-level descriptions state that trace
retrieval is debug-oriented and bounded.

- [ ] **Step 2: Run tests and verify tools do not exist**

Run:

```bash
uv run pytest -q tests/wf_mcp/test_durable_runs.py tests/wf_mcp/test_server.py
```

Expected: FAIL for missing handler/tool registrations.

- [ ] **Step 3: Implement compact inspection and trace retrieval**

Add handler methods:

```python
async def inspect_run(self, *, run_id: str) -> dict[str, Any]:
    """Return durable run summary and latest stopped-state result, without trace detail."""


async def read_run_trace(
    self, *, run_id: str, trace_range: TraceRange
) -> dict[str, Any]:
    """Return only the requested slice of a stored run trace."""
```

Register:

```text
wf.workflow.inspect_run
wf.workflow.read_run_trace
```

The legacy/broker alias surface may expose parallel helper names only if it is
still exercised by tests; do not reintroduce redundant raw call tools.

- [ ] **Step 4: Verify MCP tool response/schema tests**

Run:

```bash
uv run pytest -q tests/wf_mcp/test_durable_runs.py tests/wf_mcp/test_server.py tests/wf_mcp/test_broker_server.py
uvx ruff check src/wf_mcp tests/wf_mcp
uv run basedpyright --level error src/wf_mcp tests/wf_mcp
```

Expected: PASS and `0 errors`.

---

### Task 7: Documentation, Regression Verification, And Unsupported Policy Notes

**Files:**

- Modify: `docs/current_roadmap.md`
- Modify: `docs/workflow_artifacts.md`
- Modify: `docs/wf_mcp_operator_manual.md`
- Modify: `docs/wf_mcp_troubleshooting.md`
- Modify: `docs/superpowers/specs/2026-05-26-durable-workflow-runs-and-resume-design.md`

- [ ] **Step 1: Update docs from planned to implemented language**

When implementation passes, update documentation to state:

- run ids are durable for stopped deployments
- completed, failed, and interrupted runs are stored
- `inspect_run` and `read_run_trace` are the detail surfaces
- interrupted runs can be blocked on pinned dependency drift and later resumed
- runtime transport failures are failed runs, never implicit pauses
- retry and timeout fields still have no runtime enforcement

Do not claim per-step crash recovery, replay, tasks/progress, or retry support.

- [ ] **Step 2: Add troubleshooting paths**

Document:

```text
run_deployment -> interrupted -> inspect_run -> resume_run
resume_run -> blocked -> repair/reenable exact pinned source -> resume_run
run_deployment -> failed due to tool disconnect -> inspect_run/read_run_trace
```

- [ ] **Step 3: Run the affected suites**

Run:

```bash
uv run pytest -q tests/core/test_run_codec.py tests/artifacts/test_run_store.py tests/wf_mcp/test_durable_runs.py tests/wf_mcp/test_saved_subgraphs.py tests/wf_mcp/test_workflow_surface.py tests/wf_mcp/test_server.py tests/wf_mcp/test_broker_server.py
uvx ruff check src tests
uv run basedpyright --level error src tests
```

Expected: PASS and `0 errors`.

- [ ] **Step 4: Run the full suite**

Run:

```bash
uv run pytest -q
```

Expected baseline before this feature: `643 passed, 1 skipped, 1 xfailed`.
Expected after implementation: baseline plus the new run codec/store/durable
workflow tests, with the existing skip/xfail unchanged unless deliberately
addressed by another task.

---

## Plan Self-Review

- Spec coverage: codec, typed durable records, stopped-run persistence, pinned
  root/child/deployment snapshots, blocked resume validation, compact inspect,
  bounded trace, and retry/timeout non-support all have explicit tasks/tests.
- Package direction: `wf_artifacts.runs` is intentional for v1 because strongly
  typed run snapshots require `WorkflowArtifact` and `WorkflowDeployment`, while
  `wf_artifacts` already depends on `wf_platform`.
- Behavior boundary: no task checkpoints in-flight external calls or turns
  transport failure into resumable interruption.
- Existing-file pressure: lifecycle logic is explicitly extracted into
  `run_lifecycle.py` instead of growing `handlers.py` further.
