# wf_api Slice 4A: Operation Context Scaffolding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a protocol-neutral workflow operation context seam so future domain services can be extracted from `WorkflowSurfaceHandlers` without depending on `WfMcpService`.

**Architecture:** This is scaffolding only. `wf_api.operation_context` defines small protocols and a `WorkflowOperationContext` dataclass for stores, capability sources, event recording, workflow runtime operations, and optional live source checking. `wf_mcp.broker.service.workflow_operation_context` adapts the current `WfMcpService` into that context. No workflow handler methods move in this slice and no public payloads change.

**Tech Stack:** Python 3.14+, `typing.Protocol`, dataclasses, existing `wf_artifacts`, `wf_platform`, `wf_authoring`, `wf_core`, pytest, ruff, basedpyright.

---

## Scope

### In Scope

- Create `src/wf_api/operation_context.py`.
- Define focused protocols instead of a new god object.
- Create `src/wf_mcp/broker/service/workflow_operation_context.py` to adapt `WfMcpService`.
- Add tests proving:
  - `wf_api.operation_context` imports no `wf_mcp`.
  - a `WfMcpService` can be adapted into `WorkflowOperationContext`.
  - context stores/sources point to the existing service objects.
  - event recording and runtime methods delegate to the service.
- Add docstrings explaining this is scaffolding for later domain splits.

### Out Of Scope

- Do not move methods out of `WorkflowSurfaceHandlers`.
- Do not change `WorkflowApiBackend`.
- Do not change MCP tool request/response models.
- Do not change public payloads.
- Do not rename `WorkflowSurfaceHandlers`.
- Do not add FastAPI/HTTP.
- Do not hide or remove compatibility shims.

---

## Design

### New `wf_api.operation_context`

The context is not a service locator. It is the smallest explicit set of
capabilities that extracted domain services will need.

Protocol groups:

- `WorkflowEventRecorder`: record one lifecycle event object.
- `WorkflowSpecProvider`: look up a qualified node spec and expose capability sources.
- `WorkflowArtifactCataloger`: produce saved artifact catalog entries.
- `WorkflowRuntimeRunner`: run and resume compiled workflow plans.
- `WorkflowLiveSourceChecker`: optional live-source validation hook.

Dataclass:

```python
@dataclass(frozen=True, slots=True)
class WorkflowOperationContext:
    artifact_store: WorkflowArtifactStore | None
    draft_workspace_store: DraftWorkspaceStore | None
    run_store: RunStore | None
    capability_sources: Mapping[str, CapabilitySource]
    events: WorkflowEventRecorder
    specs: WorkflowSpecProvider
    artifacts: WorkflowArtifactCataloger
    runtime: WorkflowRuntimeRunner
    live_sources: WorkflowLiveSourceChecker | None = None
```

This will look somewhat broad, but each field is a small protocol or simple
store reference. If implementation pressure makes this mirror all of
`WfMcpService`, stop and split protocols further.

### MCP Adapter

`wf_mcp.broker.service.workflow_operation_context.context_from_service(service)`
builds the context from the current `WfMcpService`.

This adapter may import `wf_mcp`; `wf_api` must not.

---

## Task 1: Add `wf_api.operation_context`

**Files:**

- Create: `src/wf_api/operation_context.py`

- [ ] **Step 1: Create `src/wf_api/operation_context.py`**

Write this file:

```python
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from wf_artifacts import (
    DraftWorkspaceStore,
    RunStore,
    WorkflowArtifact,
    WorkflowArtifactCatalogEntry,
    WorkflowArtifactStore,
    WorkflowDeployment,
)
from wf_authoring import AsyncRegistryHandler
from wf_core import AsyncNodeHandler, RunState, Workflow
from wf_core.runtime.ops.merges import ReducerDefinition
from wf_platform import CapabilitySource

from .models import RawWorkflowPlan
from .saved_subgraphs import SavedSubgraphTree


class WorkflowEventRecorder(Protocol):
    """Records workflow lifecycle events without exposing MCP event types."""

    def record_event(self, event: object) -> None:
        """Record one event object supplied by an adapter-owned event factory."""


class WorkflowSpecProvider(Protocol):
    """Provides planner-visible capability sources and qualified node specs."""

    @property
    def capability_sources(self) -> Mapping[str, CapabilitySource]:
        """Planner-visible capability sources keyed by source id."""

    def get_qualified_spec(self, qualified_name: str) -> object:
        """Return the node spec for one fully qualified capability name."""


class WorkflowArtifactCataloger(Protocol):
    """Formats saved workflow artifacts for list/detail surfaces."""

    def workflow_artifact_catalog_entry(
        self, artifact: WorkflowArtifact
    ) -> WorkflowArtifactCatalogEntry:
        """Return the catalog entry representation for one saved artifact."""


class WorkflowRuntimeRunner(Protocol):
    """Runs and resumes workflow plans using an adapter-owned runtime backend."""

    async def run_workflow_from_plan(
        self,
        plan: RawWorkflowPlan,
        *,
        workflow_input: dict[str, Any],
        node_name_bindings: dict[str, str] | None = None,
        registry: dict[str, AsyncRegistryHandler] | None = None,
        reducers: dict[str, ReducerDefinition] | None = None,
        prepared_subgraphs: dict[str, object] | None = None,
    ) -> RunState:
        """Execute one raw workflow plan and return its run state."""

    async def resume_workflow_from_plan(
        self,
        plan: RawWorkflowPlan,
        *,
        run: RunState,
        resume_payload: dict[str, Any] | None,
        resume_outcome: str,
        node_name_bindings: dict[str, str] | None = None,
        registry: dict[str, AsyncRegistryHandler] | None = None,
        reducers: dict[str, ReducerDefinition] | None = None,
        prepared_subgraphs: dict[str, object] | None = None,
    ) -> RunState:
        """Resume one interrupted raw workflow plan and return its run state."""


class WorkflowLiveSourceChecker(Protocol):
    """Optional hook for validating live external source availability."""

    async def available_sources(self) -> list[object]:
        """Return source availability records understood by the caller."""


@dataclass(frozen=True, slots=True)
class WorkflowOperationContext:
    """Protocol-neutral dependencies needed by workflow API operations.

    This is scaffolding for splitting the large MCP-backed handler into domain
    services. Keep this shape explicit; do not add arbitrary access to the whole
    MCP service.
    """

    artifact_store: WorkflowArtifactStore | None
    draft_workspace_store: DraftWorkspaceStore | None
    run_store: RunStore | None
    capability_sources: Mapping[str, CapabilitySource]
    events: WorkflowEventRecorder
    specs: WorkflowSpecProvider
    artifacts: WorkflowArtifactCataloger
    runtime: WorkflowRuntimeRunner
    live_sources: WorkflowLiveSourceChecker | None = None


__all__ = [
    "WorkflowArtifactCataloger",
    "WorkflowEventRecorder",
    "WorkflowLiveSourceChecker",
    "WorkflowOperationContext",
    "WorkflowRuntimeRunner",
    "WorkflowSpecProvider",
]
```

- [ ] **Step 2: Run import smoke check**

```powershell
uv run python -c "from wf_api.operation_context import WorkflowOperationContext; print(WorkflowOperationContext.__name__)"
```

Expected:

```text
WorkflowOperationContext
```

---

## Task 2: Re-export Operation Context Types

**Files:**

- Modify: `src/wf_api/__init__.py`

- [ ] **Step 1: Add imports**

Add:

```python
from .operation_context import (
    WorkflowArtifactCataloger,
    WorkflowEventRecorder,
    WorkflowLiveSourceChecker,
    WorkflowOperationContext,
    WorkflowRuntimeRunner,
    WorkflowSpecProvider,
)
```

- [ ] **Step 2: Add names to `__all__`**

Add:

```python
"WorkflowArtifactCataloger",
"WorkflowEventRecorder",
"WorkflowLiveSourceChecker",
"WorkflowOperationContext",
"WorkflowRuntimeRunner",
"WorkflowSpecProvider",
```

- [ ] **Step 3: Run top-level import smoke check**

```powershell
uv run python -c "from wf_api import WorkflowOperationContext, WorkflowRuntimeRunner; print(WorkflowOperationContext.__name__, WorkflowRuntimeRunner.__name__)"
```

Expected:

```text
WorkflowOperationContext WorkflowRuntimeRunner
```

---

## Task 3: Add MCP Adapter For Operation Context

**Files:**

- Create: `src/wf_mcp/broker/service/workflow_operation_context.py`

- [ ] **Step 1: Create adapter file**

Write this file:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from wf_api.operation_context import (
    WorkflowArtifactCataloger,
    WorkflowEventRecorder,
    WorkflowLiveSourceChecker,
    WorkflowOperationContext,
    WorkflowRuntimeRunner,
    WorkflowSpecProvider,
)

from .core import WfMcpService


@dataclass(frozen=True, slots=True)
class WfMcpWorkflowEventRecorder(WorkflowEventRecorder):
    """Adapter-owned event recorder backed by WfMcpService."""

    service: WfMcpService

    def record_event(self, event: object) -> None:
        self.service._record_event(event)  # noqa: SLF001


@dataclass(frozen=True, slots=True)
class WfMcpWorkflowSpecProvider(WorkflowSpecProvider):
    """Adapter-owned spec provider backed by WfMcpService."""

    service: WfMcpService

    @property
    def capability_sources(self):
        return self.service.capability_sources

    def get_qualified_spec(self, qualified_name: str) -> object:
        return self.service._get_qualified_spec(qualified_name)  # noqa: SLF001


@dataclass(frozen=True, slots=True)
class WfMcpWorkflowArtifactCataloger(WorkflowArtifactCataloger):
    """Adapter-owned artifact catalog formatter backed by WfMcpService."""

    service: WfMcpService

    def workflow_artifact_catalog_entry(self, artifact):
        return self.service.workflow_artifact_catalog_entry(artifact)


@dataclass(frozen=True, slots=True)
class WfMcpWorkflowRuntimeRunner(WorkflowRuntimeRunner):
    """Adapter-owned runtime runner backed by WfMcpService."""

    service: WfMcpService

    async def run_workflow_from_plan(self, plan, **kwargs):
        return await self.service.run_workflow_from_plan(plan, **kwargs)

    async def resume_workflow_from_plan(self, plan, **kwargs):
        return await self.service.resume_workflow_from_plan(plan, **kwargs)


@dataclass(frozen=True, slots=True)
class WfMcpWorkflowLiveSourceChecker(WorkflowLiveSourceChecker):
    """Placeholder live source checker; real live checks remain in handlers today."""

    service: WfMcpService

    async def available_sources(self) -> list[object]:
        # Existing live source availability logic still lives near handlers.
        # Slice 4A only creates the seam; it does not move live-check behavior.
        return []


def context_from_service(service: WfMcpService) -> WorkflowOperationContext:
    """Adapt the current MCP service stack into a protocol-neutral context."""
    specs = WfMcpWorkflowSpecProvider(service)
    return WorkflowOperationContext(
        artifact_store=service.artifact_store,
        draft_workspace_store=service.draft_workspace_store,
        run_store=service.run_store,
        capability_sources=specs.capability_sources,
        events=WfMcpWorkflowEventRecorder(service),
        specs=specs,
        artifacts=WfMcpWorkflowArtifactCataloger(service),
        runtime=WfMcpWorkflowRuntimeRunner(service),
        live_sources=WfMcpWorkflowLiveSourceChecker(service),
    )


__all__ = [
    "WfMcpWorkflowArtifactCataloger",
    "WfMcpWorkflowEventRecorder",
    "WfMcpWorkflowLiveSourceChecker",
    "WfMcpWorkflowRuntimeRunner",
    "WfMcpWorkflowSpecProvider",
    "context_from_service",
]
```

- [ ] **Step 2: Run adapter import smoke check**

```powershell
uv run python -c "from wf_mcp.broker.service.workflow_operation_context import context_from_service; print(context_from_service.__name__)"
```

Expected:

```text
context_from_service
```

---

## Task 4: Add Focused Tests

**Files:**

- Create: `tests/wf_api/test_operation_context.py`

- [ ] **Step 1: Write tests**

Write this file:

```python
from __future__ import annotations

import ast
import json
from pathlib import Path

from wf_api.operation_context import WorkflowOperationContext
from wf_cli.context import load_cli_context
from wf_mcp.broker.service.workflow_operation_context import context_from_service


def test_wf_api_operation_context_imports_no_wf_mcp() -> None:
    path = Path(__file__).resolve().parents[2] / "src" / "wf_api" / "operation_context.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            if node.module.startswith("wf_mcp"):
                violations.append(f"{node.lineno}: from {node.module} import ...")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("wf_mcp"):
                    violations.append(f"{node.lineno}: import {alias.name}")

    assert violations == []


def test_context_from_service_exposes_existing_store_objects(tmp_path: Path) -> None:
    config_path = tmp_path / "wf_mcp.config.json"
    config_path.write_text(
        json.dumps(
            {
                "store_root": ".wf_mcp_store",
                "connections": [
                    {
                        "id": "demo.personal",
                        "server": "demo",
                        "account": "personal",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    cli_context = load_cli_context(config_path)

    operation_context = context_from_service(cli_context.service)

    assert isinstance(operation_context, WorkflowOperationContext)
    assert operation_context.artifact_store is cli_context.service.artifact_store
    assert operation_context.draft_workspace_store is cli_context.service.draft_workspace_store
    assert operation_context.run_store is cli_context.service.run_store
    assert operation_context.capability_sources is cli_context.service.capability_sources


def test_context_from_service_delegates_specs_and_events(tmp_path: Path) -> None:
    config_path = tmp_path / "wf_mcp.config.json"
    config_path.write_text(
        json.dumps({"store_root": ".wf_mcp_store", "connections": []}),
        encoding="utf-8",
    )
    cli_context = load_cli_context(config_path)
    operation_context = context_from_service(cli_context.service)

    event = object()
    operation_context.events.record_event(event)

    assert cli_context.service.events[-1] is event
```

- [ ] **Step 2: Run focused tests**

```powershell
uv run pytest tests/wf_api/test_operation_context.py tests/wf_api/test_import_direction.py -q
```

Expected: all pass.

---

## Task 5: Verification

- [ ] **Step 1: Run focused tests**

```powershell
uv run pytest tests/wf_api/test_operation_context.py tests/wf_api/test_import_direction.py tests/wf_cli/test_context.py -q
```

Expected: all pass.

- [ ] **Step 2: Run ruff on touched files**

```powershell
uv run ruff check src/wf_api/operation_context.py src/wf_api/__init__.py src/wf_mcp/broker/service/workflow_operation_context.py tests/wf_api/test_operation_context.py
```

Expected: all checks pass.

- [ ] **Step 3: Run basedpyright on touched files**

```powershell
uv run basedpyright --level error src/wf_api/operation_context.py src/wf_api/__init__.py src/wf_mcp/broker/service/workflow_operation_context.py tests/wf_api/test_operation_context.py
```

Expected: `0 errors`.

- [ ] **Step 4: Optional full suite**

```powershell
uv run pytest -q
```

Expected: full suite passes with the project’s existing skipped/xfailed counts.

---

## Self-Review Checklist

- `wf_api.operation_context` imports no `wf_mcp`.
- The context is not a broad wrapper around all of `WfMcpService`.
- No `WorkflowSurfaceHandlers` method body moved.
- No public payload changed.
- MCP-owned adapter code is the only new code that imports `WfMcpService`.
- Live source behavior remains unchanged; the live-source protocol is scaffolding only.
