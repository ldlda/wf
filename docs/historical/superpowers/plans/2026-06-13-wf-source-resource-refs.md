# `wf.source` Resource Ref Helpers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Add explicit source-aware helper capabilities under `wf.source` for pass-by-value resource refs using `logical_source`, starting with bounded `read_resource`.

**Architecture:** Resource refs are inert JSON data moved by normal workflow input/state/output bindings. Core bindings do not inspect or rewrite refs. Only explicit `wf.source` helper nodes dereference refs by resolving `logical_source` through runtime/platform context, then reading the concrete source via the existing source content access path. This plan depends on the platform source policy plan so `wf.source` does not require self-binding.

**Tech Stack:** Python 3.14, Pydantic models, `wf_authoring.node`, `RuntimeContext`, `WorkflowOperationContext`, `SourceCatalogService`/content access, pytest.

---

## Preconditions

- Complete `docs/historical/superpowers/plans/2026-06-13-platform-source-policy.md` first.
- `CapabilitySource(policy=SourcePolicy(platform=True, binding_required=False))` must exist.
- `wf.std` deployments should validate/run without `wf.std=wf.std` self-bindings.

---

## File Structure

- Modify `src/wf_core/run_state.py`: add optional platform runtime context to `RuntimeContext`.
- Create `src/wf_api/platform_context.py`: small protocol/model for resolving logical sources and reading resources.
- Modify `src/wf_core/runtime/engine.py`, `src/wf_core/runtime/step.py`, and `src/wf_core/runtime/ops/nodes.py`: thread the opaque platform object from workflow execution entrypoints into every `RuntimeContext`, including concurrent foreach item execution.
- Modify `src/wf_api/runtime_dependencies.py` and server runtime runners: include source binding map/platform context in runtime dependencies.
- Create `src/wf_api/source_refs.py`: Pydantic `SourceResourceRef` and bounded output model.
- Create `src/wf_api/source_helpers.py`: `wf.source.read_resource` NodeSpec factory.
- Modify `src/wf_api/local_sources.py` and MCP server composition to register `wf.source`.
- Test:
  - `tests/wf_api/test_source_refs.py`
  - `tests/wf_api/test_source_helpers.py`
  - `tests/wf_server/test_local_static_server.py`
  - `tests/wf_transport_rpc_http/test_mcp_backed_server_rpc.py`

---

### Task 1: Add Source Ref Models

**Files:**
- Create: `src/wf_api/source_refs.py`
- Modify: `src/wf_api/__init__.py`
- Test: `tests/wf_api/test_source_refs.py`

- [x] **Step 1: Write model tests**

Create `tests/wf_api/test_source_refs.py`:

```python
from __future__ import annotations

import pytest

from wf_api.source_refs import SourceResourceRef


def test_source_resource_ref_requires_logical_source_and_uri() -> None:
    ref = SourceResourceRef(
        logical_source="drive",
        uri="gdrive://file/abc",
        mime_type="application/pdf",
        name="Report.pdf",
    )

    assert ref.kind == "source_resource_ref"
    assert ref.logical_source == "drive"
    assert ref.uri == "gdrive://file/abc"
    assert ref.model_dump(mode="json")["name"] == "Report.pdf"


def test_source_resource_ref_rejects_empty_logical_source() -> None:
    with pytest.raises(ValueError):
        SourceResourceRef(logical_source="", uri="gdrive://file/abc")
```

- [x] **Step 2: Run tests and confirm failure**

Run:

```bash
uv run pytest tests/wf_api/test_source_refs.py -q
```

Expected: fails because `wf_api.source_refs` does not exist.

- [x] **Step 3: Implement models**

Create `src/wf_api/source_refs.py`:

```python
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class SourceResourceRef(BaseModel):
    """Workflow-safe resource handle.

    The ref is inert pass-by-value data. Only explicit source-aware helper nodes
    dereference it through deployment source bindings and platform context.
    """

    kind: Literal["source_resource_ref"] = "source_resource_ref"
    logical_source: str = Field(min_length=1)
    uri: str = Field(min_length=1)
    mime_type: str | None = None
    name: str | None = None
```

In `src/wf_api/__init__.py`, export `SourceResourceRef`.

- [x] **Step 4: Run tests and commit**

Run:

```bash
uv run pytest tests/wf_api/test_source_refs.py -q
uv run basedpyright --level error src/wf_api/source_refs.py tests/wf_api/test_source_refs.py
```

Expected: tests pass and typecheck has 0 errors.

Commit:

```bash
git add src/wf_api/source_refs.py src/wf_api/__init__.py tests/wf_api/test_source_refs.py
git commit -m "feat: add source resource ref model"
```

---

### Task 2: Add Platform Context To RuntimeContext

**Files:**
- Modify: `src/wf_core/run_state.py`
- Create: `src/wf_api/platform_context.py`
- Modify: `src/wf_core/runtime/engine.py`
- Modify: `src/wf_core/runtime/step.py`
- Modify: `src/wf_core/runtime/ops/nodes.py`
- Test: `tests/core/test_runtime_context.py` or existing nearest runtime context test

- [x] **Step 1: Add context tests**

Create `tests/core/test_runtime_context.py` if no equivalent exists:

```python
from __future__ import annotations

from wf_core import RuntimeContext


class _Platform:
    pass


def test_runtime_context_can_carry_platform_context() -> None:
    platform = _Platform()
    ctx = RuntimeContext(current_node_id="node", platform=platform)

    assert ctx.current_node_id == "node"
    assert ctx.platform is platform
```

- [x] **Step 2: Run test and confirm failure**

Run:

```bash
uv run pytest tests/core/test_runtime_context.py -q
```

Expected: fails because `RuntimeContext` has no `platform` field.

- [x] **Step 3: Add platform field**

In `src/wf_core/run_state.py`, update `RuntimeContext`:

```python
@dataclass(slots=True)
class RuntimeContext:
    current_node_id: str
    platform: object | None = None
```

If it is not a dataclass, preserve the current structure and add `platform: object | None = None`.

Create `src/wf_api/platform_context.py`:

```python
from __future__ import annotations

from typing import Any, Protocol


class WorkflowPlatformContext(Protocol):
    """Runtime platform services available only to explicit platform helper nodes."""

    def resolve_source(self, logical_source: str) -> str: ...

    async def read_resource(
        self,
        *,
        source_id: str,
        uri: str,
        max_chars: int,
    ) -> dict[str, Any]: ...
```

- [x] **Step 4: Pass platform context through async node execution**

Thread an opaque `platform: object | None = None` through the async runtime
entrypoints:

- `src/wf_core/runtime/engine.py`
  - `execute_workflow_async(...)`
  - `execute_workflow_result_async(...)`
  - `resume_workflow_async(...)`
  - `resume_workflow_result_async(...)`
- `src/wf_core/runtime/step.py`
  - `step_workflow_async(...)`
  - `_step_async_foreach_item_batch(...)` or the nearest helper that calls
    `invoke_node_use_async_for_frame(...)`
- `src/wf_core/runtime/ops/nodes.py`
  - `_resolve_node_execution(...)`
  - `execute_node_use_async(...)`
  - `invoke_node_use_async_for_frame(...)`

At the final context construction seam, pass:

```python
RuntimeContext(
    current_node_id=node.id,
    ...,
    platform=platform,
)
```

Keep synchronous runtime support unchanged unless tests prove it also needs the
field. The first `wf.source` helper is async and should be exercised through
the async workflow API.

Do not add source-specific code to `wf_core`. The field is an opaque object.
Add one focused async-runtime test that calls
`execute_workflow_result_async(..., platform=sentinel)` with a node handler
that asserts `ctx.platform is sentinel`.

- [x] **Step 5: Run tests and commit**

Run:

```bash
uv run pytest tests/core/test_runtime_context.py tests/authoring/test_nodes.py tests/authoring/test_async_runtime.py -q
uv run basedpyright --level error src/wf_core/run_state.py src/wf_core/runtime/engine.py src/wf_core/runtime/step.py src/wf_core/runtime/ops/nodes.py src/wf_api/platform_context.py tests/core/test_runtime_context.py
```

Expected: tests pass and typecheck has 0 errors.

Commit:

```bash
git add src/wf_core/run_state.py src/wf_core/runtime/engine.py src/wf_core/runtime/step.py src/wf_core/runtime/ops/nodes.py src/wf_api/platform_context.py tests/core/test_runtime_context.py
git commit -m "feat: carry platform context through runtime context"
```

---

### Task 3: Build Source Platform Context In API Runtime

**Files:**
- Modify: `src/wf_api/runtime_dependencies.py`
- Modify: `src/wf_server/context.py`
- Modify: `src/wf_mcp/broker/service/workflow_runtime.py`
- Test: `tests/wf_api/test_runtime_dependencies.py` or nearest existing file

- [x] **Step 1: Add tests for source resolution**

Create `tests/wf_api/test_platform_context.py`:

```python
from __future__ import annotations

import pytest

from wf_api.platform_context import SourceBindingPlatformContext


def test_platform_context_resolves_logical_source() -> None:
    context = SourceBindingPlatformContext(
        source_bindings={"drive": "drive.personal"},
        read_resource_handler=None,
    )

    assert context.resolve_source("drive") == "drive.personal"


def test_platform_context_uses_identity_for_platform_sources() -> None:
    context = SourceBindingPlatformContext(
        source_bindings={},
        platform_sources={"wf.source"},
        read_resource_handler=None,
    )

    assert context.resolve_source("wf.source") == "wf.source"


def test_platform_context_rejects_unbound_source() -> None:
    context = SourceBindingPlatformContext(source_bindings={}, read_resource_handler=None)

    with pytest.raises(KeyError, match="unbound logical source"):
        context.resolve_source("drive")
```

- [x] **Step 2: Run tests and confirm failure**

Run:

```bash
uv run pytest tests/wf_api/test_platform_context.py -q
```

Expected: fails because `SourceBindingPlatformContext` does not exist.

- [x] **Step 3: Implement platform context**

In `src/wf_api/platform_context.py`, add:

```python
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field

ReadResourceHandler = Callable[[str, str, int], Awaitable[dict[str, Any]]]


@dataclass(frozen=True, slots=True)
class SourceBindingPlatformContext:
    """Resolve logical source refs for explicit source-aware helper nodes."""

    source_bindings: Mapping[str, str]
    read_resource_handler: ReadResourceHandler | None
    platform_sources: set[str] = field(default_factory=set)

    def resolve_source(self, logical_source: str) -> str:
        if logical_source in self.platform_sources:
            return logical_source
        try:
            return self.source_bindings[logical_source]
        except KeyError as exc:
            raise KeyError(f"unbound logical source {logical_source!r}") from exc

    async def read_resource(
        self,
        *,
        source_id: str,
        uri: str,
        max_chars: int,
    ) -> dict[str, Any]:
        if self.read_resource_handler is None:
            raise RuntimeError("source resource reads are not configured")
        return await self.read_resource_handler(source_id, uri, max_chars)
```

- [x] **Step 4: Thread platform context through workflow runners**

Update `LocalWorkflowRuntimeRunner.prepare_workflow_runtime()` in `src/wf_server/context.py` to also create a platform context from deployment bindings:

```python
platform_context = SourceBindingPlatformContext(
    source_bindings={} if deployment is None else deployment.binding_map(),
    platform_sources={
        source_id
        for source_id, source in self.specs.capability_sources.items()
        if source.policy.platform
    },
    read_resource_handler=None,
)
```

Return it from `prepare_workflow_runtime()` by extending the tuple:

```python
return (
    workflow,
    dependencies.node_registry,
    dependencies.reducers,
    prepared_subgraphs,
    platform_context,
)
```

Then pass `platform=platform_context` into `execute_workflow_result_async()` and `resume_workflow_result_async()` if those functions accept it after Task 2. If Task 2 used a narrower internal function instead, adapt at that seam.

Do the equivalent in the MCP-backed runtime runner in
`src/wf_mcp/broker/service/workflow_runtime.py`. `WorkflowRuntimeService`
currently owns source/catalog runtime state but not `ContentAccessService`, so
add a small optional constructor field:

```python
read_resource_handler: ReadResourceHandler | None = None
```

When building the platform context, pass that handler through:

```python
async def _read_resource(source_id: str, uri: str, max_chars: int) -> dict[str, Any]:
    if self.read_resource_handler is None:
        raise RuntimeError("source resource reads are not configured")
    return await self.read_resource_handler(source_id, uri, max_chars)
```

Wire that field from `WfMcpService`/server construction after Task 4 adds the
content-access helper. If `read_resource_by_source_uri` does not exist yet,
commit the neutral/local platform context in this task and finish MCP wiring in
Task 4.

- [x] **Step 5: Run tests and commit**

Run:

```bash
uv run pytest tests/wf_api/test_platform_context.py tests/wf_server/test_local_static_server.py -q
uv run basedpyright --level error src/wf_api/platform_context.py src/wf_server/context.py src/wf_mcp/broker/service/workflow_runtime.py tests/wf_api/test_platform_context.py
```

Expected: tests pass and typecheck has 0 errors. If MCP runner wiring needs Task 4 helper first, commit only the neutral/local platform context in this task and document the MCP wiring in the next task.

Commit:

```bash
git add src/wf_api/platform_context.py src/wf_server/context.py src/wf_mcp/broker/service/workflow_runtime.py tests/wf_api/test_platform_context.py
git commit -m "feat: build source binding platform context"
```

---

### Task 4: Add Bounded Source Resource Read Helper

**Files:**
- Create: `src/wf_api/source_helpers.py`
- Modify: `src/wf_mcp/broker/service/content_access.py`
- Test: `tests/wf_api/test_source_helpers.py`
- Test: `tests/wf_mcp/service/test_content_access.py`

- [x] **Step 1: Add helper tests**

Create `tests/wf_api/test_source_helpers.py`:

```python
from __future__ import annotations

import pytest

from wf_api.platform_context import SourceBindingPlatformContext
from wf_api.source_helpers import read_resource
from wf_api.source_refs import SourceResourceRef
from wf_core import RuntimeContext


async def test_read_resource_resolves_logical_source_and_bounds_text() -> None:
    calls: list[tuple[str, str, int]] = []

    async def handler(source_id: str, uri: str, max_chars: int):
        calls.append((source_id, uri, max_chars))
        return {
            "contents": [
                {
                    "type": "text",
                    "text": "abcdefghijklmnopqrstuvwxyz",
                    "mimeType": "text/plain",
                }
            ]
        }

    platform = SourceBindingPlatformContext(
        source_bindings={"drive": "drive.personal"},
        read_resource_handler=handler,
    )

    result = await read_resource(
        SourceResourceRef(logical_source="drive", uri="gdrive://file/abc"),
        RuntimeContext(current_node_id="read", platform=platform),
        max_chars=5,
    )

    assert calls == [("drive.personal", "gdrive://file/abc", 5)]
    assert result.truncated is True
    assert result.text == "abcde"


async def test_read_resource_requires_platform_context() -> None:
    with pytest.raises(RuntimeError, match="platform context"):
        await read_resource(
            SourceResourceRef(logical_source="drive", uri="gdrive://file/abc"),
            RuntimeContext(current_node_id="read"),
        )
```

- [x] **Step 2: Run tests and confirm failure**

Run:

```bash
uv run pytest tests/wf_api/test_source_helpers.py -q
```

Expected: fails because `source_helpers.py` does not exist.

- [x] **Step 3: Implement bounded helper**

Create `src/wf_api/source_helpers.py`:

```python
from __future__ import annotations

from typing import cast

from pydantic import BaseModel, Field

from wf_core import RuntimeContext

from .platform_context import WorkflowPlatformContext
from .source_refs import SourceResourceRef


class ReadResourceOutput(BaseModel):
    """Bounded resource read result suitable for workflow state/output."""

    source_id: str
    uri: str
    mime_type: str | None = None
    text: str | None = None
    content_count: int
    truncated: bool = False


async def read_resource(
    ref: SourceResourceRef,
    ctx: RuntimeContext,
    *,
    max_chars: int = 4000,
) -> ReadResourceOutput:
    """Explicitly dereference one source resource ref through platform context."""
    platform = ctx.platform
    if platform is None:
        raise RuntimeError("wf.source.read_resource requires platform context")
    typed_platform = cast(WorkflowPlatformContext, platform)
    source_id = typed_platform.resolve_source(ref.logical_source)
    payload = await typed_platform.read_resource(
        source_id=source_id,
        uri=ref.uri,
        max_chars=max_chars,
    )
    contents = payload.get("contents", [])
    first = contents[0] if isinstance(contents, list) and contents else {}
    text = first.get("text") if isinstance(first, dict) else None
    if isinstance(text, str) and len(text) > max_chars:
        text = text[:max_chars]
        truncated = True
    else:
        truncated = False
    mime_type = (
        first.get("mimeType")
        if isinstance(first, dict) and isinstance(first.get("mimeType"), str)
        else ref.mime_type
    )
    return ReadResourceOutput(
        source_id=source_id,
        uri=ref.uri,
        mime_type=mime_type,
        text=text if isinstance(text, str) else None,
        content_count=len(contents) if isinstance(contents, list) else 0,
        truncated=truncated,
    )
```

If basedpyright complains that `ctx.platform` is `object`, use a runtime `Protocol` check or a local `cast(WorkflowPlatformContext, platform)` with a comment:

```python
from typing import cast
typed_platform = cast(WorkflowPlatformContext, platform)
```

- [x] **Step 4: Add source-uri content access helper**

In `src/wf_mcp/broker/service/content_access.py`, add:

```python
async def read_resource_by_source_uri(
    self,
    *,
    source_id: str,
    uri: str,
    max_chars: int,
) -> dict[str, Any]:
    """Read one provider URI from a concrete source for wf.source helpers."""
    resource = next(
        (
            entry
            for entry in self.source_catalog.list_resources(connection_id=source_id)
            if entry.uri == uri
        ),
        None,
    )
    if resource is None:
        raise KeyError(f"unknown resource {uri!r} for source {source_id!r}")
    return await self.upstream.read_resource(
        self.source_catalog.connection_lookup(source_id),
        resource.qualified_name,
        resource.uri,
    )
```

Preserve the `max_chars` parameter in the signature even if truncation is
performed by `wf_api.source_helpers`; this keeps the platform seam explicit.

- [x] **Step 5: Run tests and commit**

Run:

```bash
uv run pytest tests/wf_api/test_source_helpers.py tests/wf_mcp/service/test_content_access.py -q
uv run ruff check src/wf_api/source_helpers.py src/wf_mcp/broker/service/content_access.py tests/wf_api/test_source_helpers.py tests/wf_mcp/service/test_content_access.py
uv run basedpyright --level error src/wf_api/source_helpers.py src/wf_mcp/broker/service/content_access.py tests/wf_api/test_source_helpers.py tests/wf_mcp/service/test_content_access.py
```

Expected: tests pass, ruff clean, typecheck 0 errors.

Commit:

```bash
git add src/wf_api/source_helpers.py src/wf_mcp/broker/service/content_access.py tests/wf_api/test_source_helpers.py tests/wf_mcp/service/test_content_access.py
git commit -m "feat: add bounded source resource reader"
```

---

### Task 5: Register `wf.source` Platform Source

**Files:**
- Modify: `src/wf_api/local_sources.py`
- Modify: `src/wf_mcp/broker/service/core.py` or source registration seam
- Test: `tests/wf_server/test_local_static_server.py`
- Test: `tests/wf_transport_rpc_http/test_mcp_backed_server_rpc.py`

- [x] **Step 1: Add source inventory test**

In `tests/wf_server/test_local_static_server.py`, add:

```python
def test_local_static_server_exposes_wf_source_platform_source(tmp_path) -> None:
    server = build_local_static_workflow_server(tmp_path)

    source = server.context.specs.capability_sources["wf.source"]

    assert source.policy.platform is True
    assert source.policy.binding_required is False
    assert "wf.source.read_resource" in source.capabilities.node_specs
```

- [x] **Step 2: Run test and confirm failure**

Run:

```bash
uv run pytest tests/wf_server/test_local_static_server.py::test_local_static_server_exposes_wf_source_platform_source -q
```

Expected: fails because `wf.source` is not registered.

- [x] **Step 3: Register source**

In `src/wf_api/local_sources.py`, import:

```python
from wf_authoring import node
from wf_api.source_helpers import ReadResourceOutput, read_resource
from wf_api.source_refs import SourceResourceRef
```

Add a node wrapper that exposes `max_chars` as input:

```python
class ReadResourceInput(BaseModel):
    ref: SourceResourceRef
    max_chars: int = Field(default=4000, ge=1, le=20000)


@node(name="read_resource")
async def read_resource_node(
    payload: ReadResourceInput,
    ctx: RuntimeContext,
) -> ReadResourceOutput:
    return await read_resource(payload.ref, ctx, max_chars=payload.max_chars)
```

Register a `CapabilitySource`:

```python
CapabilitySource(
    id="wf.source",
    kind="system",
    capabilities=CapabilityBuckets(
        node_specs={"wf.source.read_resource": read_resource_node}
    ),
    visibility=SourceVisibility(planner=True, client=True, admin_dashboard=True),
    permissions=SourcePermissions(safe_for_workflow=True, calls_upstream=True),
    policy=SourcePolicy(platform=True, binding_required=False),
    description="Platform helpers for explicit source refs.",
)
```

If `local_sources.py` already qualifies specs differently, follow the existing `wf.std` pattern exactly.

For MCP-backed servers, ensure `wf.source` is included in the same built-in/platform sources loaded into the broker service. If broker service already imports `builtin_sources()`, no additional change is needed.

- [x] **Step 4: Add RPC E2E with fake MCP resource**

In `tests/wf_transport_rpc_http/test_mcp_backed_server_rpc.py`, add a test that:

1. Builds an MCP-backed server with a fake adapter/runtime exposing a resource.
2. Creates or saves an artifact using `wf.source.read_resource`.
3. Saves a deployment binding `drive -> demo.personal` but no `wf.source` binding.
4. Runs the deployment with input:

```json
{
  "ref": {
    "kind": "source_resource_ref",
    "logical_source": "drive",
    "uri": "demo://docs/welcome"
  }
}
```

5. Asserts output text is bounded and the deployment validates runnable.

Use existing fake MCP-backed server helpers in that file; do not create a live network dependency.

- [x] **Step 5: Run tests and commit**

Run:

```bash
uv run pytest tests/wf_server/test_local_static_server.py::test_local_static_server_exposes_wf_source_platform_source tests/wf_transport_rpc_http/test_mcp_backed_server_rpc.py -q
uv run ruff check src/wf_api/local_sources.py tests/wf_server/test_local_static_server.py tests/wf_transport_rpc_http/test_mcp_backed_server_rpc.py
uv run basedpyright --level error src/wf_api/local_sources.py tests/wf_server/test_local_static_server.py tests/wf_transport_rpc_http/test_mcp_backed_server_rpc.py
```

Expected: tests pass, ruff clean, typecheck 0 errors.

Commit:

```bash
git add src/wf_api/local_sources.py tests/wf_server/test_local_static_server.py tests/wf_transport_rpc_http/test_mcp_backed_server_rpc.py
git commit -m "feat: expose wf source resource helper"
```

---

### Task 6: Docs And Final Verification

**Files:**
- Modify: `docs/source_provider_guide.md`
- Modify: `docs/current_roadmap.md`

- [x] **Step 1: Update docs**

In `docs/source_provider_guide.md`, add:

````markdown
## Source Resource Refs

Resource refs are inert workflow data:

```json
{
  "kind": "source_resource_ref",
  "logical_source": "drive",
  "uri": "demo://docs/welcome"
}
```

Input/output/state bindings treat this object as ordinary JSON. Only explicit
platform helper nodes such as `wf.source.read_resource` dereference it. This
keeps large MCP resource payloads out of workflow state unless the workflow asks
for them.
````

In `docs/current_roadmap.md`, replace the `wf.source` next-design note with:

```markdown
- Completed `wf.source.read_resource`: resource refs are inert pass-by-value
  data using `logical_source`; explicit platform helper nodes dereference them
  through runtime/platform context with bounded output.
```

- [x] **Step 2: Final verification**

Run:

```bash
uv run pytest tests/wf_api/test_source_refs.py tests/wf_api/test_source_helpers.py tests/wf_server/test_local_static_server.py tests/wf_transport_rpc_http/test_mcp_backed_server_rpc.py -q
uv run ruff check src/wf_api src/wf_core src/wf_mcp tests/wf_api/test_source_refs.py tests/wf_api/test_source_helpers.py tests/wf_server/test_local_static_server.py tests/wf_transport_rpc_http/test_mcp_backed_server_rpc.py
uv run basedpyright --level error src/wf_api src/wf_core src/wf_mcp tests/wf_api/test_source_refs.py tests/wf_api/test_source_helpers.py tests/wf_server/test_local_static_server.py tests/wf_transport_rpc_http/test_mcp_backed_server_rpc.py
```

Expected: focused tests pass, ruff clean, typecheck 0 errors.

- [x] **Step 3: Commit docs**

```bash
git add docs/source_provider_guide.md docs/current_roadmap.md
git commit -m "docs: document source resource refs"
```

---

## Self-Review

- Spec coverage: plan defines pass-by-value refs, keeps core bindings inert, adds platform context, exposes explicit `wf.source.read_resource`, and documents bounded dereferencing.
- Placeholder scan: no TBD/TODO/fill-in placeholders remain.
- Type consistency: ref field is `logical_source`, helper source is `wf.source`, helper capability is `wf.source.read_resource`.
