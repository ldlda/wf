# WfMcpService Runtime Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract workflow compile/prepare/run/resume responsibilities from `WfMcpService` into a focused runtime implementation service while preserving existing public service methods and MCP/CLI behavior.

**Architecture:** Add `WorkflowRuntimeService` under `wf_mcp.broker.service`. It depends on `SourceCatalogService`, an optional artifact store, and an event emitter. `WfMcpService` remains the broker coordinator and compatibility façade; its runtime methods become thin delegates. This follows the previous `SourceCatalogService` extraction and keeps transport/auth/catalog refresh responsibilities out of this slice.

**Tech Stack:** Python 3.14, dataclasses, `wf_core` runtime APIs, `wf_api.runtime_dependencies`, `wf_api.saved_subgraphs`, pytest, ruff, basedpyright.

---

## Scope

Move now:

- `compile_plan`.
- `_prepare_workflow_runtime`, renamed to `prepare_workflow_runtime` on the new service.
- `run_workflow_from_plan`.
- `resume_workflow_from_plan`.
- Runtime event emission for `workflow_run_started`, `workflow_run_completed`, and `workflow_run_resumed`.

Keep now:

- Existing `WfMcpService.compile_plan`, `run_workflow_from_plan`, and `resume_workflow_from_plan` public method names as delegates.
- Existing source/catalog behavior in `SourceCatalogService`.
- Connection/adapters/auth/upstream I/O on `WfMcpService`.
- Catalog refresh on `WfMcpService`.
- Resource/prompt/raw method calls on `WfMcpService`.
- Event bus implementation on `WfMcpService`.

Do not do in this slice:

- Do not introduce a protocol-neutral runtime service in `wf_api`.
- Do not move `WorkflowOperationContext` itself.
- Do not change MCP tool schemas, CLI commands, run payload shape, or saved-run lifecycle models.
- Do not rename `WfMcpService`.

---

## Target File Structure

- Create `src/wf_mcp/broker/service/workflow_runtime.py`
  - Owns runtime compile/prepare/run/resume.
  - Has docstrings explaining that durable resume currently rebuilds dependencies from current in-memory service state.
  - Depends on `SourceCatalogService`, optional `WorkflowArtifactStore`, and event emitter callback.

- Modify `src/wf_mcp/broker/service/core.py`
  - Add `workflow_runtime: WorkflowRuntimeService = field(init=False)`.
  - Construct it in `__post_init__` after `source_catalog`.
  - Keep existing runtime methods as delegates.
  - Remove runtime-only imports after the move.

- Modify `src/wf_mcp/broker/service/workflow_operation_context.py`
  - `WfMcpWorkflowRuntimeRunner` should call `service.workflow_runtime` directly.

- Add direct runtime tests in `tests/wf_mcp/service/test_workflow_runtime.py`
  - Component-level compile/run tests.
  - Compatibility tests that `WfMcpService` still delegates and emits the same events.

- Update docs:
  - `docs/current_roadmap.md`
  - `docs/superpowers/research/2026-06-01-wf-api-extraction-map.md` if stale.

---

## Task 1: Add WorkflowRuntimeService Skeleton and Compile Test

**Files:**

- Create: `src/wf_mcp/broker/service/workflow_runtime.py`
- Create: `tests/wf_mcp/service/test_workflow_runtime.py`
- Modify: `src/wf_mcp/broker/service/core.py`

- [ ] **Step 1: Write the direct compile test**

Create `tests/wf_mcp/service/test_workflow_runtime.py`:

```python
from __future__ import annotations

from wf_core import NodeUse
from wf_mcp.broker.service.source_catalog import SourceCatalogService
from wf_mcp.broker.service.workflow_runtime import WorkflowRuntimeService
from wf_mcp.models import ConnectionConfig
from wf_mcp.storage import FileStore
from wf_platform import CapabilityBuckets, CapabilitySource, SourceVisibility

from ..test_support import echo_tool, local_temp_root
from .conftest import single_echo_plan


def _unused_tool_executor(connection: ConnectionConfig):
    raise AssertionError("tool executor should not be used by direct compile tests")


def _source_catalog() -> SourceCatalogService:
    connection = ConnectionConfig(
        id="demo.personal",
        server="demo",
        account="personal",
    )
    catalog = SourceCatalogService(
        store=FileStore(local_temp_root() / "runtime_source_catalog"),
        connection_lookup=lambda connection_id: connection,
        connection_list_enabled=lambda: [connection],
        connection_list_all=lambda: [connection],
        tool_executor_for=_unused_tool_executor,
        load_auth=lambda connection_id: None,
        emit_event=lambda event: None,
    )
    catalog.register_capability_source(
        CapabilitySource(
            id="demo.personal",
            kind="connection",
            capabilities=CapabilityBuckets(
                node_specs={"demo.personal.echo_tool": echo_tool}
            ),
            visibility=SourceVisibility(planner=True),
        )
    )
    return catalog


def test_workflow_runtime_service_compiles_plan_directly() -> None:
    runtime = WorkflowRuntimeService(
        source_catalog=_source_catalog(),
        artifact_store=None,
        emit_event=lambda event: None,
    )

    workflow = runtime.compile_plan(
        single_echo_plan("runtime_compile", "demo.echo_tool"),
        {"demo.echo_tool": "demo.personal.echo_tool"},
    )

    node = workflow.nodes[0]
    assert isinstance(node, NodeUse)
    assert node.node == "demo.personal.echo_tool"
    assert "demo.personal.echo_tool" in workflow.node_defs
```

- [ ] **Step 2: Run the compile test and verify it fails**

Run:

```bash
uv run pytest tests/wf_mcp/service/test_workflow_runtime.py::test_workflow_runtime_service_compiles_plan_directly -q
```

Expected: import failure because `wf_mcp.broker.service.workflow_runtime` does not exist.

- [ ] **Step 3: Create WorkflowRuntimeService with compile_plan**

Create `src/wf_mcp/broker/service/workflow_runtime.py`:

```python
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from wf_artifacts import WorkflowArtifactStore
from wf_authoring import NodeSpec
from wf_core import NodeUse, Workflow
from wf_api.models import RawWorkflowPlan

from ...events import McpEvent
from .source_catalog import SourceCatalogService

EventEmitter = Callable[[McpEvent], None]


@dataclass(slots=True)
class WorkflowRuntimeService:
    """Compile and execute workflow plans against broker-owned runtime deps.

    This service is still an MCP broker implementation detail. It receives
    source/catalog state from `SourceCatalogService`, but it does not own
    connections, adapters, auth, or upstream discovery.
    """

    source_catalog: SourceCatalogService
    artifact_store: WorkflowArtifactStore | None
    emit_event: EventEmitter

    def compile_plan(
        self,
        plan: RawWorkflowPlan,
        node_name_bindings: dict[str, str] | None = None,
    ) -> Workflow:
        node_defs: dict[str, Any] = {}
        bindings = node_name_bindings or {}
        for step in plan.nodes:
            if not isinstance(step, NodeUse):
                continue
            qualified_name = bindings.get(step.node, step.node)
            spec: NodeSpec[Any, Any] = self.source_catalog.get_qualified_spec(
                qualified_name
            )
            node_defs[qualified_name] = spec.to_node_def()

        nodes = []
        for node in plan.nodes:
            payload = node.model_dump(by_alias=True)
            if isinstance(node, NodeUse):
                payload["node"] = bindings.get(node.node, node.node)
            nodes.append(payload)

        payload = {
            "name": plan.name,
            "input_schema": plan.input_schema,
            "state_schema": plan.state_schema,
            "output_schema": plan.output_schema,
            "output": [binding.model_dump(mode="json") for binding in plan.output],
            "outcomes": plan.outcomes,
            "start": plan.start,
            "node_defs": [node.model_dump() for node in node_defs.values()],
            "nodes": nodes,
            "edges": [edge.model_dump(by_alias=True) for edge in plan.edges],
        }
        return Workflow.model_validate(payload)
```

- [ ] **Step 4: Run the compile test**

Run:

```bash
uv run pytest tests/wf_mcp/service/test_workflow_runtime.py::test_workflow_runtime_service_compiles_plan_directly -q
```

Expected: pass.

- [ ] **Step 5: Run ruff**

Run:

```bash
uv run ruff check src/wf_mcp/broker/service/workflow_runtime.py tests/wf_mcp/service/test_workflow_runtime.py
```

Expected: pass.

---

## Task 2: Wire Runtime Service Into WfMcpService as a Delegate

**Files:**

- Modify: `src/wf_mcp/broker/service/core.py`
- Test: `tests/wf_mcp/service/test_workflow_runtime.py`

- [ ] **Step 1: Add compatibility identity and delegate tests**

Append to `tests/wf_mcp/service/test_workflow_runtime.py`:

```python
from wf_mcp.broker import WfMcpService


def test_wfmcpservice_constructs_workflow_runtime_with_source_catalog() -> None:
    service = WfMcpService(store=FileStore(local_temp_root() / "runtime_delegate"))

    assert service.workflow_runtime.source_catalog is service.source_catalog
    assert service.workflow_runtime.artifact_store is service.artifact_store


def test_wfmcpservice_compile_plan_delegates_to_workflow_runtime() -> None:
    service = WfMcpService(store=FileStore(local_temp_root() / "runtime_compile_delegate"))
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_specs("demo.personal", echo_tool)

    workflow = service.compile_plan(
        single_echo_plan("runtime_delegate_compile", "demo.echo_tool"),
        {"demo.echo_tool": "demo.personal.echo_tool"},
    )

    assert "demo.personal.echo_tool" in workflow.node_defs
```

- [ ] **Step 2: Run the new tests and verify they fail**

Run:

```bash
uv run pytest tests/wf_mcp/service/test_workflow_runtime.py::test_wfmcpservice_constructs_workflow_runtime_with_source_catalog tests/wf_mcp/service/test_workflow_runtime.py::test_wfmcpservice_compile_plan_delegates_to_workflow_runtime -q
```

Expected: first test fails because `workflow_runtime` does not exist.

- [ ] **Step 3: Construct workflow_runtime in WfMcpService**

In `src/wf_mcp/broker/service/core.py`, import:

```python
from .workflow_runtime import WorkflowRuntimeService
```

Add the dataclass field:

```python
    workflow_runtime: WorkflowRuntimeService = field(init=False)
```

In `__post_init__`, after `self.source_catalog = SourceCatalogService(...)`, add:

```python
        self.workflow_runtime = WorkflowRuntimeService(
            source_catalog=self.source_catalog,
            artifact_store=self.artifact_store,
            emit_event=self._record_event,
        )
```

- [ ] **Step 4: Delegate compile_plan**

Replace `WfMcpService.compile_plan` body with:

```python
        return self.workflow_runtime.compile_plan(plan, node_name_bindings)
```

Keep the method signature unchanged.

- [ ] **Step 5: Run delegate tests**

Run:

```bash
uv run pytest tests/wf_mcp/service/test_workflow_runtime.py::test_wfmcpservice_constructs_workflow_runtime_with_source_catalog tests/wf_mcp/service/test_workflow_runtime.py::test_wfmcpservice_compile_plan_delegates_to_workflow_runtime -q
```

Expected: both pass.

- [ ] **Step 6: Run ruff**

Run:

```bash
uv run ruff check src/wf_mcp/broker/service/core.py src/wf_mcp/broker/service/workflow_runtime.py tests/wf_mcp/service/test_workflow_runtime.py
```

Expected: pass.

---

## Task 3: Move Runtime Preparation

**Files:**

- Modify: `src/wf_mcp/broker/service/workflow_runtime.py`
- Modify: `src/wf_mcp/broker/service/core.py`
- Test: `tests/wf_mcp/service/test_workflow_runtime.py`

- [ ] **Step 1: Add a direct preparation test**

Append:

```python
def test_workflow_runtime_service_prepares_node_registry_and_reducers() -> None:
    runtime = WorkflowRuntimeService(
        source_catalog=_source_catalog(),
        artifact_store=None,
        emit_event=lambda event: None,
    )

    workflow, registry, reducers, prepared_subgraphs = runtime.prepare_workflow_runtime(
        single_echo_plan("runtime_prepare", "demo.echo_tool"),
        deployment=None,
        artifact=None,
    )

    assert "demo.personal.echo_tool" in workflow.node_defs
    assert "demo.personal.echo_tool" in registry
    assert isinstance(reducers, dict)
    assert prepared_subgraphs == {}
```

- [ ] **Step 2: Run the preparation test and verify it fails**

Run:

```bash
uv run pytest tests/wf_mcp/service/test_workflow_runtime.py::test_workflow_runtime_service_prepares_node_registry_and_reducers -q
```

Expected: fail because `prepare_workflow_runtime` does not exist.

- [ ] **Step 3: Move _prepare_workflow_runtime into WorkflowRuntimeService**

In `src/wf_mcp/broker/service/workflow_runtime.py`, add imports:

```python
from wf_artifacts import WorkflowArtifact, WorkflowDeployment
from wf_api.runtime_dependencies import resolve_runtime_dependencies
from wf_api.saved_subgraphs import (
    SavedSubgraphTree,
    prepare_saved_subgraphs,
    resolve_saved_subgraph_tree,
)
```

Add the method:

```python
    def prepare_workflow_runtime(
        self,
        plan: RawWorkflowPlan,
        *,
        deployment: WorkflowDeployment | None,
        artifact: WorkflowArtifact | None,
        saved_subgraph_tree: SavedSubgraphTree | None = None,
    ) -> tuple[Workflow, dict[str, Any], dict[str, Any], dict[str, Any]]:
        """Resolve bindings once into the executable pieces core expects.

        Saved-run resume still rebuilds prepared dependencies from the current
        in-memory broker state. Durable resume will need a stricter snapshot,
        but this keeps the current platform boundary explicit.
        """
        plan_node_names = [
            node.node for node in plan.nodes if isinstance(node, NodeUse)
        ]
        runtime_artifact = artifact or WorkflowArtifact(
            id=plan.name,
            version=1,
            title=plan.name,
            input_schema=plan.input_schema,
            output_schema=plan.output_schema,
            outcomes=("completed",),
            plan=plan.model_dump(mode="json", by_alias=True),
        )
        dependencies = resolve_runtime_dependencies(
            artifact=runtime_artifact,
            deployment=deployment,
            sources=self.source_catalog.capability_sources,
            plan_node_names=plan_node_names,
        )
        prepared_subgraphs = {}
        if saved_subgraph_tree is not None:
            prepared_subgraphs = prepare_saved_subgraphs(
                tree=saved_subgraph_tree,
                deployment=deployment,
                sources=self.source_catalog.capability_sources,
                compile_plan=self.compile_plan,
            )
        elif artifact is not None and self.artifact_store is not None:
            tree = resolve_saved_subgraph_tree(
                root_artifact=artifact,
                artifact_store=self.artifact_store,
            )
            prepared_subgraphs = prepare_saved_subgraphs(
                tree=tree,
                deployment=deployment,
                sources=self.source_catalog.capability_sources,
                compile_plan=self.compile_plan,
            )
        workflow = self.compile_plan(plan, dependencies.node_name_bindings)
        return (
            workflow,
            dependencies.node_registry,
            dependencies.reducers,
            prepared_subgraphs,
        )
```

- [ ] **Step 4: Delegate _prepare_workflow_runtime**

In `src/wf_mcp/broker/service/core.py`, replace `_prepare_workflow_runtime` body with:

```python
        return self.workflow_runtime.prepare_workflow_runtime(
            plan,
            deployment=deployment,
            artifact=artifact,
            saved_subgraph_tree=saved_subgraph_tree,
        )
```

Keep the private method signature unchanged for compatibility with any tests or internal callers.

- [ ] **Step 5: Run preparation and hydrated runtime regression tests**

Run:

```bash
uv run pytest tests/wf_mcp/service/test_workflow_runtime.py::test_workflow_runtime_service_prepares_node_registry_and_reducers tests/wf_mcp/service/test_catalog.py::test_service_hydrates_planner_specs_from_stored_catalog -q
```

Expected: both pass.

- [ ] **Step 6: Run ruff**

Run:

```bash
uv run ruff check src/wf_mcp/broker/service/core.py src/wf_mcp/broker/service/workflow_runtime.py tests/wf_mcp/service/test_workflow_runtime.py
```

Expected: pass.

---

## Task 4: Move Run and Resume Execution

**Files:**

- Modify: `src/wf_mcp/broker/service/workflow_runtime.py`
- Modify: `src/wf_mcp/broker/service/core.py`
- Test: `tests/wf_mcp/service/test_workflow_runtime.py`
- Test: `tests/wf_api/test_run_api.py`

- [ ] **Step 1: Add a direct run test with event assertions**

Append:

```python
import asyncio


def test_workflow_runtime_service_runs_plan_and_emits_events() -> None:
    events = []
    runtime = WorkflowRuntimeService(
        source_catalog=_source_catalog(),
        artifact_store=None,
        emit_event=events.append,
    )

    run = asyncio.run(
        runtime.run_workflow_from_plan(
            single_echo_plan("runtime_run", "demo.echo_tool"),
            {"text": "hello"},
        )
    )

    assert run.output["echoed"] == "hello"
    assert [event.type for event in events] == [
        "workflow_run_started",
        "workflow_run_completed",
    ]
    assert events[1].payload["status"] == "completed"
```

- [ ] **Step 2: Run the direct run test and verify it fails**

Run:

```bash
uv run pytest tests/wf_mcp/service/test_workflow_runtime.py::test_workflow_runtime_service_runs_plan_and_emits_events -q
```

Expected: fail because `WorkflowRuntimeService.run_workflow_from_plan` does not exist.

- [ ] **Step 3: Add run and resume methods to WorkflowRuntimeService**

In `src/wf_mcp/broker/service/workflow_runtime.py`, add imports:

```python
from wf_core import (
    RunState,
    execute_workflow_result_async,
    resume_workflow_result_async,
)
from ...events import make_event
```

Add:

```python
    async def run_workflow_from_plan(
        self,
        plan: RawWorkflowPlan,
        workflow_input: dict[str, Any],
        deployment: WorkflowDeployment | None = None,
        artifact: WorkflowArtifact | None = None,
        saved_subgraph_tree: SavedSubgraphTree | None = None,
    ) -> RunState:
        self.emit_event(
            make_event(
                "workflow_run_started",
                workflow_name=plan.name,
                payload={"input_keys": sorted(workflow_input.keys())},
            )
        )
        workflow, registry, reducers, prepared_subgraphs = (
            self.prepare_workflow_runtime(
                plan,
                deployment=deployment,
                artifact=artifact,
                saved_subgraph_tree=saved_subgraph_tree,
            )
        )
        run = await execute_workflow_result_async(
            workflow,
            workflow_input,
            registry,
            reducers=reducers,
            subgraphs=prepared_subgraphs,
        )
        self.emit_event(
            make_event(
                "workflow_run_completed",
                workflow_name=plan.name,
                payload={"status": run.status.value},
            )
        )
        return run

    async def resume_workflow_from_plan(
        self,
        plan: RawWorkflowPlan,
        run: RunState,
        *,
        resume_payload: dict[str, Any],
        resume_outcome: str = "submitted",
        deployment: WorkflowDeployment | None = None,
        artifact: WorkflowArtifact | None = None,
        saved_subgraph_tree: SavedSubgraphTree | None = None,
    ) -> RunState:
        """Resume one stopped run using its prepared runtime dependency boundary."""
        workflow, registry, reducers, prepared_subgraphs = (
            self.prepare_workflow_runtime(
                plan,
                deployment=deployment,
                artifact=artifact,
                saved_subgraph_tree=saved_subgraph_tree,
            )
        )
        resumed = await resume_workflow_result_async(
            workflow,
            run,
            registry,
            resume_payload=resume_payload,
            resume_outcome=resume_outcome,
            reducers=reducers,
            subgraphs=prepared_subgraphs,
        )
        self.emit_event(
            make_event(
                "workflow_run_resumed",
                workflow_name=plan.name,
                payload={"status": resumed.status.value},
            )
        )
        return resumed
```

- [ ] **Step 4: Delegate WfMcpService run/resume**

Replace `WfMcpService.run_workflow_from_plan` body with:

```python
        return await self.workflow_runtime.run_workflow_from_plan(
            plan,
            workflow_input,
            deployment=deployment,
            artifact=artifact,
            saved_subgraph_tree=saved_subgraph_tree,
        )
```

Replace `WfMcpService.resume_workflow_from_plan` body with:

```python
        return await self.workflow_runtime.resume_workflow_from_plan(
            plan,
            run,
            resume_payload=resume_payload,
            resume_outcome=resume_outcome,
            deployment=deployment,
            artifact=artifact,
            saved_subgraph_tree=saved_subgraph_tree,
        )
```

Keep public signatures unchanged.

- [ ] **Step 5: Run direct and API run tests**

Run:

```bash
uv run pytest tests/wf_mcp/service/test_workflow_runtime.py::test_workflow_runtime_service_runs_plan_and_emits_events tests/wf_api/test_run_api.py -q
```

Expected: pass.

- [ ] **Step 6: Run ruff**

Run:

```bash
uv run ruff check src/wf_mcp/broker/service/core.py src/wf_mcp/broker/service/workflow_runtime.py tests/wf_mcp/service/test_workflow_runtime.py
```

Expected: pass.

---

## Task 5: Point WorkflowOperationContext Runtime Adapter at workflow_runtime

**Files:**

- Modify: `src/wf_mcp/broker/service/workflow_operation_context.py`
- Test: `tests/wf_api/test_operation_context.py`
- Test: `tests/wf_api/test_run_api.py`

- [ ] **Step 1: Add an adapter identity test**

In `tests/wf_api/test_operation_context.py`, add:

```python
def test_context_runtime_runner_uses_workflow_runtime_service() -> None:
    service = WfMcpService(store=FileStore(local_temp_root() / "context_runtime"))
    context = context_from_service(service)

    assert getattr(context.runtime, "runtime") is service.workflow_runtime
```

If this file does not have `local_temp_root`, use the same temp-store helper style already used by its neighboring tests.

- [ ] **Step 2: Run the adapter test and verify it fails**

Run:

```bash
uv run pytest tests/wf_api/test_operation_context.py::test_context_runtime_runner_uses_workflow_runtime_service -q
```

Expected: fail because `WfMcpWorkflowRuntimeRunner` stores `service`, not `runtime`.

- [ ] **Step 3: Update runtime adapter**

In `src/wf_mcp/broker/service/workflow_operation_context.py`, import:

```python
from .workflow_runtime import WorkflowRuntimeService
```

Change:

```python
class WfMcpWorkflowRuntimeRunner(WorkflowRuntimeRunner):
    """Adapter-owned runtime runner backed by WfMcpService."""

    service: WfMcpService
```

to:

```python
class WfMcpWorkflowRuntimeRunner(WorkflowRuntimeRunner):
    """Adapter-owned runtime runner backed by WorkflowRuntimeService."""

    runtime: WorkflowRuntimeService
```

Replace calls from `self.service.run_workflow_from_plan(...)` and `self.service.resume_workflow_from_plan(...)` to `self.runtime.run_workflow_from_plan(...)` and `self.runtime.resume_workflow_from_plan(...)`.

In `context_from_service`, change:

```python
        runtime=WfMcpWorkflowRuntimeRunner(service),
```

to:

```python
        runtime=WfMcpWorkflowRuntimeRunner(service.workflow_runtime),
```

- [ ] **Step 4: Run context and run API tests**

Run:

```bash
uv run pytest tests/wf_api/test_operation_context.py::test_context_runtime_runner_uses_workflow_runtime_service tests/wf_api/test_run_api.py -q
```

Expected: pass.

- [ ] **Step 5: Run ruff**

Run:

```bash
uv run ruff check src/wf_mcp/broker/service/workflow_operation_context.py tests/wf_api/test_operation_context.py
```

Expected: pass.

---

## Task 6: Clean Imports, Docs, and Verify

**Files:**

- Modify: `src/wf_mcp/broker/service/core.py`
- Modify: `src/wf_mcp/broker/service/workflow_runtime.py`
- Modify: `docs/current_roadmap.md`
- Modify: `docs/superpowers/research/2026-06-01-wf-api-extraction-map.md` if stale.

- [ ] **Step 1: Remove stale runtime imports from core.py**

After the move, `src/wf_mcp/broker/service/core.py` should no longer import runtime-only names such as:

```python
from wf_core import NodeUse, Workflow, execute_workflow_result_async, resume_workflow_result_async
from wf_api.runtime_dependencies import resolve_runtime_dependencies
from wf_api.saved_subgraphs import prepare_saved_subgraphs, resolve_saved_subgraph_tree
```

Keep names still needed for type annotations, public signatures, or non-runtime service methods:

```python
from wf_core import RunState
from wf_api.models import RawWorkflowPlan
from wf_api.saved_subgraphs import SavedSubgraphTree
```

- [ ] **Step 2: Add roadmap note**

In `docs/current_roadmap.md`, under the wf_api/service extraction bullets, add:

```markdown
  - Workflow runtime execution is being separated from broker coordination.
    `WorkflowRuntimeService` now owns plan compilation, dependency preparation,
    run, and resume; `WfMcpService` keeps delegate methods for compatibility.
```

- [ ] **Step 3: Update extraction map if stale**

If `docs/superpowers/research/2026-06-01-wf-api-extraction-map.md` says `WfMcpService` directly owns workflow runtime execution, add or update a note:

```markdown
Workflow runtime ownership is now split: `WorkflowRuntimeService` owns plan
compilation, dependency preparation, run, and resume. `WfMcpService` remains the
broker coordinator and compatibility façade.
```

Do not edit the file if it already describes this state.

- [ ] **Step 4: Run focused verification**

Run:

```bash
uv run pytest tests/wf_mcp/service/test_workflow_runtime.py tests/wf_mcp/service/test_catalog.py::test_service_hydrates_planner_specs_from_stored_catalog tests/wf_api/test_operation_context.py tests/wf_api/test_run_api.py tests/wf_mcp/workflow_surface/test_runs.py -q
```

Expected: all selected tests pass.

- [ ] **Step 5: Run full verification**

Run:

```bash
uv run pytest -q
uv run ruff check src/wf_mcp/broker/service src/wf_api tests/wf_mcp/service tests/wf_api
uv run ruff format --check src/wf_mcp/broker/service src/wf_api tests/wf_mcp/service tests/wf_api docs/current_roadmap.md
uv run basedpyright --level error
```

Expected:

- pytest passes.
- ruff check passes.
- ruff format check passes.
- basedpyright reports `0 errors`. If the known workspace enumeration warning causes a nonzero exit despite `0 errors`, record the exact output.

---

## Non-Goals and Follow-Up Slices

This plan intentionally leaves these slices for later:

1. **Transport/upstream service extraction:** move connection lookup, adapter lookup, auth loading, resource reads, prompt rendering, raw method calls, and notifications.
2. **Event recorder extraction:** turn `_record_event` and catalog change event emission into an injected event recorder implementation.
3. **WfMcpService rename:** once most implementations are extracted, rename the remaining coordinator to a clearer broker runtime name if the public import impact is acceptable.
4. **Protocol-neutral API expansion:** decide whether runtime execution belongs behind a `wf_api` implementation protocol once CLI/HTTP need a shared process boundary.

---

## Self-Review

- Spec coverage: The plan extracts compile/prepare/run/resume and preserves current public service methods, context adaptation, saved subgraph preparation, and run payload behavior.
- Placeholder scan: No placeholders or vague “write tests” steps remain; each task has explicit code snippets and commands.
- Type consistency: `WorkflowRuntimeService` receives `SourceCatalogService`, `WorkflowArtifactStore | None`, and `EventEmitter`; later tasks use the same names and signatures.
