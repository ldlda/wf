# wf_sources_mcp SDK Protocols Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move MCP upstream adapter result/protocol types into `wf_sources_mcp` so runtime and discovery can later move without depending on `wf_mcp.sdk` shims.

**Architecture:** `wf_sources_mcp` owns source-provider contracts. `wf_mcp.sdk` remains the old compatibility import path and still owns `McpSdkAdapter` plus MCP SDK converters for now. This slice moves protocol/result shapes only; no live MCP transport/session/converter code moves.

**Tech Stack:** Python 3.14, dataclasses, typing Protocols, pytest, Ruff, basedpyright, `src/` package layout.

---

## Boundaries

Move only:

- `ToolCallResult`
- `BackendAdapter`
- `ToolExecutor`

Do not move:

- `McpSdkAdapter`
- `wf_mcp.sdk.converters`
- `wf_mcp.runtime.session`
- `wf_mcp.runtime.factory`
- `wf_mcp.runtime.pool`
- `wf_mcp.broker.discovery`
- `wf_mcp.broker.service.upstream_transport`

Temporary dependency note:

- `BackendAdapter` and `ToolExecutor` still reference `wf_mcp.models.ConnectionConfig` until the connection runtime DTO moves out of `wf_mcp`.
- They should use `wf_sources_mcp.auth.AuthRecord` and `wf_sources_mcp.catalog` DTOs.

## File Map

Create:

- `src/wf_sources_mcp/sdk/__init__.py` — exports `BackendAdapter`, `ToolCallResult`, `ToolExecutor`.
- `src/wf_sources_mcp/sdk/protocols.py` — canonical protocol/result shapes.
- `tests/wf_sources_mcp/test_sdk_protocols.py` — canonical tests.

Modify:

- `src/wf_sources_mcp/__init__.py` — optionally lazy-export the protocol symbols.
- `src/wf_mcp/sdk/base.py` — replace with compatibility shim.
- `src/wf_mcp/sdk/__init__.py` — import `BackendAdapter` and `ToolCallResult` from canonical module, keep `McpSdkAdapter`.
- `src/wf_mcp/runtime/protocols.py` — replace `ToolExecutor` definition with shim import.
- `src/wf_mcp/runtime/__init__.py` — continue exporting `ToolExecutor`.
- `src/wf_mcp/sdk/adapter.py` — import `BackendAdapter`, `ToolCallResult` from `wf_sources_mcp.sdk`.
- `src/wf_mcp/sdk/converters.py` — import `ToolCallResult` from `wf_sources_mcp.sdk`.
- Production code that imports `BackendAdapter`, `ToolCallResult`, or `ToolExecutor` may be rewritten to `wf_sources_mcp.sdk`.
- `tests/wf_mcp/test_compat_imports.py` — add shim identity tests.
- `tests/wf_sources_mcp/test_import_direction_guard.py` — forbid importing old `wf_mcp.sdk` / `wf_mcp.runtime.protocols` from `wf_sources_mcp`.
- `docs/current_roadmap.md` — mark SDK protocol slice complete.
- `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md` — add the completed slice before runtime/session services.

After implementation, move this plan to:

- `docs/historical/superpowers/plans/2026-06-07-wf-sources-mcp-sdk-protocols-slice.md`

---

### Task 1: Create Canonical SDK Protocol Module

**Files:**
- Create: `src/wf_sources_mcp/sdk/protocols.py`
- Create: `src/wf_sources_mcp/sdk/__init__.py`
- Test: `tests/wf_sources_mcp/test_sdk_protocols.py`

- [ ] **Step 1: Create `protocols.py`**

Create `src/wf_sources_mcp/sdk/protocols.py`:

```python
"""Protocol/result contracts for MCP upstream source providers.

The temporary `wf_mcp.models.ConnectionConfig` dependency remains until broker
runtime connection DTOs move to a neutral/source-provider package.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

from wf_sources_mcp.auth import AuthRecord
from wf_sources_mcp.catalog import DiscoveredPrompt, DiscoveredResource, DiscoveredTool

if TYPE_CHECKING:
    from wf_mcp.models import ConnectionConfig


@dataclass(slots=True)
class ToolCallResult:
    outcome: str
    output: dict[str, Any] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)


class BackendAdapter(Protocol):
    async def list_tools(
        self,
        connection: ConnectionConfig,
        auth: AuthRecord | None,
    ) -> list[DiscoveredTool]: ...

    async def list_resources(
        self,
        connection: ConnectionConfig,
        auth: AuthRecord | None,
    ) -> list[DiscoveredResource]: ...

    async def list_prompts(
        self,
        connection: ConnectionConfig,
        auth: AuthRecord | None,
    ) -> list[DiscoveredPrompt]: ...

    async def get_connection_metadata(
        self,
        connection: ConnectionConfig,
        auth: AuthRecord | None,
    ) -> dict[str, Any]: ...

    async def read_resource(
        self,
        connection: ConnectionConfig,
        auth: AuthRecord | None,
        uri: str,
    ) -> dict[str, Any]: ...

    async def get_prompt(
        self,
        connection: ConnectionConfig,
        auth: AuthRecord | None,
        prompt_name: str,
        arguments: dict[str, str] | None = None,
    ) -> dict[str, Any]: ...

    async def invoke_method(
        self,
        connection: ConnectionConfig,
        auth: AuthRecord | None,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]: ...

    async def send_notification(
        self,
        connection: ConnectionConfig,
        auth: AuthRecord | None,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> None: ...

    async def call_tool(
        self,
        connection: ConnectionConfig,
        auth: AuthRecord | None,
        tool_name: str,
        payload: dict[str, Any],
    ) -> ToolCallResult: ...


class ToolExecutor(Protocol):
    """Runtime boundary for executing MCP tools from workflow nodes.

    Discovery can stay one-shot, but workflow execution needs this smaller
    protocol so persistent runtime pools can replace one-shot adapters without
    changing generated NodeSpecs.
    """

    async def call_tool(
        self,
        connection: ConnectionConfig,
        auth: AuthRecord | None,
        tool_name: str,
        payload: dict[str, Any],
    ) -> ToolCallResult: ...


__all__ = [
    "BackendAdapter",
    "ToolCallResult",
    "ToolExecutor",
]
```

- [ ] **Step 2: Create SDK package exports**

Create `src/wf_sources_mcp/sdk/__init__.py`:

```python
from __future__ import annotations

from .protocols import BackendAdapter, ToolCallResult, ToolExecutor

__all__ = [
    "BackendAdapter",
    "ToolCallResult",
    "ToolExecutor",
]
```

- [ ] **Step 3: Add canonical tests**

Create `tests/wf_sources_mcp/test_sdk_protocols.py`:

```python
from __future__ import annotations

from dataclasses import is_dataclass
from typing import cast

from wf_mcp.models import ConnectionConfig
from wf_sources_mcp.auth import AuthRecord
from wf_sources_mcp.catalog import DiscoveredTool
from wf_sources_mcp.sdk import BackendAdapter, ToolCallResult, ToolExecutor


class EchoAdapter:
    async def list_tools(
        self,
        connection: ConnectionConfig,
        auth: AuthRecord | None,
    ) -> list[DiscoveredTool]:
        return [
            DiscoveredTool(
                name="echo",
                title=None,
                description="Echo",
                input_schema={"type": "object"},
                output_schema={"type": "object"},
            )
        ]

    async def call_tool(
        self,
        connection: ConnectionConfig,
        auth: AuthRecord | None,
        tool_name: str,
        payload: dict[str, object],
    ) -> ToolCallResult:
        return ToolCallResult(outcome="ok", output={"echoed": payload})


def test_tool_call_result_is_slots_dataclass_with_empty_defaults() -> None:
    result = ToolCallResult(outcome="ok")

    assert is_dataclass(result)
    assert result.output == {}
    assert result.meta == {}


async def test_backend_adapter_protocol_can_describe_tool_listing() -> None:
    adapter = cast(BackendAdapter, EchoAdapter())
    tools = await adapter.list_tools(
        ConnectionConfig(id="demo.default", server="demo", account="default"),
        None,
    )

    assert tools[0].name == "echo"


async def test_tool_executor_protocol_can_describe_tool_calls() -> None:
    executor = cast(ToolExecutor, EchoAdapter())
    result = await executor.call_tool(
        ConnectionConfig(id="demo.default", server="demo", account="default"),
        None,
        "echo",
        {"message": "hello"},
    )

    assert result.outcome == "ok"
    assert result.output == {"echoed": {"message": "hello"}}
```

- [ ] **Step 4: Run canonical tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_sdk_protocols.py -q
```

Expected: 3 tests pass.

---

### Task 2: Replace Old Protocol Modules With Shims

**Files:**
- Modify: `src/wf_mcp/sdk/base.py`
- Modify: `src/wf_mcp/sdk/__init__.py`
- Modify: `src/wf_mcp/runtime/protocols.py`
- Modify: `src/wf_mcp/runtime/__init__.py`
- Modify: `tests/wf_mcp/test_compat_imports.py`

- [ ] **Step 1: Replace `wf_mcp.sdk.base` with shim**

Set `src/wf_mcp/sdk/base.py` to:

```python
"""Compatibility shim for MCP upstream SDK protocol/result types.

Canonical implementation lives in `wf_sources_mcp.sdk`.
"""

from __future__ import annotations

from wf_sources_mcp.sdk import BackendAdapter, ToolCallResult

__all__ = [
    "BackendAdapter",
    "ToolCallResult",
]
```

- [ ] **Step 2: Update `wf_mcp.sdk.__init__`**

Set `src/wf_mcp/sdk/__init__.py` to:

```python
from wf_sources_mcp.sdk import BackendAdapter, ToolCallResult

from .adapter import McpSdkAdapter

__all__ = ["BackendAdapter", "McpSdkAdapter", "ToolCallResult"]
```

- [ ] **Step 3: Replace `wf_mcp.runtime.protocols` with shim**

Set `src/wf_mcp/runtime/protocols.py` to:

```python
"""Compatibility shim for MCP runtime execution protocol.

Canonical implementation lives in `wf_sources_mcp.sdk`.
"""

from __future__ import annotations

from wf_sources_mcp.sdk import ToolExecutor

__all__ = [
    "ToolExecutor",
]
```

- [ ] **Step 4: Keep `wf_mcp.runtime.__init__` facade**

`src/wf_mcp/runtime/__init__.py` should still export `ToolExecutor`:

```python
from .factory import PersistentSessionFactory
from .pool import McpRuntimePool, connection_runtime_fingerprint
from .protocols import ToolExecutor
from .session import PersistentMcpSession

__all__ = [
    "McpRuntimePool",
    "PersistentMcpSession",
    "PersistentSessionFactory",
    "ToolExecutor",
    "connection_runtime_fingerprint",
]
```

- [ ] **Step 5: Add shim identity tests**

Append to `tests/wf_mcp/test_compat_imports.py`:

```python
def test_wf_mcp_sdk_protocol_shims_reexport_wf_sources_mcp_sdk() -> None:
    from wf_mcp.sdk import BackendAdapter as CompatBackendAdapter
    from wf_mcp.sdk import ToolCallResult as CompatToolCallResult
    from wf_mcp.sdk.base import BackendAdapter as CompatBaseBackendAdapter
    from wf_mcp.sdk.base import ToolCallResult as CompatBaseToolCallResult
    from wf_sources_mcp.sdk import BackendAdapter, ToolCallResult

    assert CompatBackendAdapter is BackendAdapter
    assert CompatToolCallResult is ToolCallResult
    assert CompatBaseBackendAdapter is BackendAdapter
    assert CompatBaseToolCallResult is ToolCallResult


def test_wf_mcp_runtime_protocol_shim_reexports_wf_sources_mcp_tool_executor() -> None:
    from wf_mcp.runtime import ToolExecutor as CompatRuntimeToolExecutor
    from wf_mcp.runtime.protocols import ToolExecutor as CompatProtocolToolExecutor
    from wf_sources_mcp.sdk import ToolExecutor

    assert CompatRuntimeToolExecutor is ToolExecutor
    assert CompatProtocolToolExecutor is ToolExecutor
```

- [ ] **Step 6: Run compatibility tests**

Run:

```bash
uv run pytest tests/wf_mcp/test_compat_imports.py tests/wf_mcp/test_workflow_wrappers.py -q
```

Expected: compatibility tests pass.

---

### Task 3: Rewrite Production Imports to Canonical Protocols

**Files:**
- Modify: production files under `src/wf_mcp/` that consume `BackendAdapter`, `ToolCallResult`, or `ToolExecutor`.

- [ ] **Step 1: Update direct consumers**

Rewrite production imports for moved symbols to:

```python
from wf_sources_mcp.sdk import BackendAdapter, ToolCallResult, ToolExecutor
```

Likely files:

- `src/wf_mcp/broker/discovery.py`
- `src/wf_mcp/broker/service/adapters.py`
- `src/wf_mcp/broker/service/core.py`
- `src/wf_mcp/broker/service/source_catalog.py`
- `src/wf_mcp/broker/service/upstream_transport.py`
- `src/wf_mcp/runtime/session.py`
- `src/wf_mcp/runtime/pool.py`
- `src/wf_mcp/sdk/adapter.py`
- `src/wf_mcp/sdk/converters.py`
- `src/wf_mcp/workflow/wrappers.py`

Do not move or rewrite imports for:

- `McpSdkAdapter`
- `McpRuntimePool`
- `PersistentSessionFactory`
- `PersistentMcpSession`
- `tool_result_to_call_result`
- `workflow_output_schema_from_mcp_tool_schema`

- [ ] **Step 2: Confirm production imports no longer depend on old protocol shims**

Run:

```bash
rg -n "from wf_mcp\\.sdk import (BackendAdapter|ToolCallResult)|from wf_mcp\\.sdk\\.base|from wf_mcp\\.runtime import ToolExecutor|from wf_mcp\\.runtime\\.protocols|from \\.\\.sdk import (BackendAdapter|ToolCallResult)|from \\.sdk import (BackendAdapter|ToolCallResult)|from \\.\\.runtime import ToolExecutor|from \\.runtime import ToolExecutor" src
```

Expected: old protocol/result imports remain only in shim/facade files or imports of non-moved runtime/adapter classes.

- [ ] **Step 3: Run focused production tests**

Run:

```bash
uv run pytest tests/wf_mcp/test_workflow_wrappers.py tests/wf_mcp/test_sdk_adapter.py tests/wf_mcp/test_sdk_converters.py tests/wf_mcp/test_stateful_runtime.py tests/wf_mcp/service/test_upstream_transport.py tests/wf_mcp/service/test_catalog.py -q
```

Expected: all focused tests pass.

---

### Task 4: Strengthen Import-Direction Guard

**Files:**
- Modify: `tests/wf_sources_mcp/test_import_direction_guard.py`
- Test: `tests/wf_sources_mcp/test_import_direction_guard.py`

- [ ] **Step 1: Add old SDK/runtime protocol modules to forbidden set**

Append this test to `tests/wf_sources_mcp/test_import_direction_guard.py`:

```python
def test_wf_sources_mcp_does_not_import_old_sdk_protocol_modules() -> None:
    root = Path(__file__).resolve().parents[2] / "src" / "wf_sources_mcp"
    forbidden = {
        "wf_mcp.sdk",
        "wf_mcp.sdk.base",
        "wf_mcp.runtime",
        "wf_mcp.runtime.protocols",
    }
    violations: list[str] = []

    for py_file in sorted(root.rglob("*.py")):
        rel = py_file.relative_to(root.parent)
        module = str(rel.with_suffix("")).replace("/", ".").replace("\\", ".")
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module in forbidden:
                violations.append(f"{module}:{node.lineno}: from {node.module} import ...")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in forbidden:
                        violations.append(f"{module}:{node.lineno}: import {alias.name}")

    assert violations == [], (
        "wf_sources_mcp still imports old wf_mcp SDK/runtime protocol modules:\n"
        + "\n".join(f"  {violation}" for violation in violations)
    )
```

- [ ] **Step 2: Run guard tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_import_direction_guard.py -q
```

Expected: guard tests pass.

---

### Task 5: Docs Status and Plan Archival

**Files:**
- Modify: `docs/current_roadmap.md`
- Modify: `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`
- Move: `docs/superpowers/plans/2026-06-07-wf-sources-mcp-sdk-protocols-slice.md` to `docs/historical/superpowers/plans/2026-06-07-wf-sources-mcp-sdk-protocols-slice.md`

- [ ] **Step 1: Update roadmap**

In `docs/current_roadmap.md`, under the MCP package split section, add:

```markdown
      Fourth `wf_sources_mcp` slice complete: upstream SDK protocol/result
      types (`BackendAdapter`, `ToolExecutor`, `ToolCallResult`) now live in
      `wf_sources_mcp.sdk`, with `wf_mcp.sdk` and `wf_mcp.runtime.protocols`
      retained as compatibility shims.
```

- [ ] **Step 2: Update long-lived API boundary spec**

In `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`, update the `wf_sources_mcp` status list so it includes:

```markdown
4. Complete: upstream SDK protocol/result types moved to `wf_sources_mcp.sdk`, with `wf_mcp.sdk` and `wf_mcp.runtime.protocols` retained as shims.
5. Upstream transport/discovery/session services.
```

- [ ] **Step 3: Move completed plan to historical**

Run:

```bash
git mv docs/superpowers/plans/2026-06-07-wf-sources-mcp-sdk-protocols-slice.md docs/historical/superpowers/plans/2026-06-07-wf-sources-mcp-sdk-protocols-slice.md
```

Expected: `git status --short` shows an `R` rename for this plan.

---

### Task 6: Final Verification

**Files:**
- All changed files

- [ ] **Step 1: Run focused extraction tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp tests/wf_mcp/test_compat_imports.py tests/wf_mcp/test_workflow_wrappers.py tests/wf_mcp/test_sdk_adapter.py tests/wf_mcp/test_sdk_converters.py tests/wf_mcp/test_stateful_runtime.py tests/wf_mcp/service/test_upstream_transport.py tests/wf_mcp/service/test_catalog.py -q
```

Expected: all focused tests pass.

- [ ] **Step 2: Run lint and type checks**

Run:

```bash
uv run ruff check src tests
uv run basedpyright --level error src
```

Expected: Ruff reports `All checks passed!`; basedpyright reports `0 errors`.

- [ ] **Step 3: Run full suite**

Run:

```bash
uv run pytest -q
```

Expected: full suite passes with current skip/xfail counts.

- [ ] **Step 4: Review remaining old protocol imports**

Run:

```bash
rg -n "from wf_mcp\\.sdk import (BackendAdapter|ToolCallResult)|from wf_mcp\\.sdk\\.base|from wf_mcp\\.runtime import ToolExecutor|from wf_mcp\\.runtime\\.protocols" src tests
```

Expected: remaining occurrences are compatibility shims, facade exports, or tests intentionally exercising old import paths.

- [ ] **Step 5: Report**

Report:

- files created/modified
- focused/full verification output
- whether `wf_sources_mcp.sdk` owns `BackendAdapter`, `ToolExecutor`, and `ToolCallResult`
- whether compatibility shims remain
- deviations from this plan

Do not commit unless the user explicitly asks. If committing, use:

```bash
git add -A
git commit -m "refactor: move mcp sdk protocols to wf_sources_mcp"
```

---

## Self-Review

- Spec coverage: moves source-provider protocol/result seams needed before runtime/session migration.
- Placeholder scan: no `TODO`, `TBD`, or unspecified test steps.
- Type consistency: `BackendAdapter`, `ToolExecutor`, and `ToolCallResult` retain existing signatures and names, with only canonical import ownership changing.
