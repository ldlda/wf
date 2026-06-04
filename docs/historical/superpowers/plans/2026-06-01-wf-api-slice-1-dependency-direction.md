# wf_api Slice 1: Dependency Direction — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce `wf_api` as a protocol-neutral facade that both `wf_cli` and `wf_mcp` call, while `wf_api` imports zero `wf_mcp` modules.

**Architecture:** `WorkflowApi` is a thin delegating facade over `WorkflowApiBackend`, a protocol defining high-level workflow operation methods. `WfMcpWorkflowApiBackend` wraps the existing `WorkflowSurfaceHandlers(WfMcpService)` and implements the protocol. The existing handler implementation stays in `wf_mcp` unchanged.

**Tech Stack:** Python 3.14+, pydantic, existing `wf_artifacts`/`wf_platform`/`wf_authoring`/`wf_core` packages.

---

## Import Direction Rules

```text
wf_api  ->  wf_artifacts, wf_platform, wf_authoring, wf_core   (OK)
wf_api  ->  wf_mcp                                              (FORBIDDEN)
wf_mcp  ->  wf_api                                              (OK — adapter direction)
wf_cli  ->  wf_api                                              (OK)
wf_cli  ->  wf_mcp                                              (OK — config/service construction)
```

## What This Plan Does NOT Do

- No helper-module migration (`constants`, `refs`, `next_actions`, `wrapper_hints`, `saved_subgraphs`, `run_lifecycle`, `runtime_dependencies` stay in `wf_mcp.workflow_surface`)
- No event/listing/model migration (`McpEvent`, `make_event`, `matches_query`, `paged_list_payload`, `RawWorkflowPlan` stay in `wf_mcp`)
- No domain split of `WorkflowSurfaceHandlers`
- No store redesign
- No response shape changes
- No FastAPI
- No renaming of `WorkflowSurfaceHandlers` or `McpEvent`

## Risks and Intentional Deferrals

1. **`wf_api` is thin today.** `WorkflowApi` just delegates. The value is the seam, not the logic. Logic extraction happens in later slices.

2. **`TraceRange` is duplicated as a temporary API DTO.** `wf_api.backend.TraceRange` is a minimal dataclass matching `wf_mcp.workflow_surface.models.TraceRange`. The adapter converts. This duplication is acceptable for Slice 1 because `TraceRange` is trivial (two int fields) and keeps `wf_api` free of `wf_mcp` imports. Do not let this become two long-lived domain models; later slices should unify or move the canonical range model once the API boundary is proven.

3. **`wf_cli` still imports `wf_mcp` for config/service construction.** `load_cli_context` calls `wf_mcp.broker.build_service_from_config`. This stays until store/config extraction (Slice 6 in the roadmap).

4. **`WorkflowSurfaceHandlers` is not renamed.** It stays as-is in `wf_mcp.workflow_surface.handlers`. The `wf_api.WorkflowApi` wraps it. Renaming is Slice 2.

5. **MCP tool request/response models stay in `wf_mcp.workflow_surface.models`.** `tools.py` continues to import from `.models`. No change.

---

## File Structure

### New files

| File | Responsibility |
|------|---------------|
| `src/wf_api/__init__.py` | Package root; re-exports `WorkflowApi`, `WorkflowApiBackend` |
| `src/wf_api/backend.py` | `WorkflowApiBackend` protocol + `TraceRange` dataclass |
| `src/wf_api/service.py` | `WorkflowApi` thin delegating facade |
| `src/wf_mcp/broker/service/workflow_api_backend.py` | `WfMcpWorkflowApiBackend` adapter |

### Modified files

| File | Change |
|------|--------|
| `src/wf_cli/context.py` | Import `WorkflowApi` + `WfMcpWorkflowApiBackend`; update `CliContext.handlers` type and `load_cli_context` |
| `src/wf_mcp/workflow_surface/tools.py` | Import `WorkflowApi` + `WfMcpWorkflowApiBackend`; update `register_workflow_tools` |

### Unchanged files

- `src/wf_mcp/workflow_surface/handlers.py` — **no changes**
- `src/wf_mcp/workflow_surface/models.py` — **no changes**
- `src/wf_mcp/workflow_surface/__init__.py` — **no changes**
- All `src/wf_mcp/workflow_surface/` helpers — **no changes**
- Existing tests — **no behavior changes expected**
- New tests under `tests/wf_api/` — import-direction and adapter-context guardrails

---

## Task 1: Create `wf_api` package with `WorkflowApiBackend` protocol

**Files:**

- Create: `src/wf_api/__init__.py`
- Create: `src/wf_api/backend.py`

- [ ] **Step 1: Create the package directory**

```powershell
New-Item -ItemType Directory -Path "src\wf_api" -Force
```

- [ ] **Step 2: Write `src/wf_api/backend.py`**

This file defines the `WorkflowApiBackend` protocol (high-level workflow operations) and a minimal `TraceRange` dataclass.

Slice 1 intentionally mirrors the current workflow-surface method shape. Most
methods still accept/return `dict[str, Any]`; that is acceptable here because
this slice proves the dependency seam, not the final domain API. Later slices
can replace selected method payloads with stronger domain models after callers
are using `WorkflowApi`.

```python
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class TraceRange:
    """Caller-bounded debug trace slice for durable deployment runs."""

    start: int = 0
    limit: int = 20


@runtime_checkable
class WorkflowApiBackend(Protocol):
    """High-level workflow operation protocol.

    Implementations wrap a concrete service (e.g. WorkflowSurfaceHandlers
    backed by WfMcpService) so that wf_api never imports wf_mcp.
    """

    # -- capabilities --

    async def list_capabilities(
        self,
        *,
        query: str | None = None,
        source_id: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]: ...

    async def inspect_capability(
        self,
        *,
        qualified_name: str,
    ) -> dict[str, Any]: ...

    async def call_capability(
        self,
        *,
        qualified_name: str,
        payload: dict[str, Any],
        deployment_id: str | None = None,
    ) -> dict[str, Any]: ...

    # -- artifacts --

    async def list_artifacts(
        self,
        *,
        query: str | None = None,
        kind: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]: ...

    async def inspect_artifact(
        self,
        *,
        artifact_id: str,
        version: int,
    ) -> dict[str, Any]: ...

    async def save_artifact(
        self,
        artifact: dict[str, Any],
    ) -> dict[str, Any]: ...

    async def create_artifact_from_plan(
        self,
        *,
        artifact_id: str,
        version: int,
        title: str,
        plan: dict[str, Any],
        outcomes: Sequence[str],
        kind: str = "workflow",
        description: str | None = None,
        required_capabilities: dict[str, dict[str, Any]] | None = None,
        source_bindings: dict[str, str] | None = None,
        created_from_catalog_version: str | None = None,
    ) -> dict[str, Any]: ...

    async def create_artifact_from_draft(
        self,
        *,
        artifact_id: str,
        version: int,
        title: str,
        draft: dict[str, Any],
        outcomes: Sequence[str],
        kind: str = "workflow",
        description: str | None = None,
        required_capabilities: dict[str, dict[str, Any]] | None = None,
        source_bindings: dict[str, str] | None = None,
        created_from_catalog_version: str | None = None,
    ) -> dict[str, Any]: ...

    async def create_artifact_from_workspace(
        self,
        *,
        workspace_id: str,
        artifact_id: str,
        version: int,
        title: str,
        outcomes: Sequence[str],
        kind: str = "workflow",
        description: str | None = None,
        required_capabilities: dict[str, dict[str, Any]] | None = None,
        source_bindings: dict[str, str] | None = None,
        created_from_catalog_version: str | None = None,
    ) -> dict[str, Any]: ...

    async def create_wrapper_from_workspace(
        self,
        *,
        workspace_id: str,
        artifact_id: str,
        version: int,
        title: str,
        outcomes: Sequence[str],
        description: str | None = None,
        required_capabilities: dict[str, dict[str, Any]] | None = None,
        source_bindings: dict[str, str] | None = None,
        created_from_catalog_version: str | None = None,
    ) -> dict[str, Any]: ...

    # -- drafts --

    async def validate_draft(
        self,
        *,
        draft: dict[str, Any],
    ) -> dict[str, Any]: ...

    async def compile_draft(
        self,
        *,
        draft: dict[str, Any],
    ) -> dict[str, Any]: ...

    async def patch_draft(
        self,
        *,
        draft: dict[str, Any],
        patch: list[dict[str, Any]],
    ) -> dict[str, Any]: ...

    # -- draft workspaces --

    async def list_draft_workspaces(self) -> dict[str, Any]: ...

    async def create_draft_workspace(
        self,
        *,
        workspace_id: str,
        draft: dict[str, Any],
        title: str | None = None,
    ) -> dict[str, Any]: ...

    async def get_draft_workspace(
        self,
        *,
        workspace_id: str,
        include_draft: bool = False,
    ) -> dict[str, Any]: ...

    async def delete_draft_workspace(
        self,
        *,
        workspace_id: str,
    ) -> dict[str, Any]: ...

    async def validate_draft_workspace(
        self,
        *,
        workspace_id: str,
    ) -> dict[str, Any]: ...

    async def patch_draft_workspace(
        self,
        *,
        workspace_id: str,
        revision: int,
        patch: list[dict[str, Any]],
    ) -> dict[str, Any]: ...

    async def set_draft_name(
        self,
        *,
        workspace_id: str,
        revision: int,
        name: str,
    ) -> dict[str, Any]: ...

    async def set_draft_route(
        self,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        outcome: str,
        target: str,
    ) -> dict[str, Any]: ...

    async def set_step_input_map(
        self,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        input_map: dict[str, str],
    ) -> dict[str, Any]: ...

    async def set_step_output_map(
        self,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        output_map: dict[str, str],
    ) -> dict[str, Any]: ...

    async def create_minimal_draft_workspace(
        self,
        *,
        workspace_id: str,
        name: str,
        capability_name: str,
        input_schema: dict[str, Any],
        state_schema: dict[str, Any],
        output_schema: dict[str, Any],
        input: Sequence[Any] | None = None,
        output: Sequence[Any] | None = None,
        input_map: dict[str, str] | None = None,
        output_map: dict[str, str] | None = None,
        error_message_source: Any | None = None,
        title: str | None = None,
    ) -> dict[str, Any]: ...

    async def create_draft_workspace_from_capability(
        self,
        *,
        workspace_id: str,
        capability_name: str,
        name: str | None = None,
        title: str | None = None,
        input_schema: dict[str, Any] | None = None,
        state_schema: dict[str, Any] | None = None,
        output_schema: dict[str, Any] | None = None,
        input: Sequence[Any] | None = None,
        output: Sequence[Any] | None = None,
        input_map: dict[str, str] | None = None,
        output_map: dict[str, str] | None = None,
        error_message_source: Any | None = None,
    ) -> dict[str, Any]: ...

    # -- deployments --

    async def list_deployments(self) -> dict[str, Any]: ...

    async def inspect_deployment(
        self,
        *,
        deployment_id: str,
    ) -> dict[str, Any]: ...

    async def save_deployment(
        self,
        deployment: dict[str, Any],
    ) -> dict[str, Any]: ...

    async def delete_deployment(
        self,
        *,
        deployment_id: str,
    ) -> dict[str, Any]: ...

    async def validate_deployment(
        self,
        *,
        deployment_id: str,
        live_check: bool = False,
    ) -> dict[str, Any]: ...

    # -- runs --

    async def run_deployment(
        self,
        *,
        deployment_id: str,
        workflow_input: dict[str, Any],
        trace_range: TraceRange | None = None,
    ) -> dict[str, Any]: ...

    async def resume_run(
        self,
        *,
        run_id: str,
        resume_payload: dict[str, Any],
        resume_outcome: str = "submitted",
        trace_range: TraceRange | None = None,
    ) -> dict[str, Any]: ...

    async def inspect_run(
        self,
        *,
        run_id: str,
    ) -> dict[str, Any]: ...

    async def read_run_trace(
        self,
        *,
        run_id: str,
        trace_range: TraceRange,
    ) -> dict[str, Any]: ...
```

- [ ] **Step 3: Write `src/wf_api/__init__.py`**

```python
from __future__ import annotations

from .backend import TraceRange, WorkflowApiBackend
from .service import WorkflowApi

__all__ = ["TraceRange", "WorkflowApi", "WorkflowApiBackend"]
```

- [ ] **Step 4: Verify import**

```powershell
uv run python -c "from wf_api import WorkflowApi, WorkflowApiBackend, TraceRange; print('OK')"
```

Expected: `OK`.

---

## Task 2: Create `WorkflowApi` facade

**Files:**

- Create: `src/wf_api/service.py`

- [ ] **Step 1: Write `src/wf_api/service.py`**

This is a thin delegating facade. Every method calls `self.backend.<method>(...)`. No logic, no `wf_mcp` imports.

```python
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from .backend import TraceRange, WorkflowApiBackend


class WorkflowApi:
    """Protocol-neutral workflow application facade.

    Delegates every operation to a WorkflowApiBackend implementation.
    This class owns no business logic; it exists so that callers
    (wf_cli, wf_mcp tools, future HTTP adapters) share one entry point
    that does not import wf_mcp.
    """

    def __init__(self, backend: WorkflowApiBackend) -> None:
        self.backend = backend

    # -- capabilities --

    async def list_capabilities(
        self,
        *,
        query: str | None = None,
        source_id: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        return await self.backend.list_capabilities(
            query=query, source_id=source_id, cursor=cursor, limit=limit,
        )

    async def inspect_capability(
        self,
        *,
        qualified_name: str,
    ) -> dict[str, Any]:
        return await self.backend.inspect_capability(qualified_name=qualified_name)

    async def call_capability(
        self,
        *,
        qualified_name: str,
        payload: dict[str, Any],
        deployment_id: str | None = None,
    ) -> dict[str, Any]:
        return await self.backend.call_capability(
            qualified_name=qualified_name, payload=payload, deployment_id=deployment_id,
        )

    # -- artifacts --

    async def list_artifacts(
        self,
        *,
        query: str | None = None,
        kind: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        return await self.backend.list_artifacts(
            query=query, kind=kind, cursor=cursor, limit=limit,
        )

    async def inspect_artifact(
        self,
        *,
        artifact_id: str,
        version: int,
    ) -> dict[str, Any]:
        return await self.backend.inspect_artifact(
            artifact_id=artifact_id, version=version,
        )

    async def save_artifact(
        self,
        artifact: dict[str, Any],
    ) -> dict[str, Any]:
        return await self.backend.save_artifact(artifact)

    async def create_artifact_from_plan(
        self,
        *,
        artifact_id: str,
        version: int,
        title: str,
        plan: dict[str, Any],
        outcomes: Sequence[str],
        kind: str = "workflow",
        description: str | None = None,
        required_capabilities: dict[str, dict[str, Any]] | None = None,
        source_bindings: dict[str, str] | None = None,
        created_from_catalog_version: str | None = None,
    ) -> dict[str, Any]:
        return await self.backend.create_artifact_from_plan(
            artifact_id=artifact_id,
            version=version,
            title=title,
            plan=plan,
            outcomes=outcomes,
            kind=kind,
            description=description,
            required_capabilities=required_capabilities,
            source_bindings=source_bindings,
            created_from_catalog_version=created_from_catalog_version,
        )

    async def create_artifact_from_draft(
        self,
        *,
        artifact_id: str,
        version: int,
        title: str,
        draft: dict[str, Any],
        outcomes: Sequence[str],
        kind: str = "workflow",
        description: str | None = None,
        required_capabilities: dict[str, dict[str, Any]] | None = None,
        source_bindings: dict[str, str] | None = None,
        created_from_catalog_version: str | None = None,
    ) -> dict[str, Any]:
        return await self.backend.create_artifact_from_draft(
            artifact_id=artifact_id,
            version=version,
            title=title,
            draft=draft,
            outcomes=outcomes,
            kind=kind,
            description=description,
            required_capabilities=required_capabilities,
            source_bindings=source_bindings,
            created_from_catalog_version=created_from_catalog_version,
        )

    async def create_artifact_from_workspace(
        self,
        *,
        workspace_id: str,
        artifact_id: str,
        version: int,
        title: str,
        outcomes: Sequence[str],
        kind: str = "workflow",
        description: str | None = None,
        required_capabilities: dict[str, dict[str, Any]] | None = None,
        source_bindings: dict[str, str] | None = None,
        created_from_catalog_version: str | None = None,
    ) -> dict[str, Any]:
        return await self.backend.create_artifact_from_workspace(
            workspace_id=workspace_id,
            artifact_id=artifact_id,
            version=version,
            title=title,
            outcomes=outcomes,
            kind=kind,
            description=description,
            required_capabilities=required_capabilities,
            source_bindings=source_bindings,
            created_from_catalog_version=created_from_catalog_version,
        )

    async def create_wrapper_from_workspace(
        self,
        *,
        workspace_id: str,
        artifact_id: str,
        version: int,
        title: str,
        outcomes: Sequence[str],
        description: str | None = None,
        required_capabilities: dict[str, dict[str, Any]] | None = None,
        source_bindings: dict[str, str] | None = None,
        created_from_catalog_version: str | None = None,
    ) -> dict[str, Any]:
        return await self.backend.create_wrapper_from_workspace(
            workspace_id=workspace_id,
            artifact_id=artifact_id,
            version=version,
            title=title,
            outcomes=outcomes,
            description=description,
            required_capabilities=required_capabilities,
            source_bindings=source_bindings,
            created_from_catalog_version=created_from_catalog_version,
        )

    # -- drafts --

    async def validate_draft(
        self,
        *,
        draft: dict[str, Any],
    ) -> dict[str, Any]:
        return await self.backend.validate_draft(draft=draft)

    async def compile_draft(
        self,
        *,
        draft: dict[str, Any],
    ) -> dict[str, Any]:
        return await self.backend.compile_draft(draft=draft)

    async def patch_draft(
        self,
        *,
        draft: dict[str, Any],
        patch: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return await self.backend.patch_draft(draft=draft, patch=patch)

    # -- draft workspaces --

    async def list_draft_workspaces(self) -> dict[str, Any]:
        return await self.backend.list_draft_workspaces()

    async def create_draft_workspace(
        self,
        *,
        workspace_id: str,
        draft: dict[str, Any],
        title: str | None = None,
    ) -> dict[str, Any]:
        return await self.backend.create_draft_workspace(
            workspace_id=workspace_id, draft=draft, title=title,
        )

    async def get_draft_workspace(
        self,
        *,
        workspace_id: str,
        include_draft: bool = False,
    ) -> dict[str, Any]:
        return await self.backend.get_draft_workspace(
            workspace_id=workspace_id, include_draft=include_draft,
        )

    async def delete_draft_workspace(
        self,
        *,
        workspace_id: str,
    ) -> dict[str, Any]:
        return await self.backend.delete_draft_workspace(workspace_id=workspace_id)

    async def validate_draft_workspace(
        self,
        *,
        workspace_id: str,
    ) -> dict[str, Any]:
        return await self.backend.validate_draft_workspace(workspace_id=workspace_id)

    async def patch_draft_workspace(
        self,
        *,
        workspace_id: str,
        revision: int,
        patch: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return await self.backend.patch_draft_workspace(
            workspace_id=workspace_id, revision=revision, patch=patch,
        )

    async def set_draft_name(
        self,
        *,
        workspace_id: str,
        revision: int,
        name: str,
    ) -> dict[str, Any]:
        return await self.backend.set_draft_name(
            workspace_id=workspace_id, revision=revision, name=name,
        )

    async def set_draft_route(
        self,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        outcome: str,
        target: str,
    ) -> dict[str, Any]:
        return await self.backend.set_draft_route(
            workspace_id=workspace_id,
            revision=revision,
            step_id=step_id,
            outcome=outcome,
            target=target,
        )

    async def set_step_input_map(
        self,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        input_map: dict[str, str],
    ) -> dict[str, Any]:
        return await self.backend.set_step_input_map(
            workspace_id=workspace_id,
            revision=revision,
            step_id=step_id,
            input_map=input_map,
        )

    async def set_step_output_map(
        self,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        output_map: dict[str, str],
    ) -> dict[str, Any]:
        return await self.backend.set_step_output_map(
            workspace_id=workspace_id,
            revision=revision,
            step_id=step_id,
            output_map=output_map,
        )

    async def create_minimal_draft_workspace(
        self,
        *,
        workspace_id: str,
        name: str,
        capability_name: str,
        input_schema: dict[str, Any],
        state_schema: dict[str, Any],
        output_schema: dict[str, Any],
        input: Sequence[Any] | None = None,
        output: Sequence[Any] | None = None,
        input_map: dict[str, str] | None = None,
        output_map: dict[str, str] | None = None,
        error_message_source: Any | None = None,
        title: str | None = None,
    ) -> dict[str, Any]:
        return await self.backend.create_minimal_draft_workspace(
            workspace_id=workspace_id,
            name=name,
            capability_name=capability_name,
            input_schema=input_schema,
            state_schema=state_schema,
            output_schema=output_schema,
            input=input,
            output=output,
            input_map=input_map,
            output_map=output_map,
            error_message_source=error_message_source,
            title=title,
        )

    async def create_draft_workspace_from_capability(
        self,
        *,
        workspace_id: str,
        capability_name: str,
        name: str | None = None,
        title: str | None = None,
        input_schema: dict[str, Any] | None = None,
        state_schema: dict[str, Any] | None = None,
        output_schema: dict[str, Any] | None = None,
        input: Sequence[Any] | None = None,
        output: Sequence[Any] | None = None,
        input_map: dict[str, str] | None = None,
        output_map: dict[str, str] | None = None,
        error_message_source: Any | None = None,
    ) -> dict[str, Any]:
        return await self.backend.create_draft_workspace_from_capability(
            workspace_id=workspace_id,
            capability_name=capability_name,
            name=name,
            title=title,
            input_schema=input_schema,
            state_schema=state_schema,
            output_schema=output_schema,
            input=input,
            output=output,
            input_map=input_map,
            output_map=output_map,
            error_message_source=error_message_source,
        )

    # -- deployments --

    async def list_deployments(self) -> dict[str, Any]:
        return await self.backend.list_deployments()

    async def inspect_deployment(
        self,
        *,
        deployment_id: str,
    ) -> dict[str, Any]:
        return await self.backend.inspect_deployment(deployment_id=deployment_id)

    async def save_deployment(
        self,
        deployment: dict[str, Any],
    ) -> dict[str, Any]:
        return await self.backend.save_deployment(deployment)

    async def delete_deployment(
        self,
        *,
        deployment_id: str,
    ) -> dict[str, Any]:
        return await self.backend.delete_deployment(deployment_id=deployment_id)

    async def validate_deployment(
        self,
        *,
        deployment_id: str,
        live_check: bool = False,
    ) -> dict[str, Any]:
        return await self.backend.validate_deployment(
            deployment_id=deployment_id, live_check=live_check,
        )

    # -- runs --

    async def run_deployment(
        self,
        *,
        deployment_id: str,
        workflow_input: dict[str, Any],
        trace_range: TraceRange | None = None,
    ) -> dict[str, Any]:
        return await self.backend.run_deployment(
            deployment_id=deployment_id,
            workflow_input=workflow_input,
            trace_range=trace_range,
        )

    async def resume_run(
        self,
        *,
        run_id: str,
        resume_payload: dict[str, Any],
        resume_outcome: str = "submitted",
        trace_range: TraceRange | None = None,
    ) -> dict[str, Any]:
        return await self.backend.resume_run(
            run_id=run_id,
            resume_payload=resume_payload,
            resume_outcome=resume_outcome,
            trace_range=trace_range,
        )

    async def inspect_run(
        self,
        *,
        run_id: str,
    ) -> dict[str, Any]:
        return await self.backend.inspect_run(run_id=run_id)

    async def read_run_trace(
        self,
        *,
        run_id: str,
        trace_range: TraceRange,
    ) -> dict[str, Any]:
        return await self.backend.read_run_trace(
            run_id=run_id, trace_range=trace_range,
        )
```

- [ ] **Step 2: Verify import**

```powershell
uv run python -c "from wf_api.service import WorkflowApi; print('OK')"
```

Expected: `OK`.

---

## Task 3: Create `WfMcpWorkflowApiBackend` adapter

**Files:**

- Create: `src/wf_mcp/broker/service/workflow_api_backend.py`

- [ ] **Step 1: Write `src/wf_mcp/broker/service/workflow_api_backend.py`**

This adapter wraps the existing `WorkflowSurfaceHandlers(WfMcpService)`. It converts `wf_api.backend.TraceRange` to the handler's `TraceRange` before delegating.

```python
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from wf_api.backend import TraceRange as ApiTraceRange

from ...workflow_surface.handlers import WorkflowSurfaceHandlers
from ...workflow_surface.models import TraceRange as HandlerTraceRange
from .core import WfMcpService


def _to_handler_trace_range(tr: ApiTraceRange) -> HandlerTraceRange:
    return HandlerTraceRange(start=tr.start, limit=tr.limit)


class WfMcpWorkflowApiBackend:
    """Adapt existing WorkflowSurfaceHandlers into WorkflowApiBackend."""

    def __init__(self, service: WfMcpService) -> None:
        self._handlers = WorkflowSurfaceHandlers(service)

    # -- capabilities --

    async def list_capabilities(
        self,
        *,
        query: str | None = None,
        source_id: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        return await self._handlers.list_capabilities(
            query=query, source_id=source_id, cursor=cursor, limit=limit,
        )

    async def inspect_capability(
        self,
        *,
        qualified_name: str,
    ) -> dict[str, Any]:
        return await self._handlers.inspect_capability(qualified_name=qualified_name)

    async def call_capability(
        self,
        *,
        qualified_name: str,
        payload: dict[str, Any],
        deployment_id: str | None = None,
    ) -> dict[str, Any]:
        return await self._handlers.call_capability(
            qualified_name=qualified_name, payload=payload, deployment_id=deployment_id,
        )

    # -- artifacts --

    async def list_artifacts(
        self,
        *,
        query: str | None = None,
        kind: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        return await self._handlers.list_artifacts(
            query=query, kind=kind, cursor=cursor, limit=limit,
        )

    async def inspect_artifact(
        self,
        *,
        artifact_id: str,
        version: int,
    ) -> dict[str, Any]:
        return await self._handlers.inspect_artifact(
            artifact_id=artifact_id, version=version,
        )

    async def save_artifact(
        self,
        artifact: dict[str, Any],
    ) -> dict[str, Any]:
        return await self._handlers.save_artifact(artifact)

    async def create_artifact_from_plan(
        self,
        *,
        artifact_id: str,
        version: int,
        title: str,
        plan: dict[str, Any],
        outcomes: Sequence[str],
        kind: str = "workflow",
        description: str | None = None,
        required_capabilities: dict[str, dict[str, Any]] | None = None,
        source_bindings: dict[str, str] | None = None,
        created_from_catalog_version: str | None = None,
    ) -> dict[str, Any]:
        return await self._handlers.create_artifact_from_plan(
            artifact_id=artifact_id,
            version=version,
            title=title,
            plan=plan,
            outcomes=outcomes,
            kind=kind,
            description=description,
            required_capabilities=required_capabilities,
            source_bindings=source_bindings,
            created_from_catalog_version=created_from_catalog_version,
        )

    async def create_artifact_from_draft(
        self,
        *,
        artifact_id: str,
        version: int,
        title: str,
        draft: dict[str, Any],
        outcomes: Sequence[str],
        kind: str = "workflow",
        description: str | None = None,
        required_capabilities: dict[str, dict[str, Any]] | None = None,
        source_bindings: dict[str, str] | None = None,
        created_from_catalog_version: str | None = None,
    ) -> dict[str, Any]:
        return await self._handlers.create_artifact_from_draft(
            artifact_id=artifact_id,
            version=version,
            title=title,
            draft=draft,
            outcomes=outcomes,
            kind=kind,
            description=description,
            required_capabilities=required_capabilities,
            source_bindings=source_bindings,
            created_from_catalog_version=created_from_catalog_version,
        )

    async def create_artifact_from_workspace(
        self,
        *,
        workspace_id: str,
        artifact_id: str,
        version: int,
        title: str,
        outcomes: Sequence[str],
        kind: str = "workflow",
        description: str | None = None,
        required_capabilities: dict[str, dict[str, Any]] | None = None,
        source_bindings: dict[str, str] | None = None,
        created_from_catalog_version: str | None = None,
    ) -> dict[str, Any]:
        return await self._handlers.create_artifact_from_workspace(
            workspace_id=workspace_id,
            artifact_id=artifact_id,
            version=version,
            title=title,
            outcomes=outcomes,
            kind=kind,
            description=description,
            required_capabilities=required_capabilities,
            source_bindings=source_bindings,
            created_from_catalog_version=created_from_catalog_version,
        )

    async def create_wrapper_from_workspace(
        self,
        *,
        workspace_id: str,
        artifact_id: str,
        version: int,
        title: str,
        outcomes: Sequence[str],
        description: str | None = None,
        required_capabilities: dict[str, dict[str, Any]] | None = None,
        source_bindings: dict[str, str] | None = None,
        created_from_catalog_version: str | None = None,
    ) -> dict[str, Any]:
        return await self._handlers.create_wrapper_from_workspace(
            workspace_id=workspace_id,
            artifact_id=artifact_id,
            version=version,
            title=title,
            outcomes=outcomes,
            description=description,
            required_capabilities=required_capabilities,
            source_bindings=source_bindings,
            created_from_catalog_version=created_from_catalog_version,
        )

    # -- drafts --

    async def validate_draft(
        self,
        *,
        draft: dict[str, Any],
    ) -> dict[str, Any]:
        return await self._handlers.validate_draft(draft=draft)

    async def compile_draft(
        self,
        *,
        draft: dict[str, Any],
    ) -> dict[str, Any]:
        return await self._handlers.compile_draft(draft=draft)

    async def patch_draft(
        self,
        *,
        draft: dict[str, Any],
        patch: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return await self._handlers.patch_draft(draft=draft, patch=patch)

    # -- draft workspaces --

    async def list_draft_workspaces(self) -> dict[str, Any]:
        return await self._handlers.list_draft_workspaces()

    async def create_draft_workspace(
        self,
        *,
        workspace_id: str,
        draft: dict[str, Any],
        title: str | None = None,
    ) -> dict[str, Any]:
        return await self._handlers.create_draft_workspace(
            workspace_id=workspace_id, draft=draft, title=title,
        )

    async def get_draft_workspace(
        self,
        *,
        workspace_id: str,
        include_draft: bool = False,
    ) -> dict[str, Any]:
        return await self._handlers.get_draft_workspace(
            workspace_id=workspace_id, include_draft=include_draft,
        )

    async def delete_draft_workspace(
        self,
        *,
        workspace_id: str,
    ) -> dict[str, Any]:
        return await self._handlers.delete_draft_workspace(workspace_id=workspace_id)

    async def validate_draft_workspace(
        self,
        *,
        workspace_id: str,
    ) -> dict[str, Any]:
        return await self._handlers.validate_draft_workspace(workspace_id=workspace_id)

    async def patch_draft_workspace(
        self,
        *,
        workspace_id: str,
        revision: int,
        patch: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return await self._handlers.patch_draft_workspace(
            workspace_id=workspace_id, revision=revision, patch=patch,
        )

    async def set_draft_name(
        self,
        *,
        workspace_id: str,
        revision: int,
        name: str,
    ) -> dict[str, Any]:
        return await self._handlers.set_draft_name(
            workspace_id=workspace_id, revision=revision, name=name,
        )

    async def set_draft_route(
        self,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        outcome: str,
        target: str,
    ) -> dict[str, Any]:
        return await self._handlers.set_draft_route(
            workspace_id=workspace_id,
            revision=revision,
            step_id=step_id,
            outcome=outcome,
            target=target,
        )

    async def set_step_input_map(
        self,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        input_map: dict[str, str],
    ) -> dict[str, Any]:
        return await self._handlers.set_step_input_map(
            workspace_id=workspace_id,
            revision=revision,
            step_id=step_id,
            input_map=input_map,
        )

    async def set_step_output_map(
        self,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        output_map: dict[str, str],
    ) -> dict[str, Any]:
        return await self._handlers.set_step_output_map(
            workspace_id=workspace_id,
            revision=revision,
            step_id=step_id,
            output_map=output_map,
        )

    async def create_minimal_draft_workspace(
        self,
        *,
        workspace_id: str,
        name: str,
        capability_name: str,
        input_schema: dict[str, Any],
        state_schema: dict[str, Any],
        output_schema: dict[str, Any],
        input: Sequence[Any] | None = None,
        output: Sequence[Any] | None = None,
        input_map: dict[str, str] | None = None,
        output_map: dict[str, str] | None = None,
        error_message_source: Any | None = None,
        title: str | None = None,
    ) -> dict[str, Any]:
        return await self._handlers.create_minimal_draft_workspace(
            workspace_id=workspace_id,
            name=name,
            capability_name=capability_name,
            input_schema=input_schema,
            state_schema=state_schema,
            output_schema=output_schema,
            input=input,
            output=output,
            input_map=input_map,
            output_map=output_map,
            error_message_source=error_message_source,
            title=title,
        )

    async def create_draft_workspace_from_capability(
        self,
        *,
        workspace_id: str,
        capability_name: str,
        name: str | None = None,
        title: str | None = None,
        input_schema: dict[str, Any] | None = None,
        state_schema: dict[str, Any] | None = None,
        output_schema: dict[str, Any] | None = None,
        input: Sequence[Any] | None = None,
        output: Sequence[Any] | None = None,
        input_map: dict[str, str] | None = None,
        output_map: dict[str, str] | None = None,
        error_message_source: Any | None = None,
    ) -> dict[str, Any]:
        return await self._handlers.create_draft_workspace_from_capability(
            workspace_id=workspace_id,
            capability_name=capability_name,
            name=name,
            title=title,
            input_schema=input_schema,
            state_schema=state_schema,
            output_schema=output_schema,
            input=input,
            output=output,
            input_map=input_map,
            output_map=output_map,
            error_message_source=error_message_source,
        )

    # -- deployments --

    async def list_deployments(self) -> dict[str, Any]:
        return await self._handlers.list_deployments()

    async def inspect_deployment(
        self,
        *,
        deployment_id: str,
    ) -> dict[str, Any]:
        return await self._handlers.inspect_deployment(deployment_id=deployment_id)

    async def save_deployment(
        self,
        deployment: dict[str, Any],
    ) -> dict[str, Any]:
        return await self._handlers.save_deployment(deployment)

    async def delete_deployment(
        self,
        *,
        deployment_id: str,
    ) -> dict[str, Any]:
        return await self._handlers.delete_deployment(deployment_id=deployment_id)

    async def validate_deployment(
        self,
        *,
        deployment_id: str,
        live_check: bool = False,
    ) -> dict[str, Any]:
        return await self._handlers.validate_deployment(
            deployment_id=deployment_id, live_check=live_check,
        )

    # -- runs --

    async def run_deployment(
        self,
        *,
        deployment_id: str,
        workflow_input: dict[str, Any],
        trace_range: ApiTraceRange | None = None,
    ) -> dict[str, Any]:
        return await self._handlers.run_deployment(
            deployment_id=deployment_id,
            workflow_input=workflow_input,
            trace_range=_to_handler_trace_range(trace_range) if trace_range is not None else None,
        )

    async def resume_run(
        self,
        *,
        run_id: str,
        resume_payload: dict[str, Any],
        resume_outcome: str = "submitted",
        trace_range: ApiTraceRange | None = None,
    ) -> dict[str, Any]:
        return await self._handlers.resume_run(
            run_id=run_id,
            resume_payload=resume_payload,
            resume_outcome=resume_outcome,
            trace_range=_to_handler_trace_range(trace_range) if trace_range is not None else None,
        )

    async def inspect_run(
        self,
        *,
        run_id: str,
    ) -> dict[str, Any]:
        return await self._handlers.inspect_run(run_id=run_id)

    async def read_run_trace(
        self,
        *,
        run_id: str,
        trace_range: ApiTraceRange,
    ) -> dict[str, Any]:
        return await self._handlers.read_run_trace(
            run_id=run_id, trace_range=_to_handler_trace_range(trace_range),
        )
```

- [ ] **Step 2: Verify import**

```powershell
uv run python -c "from wf_mcp.broker.service.workflow_api_backend import WfMcpWorkflowApiBackend; print('OK')"
```

Expected: `OK`.

---

## Task 4: Update `wf_cli.context` to use `WorkflowApi`

**Files:**

- Modify: `src/wf_cli/context.py`

- [ ] **Step 1: Update `src/wf_cli/context.py`**

Patch imports, the `CliContext.handlers` type, and the `load_cli_context`
construction. Do not blindly overwrite the whole file if it has changed since
this plan was written.

Target shape:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import typer

from wf_api import WorkflowApi
from wf_mcp.broker import build_service_from_config, load_broker_config
from wf_mcp.broker.service import WfMcpService
from wf_mcp.broker.service.workflow_api_backend import WfMcpWorkflowApiBackend


@dataclass(frozen=True)
class CliContext:
    """Protocol-neutral CLI handle over the current workflow service stack.

    V1 intentionally reuses wf_mcp service construction because that is where
    config, store, source, artifact, draft, and run wiring currently lives. Keep
    this dependency behind context.py so later extraction does not affect every
    command module.
    """

    config_path: Path
    service: WfMcpService
    handlers: WorkflowApi


def config_path_from_context(ctx: typer.Context) -> str:
    """Return the root --config path captured by the Typer callback."""
    obj = ctx.obj if isinstance(ctx.obj, dict) else {}
    value = obj.get("config_path", "wf_mcp.config.json")
    return value if isinstance(value, str) else "wf_mcp.config.json"


def load_cli_context(config_path: str | Path) -> CliContext:
    """Load config and build workflow-surface handlers for CLI commands."""
    resolved_config_path = Path(config_path)
    config = load_broker_config(resolved_config_path)
    service = build_service_from_config(config)
    return CliContext(
        config_path=resolved_config_path,
        service=service,
        handlers=WorkflowApi(WfMcpWorkflowApiBackend(service)),
    )
```

- [ ] **Step 2: Verify CLI tests pass**

```powershell
uv run pytest tests/wf_cli/ -q
```

Expected: all pass. CLI commands use `context.handlers.X()` which now calls through `WorkflowApi` → `WfMcpWorkflowApiBackend` → `WorkflowSurfaceHandlers`.

---

## Task 5: Update MCP tool registration to use `WorkflowApi`

**Files:**

- Modify: `src/wf_mcp/workflow_surface/tools.py`

- [ ] **Step 1: Update imports in `src/wf_mcp/workflow_surface/tools.py`**

Change lines 10-12 from:

```python
from wf_mcp.broker.service import WfMcpService

from .handlers import WorkflowSurfaceHandlers
```

To:

```python
from wf_api import WorkflowApi
from wf_mcp.broker.service import WfMcpService
from wf_mcp.broker.service.workflow_api_backend import WfMcpWorkflowApiBackend
```

- [ ] **Step 2: Update `register_workflow_tools` function body**

Change line 39 from:

```python
    handlers = WorkflowSurfaceHandlers(service)
```

To:

```python
    handlers = WorkflowApi(WfMcpWorkflowApiBackend(service))
```

All remaining `handlers.X(...)` calls in the function body stay identical — `WorkflowApi` has the same method names as `WorkflowSurfaceHandlers`.

- [ ] **Step 3: Verify workflow surface tests pass**

```powershell
uv run pytest tests/wf_mcp/workflow_surface/ -q
```

Expected: all pass.

---

## Task 6: Add import-direction test

**Files:**

- Create: `tests/wf_api/test_import_direction.py`

- [ ] **Step 1: Create `tests/wf_api/__init__.py`**

```powershell
New-Item -ItemType Directory -Path "tests\wf_api" -Force
```

Write empty `tests/wf_api/__init__.py`:

```python
```

- [ ] **Step 2: Write `tests/wf_api/test_import_direction.py`**

```python
from __future__ import annotations

import ast
from pathlib import Path


def test_wf_api_has_no_wf_mcp_imports() -> None:
    """wf_api must not import any wf_mcp modules."""
    wf_api_root = Path(__file__).resolve().parents[2] / "src" / "wf_api"
    violations: list[str] = []

    for py_file in sorted(wf_api_root.rglob("*.py")):
        rel = py_file.relative_to(wf_api_root.parent)
        module = str(rel.with_suffix("")).replace("/", ".").replace("\\", ".")
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module is not None:
                if node.module.startswith("wf_mcp") or node.module.startswith("wf_mcp."):
                    violations.append(
                        f"{module}:{node.lineno}: from {node.module} import ..."
                    )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("wf_mcp"):
                        violations.append(f"{module}:{node.lineno}: import {alias.name}")

    assert violations == [], (
        "wf_api imports wf_mcp — this breaks the dependency direction rule:\n"
        + "\n".join(f"  {v}" for v in violations)
    )
```

- [ ] **Step 3: Run the test**

```powershell
uv run pytest tests/wf_api/test_import_direction.py -v
```

Expected: `PASSED`.

---

## Task 7: Add `CliContext.handlers` type test

**Files:**

- Create: `tests/wf_api/test_cli_context_uses_api.py`

- [ ] **Step 1: Write `tests/wf_api/test_cli_context_uses_api.py`**

```python
from __future__ import annotations

import json
from pathlib import Path

from wf_api import WorkflowApi
from wf_cli.context import load_cli_context


def test_load_cli_context_returns_workflow_api(tmp_path: Path) -> None:
    """CliContext.handlers must be WorkflowApi, not WorkflowSurfaceHandlers."""
    root = tmp_path / "wf_cli_api_check"
    root.mkdir()
    config_path = root / "wf_mcp.config.json"
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

    context = load_cli_context(config_path)

    assert isinstance(context.handlers, WorkflowApi)
    assert hasattr(context.handlers, "backend")
```

- [ ] **Step 2: Run the test**

```powershell
uv run pytest tests/wf_api/test_cli_context_uses_api.py -v
```

Expected: `PASSED`.

---

## Task 8: Full test suite verification

- [ ] **Step 1: Run workflow surface tests**

```powershell
uv run pytest tests/wf_mcp/workflow_surface/ -q
```

Expected: all pass.

- [ ] **Step 2: Run CLI tests**

```powershell
uv run pytest tests/wf_cli/ -q
```

Expected: all pass.

- [ ] **Step 3: Run full test suite**

```powershell
uv run pytest -q
```

Expected: all pass.

- [ ] **Step 4: Run lint**

```powershell
uv run ruff check src/wf_api/ src/wf_mcp/broker/service/workflow_api_backend.py src/wf_cli/context.py src/wf_mcp/workflow_surface/tools.py
```

Expected: no errors.

- [ ] **Step 5: Run typecheck**

```powershell
uv run basedpyright --level error
```

Expected: no new errors.
