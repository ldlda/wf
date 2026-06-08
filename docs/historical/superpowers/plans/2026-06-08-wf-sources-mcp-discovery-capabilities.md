# MCP Discovery Capabilities Move Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move MCP upstream capability discovery/listing helpers from `wf_mcp.broker.discovery` into canonical `wf_sources_mcp.discovery` without moving NodeSpec wrapping yet.

**Architecture:** `wf_sources_mcp.discovery` will own `DiscoveredConnectionCapabilities`, `discover_connection_capabilities`, and optional resource/prompt fallback handling. `wf_mcp.broker.discovery` remains as a partial compatibility module: it re-exports moved discovery symbols and keeps `specs_from_discovered_tools` local because that function still depends on `wf_mcp.workflow.wrappers` and broker event types.

**Tech Stack:** Python 3.14, MCP SDK `McpError` / `METHOD_NOT_FOUND`, `wf_sources_mcp` typed connections, pytest, ruff, basedpyright.

---

## Hard Boundaries

- Do not move `specs_from_discovered_tools` in this slice.
- Do not move `wf_mcp.workflow.wrappers` in this slice.
- Do not change catalog refresh behavior or event emission.
- Do not add any `wf_mcp` imports to `src/wf_sources_mcp/discovery.py`.
- Preserve compatibility imports from `wf_mcp.broker.discovery`.
- Do not commit unless the caller explicitly asks for a commit.

## File Map

- Create `src/wf_sources_mcp/discovery.py`: canonical discovery/listing helpers.
- Modify `src/wf_sources_mcp/__init__.py`: export moved discovery symbols lazily or directly, depending on circular imports.
- Modify `src/wf_mcp/broker/discovery.py`: keep `specs_from_discovered_tools`, re-export moved discovery symbols.
- Modify `src/wf_mcp/broker/service/upstream_transport.py`: import `discover_connection_capabilities` from `wf_sources_mcp.discovery`; keep `specs_from_discovered_tools` from `wf_mcp.broker.discovery`.
- Keep `src/wf_mcp/broker/__init__.py` public exports working.
- Create `tests/wf_sources_mcp/test_discovery.py`: canonical discovery tests.
- Modify `tests/wf_mcp/test_compat_imports.py`: shim identity test.
- Modify `tests/wf_sources_mcp/test_import_direction_guard.py`: forbid `wf_mcp.broker.discovery` imports inside `wf_sources_mcp`.
- Modify docs: `docs/current_roadmap.md` and `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`.
- Move this plan to `docs/historical/superpowers/plans/` after implementation is verified.

---

### Task 1: Add Canonical Discovery Tests

**Files:**
- Create: `tests/wf_sources_mcp/test_discovery.py`

- [ ] **Step 1: Write tests for successful discovery and optional capability fallback**

Create `tests/wf_sources_mcp/test_discovery.py`:

```python
from __future__ import annotations

from typing import Any

import pytest
from mcp import McpError
from mcp.types import ErrorData

from wf_sources_mcp.auth import AuthRecord
from wf_sources_mcp.catalog import DiscoveredPrompt, DiscoveredResource, DiscoveredTool
from wf_sources_mcp.connections import McpSourceConnection
from wf_sources_mcp.discovery import discover_connection_capabilities
from wf_sources_mcp.sdk import BackendAdapter, ToolCallResult
from wf_sources_mcp.transports import StdioSourceTransport


def _connection() -> McpSourceConnection:
    return McpSourceConnection(
        id="demo.default",
        provider="demo",
        account="default",
        transport=StdioSourceTransport(command="demo-mcp"),
    )


class _Adapter:
    def __init__(self) -> None:
        self.seen_connections: list[McpSourceConnection] = []

    async def list_tools(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
    ) -> list[DiscoveredTool]:
        self.seen_connections.append(connection)
        return [
            DiscoveredTool(
                name="echo",
                title="Echo",
                description="Echo input",
                input_schema={"type": "object"},
                output_schema={"type": "object"},
            )
        ]

    async def list_resources(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
    ) -> list[DiscoveredResource]:
        return [
            DiscoveredResource(
                uri="demo://docs/guide",
                name="guide",
                title="Guide",
                description="Read me",
            )
        ]

    async def list_prompts(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
    ) -> list[DiscoveredPrompt]:
        return [
            DiscoveredPrompt(
                name="summarize",
                title="Summarize",
                description="Summarize text",
            )
        ]

    async def get_connection_metadata(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
    ) -> dict[str, Any]:
        return {"server": connection.provider}

    async def read_resource(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
        uri: str,
    ) -> dict[str, Any]:
        raise NotImplementedError

    async def get_prompt(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
        prompt_name: str,
        arguments: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError

    async def invoke_method(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError

    async def send_notification(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError

    async def call_tool(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
        tool_name: str,
        payload: dict[str, Any],
    ) -> ToolCallResult:
        raise NotImplementedError


class _ToolsOnlyAdapter(_Adapter):
    async def list_resources(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
    ) -> list[DiscoveredResource]:
        raise McpError(ErrorData(code=-32601, message="Method not found"))

    async def list_prompts(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
    ) -> list[DiscoveredPrompt]:
        raise ExceptionGroup(
            "unhandled errors in a TaskGroup",
            [McpError(ErrorData(code=-32601, message="Method not found"))],
        )


class _BrokenResourceAdapter(_Adapter):
    async def list_resources(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
    ) -> list[DiscoveredResource]:
        raise RuntimeError("resource listing broke")


async def test_discover_connection_capabilities_collects_all_capability_families() -> None:
    adapter = _Adapter()
    connection = _connection()

    capabilities = await discover_connection_capabilities(
        connection=connection,
        auth=None,
        adapter=adapter,
    )

    assert capabilities.tools[0].name == "echo"
    assert capabilities.resources[0].name == "guide"
    assert capabilities.prompts[0].name == "summarize"
    assert capabilities.metadata == {"server": "demo"}
    assert adapter.seen_connections == [connection]


async def test_discover_connection_capabilities_treats_missing_optional_families_as_empty() -> None:
    capabilities = await discover_connection_capabilities(
        connection=_connection(),
        auth=None,
        adapter=_ToolsOnlyAdapter(),
    )

    assert [tool.name for tool in capabilities.tools] == ["echo"]
    assert capabilities.resources == []
    assert capabilities.prompts == []


async def test_discover_connection_capabilities_reraises_non_method_not_found_errors() -> None:
    with pytest.raises(RuntimeError, match="resource listing broke"):
        await discover_connection_capabilities(
            connection=_connection(),
            auth=None,
            adapter=_BrokenResourceAdapter(),
        )


def test_backend_adapter_static_shape() -> None:
    adapter: BackendAdapter = _Adapter()

    assert adapter is not None
```

- [ ] **Step 2: Run the tests and verify they fail before implementation**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_discovery.py -q
```

Expected: fail with `ModuleNotFoundError` / import error for `wf_sources_mcp.discovery`.

---

### Task 2: Create `wf_sources_mcp.discovery`

**Files:**
- Create: `src/wf_sources_mcp/discovery.py`

- [ ] **Step 1: Add canonical discovery implementation**

Create `src/wf_sources_mcp/discovery.py`:

```python
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar

from mcp import McpError
from mcp.types import METHOD_NOT_FOUND

from wf_sources_mcp.auth import AuthRecord
from wf_sources_mcp.catalog import DiscoveredPrompt, DiscoveredResource, DiscoveredTool
from wf_sources_mcp.connections import McpSourceConnection
from wf_sources_mcp.sdk import BackendAdapter

_CapabilityT = TypeVar("_CapabilityT")


@dataclass(slots=True)
class DiscoveredConnectionCapabilities:
    tools: list[DiscoveredTool] = field(default_factory=list)
    resources: list[DiscoveredResource] = field(default_factory=list)
    prompts: list[DiscoveredPrompt] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


async def discover_connection_capabilities(
    *,
    connection: McpSourceConnection,
    auth: AuthRecord | None,
    adapter: BackendAdapter,
) -> DiscoveredConnectionCapabilities:
    tools = await adapter.list_tools(connection, auth)
    resources = await _list_optional_capabilities(
        lambda: adapter.list_resources(connection, auth)
    )
    prompts = await _list_optional_capabilities(lambda: adapter.list_prompts(connection, auth))
    metadata = await adapter.get_connection_metadata(connection, auth)
    return DiscoveredConnectionCapabilities(
        tools=tools,
        resources=resources,
        prompts=prompts,
        metadata=metadata,
    )


async def _list_optional_capabilities(
    load: Callable[[], Awaitable[list[_CapabilityT]]],
) -> list[_CapabilityT]:
    """Treat unsupported optional MCP capability families as empty lists.

    Some SDK transports raise ``METHOD_NOT_FOUND`` from inside an
    ``ExceptionGroup`` because the request ran through a task group. Resources
    and prompts are optional families, so only that exact root error means "not
    supported"; every other failure still needs to surface.
    """
    try:
        return await load()
    except Exception as exc:
        root = _root_exception(exc)
        if isinstance(root, McpError) and root.error.code == METHOD_NOT_FOUND:
            return []
        raise


def _root_exception(exc: BaseException) -> BaseException:
    """Unwrap the first nested exception from MCP task-group ExceptionGroups."""
    current: BaseException = exc
    while isinstance(current, ExceptionGroup) and current.exceptions:
        nested = current.exceptions[0]
        if isinstance(nested, BaseException):
            current = nested
            continue
        break
    return current


__all__ = ["DiscoveredConnectionCapabilities", "discover_connection_capabilities"]
```

- [ ] **Step 2: Run canonical tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_discovery.py -q
```

Expected: all tests pass.

---

### Task 3: Export Discovery Symbols From `wf_sources_mcp`

**Files:**
- Modify: `src/wf_sources_mcp/__init__.py`

- [ ] **Step 1: Inspect existing lazy export style**

Open `src/wf_sources_mcp/__init__.py`. If it already uses `__getattr__` for circular imports, extend that style. If it is direct exports only, add direct imports.

- [ ] **Step 2: Add exports without creating circular imports**

The target public API must support:

```python
from wf_sources_mcp import (
    DiscoveredConnectionCapabilities,
    discover_connection_capabilities,
)
```

If direct imports are safe, add:

```python
from .discovery import DiscoveredConnectionCapabilities, discover_connection_capabilities
```

and extend `__all__`:

```python
    "DiscoveredConnectionCapabilities",
    "discover_connection_capabilities",
```

If direct imports cause a circular import, use the existing package-level lazy export pattern and add these names to it.

- [ ] **Step 3: Add a small export assertion to canonical tests**

Append to `tests/wf_sources_mcp/test_discovery.py`:

```python
def test_discovery_symbols_export_from_package_root() -> None:
    from wf_sources_mcp import (
        DiscoveredConnectionCapabilities as RootDiscoveredConnectionCapabilities,
    )
    from wf_sources_mcp import (
        discover_connection_capabilities as root_discover_connection_capabilities,
    )
    from wf_sources_mcp.discovery import (
        DiscoveredConnectionCapabilities,
        discover_connection_capabilities,
    )

    assert RootDiscoveredConnectionCapabilities is DiscoveredConnectionCapabilities
    assert root_discover_connection_capabilities is discover_connection_capabilities
```

- [ ] **Step 4: Run canonical tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_discovery.py -q
```

Expected: all tests pass.

---

### Task 4: Keep `wf_mcp.broker.discovery` as a Partial Shim

**Files:**
- Modify: `src/wf_mcp/broker/discovery.py`
- Modify: `tests/wf_mcp/test_compat_imports.py`

- [ ] **Step 1: Remove moved implementation from `wf_mcp.broker.discovery`**

Edit `src/wf_mcp/broker/discovery.py`:

- Remove imports that only supported moved code:

```python
from collections.abc import Awaitable
from dataclasses import dataclass, field
from mcp import McpError
from mcp.types import METHOD_NOT_FOUND
from wf_sources_mcp.catalog import DiscoveredPrompt, DiscoveredResource
from wf_sources_mcp.sdk import BackendAdapter
from ..shared import root_exception
```

- Add canonical imports:

```python
from wf_sources_mcp.discovery import (
    DiscoveredConnectionCapabilities,
    discover_connection_capabilities,
)
```

- Keep imports needed by `specs_from_discovered_tools`:

```python
from collections.abc import Callable
from typing import Any

from wf_authoring import NodeSpec
from wf_sources_mcp.catalog import DiscoveredTool
from wf_sources_mcp.connections import mcp_source_connection_from_connection_config
from wf_sources_mcp.sdk import ToolExecutor

from ..auth import AuthRecord
from ..models import ConnectionConfig
from ..workflow import wrap_discovered_tool
from .events import McpEvent
```

The resulting module should still define `specs_from_discovered_tools` exactly as before, and should export:

```python
__all__ = [
    "DiscoveredConnectionCapabilities",
    "discover_connection_capabilities",
    "specs_from_discovered_tools",
]
```

- [ ] **Step 2: Add compatibility identity tests**

Append to `tests/wf_mcp/test_compat_imports.py`:

```python
def test_wf_mcp_broker_discovery_shim_reexports_wf_sources_mcp_discovery() -> None:
    from wf_mcp.broker.discovery import (
        DiscoveredConnectionCapabilities as CompatDiscoveredConnectionCapabilities,
    )
    from wf_mcp.broker.discovery import (
        discover_connection_capabilities as compat_discover_connection_capabilities,
    )
    from wf_sources_mcp.discovery import (
        DiscoveredConnectionCapabilities,
        discover_connection_capabilities,
    )

    assert CompatDiscoveredConnectionCapabilities is DiscoveredConnectionCapabilities
    assert compat_discover_connection_capabilities is discover_connection_capabilities
```

- [ ] **Step 3: Run compatibility test**

Run:

```bash
uv run pytest tests/wf_mcp/test_compat_imports.py::test_wf_mcp_broker_discovery_shim_reexports_wf_sources_mcp_discovery -q
```

Expected: pass.

---

### Task 5: Update Broker Call Site to Convert at Boundary

**Files:**
- Modify: `src/wf_mcp/broker/service/upstream_transport.py`

- [ ] **Step 1: Split imports**

Change the discovery imports from:

```python
from wf_mcp.broker.discovery import (
    discover_connection_capabilities,
    specs_from_discovered_tools,
)
```

to:

```python
from wf_mcp.broker.discovery import specs_from_discovered_tools
from wf_sources_mcp.discovery import discover_connection_capabilities
```

The file already imports `mcp_source_connection_from_connection_config`; keep that import.

- [ ] **Step 2: Pass `McpSourceConnection` to canonical discovery**

In `refresh_connection_catalog`, find:

```python
capabilities = await discover_connection_capabilities(
    connection=connection,
    auth=auth,
    adapter=adapter,
)
```

Replace it with:

```python
source_connection = mcp_source_connection_from_connection_config(connection)
capabilities = await discover_connection_capabilities(
    connection=source_connection,
    auth=auth,
    adapter=adapter,
)
```

If `source_connection` is already created nearby for another call in the same method, reuse the existing variable instead of duplicating it.

- [ ] **Step 3: Run focused upstream transport tests**

Run:

```bash
uv run pytest tests/wf_mcp/service/test_upstream_transport.py tests/wf_mcp/service/test_catalog.py tests/wf_mcp/test_sdk_adapter.py -q
```

Expected: pass.

---

### Task 6: Strengthen Import-Direction Guard

**Files:**
- Modify: `tests/wf_sources_mcp/test_import_direction_guard.py`

- [ ] **Step 1: Add a forbidden old discovery import test**

Append to `tests/wf_sources_mcp/test_import_direction_guard.py`:

```python
def test_wf_sources_mcp_does_not_import_old_broker_discovery_module() -> None:
    root = Path(__file__).resolve().parents[2] / "src" / "wf_sources_mcp"
    forbidden = {"wf_mcp.broker.discovery"}
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
        "wf_sources_mcp still imports old wf_mcp broker discovery module:\n"
        + "\n".join(f"  {violation}" for violation in violations)
    )
```

- [ ] **Step 2: Run import guard**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_import_direction_guard.py -q
```

Expected: pass.

---

### Task 7: Update Docs and Archive Plan

**Files:**
- Modify: `docs/current_roadmap.md`
- Modify: `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`
- Move: `docs/superpowers/plans/2026-06-08-wf-sources-mcp-discovery-capabilities.md` to `docs/historical/superpowers/plans/2026-06-08-wf-sources-mcp-discovery-capabilities.md`

- [ ] **Step 1: Update `docs/current_roadmap.md`**

Under the MCP upstream source runtime cleanup / `wf_sources_mcp` section, add:

```markdown
    - Completed: MCP upstream capability discovery (`discover_connection_capabilities`
      and `DiscoveredConnectionCapabilities`) now lives in `wf_sources_mcp.discovery`.
      Tool-to-NodeSpec wrapping remains in `wf_mcp` until the event/wrapper seam
      is neutralized.
```

- [ ] **Step 2: Update `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`**

Add a completed numbered item before the pending upstream transport/discovery/session services item:

```markdown
16. Complete: MCP upstream capability discovery moved to
    `wf_sources_mcp.discovery`, with `wf_mcp.broker.discovery` retaining
    compatibility re-exports. `specs_from_discovered_tools` remains in `wf_mcp`
    until the wrapper/event seam is neutralized.
```

If numbering differs because new items landed meanwhile, keep the completed item before the broad pending item and renumber.

- [ ] **Step 3: Archive the plan**

Run:

```bash
git mv docs/superpowers/plans/2026-06-08-wf-sources-mcp-discovery-capabilities.md docs/historical/superpowers/plans/2026-06-08-wf-sources-mcp-discovery-capabilities.md
```

Expected: `git status --short` shows an `R` rename for the plan.

---

### Task 8: Final Verification

**Files:**
- No code edits unless verification finds a real issue.

- [ ] **Step 1: Run focused tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_discovery.py tests/wf_sources_mcp/test_import_direction_guard.py tests/wf_mcp/test_compat_imports.py tests/wf_mcp/service/test_upstream_transport.py tests/wf_mcp/service/test_catalog.py tests/wf_mcp/test_sdk_adapter.py -q
```

Expected: all selected tests pass.

- [ ] **Step 2: Run source-provider tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp -q
```

Expected: all `wf_sources_mcp` tests pass.

- [ ] **Step 3: Run lint**

Run:

```bash
uv run ruff check src/wf_sources_mcp/discovery.py src/wf_mcp/broker/discovery.py src/wf_mcp/broker/service/upstream_transport.py tests/wf_sources_mcp/test_discovery.py tests/wf_sources_mcp/test_import_direction_guard.py tests/wf_mcp/test_compat_imports.py
```

Expected: `All checks passed!`

- [ ] **Step 4: Run typecheck**

Run:

```bash
uv run basedpyright --level error src/wf_sources_mcp/discovery.py src/wf_mcp/broker/discovery.py src/wf_mcp/broker/service/upstream_transport.py tests/wf_sources_mcp/test_discovery.py
```

Expected: `0 errors, 0 warnings, 0 notes`

- [ ] **Step 5: Check old import usage**

Run:

```bash
rg -n "wf_mcp\.broker\.discovery|from \.discovery import|from \.\.discovery import" src tests
```

Expected:

- `src/wf_mcp/broker/__init__.py` may still export from `.discovery`.
- `src/wf_mcp/broker/service/upstream_transport.py` may still import `specs_from_discovered_tools` from `wf_mcp.broker.discovery`.
- `tests/wf_mcp/test_compat_imports.py` and import-direction guard may reference the old path.
- `src/wf_sources_mcp` must not import the old path.

- [ ] **Step 6: Check whitespace**

Run:

```bash
git diff --check
```

Expected: no whitespace errors. CRLF warnings on Windows are acceptable.

---

## Expected Final Report

The implementer should report:

- Files created, modified, and moved.
- Exact verification commands and pass/fail output.
- Confirmation that `wf_sources_mcp.discovery` imports no `wf_mcp` modules.
- Confirmation that `specs_from_discovered_tools` still lives in `wf_mcp.broker.discovery`.
- Any deviations from this plan.

Do not claim "full suite passed" unless the full suite was actually run.
