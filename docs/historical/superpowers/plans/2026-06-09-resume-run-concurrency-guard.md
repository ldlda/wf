# Resume Run Concurrency Guard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent two concurrent `resume_run` calls in the same server process from both advancing the same interrupted run from the same checkpoint.

**Architecture:** Add a small process-local keyed async lock helper in `wf_api`, then wrap `WorkflowRunApi.resume_run()` with a critical section keyed by `run_id`. This intentionally protects one long-lived API process; it does not pretend the JSON filesystem store is safe for multi-process/cloud concurrency, which remains a transactional-store follow-up.

**Tech Stack:** Python 3.14, `asyncio.Lock`, pytest, pytest-asyncio, `wf_api`, `wf_artifacts.FileRunStore`.

---

## File Structure

- Create `src/wf_api/run_locks.py`
  - Owns one focused helper, `AsyncKeyedLock`, for process-local async critical sections keyed by string ids.
  - No dependency on run models or stores.
- Modify `src/wf_api/runs.py`
  - Instantiate a resume lock registry on `WorkflowRunApi`.
  - Wrap the existing resume implementation in `async with self._resume_locks.lock(run_id)`.
  - Add a short comment explaining why the lock lives above `RunStore`.
- Create `tests/wf_api/test_run_locks.py`
  - Tests lock serialization for the same key and concurrency for different keys.
- Create `tests/wf_api/test_resume_concurrency.py`
  - Seeds an interrupted run directly in `FileRunStore`.
  - Uses a fake runtime that blocks inside `resume_workflow_from_plan`.
  - Starts two concurrent resumes for the same `run_id`.
  - Asserts only the first reaches runtime and the second rejects after the first persists completion.
- Modify `docs/superpowers/specs/2026-06-03-persisted-run-resume-contract.md`
  - Mark the process-local guard as the next concrete slice.
  - Keep the transactional-store limitation explicit.
- Modify `docs/current_roadmap.md`
  - Link this active implementation plan under Priority 2.

---

### Task 1: Add Keyed Async Lock Tests

**Files:**
- Create: `tests/wf_api/test_run_locks.py`

- [ ] **Step 1: Write failing tests for the lock helper**

Create `tests/wf_api/test_run_locks.py`:

```python
from __future__ import annotations

import asyncio

from wf_api.run_locks import AsyncKeyedLock


async def test_async_keyed_lock_serializes_same_key() -> None:
    locks = AsyncKeyedLock()
    entered: list[str] = []
    release_first = asyncio.Event()

    async def first() -> None:
        async with locks.lock("run_123"):
            entered.append("first")
            await release_first.wait()

    async def second() -> None:
        async with locks.lock("run_123"):
            entered.append("second")

    first_task = asyncio.create_task(first())
    await asyncio.sleep(0)
    second_task = asyncio.create_task(second())
    await asyncio.sleep(0)

    assert entered == ["first"]

    release_first.set()
    await asyncio.gather(first_task, second_task)

    assert entered == ["first", "second"]


async def test_async_keyed_lock_allows_different_keys_concurrently() -> None:
    locks = AsyncKeyedLock()
    entered: list[str] = []
    release = asyncio.Event()

    async def hold(key: str) -> None:
        async with locks.lock(key):
            entered.append(key)
            await release.wait()

    first_task = asyncio.create_task(hold("run_a"))
    second_task = asyncio.create_task(hold("run_b"))
    await asyncio.sleep(0)

    assert entered == ["run_a", "run_b"]

    release.set()
    await asyncio.gather(first_task, second_task)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/wf_api/test_run_locks.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'wf_api.run_locks'`.

---

### Task 2: Implement `AsyncKeyedLock`

**Files:**
- Create: `src/wf_api/run_locks.py`

- [ ] **Step 1: Add the keyed lock helper**

Create `src/wf_api/run_locks.py`:

```python
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass


@dataclass(slots=True)
class _LockEntry:
    lock: asyncio.Lock
    users: int = 0


class AsyncKeyedLock:
    """Process-local async critical sections keyed by a stable string id.

    This helper intentionally does not provide cross-process locking. Use it for
    one API/server process; use a transactional store for multi-worker safety.
    """

    def __init__(self) -> None:
        self._guard = asyncio.Lock()
        self._entries: dict[str, _LockEntry] = {}

    @asynccontextmanager
    async def lock(self, key: str) -> AsyncIterator[None]:
        """Hold the critical section for `key` until the context exits."""
        entry = await self._retain(key)
        await entry.lock.acquire()
        try:
            yield
        finally:
            entry.lock.release()
            await self._release(key, entry)

    async def _retain(self, key: str) -> _LockEntry:
        async with self._guard:
            entry = self._entries.get(key)
            if entry is None:
                entry = _LockEntry(lock=asyncio.Lock())
                self._entries[key] = entry
            entry.users += 1
            return entry

    async def _release(self, key: str, entry: _LockEntry) -> None:
        async with self._guard:
            entry.users -= 1
            if entry.users == 0 and not entry.lock.locked():
                self._entries.pop(key, None)
```

- [ ] **Step 2: Run keyed lock tests**

Run:

```bash
uv run pytest tests/wf_api/test_run_locks.py -q
```

Expected: PASS, `2 passed`.

- [ ] **Step 3: Run lint/typecheck on the new helper**

Run:

```bash
uv run ruff check src/wf_api/run_locks.py tests/wf_api/test_run_locks.py
uv run basedpyright --level error src/wf_api/run_locks.py tests/wf_api/test_run_locks.py
```

Expected:

```text
All checks passed!
0 errors, 0 warnings, 0 notes
```

- [ ] **Step 4: Commit the helper**

Run:

```bash
git add src/wf_api/run_locks.py tests/wf_api/test_run_locks.py
git commit -m "feat: add async keyed lock helper"
```

---

### Task 3: Add Same-Run Resume Race Regression Test

**Files:**
- Create: `tests/wf_api/test_resume_concurrency.py`

- [ ] **Step 1: Write the failing resume race test**

Create `tests/wf_api/test_resume_concurrency.py`:

```python
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
from wf_platform import CapabilityBuckets, CapabilitySource


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


def test_resume_run_serializes_same_run_attempts(tmp_path: Path) -> None:
    async def scenario() -> None:
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

    asyncio.run(scenario())


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
            tree=SavedSubgraphTree(artifacts_by_ref={}),
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
            "nodes": [
                {"id": "end_submitted", "type": "end", "outcome": "submitted"}
            ],
            "edges": [],
        },
    )
```

- [ ] **Step 2: Run the test to verify the race exists**

Run:

```bash
uv run pytest tests/wf_api/test_resume_concurrency.py -q
```

Expected before wiring the lock: FAIL. The likely failure is:

```text
assert runtime.entered == 1
E assert 2 == 1
```

If the failure appears later as duplicate checkpoint sequence or final output from `"second"`, that is also acceptable. The test must fail because the second concurrent resume reaches runtime or writes from the same starting checkpoint.

---

### Task 4: Wrap `WorkflowRunApi.resume_run` With the Keyed Lock

**Files:**
- Modify: `src/wf_api/runs.py`

- [ ] **Step 1: Import and instantiate the lock helper**

In `src/wf_api/runs.py`, add the import:

```python
from .run_locks import AsyncKeyedLock
```

Change the constructor from:

```python
    def __init__(self, context: WorkflowOperationContext) -> None:
        self.context = context
        self.deployments = WorkflowDeploymentApi(context)
```

to:

```python
    def __init__(
        self,
        context: WorkflowOperationContext,
        *,
        resume_locks: AsyncKeyedLock | None = None,
    ) -> None:
        self.context = context
        self.deployments = WorkflowDeploymentApi(context)
        self._resume_locks = resume_locks or AsyncKeyedLock()
```

- [ ] **Step 2: Split the unlocked resume body into a private helper**

Replace the current `resume_run` method with this wrapper plus private method:

```python
    async def resume_run(
        self,
        *,
        run_id: str,
        resume_payload: dict[str, Any],
        resume_outcome: str = "submitted",
        trace_range: TraceRangeLike | None = None,
    ) -> dict[str, Any]:
        """Resume one durable interrupted deployment run."""
        # FileRunStore locks individual file writes only. The API layer owns the
        # process-local read/execute/write critical section for one run id.
        async with self._resume_locks.lock(run_id):
            return await self._resume_run_unlocked(
                run_id=run_id,
                resume_payload=resume_payload,
                resume_outcome=resume_outcome,
                trace_range=trace_range,
            )

    async def _resume_run_unlocked(
        self,
        *,
        run_id: str,
        resume_payload: dict[str, Any],
        resume_outcome: str,
        trace_range: TraceRangeLike | None,
    ) -> dict[str, Any]:
        trace_values = _trace_range_values(trace_range)
        record, stopped_run = restore_interrupted_run(self._run_store(), run_id)
        environment = record.environment
        diagnostics = validate_pinned_resume_environment(
            record=record,
            sources=_available_sources(self.context.specs.capability_sources),
        )
        if has_blocking_diagnostics(diagnostics):
            blocked = mark_resume_blocked(
                store=self._run_store(),
                record=record,
                diagnostics=diagnostics,
            )
            return _run_payload(
                deployment=environment.deployment,
                artifact=environment.root_artifact,
                status=stopped_run.status.value,
                run_id=blocked.id,
                resume_readiness=blocked.resume_readiness.value,
                interrupt=_interrupt_payload(stopped_run),
                outcome=stopped_run.outcome,
                error=stopped_run.error,
                output=stopped_run.output,
                diagnostics=diagnostics,
                trace_count=len(stopped_run.trace),
            )
        plan = raw_plan_from_artifact(environment.root_artifact)
        tree = saved_subgraph_tree_from_snapshots(environment.child_artifacts)
        run = await self.context.runtime.resume_workflow_from_plan(
            plan,
            stopped_run,
            resume_payload=resume_payload,
            resume_outcome=resume_outcome,
            deployment=environment.deployment,
            artifact=environment.root_artifact,
            saved_subgraph_tree=tree,
        )
        next_record = persist_stopped_run(
            store=self._run_store(),
            environment=environment,
            run=run,
            run_id=run_id,
        )
        return _run_payload(
            deployment=environment.deployment,
            artifact=environment.root_artifact,
            status=run.status.value,
            run_id=next_record.id,
            resume_readiness=next_record.resume_readiness.value,
            interrupt=_interrupt_payload(run),
            outcome=run.outcome,
            error=run.error,
            output=run.output,
            trace_count=len(run.trace),
            **_trace_slice_fields(run, trace_values),
        )
```

The body is the existing implementation moved under `_resume_run_unlocked`; do not change blocked-resume or persistence semantics.

- [ ] **Step 3: Run the resume race test**

Run:

```bash
uv run pytest tests/wf_api/test_resume_concurrency.py -q
```

Expected: PASS, `1 passed`.

- [ ] **Step 4: Run existing run API tests**

Run:

```bash
uv run pytest tests/wf_api/test_run_api.py tests/wf_api/test_resume_concurrency.py tests/wf_api/test_run_locks.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit the API wiring**

Run:

```bash
git add src/wf_api/runs.py tests/wf_api/test_resume_concurrency.py
git commit -m "fix: serialize same-run resume attempts"
```

---

### Task 5: Update Durable Resume Docs

**Files:**
- Modify: `docs/superpowers/specs/2026-06-03-persisted-run-resume-contract.md`
- Modify: `docs/current_roadmap.md`

- [ ] **Step 1: Update the resume contract current implementation section**

In `docs/superpowers/specs/2026-06-03-persisted-run-resume-contract.md`, under `### resume_run`, change the current implementation bullets to:

```markdown
Current implementation:

- `WorkflowRunApi.resume_run()` follows this contract for stored interrupted
  runs and blocked dependency validation.
- Same-process callers are serialized per `run_id` around the restore,
  dependency validation, runtime resume, and checkpoint write sequence.
- `restore_interrupted_run()` rejects non-interrupted statuses.
- `mark_resume_blocked()` updates run summary without writing a checkpoint.
```

- [ ] **Step 2: Update the store contract limitation**

In the same spec, replace the `Current limits:` list under `## Store Contract` with:

```markdown
Current limits:

- `WorkflowRunApi.resume_run()` provides a process-local per-run critical
  section for one API/server process.
- `FileRunStore` locks individual file writes only; it does not provide
  compare-and-swap or cross-process transactions.
- The file store is appropriate for local/dev/single-process use.
- A multi-worker or cloud deployment still needs SQLite/Postgres or another
  transactional store before claiming strong concurrent resume safety.
```

- [ ] **Step 3: Update the gap list**

In the same spec, replace gap item `4. **Resume concurrency guard**` with:

```markdown
4. **Resume concurrency guard**
   - Implemented for same-process API callers through a per-`run_id` async
     critical section in `WorkflowRunApi.resume_run()`.
   - Cross-process protection remains part of the transactional backend gap.
```

- [ ] **Step 4: Update the roadmap**

In `docs/current_roadmap.md`, under `## Priority 2: Durable Run/Resume Hardening`, replace:

```markdown
- Add same-run concurrency protection around `resume_run`.
- Clarify store-level locking/transaction expectations for filesystem stores.
```

with:

```markdown
- Completed: same-process `resume_run` calls are serialized per run id.
  Implementation:
  [`resume run concurrency guard`](historical/superpowers/plans/2026-06-09-resume-run-concurrency-guard.md).
- Clarify store-level locking/transaction expectations for future filesystem
  and transactional stores.
```

- [ ] **Step 5: Move this plan to historical after implementation**

After all code and docs pass verification, move this plan:

```bash
git mv docs/superpowers/plans/2026-06-09-resume-run-concurrency-guard.md docs/historical/superpowers/plans/2026-06-09-resume-run-concurrency-guard.md
```

Then commit docs:

```bash
git add docs/current_roadmap.md docs/superpowers/specs/2026-06-03-persisted-run-resume-contract.md docs/historical/superpowers/plans/2026-06-09-resume-run-concurrency-guard.md
git commit -m "docs: record resume concurrency guard"
```

---

### Task 6: Final Verification

**Files:**
- No new files.

- [ ] **Step 1: Run focused tests**

Run:

```bash
uv run pytest tests/wf_api/test_run_locks.py tests/wf_api/test_resume_concurrency.py tests/wf_api/test_run_api.py tests/wf_mcp/test_saved_subgraphs.py tests/wf_transport_rpc_http/test_mcp_backed_server_rpc.py -q
```

Expected: all selected tests pass.

- [ ] **Step 2: Run broader API tests**

Run:

```bash
uv run pytest tests/wf_api -q
```

Expected: all `wf_api` tests pass.

- [ ] **Step 3: Run lint and typecheck**

Run:

```bash
uv run ruff check src/wf_api tests/wf_api
uv run ruff format --check src/wf_api tests/wf_api
uv run basedpyright --level error src/wf_api tests/wf_api/test_run_locks.py tests/wf_api/test_resume_concurrency.py tests/wf_api/test_run_api.py
```

Expected:

```text
All checks passed!
0 errors, 0 warnings, 0 notes
```

- [ ] **Step 4: Inspect git status**

Run:

```bash
git status --short
```

Expected: clean working tree after the commits above.

---

## Self-Review

- Spec coverage: The plan implements the roadmap gap "same-run concurrency protection around `resume_run`" and explicitly preserves the store-level transactional limitation.
- Placeholder scan: No `TBD`, vague "handle errors", or unspecified test work remains.
- Type consistency: `AsyncKeyedLock`, `WorkflowRunApi.resume_run`, `RawWorkflowPlan`, `WorkflowOperationContext`, `FileRunStore`, and `SavedSubgraphTree` names match current code.
- Scope control: This plan does not add run listing, checkpoint listing, retries, cloud transactions, or public API shape changes.
