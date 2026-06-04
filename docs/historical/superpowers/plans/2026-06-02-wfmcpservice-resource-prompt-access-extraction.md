# WfMcpService Resource/Prompt Access Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract the local-docs-aware resource read and prompt render logic from `WfMcpService` into a focused `ContentAccessService` while preserving existing MCP admin, CLI, and workflow behavior.

**Architecture:** Add `ContentAccessService` under `wf_mcp.broker.service`. It owns the "is this a local doc? if so return inline, else look up catalog entry and delegate upstream" branching that currently lives in `WfMcpService.read_resource` and `WfMcpService.render_prompt`. `WfMcpService` remains the compatibility coordinator; its `read_resource` and `render_prompt` become one-line delegates.

**Why a new service instead of folding into `UpstreamTransportService`:** The local-docs check depends on `SourceCatalogService`, not on upstream adapters. Putting it in `UpstreamTransportService` would add a cross-cutting catalog dependency to a transport-focused service. A thin content-access layer keeps the boundary clean.

**Tech Stack:** Python 3.14, dataclasses, `SourceCatalogService`, `UpstreamTransportService`, `ConnectionService`, pytest, ruff, basedpyright.

---

## Scope

Move now:

- `WfMcpService.read_resource` branching logic (local docs check + upstream delegation).
- `WfMcpService.render_prompt` branching logic (local docs check + upstream delegation).

Keep now:

- `invoke_method`. Already a clean delegate to `upstream`; no local-docs branching. Does not belong in this service.
- `send_notification`. Same reasoning.
- `refresh_connection_catalog`. Different semantics; stays on `WfMcpService` / `UpstreamTransportService`.
- All other `WfMcpService` delegates and compatibility properties.
- Event recording internals on `BrokerEventRecorder`.

Do not do in this slice:

- Do not move `invoke_method` or `send_notification` into `ContentAccessService`.
- Do not move `refresh_connection_catalog`.
- Do not rename `WfMcpService`.
- Do not change adapter implementations.
- Do not change MCP tool schemas or CLI behavior.

---

## Target File Structure

- Create `src/wf_mcp/broker/service/content_access.py`
  - Owns `ContentAccessService`.
  - Depends on `SourceCatalogService` (for local docs lookup and catalog entry resolution), `UpstreamTransportService` (for upstream reads/renders), `ConnectionService` (for connection lookup), and `BrokerEventRecorder` (for local-docs event recording).
  - Contains docstrings stating this is a broker-internal service, not a protocol-neutral API.

- Modify `src/wf_mcp/broker/service/core.py`
  - Add `content_access: ContentAccessService = field(init=False)`.
  - Construct it after `source_catalog`, `upstream`, `connection_service`, and `events` in `__post_init__`.
  - Replace `read_resource` and `render_prompt` bodies with one-line delegates.

- Add tests in `tests/wf_mcp/service/test_content_access.py`.

- Update docs:
  - `docs/superpowers/research/2026-06-02-wfmcpservice-remaining-responsibilities.md` if stale.

---

## Task 1: Add ContentAccessService Skeleton

**Files:**

- Create: `src/wf_mcp/broker/service/content_access.py`
- Create: `tests/wf_mcp/service/test_content_access.py`

- [ ] **Step 1: Write a direct local-resource test**

Create `tests/wf_mcp/service/test_content_access.py`:

```python
from __future__ import annotations

import asyncio

import pytest

from wf_mcp.broker import WfMcpService
from wf_mcp.broker.service.content_access import ContentAccessService
from wf_mcp.broker.service.connection_service import ConnectionService
from wf_mcp.broker.service.events import BrokerEventRecorder
from wf_mcp.broker.service.source_catalog import SourceCatalogService
from wf_mcp.broker.service.upstream_transport import UpstreamTransportService
from wf_mcp.events import EventBus
from wf_mcp.models import ConnectionConfig
from wf_mcp.storage import FileStore
from wf_platform import (
    CapabilityBuckets,
    CapabilitySource,
    DocumentationPrompt,
    DocumentationResource,
    SourceVisibility,
)

from ..test_support import FakeAdapter, local_temp_root


def _make_content_access(
    *,
    store_root: str = "content_access_default",
) -> tuple[ContentAccessService, BrokerEventRecorder]:
    store = FileStore(local_temp_root() / store_root)
    events = BrokerEventRecorder(EventBus())
    connection_service = ConnectionService(events=events)
    upstream = UpstreamTransportService(
        store=store,
        event_sink=events.record_event,
    )
    source_catalog = SourceCatalogService(
        store=store,
        connection_lookup=connection_service.get,
        connection_list_enabled=connection_service.list_enabled,
        connection_list_all=connection_service.list_all,
        tool_executor_for=upstream.tool_executor_for,
        load_auth=upstream.load_auth,
        emit_event=events.record_event,
    )
    connection_service.bind_source_catalog(source_catalog)
    _register_local_docs(source_catalog)
    content_access = ContentAccessService(
        source_catalog=source_catalog,
        upstream=upstream,
        connection_service=connection_service,
        event_sink=events.record_event,
    )
    return content_access, events


def _register_local_docs(source_catalog: SourceCatalogService) -> None:
    """Install deterministic local docs without depending on repo Markdown files."""
    source_catalog.register_capability_source(
        CapabilitySource(
            id="test.docs",
            kind="system",
            capabilities=CapabilityBuckets(
                resources={
                    "test.docs.example": DocumentationResource(
                        name="test.docs.example",
                        uri="wf://docs/example",
                        title="Example Doc",
                        description="Test documentation resource.",
                        mime_type="text/markdown",
                        text="# Example",
                    )
                },
                prompts={
                    "test.docs.guide": DocumentationPrompt(
                        name="test.docs.guide",
                        title="Guide Prompt",
                        description="Test documentation prompt.",
                        text="Use the test docs.",
                    )
                },
            ),
            visibility=SourceVisibility(planner=True),
        )
    )


def test_content_access_reads_local_documentation_resource() -> None:
    content_access, events = _make_content_access()

    result = asyncio.run(
        content_access.read_resource("test.docs.example")
    )

    assert result["contents"][0]["uri"] == "wf://docs/example"
    assert result["contents"][0]["text"] == "# Example"
    assert "resource_read_completed" in [e.kind for e in events.list_events()]
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```bash
uv run pytest tests/wf_mcp/service/test_content_access.py::test_content_access_reads_local_documentation_resource -q
```

Expected: import failure because `content_access.py` does not exist.

- [ ] **Step 3: Create the skeleton service**

Create `src/wf_mcp/broker/service/content_access.py`:

```python
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from wf_mcp.events import McpEvent, make_event

from .connection_service import ConnectionService
from .source_catalog import SourceCatalogService
from .upstream_transport import UpstreamTransportService

EventSink = Callable[[McpEvent], None]


@dataclass(slots=True)
class ContentAccessService:
    """Own local-docs-aware resource reads and prompt renders for the broker.

    This service checks SourceCatalogService for local documentation entries
    before falling back to upstream transport. It is broker-internal, not a
    protocol-neutral content API.
    """

    source_catalog: SourceCatalogService
    upstream: UpstreamTransportService
    connection_service: ConnectionService
    event_sink: EventSink

    async def read_resource(self, qualified_name: str) -> dict[str, Any]:
        local_resource = self.source_catalog.local_documentation_resource(
            qualified_name
        )
        if local_resource is not None:
            self.event_sink(
                make_event(
                    "resource_read_completed",
                    capability_id=qualified_name,
                    payload={"uri": local_resource.uri, "source": "local"},
                )
            )
            return {
                "contents": [
                    {
                        "uri": local_resource.uri,
                        "mimeType": local_resource.mime_type,
                        "text": local_resource.text,
                    }
                ]
            }

        resource = self.source_catalog.get_resource(qualified_name)
        connection = self.connection_service.get(resource.connection_id)
        return await self.upstream.read_resource(
            connection,
            qualified_name,
            resource.uri,
        )

    async def render_prompt(
        self,
        qualified_name: str,
        *,
        arguments: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        local_prompt = self.source_catalog.local_documentation_prompt(qualified_name)
        if local_prompt is not None:
            self.event_sink(
                make_event(
                    "prompt_get_completed",
                    capability_id=qualified_name,
                    payload={
                        "argument_keys": sorted((arguments or {}).keys()),
                        "source": "local",
                    },
                )
            )
            return {
                "description": local_prompt.description,
                "messages": [
                    {
                        "role": "user",
                        "content": {
                            "type": "text",
                            "text": local_prompt.text,
                        },
                    }
                ],
            }

        prompt = self.source_catalog.get_prompt(qualified_name)
        connection = self.connection_service.get(prompt.connection_id)
        return await self.upstream.render_prompt(
            connection,
            qualified_name,
            prompt.local_name,
            arguments,
        )
```

- [ ] **Step 4: Run the test**

Run:

```bash
uv run pytest tests/wf_mcp/service/test_content_access.py::test_content_access_reads_local_documentation_resource -q
```

Expected: pass.

- [ ] **Step 5: Run ruff**

Run:

```bash
uv run ruff check src/wf_mcp/broker/service/content_access.py tests/wf_mcp/service/test_content_access.py
```

Expected: pass.

---

## Task 2: Add Direct Upstream Resource and Prompt Tests

**Files:**

- Modify: `tests/wf_mcp/service/test_content_access.py`

- [ ] **Step 1: Add upstream resource read test**

Append to `tests/wf_mcp/service/test_content_access.py`:

```python
def test_content_access_reads_upstream_resource_with_events() -> None:
    service = WfMcpService(
        store=FileStore(local_temp_root() / "content_upstream_resource")
    )
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_adapter("demo", FakeAdapter())
    asyncio.run(service.refresh_connection_catalog("demo.personal"))

    result = asyncio.run(
        service.content_access.read_resource("demo.personal.resource.welcome")
    )

    assert result["contents"][0]["text"] == "Welcome from the fake adapter resource."
    event_kinds = [e.kind for e in service.list_events()]
    assert "resource_read_started" in event_kinds
    assert "resource_read_completed" in event_kinds


def test_content_access_renders_upstream_prompt_with_events() -> None:
    service = WfMcpService(
        store=FileStore(local_temp_root() / "content_upstream_prompt")
    )
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_adapter("demo", FakeAdapter())
    asyncio.run(service.refresh_connection_catalog("demo.personal"))

    result = asyncio.run(
        service.content_access.render_prompt(
            "demo.personal.prompt.summarize",
            arguments={"text": "hello world"},
        )
    )

    assert "hello world" in result["messages"][0]["content"]["text"]
    event_kinds = [e.kind for e in service.list_events()]
    assert "prompt_get_started" in event_kinds
    assert "prompt_get_completed" in event_kinds
```

- [ ] **Step 2: Run the tests and verify they fail**

Run:

```bash
uv run pytest tests/wf_mcp/service/test_content_access.py::test_content_access_reads_upstream_resource_with_events tests/wf_mcp/service/test_content_access.py::test_content_access_renders_upstream_prompt_with_events -q
```

Expected: fail because `service.content_access` does not exist on `WfMcpService`.

- [ ] **Step 3: Wire ContentAccessService into WfMcpService**

In `src/wf_mcp/broker/service/core.py`, import:

```python
from .content_access import ContentAccessService
```

Add field:

```python
    content_access: ContentAccessService = field(init=False)
```

In `__post_init__`, after constructing `upstream`, `source_catalog`, `connection_service`, and `events`:

```python
        self.content_access = ContentAccessService(
            source_catalog=self.source_catalog,
            upstream=self.upstream,
            connection_service=self.connection_service,
            event_sink=self.events.record_event,
        )
```

- [ ] **Step 4: Run the tests**

Run:

```bash
uv run pytest tests/wf_mcp/service/test_content_access.py::test_content_access_reads_upstream_resource_with_events tests/wf_mcp/service/test_content_access.py::test_content_access_renders_upstream_prompt_with_events -q
```

Expected: pass.

- [ ] **Step 5: Run ruff**

Run:

```bash
uv run ruff check src/wf_mcp/broker/service/core.py src/wf_mcp/broker/service/content_access.py tests/wf_mcp/service/test_content_access.py
```

Expected: pass.

---

## Task 3: Delegate WfMcpService.read_resource and render_prompt

**Files:**

- Modify: `src/wf_mcp/broker/service/core.py`
- Test: `tests/wf_mcp/service/test_events.py`
- Test: `tests/wf_mcp/service/test_content_access.py`

- [ ] **Step 1: Replace read_resource body with delegate**

In `src/wf_mcp/broker/service/core.py`, replace:

```python
    async def read_resource(self, qualified_name: str) -> dict[str, Any]:
        local_resource = self.source_catalog.local_documentation_resource(
            qualified_name
        )
        if local_resource is not None:
            self._record_event(
                make_event(
                    "resource_read_completed",
                    capability_id=qualified_name,
                    payload={"uri": local_resource.uri, "source": "local"},
                )
            )
            return {
                "contents": [
                    {
                        "uri": local_resource.uri,
                        "mimeType": local_resource.mime_type,
                        "text": local_resource.text,
                    }
                ]
            }

        resource = self.get_resource(qualified_name)
        connection = self.connections.get(resource.connection_id)
        return await self.upstream.read_resource(
            connection,
            qualified_name,
            resource.uri,
        )
```

with:

```python
    async def read_resource(self, qualified_name: str) -> dict[str, Any]:
        return await self.content_access.read_resource(qualified_name)
```

- [ ] **Step 2: Replace render_prompt body with delegate**

Replace:

```python
    async def render_prompt(
        self,
        qualified_name: str,
        *,
        arguments: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        local_prompt = self.source_catalog.local_documentation_prompt(qualified_name)
        if local_prompt is not None:
            self._record_event(
                make_event(
                    "prompt_get_completed",
                    capability_id=qualified_name,
                    payload={
                        "argument_keys": sorted((arguments or {}).keys()),
                        "source": "local",
                    },
                )
            )
            return {
                "description": local_prompt.description,
                "messages": [
                    {
                        "role": "user",
                        "content": {
                            "type": "text",
                            "text": local_prompt.text,
                        },
                    }
                ],
            }

        prompt = self.get_prompt(qualified_name)
        connection = self.connections.get(prompt.connection_id)
        return await self.upstream.render_prompt(
            connection,
            qualified_name,
            prompt.local_name,
            arguments,
        )
```

with:

```python
    async def render_prompt(
        self,
        qualified_name: str,
        *,
        arguments: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        return await self.content_access.render_prompt(
            qualified_name,
            arguments=arguments,
        )
```

- [ ] **Step 3: Run the existing event/proxy tests**

Run:

```bash
uv run pytest tests/wf_mcp/service/test_events.py::test_service_can_proxy_resource_reads_and_prompt_gets -q
```

Expected: pass. This proves the delegate preserves existing behavior.

- [ ] **Step 4: Run full content_access tests**

Run:

```bash
uv run pytest tests/wf_mcp/service/test_content_access.py -q
```

Expected: pass.

- [ ] **Step 5: Run ruff**

Run:

```bash
uv run ruff check src/wf_mcp/broker/service/core.py
```

Expected: pass.

---

## Task 4: Add Local Prompt Test and Edge-Case Coverage

**Files:**

- Modify: `tests/wf_mcp/service/test_content_access.py`

- [ ] **Step 1: Add local prompt test**

Append:

```python
def test_content_access_renders_local_documentation_prompt() -> None:
    content_access, events = _make_content_access(
        store_root="content_access_local_prompt"
    )

    result = asyncio.run(
        content_access.render_prompt("test.docs.guide")
    )

    assert result["description"] == "Test documentation prompt."
    assert result["messages"][0]["role"] == "user"
    assert result["messages"][0]["content"]["text"] == "Use the test docs."
    assert "prompt_get_completed" in [e.kind for e in events.list_events()]
```

- [ ] **Step 2: Run the local prompt test**

Run:

```bash
uv run pytest tests/wf_mcp/service/test_content_access.py::test_content_access_renders_local_documentation_prompt -q
```

Expected: pass.

- [ ] **Step 3: Add missing-resource error test**

Append:

```python
def test_content_access_raises_on_unknown_resource() -> None:
    content_access, _ = _make_content_access(
        store_root="content_access_missing_resource"
    )

    with pytest.raises(KeyError):
        asyncio.run(content_access.read_resource("nonexistent.resource"))
```

- [ ] **Step 4: Run the error test**

Run:

```bash
uv run pytest tests/wf_mcp/service/test_content_access.py::test_content_access_raises_on_unknown_resource -q
```

Expected: pass (KeyError from catalog lookup).

- [ ] **Step 5: Run ruff**

Run:

```bash
uv run ruff check tests/wf_mcp/service/test_content_access.py
```

Expected: pass.

---

## Task 5: Clean Unused Imports and Verify

**Files:**

- Modify: `src/wf_mcp/broker/service/core.py`
- Modify: `docs/superpowers/research/2026-06-02-wfmcpservice-remaining-responsibilities.md` if stale.

- [ ] **Step 1: Remove stale imports from core.py**

After the delegate change, `core.py` may no longer use `make_event` directly (verify with grep). If `make_event` is still used by `_record_catalog_change_events` or other methods, keep it. Only remove imports that are truly unused after the extraction.

Run:

```bash
rg -n "make_event" src/wf_mcp/broker/service/core.py
```

If only the removed `read_resource`/`render_prompt` bodies used `make_event`, remove the import. Otherwise keep it.

- [ ] **Step 2: Update research doc if stale**

If `docs/superpowers/research/2026-06-02-wfmcpservice-remaining-responsibilities.md` still lists `read_resource` and `render_prompt` as "Mixed real responsibility", update their classification:

```markdown
| `read_resource` | Delegates to `ContentAccessService` | Compatibility facade | Keep for admin/MCP callers; new code should call `content_access`. |
| `render_prompt` | Delegates to `ContentAccessService` | Compatibility facade | Keep for admin/MCP callers; new code should call `content_access`. |
```

- [ ] **Step 3: Run focused verification**

Run:

```bash
uv run pytest tests/wf_mcp/service/test_content_access.py tests/wf_mcp/service/test_events.py -q
```

Expected: all selected tests pass.

- [ ] **Step 4: Run full verification**

Run:

```bash
uv run pytest -q
uv run ruff check src/wf_mcp/broker/service tests/wf_mcp/service
uv run ruff format --check src/wf_mcp/broker/service tests/wf_mcp/service
uv run basedpyright --level error
```

Expected:

- pytest passes.
- ruff check passes.
- ruff format check passes.
- basedpyright reports `0 errors`. If the known workspace enumeration warning causes a nonzero exit despite `0 errors`, record the exact output.

---

## Non-Goals and Follow-Up Slices

This plan intentionally leaves these for later:

1. **`invoke_method`/`send_notification`:** Already clean delegates to `upstream`. No local-docs branching. Moving them would add coupling without reducing complexity.
2. **`refresh_connection_catalog`:** Different semantics (catalog refresh, not content access). Stays on `WfMcpService` / `UpstreamTransportService`.
3. **Connection registry extraction:** Already done in `ConnectionService`; do not change it in this slice.
4. **Event recorder extraction:** Already done in `BrokerEventRecorder`; do not change it in this slice.
5. **`workflow_artifact_catalog_entry`:** Not broker content access; handle in a separate small cleanup.

---

## Self-Review

- Spec coverage: The plan extracts the local-docs-aware resource/prompt branching logic while preserving current public `WfMcpService` methods as one-line delegates. Upstream event semantics are unchanged.
- Placeholder scan: No placeholder implementation tasks are left. Local docs tests use deterministic test-only resource and prompt keys.
- Type consistency: `ContentAccessService` depends on `SourceCatalogService`, `UpstreamTransportService`, `ConnectionService`, and an `EventSink` callback. `WfMcpService.content_access` is exposed as a public field so callers (admin handlers, tests) can use it directly.
