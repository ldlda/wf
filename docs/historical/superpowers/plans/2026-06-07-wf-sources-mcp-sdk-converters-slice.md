# wf_sources_mcp SDK Converters Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move MCP SDK conversion helpers into `wf_sources_mcp.sdk.converters` so adapter/runtime code can later move without depending on `wf_mcp.sdk.converters`.

**Architecture:** `wf_sources_mcp` owns upstream MCP conversion logic from MCP SDK models into workflow-source DTOs. `wf_mcp.sdk.converters` remains a compatibility shim. This slice moves pure conversion functions only; it does not move `McpSdkAdapter`, runtime sessions, broker discovery, or upstream transport services.

**Tech Stack:** Python 3.14, MCP SDK model types, pytest, Ruff, basedpyright, `src/` package layout.

---

## Boundaries

Move only:

- `tool_to_discovered`
- `resource_to_discovered`
- `prompt_to_discovered`
- `tool_result_to_call_result`
- `workflow_output_schema_from_mcp_tool_schema`

Do not move:

- `McpSdkAdapter`
- `PersistentMcpSession`
- `PersistentSessionFactory`
- `McpRuntimePool`
- `discover_connection_capabilities`
- `snapshot_from_specs`
- `UpstreamTransportService`

## File Map

Create:

- `src/wf_sources_mcp/sdk/converters.py` — canonical converter helpers.
- `tests/wf_sources_mcp/test_sdk_converters.py` — canonical converter tests.

Modify:

- `src/wf_sources_mcp/sdk/__init__.py` — export converter helpers if convenient.
- `src/wf_mcp/sdk/converters.py` — compatibility shim.
- `src/wf_mcp/sdk/adapter.py` — import converters from canonical path.
- `src/wf_mcp/runtime/session.py` — import `tool_result_to_call_result` from canonical path.
- `src/wf_mcp/broker/catalog.py` — import `workflow_output_schema_from_mcp_tool_schema` from canonical path.
- `tests/wf_mcp/test_compat_imports.py` — shim identity test.
- `tests/wf_sources_mcp/test_import_direction_guard.py` — guard against old converter imports.
- `docs/current_roadmap.md` — mark converter slice complete.
- `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md` — mark converter slice complete.

After implementation, move this plan to:

- `docs/historical/superpowers/plans/2026-06-07-wf-sources-mcp-sdk-converters-slice.md`

---

### Task 1: Create Canonical Converter Module

**Files:**
- Create: `src/wf_sources_mcp/sdk/converters.py`
- Modify: `src/wf_sources_mcp/sdk/__init__.py`
- Test: `tests/wf_sources_mcp/test_sdk_converters.py`

- [ ] **Step 1: Create converter module**

Create `src/wf_sources_mcp/sdk/converters.py` by moving the current implementation from `src/wf_mcp/sdk/converters.py`:

```python
from __future__ import annotations

from typing import Any

from mcp.types import CallToolResult as McpCallToolResult
from mcp.types import Prompt as McpPrompt
from mcp.types import Resource as McpResource
from mcp.types import Tool as McpTool

from wf_sources_mcp.catalog import DiscoveredPrompt, DiscoveredResource, DiscoveredTool
from wf_sources_mcp.sdk import ToolCallResult


def tool_to_discovered(tool: McpTool) -> DiscoveredTool:
    """Convert an MCP SDK tool into the source discovery model."""
    output_schema = workflow_output_schema_from_mcp_tool_schema(tool.outputSchema)
    display_name = (
        tool.annotations.title
        if tool.annotations is not None and tool.annotations.title
        else tool.title
    )
    return DiscoveredTool(
        name=tool.name,
        title=display_name,
        description=tool.description,
        input_schema=tool.inputSchema,
        output_schema=output_schema,
        outcomes=("ok", "error"),
        metadata=tool.model_dump(by_alias=True, mode="json"),
    )


def workflow_output_schema_from_mcp_tool_schema(
    schema: dict[str, Any] | None,
) -> dict[str, Any]:
    """Return the MCP tool output schema without inventing workflow fields.

    MCP tools without structured output expose raw content blocks. Those blocks
    can be text, images, resource links, or mixed results, so this layer must not
    pretend there is a stable top-level ``text`` field. Workflow authors should
    add an explicit wrapper/extraction node for the block shape they expect.
    """
    return schema or {
        "type": "object",
        "properties": {"content": {"type": "array"}},
    }


def resource_to_discovered(resource: McpResource) -> DiscoveredResource:
    """Convert an MCP SDK resource into the source discovery model."""
    local_name = resource.name or str(resource.uri)
    return DiscoveredResource(
        uri=str(resource.uri),
        name=local_name,
        title=resource.title,
        description=resource.description,
        mime_type=resource.mimeType,
        metadata=resource.model_dump(by_alias=True, mode="json"),
    )


def prompt_to_discovered(prompt: McpPrompt) -> DiscoveredPrompt:
    """Convert an MCP SDK prompt into the source discovery model."""
    arguments = [
        argument.model_dump(by_alias=True, mode="json")
        for argument in prompt.arguments or []
    ]
    return DiscoveredPrompt(
        name=prompt.name,
        title=prompt.title,
        description=prompt.description,
        arguments=arguments,
        metadata=prompt.model_dump(by_alias=True, mode="json"),
    )


def tool_result_to_call_result(result: McpCallToolResult) -> ToolCallResult:
    """Convert an MCP SDK tool call result into the adapter result model."""
    if result.structuredContent is not None:
        output = result.structuredContent
    else:
        output: dict[str, Any] = {
            "content": [item.model_dump(by_alias=True) for item in result.content]
        }
    return ToolCallResult(
        outcome="error" if result.isError else "ok",
        output=output,
        meta=result.meta or {},
    )


__all__ = [
    "prompt_to_discovered",
    "resource_to_discovered",
    "tool_result_to_call_result",
    "tool_to_discovered",
    "workflow_output_schema_from_mcp_tool_schema",
]
```

- [ ] **Step 2: Export converter helpers**

Update `src/wf_sources_mcp/sdk/__init__.py` to import and export:

```python
from .converters import (
    prompt_to_discovered,
    resource_to_discovered,
    tool_result_to_call_result,
    tool_to_discovered,
    workflow_output_schema_from_mcp_tool_schema,
)
```

Add those names to `__all__`.

- [ ] **Step 3: Add canonical converter tests**

Create `tests/wf_sources_mcp/test_sdk_converters.py` by copying `tests/wf_mcp/test_sdk_converters.py`, but change imports to:

```python
from wf_sources_mcp.sdk.converters import (
    tool_result_to_call_result,
    tool_to_discovered,
)
```

Keep the four existing test bodies unchanged.

- [ ] **Step 4: Run canonical converter tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_sdk_converters.py -q
```

Expected: 4 tests pass.

---

### Task 2: Replace Old Converter Module With Shim

**Files:**
- Modify: `src/wf_mcp/sdk/converters.py`
- Modify: `tests/wf_mcp/test_compat_imports.py`

- [ ] **Step 1: Replace old converter module**

Set `src/wf_mcp/sdk/converters.py` to:

```python
"""Compatibility shim for MCP SDK converter helpers.

Canonical implementation lives in `wf_sources_mcp.sdk.converters`.
"""

from __future__ import annotations

from wf_sources_mcp.sdk.converters import (
    prompt_to_discovered,
    resource_to_discovered,
    tool_result_to_call_result,
    tool_to_discovered,
    workflow_output_schema_from_mcp_tool_schema,
)

__all__ = [
    "prompt_to_discovered",
    "resource_to_discovered",
    "tool_result_to_call_result",
    "tool_to_discovered",
    "workflow_output_schema_from_mcp_tool_schema",
]
```

- [ ] **Step 2: Add shim identity test**

Append to `tests/wf_mcp/test_compat_imports.py`:

```python
def test_wf_mcp_sdk_converter_shim_reexports_wf_sources_mcp_converters() -> None:
    from wf_mcp.sdk.converters import tool_result_to_call_result as compat_tool_result
    from wf_mcp.sdk.converters import tool_to_discovered as compat_tool_to_discovered
    from wf_mcp.sdk.converters import (
        workflow_output_schema_from_mcp_tool_schema as compat_output_schema,
    )
    from wf_sources_mcp.sdk.converters import (
        tool_result_to_call_result,
        tool_to_discovered,
        workflow_output_schema_from_mcp_tool_schema,
    )

    assert compat_tool_result is tool_result_to_call_result
    assert compat_tool_to_discovered is tool_to_discovered
    assert compat_output_schema is workflow_output_schema_from_mcp_tool_schema
```

- [ ] **Step 3: Run compatibility tests**

Run:

```bash
uv run pytest tests/wf_mcp/test_compat_imports.py tests/wf_mcp/test_sdk_converters.py -q
```

Expected: compatibility tests and old converter tests pass.

---

### Task 3: Rewrite Production Imports to Canonical Converter Path

**Files:**
- Modify: `src/wf_mcp/sdk/adapter.py`
- Modify: `src/wf_mcp/runtime/session.py`
- Modify: `src/wf_mcp/broker/catalog.py`

- [ ] **Step 1: Update adapter imports**

In `src/wf_mcp/sdk/adapter.py`, replace:

```python
from .converters import (
    prompt_to_discovered,
    resource_to_discovered,
    tool_result_to_call_result,
    tool_to_discovered,
)
```

with:

```python
from wf_sources_mcp.sdk.converters import (
    prompt_to_discovered,
    resource_to_discovered,
    tool_result_to_call_result,
    tool_to_discovered,
)
```

- [ ] **Step 2: Update runtime session import**

In `src/wf_mcp/runtime/session.py`, replace:

```python
from ..sdk.converters import tool_result_to_call_result
```

with:

```python
from wf_sources_mcp.sdk.converters import tool_result_to_call_result
```

- [ ] **Step 3: Update broker catalog import**

In `src/wf_mcp/broker/catalog.py`, replace:

```python
from ..sdk.converters import workflow_output_schema_from_mcp_tool_schema
```

with:

```python
from wf_sources_mcp.sdk.converters import (
    workflow_output_schema_from_mcp_tool_schema,
)
```

- [ ] **Step 4: Confirm production imports no longer use old converter path**

Run:

```bash
rg -n "wf_mcp\\.sdk\\.converters|\\.sdk\\.converters|\\.\\.sdk\\.converters" src
```

Expected: only `src/wf_mcp/sdk/converters.py` shim may mention `wf_sources_mcp.sdk.converters`; no production code imports old converter path.

- [ ] **Step 5: Run focused production tests**

Run:

```bash
uv run pytest tests/wf_mcp/test_sdk_adapter.py tests/wf_mcp/test_sdk_converters.py tests/wf_mcp/test_stateful_runtime.py tests/wf_mcp/service/test_catalog.py -q
```

Expected: all focused tests pass.

---

### Task 4: Strengthen Import-Direction Guard

**Files:**
- Modify: `tests/wf_sources_mcp/test_import_direction_guard.py`

- [ ] **Step 1: Add old converter module to forbidden guard**

Append this test to `tests/wf_sources_mcp/test_import_direction_guard.py`:

```python
def test_wf_sources_mcp_does_not_import_old_sdk_converter_module() -> None:
    root = Path(__file__).resolve().parents[2] / "src" / "wf_sources_mcp"
    forbidden = {
        "wf_mcp.sdk.converters",
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
        "wf_sources_mcp still imports old wf_mcp SDK converter module:\n"
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
- Move: `docs/superpowers/plans/2026-06-07-wf-sources-mcp-sdk-converters-slice.md` to `docs/historical/superpowers/plans/2026-06-07-wf-sources-mcp-sdk-converters-slice.md`

- [ ] **Step 1: Update roadmap**

In `docs/current_roadmap.md`, under the MCP package split section, add:

```markdown
     Fifth `wf_sources_mcp` slice complete: MCP SDK conversion helpers now live
     in `wf_sources_mcp.sdk.converters`, with `wf_mcp.sdk.converters` retained
     as a compatibility shim.
```

- [ ] **Step 2: Update long-lived API boundary spec**

In `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`, update the `wf_sources_mcp` status list so it includes:

```markdown
5. Complete: MCP SDK conversion helpers moved to `wf_sources_mcp.sdk.converters`, with `wf_mcp.sdk.converters` retained as a shim.
6. Upstream transport/discovery/session services.
```

- [ ] **Step 3: Move completed plan to historical**

Run:

```bash
git mv docs/superpowers/plans/2026-06-07-wf-sources-mcp-sdk-converters-slice.md docs/historical/superpowers/plans/2026-06-07-wf-sources-mcp-sdk-converters-slice.md
```

Expected: `git status --short` shows an `R` rename for this plan.

---

### Task 6: Final Verification

**Files:**
- All changed files

- [ ] **Step 1: Run focused extraction tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp tests/wf_mcp/test_compat_imports.py tests/wf_mcp/test_sdk_adapter.py tests/wf_mcp/test_sdk_converters.py tests/wf_mcp/test_stateful_runtime.py tests/wf_mcp/service/test_catalog.py -q
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

Expected: full suite passes with current skip/xfail counts. If it times out locally, rerun with a longer timeout before reporting.

- [ ] **Step 4: Review remaining old converter imports**

Run:

```bash
rg -n "wf_mcp\\.sdk\\.converters|from wf_mcp\\.sdk\\.converters|from \\.\\.sdk\\.converters|from \\.sdk\\.converters" src tests
```

Expected: remaining occurrences are compatibility shims or tests intentionally exercising old import paths.

- [ ] **Step 5: Report**

Report:

- files created/modified
- focused/full verification output
- whether `wf_sources_mcp.sdk.converters` owns all converter helpers
- whether `wf_mcp.sdk.converters` remains as a shim
- deviations from this plan

Do not commit unless the user explicitly asks. If committing, use:

```bash
git add -A
git commit -m "refactor: move mcp sdk converters to wf_sources_mcp"
```

---

## Self-Review

- Spec coverage: moves the pure conversion helpers needed before moving SDK adapter/runtime sessions.
- Placeholder scan: no `TODO`, `TBD`, or unspecified test steps.
- Type consistency: function names and behavior match current `wf_mcp.sdk.converters` exactly, with only import ownership changing.
