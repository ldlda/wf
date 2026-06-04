# WfMcpService Event Recorder Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract broker event recording and catalog-change event fanout from `WfMcpService` into a focused `BrokerEventRecorder` while preserving existing event history, subscribers, and public service methods.

**Architecture:** Add `BrokerEventRecorder` under `wf_mcp.broker.service`. It wraps the existing `EventBus`, owns `record_event`, `record_kind`, `record_catalog_change_events`, and `list_events`. `WfMcpService` keeps `event_bus` for compatibility with server/proxy wiring and keeps `_record_event` / `_record_catalog_change_events` as delegates until later cleanup.

**Tech Stack:** Python 3.14, dataclasses, existing `wf_mcp.events.EventBus`/`McpEvent`, pytest, ruff, basedpyright.

---

## Scope

Move now:

- Direct `event_bus.publish(...)` usage.
- `list_events`.
- `_record_event`, as `BrokerEventRecorder.record_event`.
- `_record_catalog_change_events`, as `BrokerEventRecorder.record_catalog_change_events`.
- Event construction helper for simple workflow/API events, as `BrokerEventRecorder.record_kind`.

Keep now:

- `WfMcpService.event_bus` dataclass field for server/proxy compatibility.
- `WfMcpService.list_events`, `_record_event`, and `_record_catalog_change_events` as delegates.
- Event kind strings and payload shapes.
- Existing `wf_api.operation_context.WorkflowEventRecorder` protocol.

Do not do in this slice:

- Do not move `EventBus` itself.
- Do not change notification projection.
- Do not convert all event callers to a new domain event enum.
- Do not remove private delegate methods from `WfMcpService`.

---

## Target File Structure

- Create `src/wf_mcp/broker/service/events.py`
  - Defines `BrokerEventRecorder`.
  - Owns catalog-change fanout logic.
  - Has docstrings stating this is broker-local event recording, not MCP notification delivery.

- Modify `src/wf_mcp/broker/service/core.py`
  - Add `events: BrokerEventRecorder = field(init=False)`.
  - Construct it from `event_bus` in `__post_init__`.
  - Pass `self.events.record_event` into `UpstreamTransportService`, `SourceCatalogService`, and `WorkflowRuntimeService`.
  - Delegate public/private event methods.

- Modify `src/wf_mcp/broker/service/workflow_operation_context.py`
  - `WfMcpWorkflowEventRecorder` should hold `BrokerEventRecorder`, not call `service._record_event`.

- Add tests in `tests/wf_mcp/service/test_event_recorder.py`.

- Update docs:
  - `docs/current_roadmap.md`.
  - `docs/superpowers/research/2026-06-01-wf-api-extraction-map.md` if stale.

---

## Task 1: Add BrokerEventRecorder Skeleton

**Files:**

- Create: `src/wf_mcp/broker/service/events.py`
- Create: `tests/wf_mcp/service/test_event_recorder.py`

- [ ] **Step 1: Write direct event recorder tests**

Create `tests/wf_mcp/service/test_event_recorder.py`:

```python
from __future__ import annotations

from wf_mcp.broker.service.events import BrokerEventRecorder
from wf_mcp.events import EventBus, make_event


def test_broker_event_recorder_records_existing_event() -> None:
    bus = EventBus()
    recorder = BrokerEventRecorder(bus)
    event = make_event("connection_registered", connection_id="demo.personal")

    recorder.record_event(event)

    assert recorder.list_events()[0] is event
    assert bus.list_events()[0] is event


def test_broker_event_recorder_builds_simple_event() -> None:
    recorder = BrokerEventRecorder(EventBus())

    recorder.record_kind(
        "workflow_artifact_saved",
        capability_id="echo",
        payload={"version": 1},
    )

    event = recorder.list_events()[0]
    assert event.kind == "workflow_artifact_saved"
    assert event.capability_id == "echo"
    assert event.payload["version"] == 1
```

- [ ] **Step 2: Run the tests and verify they fail**

Run:

```bash
uv run pytest tests/wf_mcp/service/test_event_recorder.py::test_broker_event_recorder_records_existing_event tests/wf_mcp/service/test_event_recorder.py::test_broker_event_recorder_builds_simple_event -q
```

Expected: import failure because `wf_mcp.broker.service.events` does not exist.

- [ ] **Step 3: Create BrokerEventRecorder**

Create `src/wf_mcp/broker/service/events.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from wf_mcp.events import EventBus, McpEvent, make_event


@dataclass(slots=True)
class BrokerEventRecorder:
    """Broker-local event recorder backed by the existing EventBus.

    This class records and fans out local service events. MCP notifications are
    still projected by subscribers/resources elsewhere; this is only the broker
    event emission boundary.
    """

    event_bus: EventBus

    def record_event(self, event: McpEvent) -> None:
        self.event_bus.publish(event)

    def record_kind(
        self,
        event_type: str,
        *,
        connection_id: str | None = None,
        capability_id: str | None = None,
        workflow_name: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        self.record_event(
            make_event(
                event_type,
                connection_id=connection_id,
                capability_id=capability_id,
                workflow_name=workflow_name,
                payload=payload or {},
            )
        )

    def list_events(self) -> list[McpEvent]:
        return self.event_bus.list_events()
```

- [ ] **Step 4: Run the tests**

Run:

```bash
uv run pytest tests/wf_mcp/service/test_event_recorder.py::test_broker_event_recorder_records_existing_event tests/wf_mcp/service/test_event_recorder.py::test_broker_event_recorder_builds_simple_event -q
```

Expected: pass.

- [ ] **Step 5: Run ruff**

Run:

```bash
uv run ruff check src/wf_mcp/broker/service/events.py tests/wf_mcp/service/test_event_recorder.py
```

Expected: pass.

---

## Task 2: Move Catalog-Change Fanout Into BrokerEventRecorder

**Files:**

- Modify: `src/wf_mcp/broker/service/events.py`
- Test: `tests/wf_mcp/service/test_event_recorder.py`

- [ ] **Step 1: Write direct catalog fanout test**

Append to `tests/wf_mcp/service/test_event_recorder.py`:

```python
from wf_mcp.models import CatalogSnapshot


def test_broker_event_recorder_records_catalog_change_fanout() -> None:
    recorder = BrokerEventRecorder(EventBus())
    snapshot = CatalogSnapshot(
        connection_id="demo.personal",
        nodes=[
            {
                "qualified_name": "demo.personal.echo",
                "connection_id": "demo.personal",
                "local_name": "echo",
                "input_schema": {},
                "output_schema": {},
                "outcomes": ["ok"],
            }
        ],
        resources=[
            {
                "qualified_name": "demo.personal.resource.welcome",
                "connection_id": "demo.personal",
                "local_name": "welcome",
                "uri": "demo://welcome",
            }
        ],
        prompts=[
            {
                "qualified_name": "demo.personal.prompt.welcome",
                "connection_id": "demo.personal",
                "local_name": "welcome",
            }
        ],
        fetched_at_epoch_ms=1,
        max_age_seconds=300,
    )

    recorder.record_catalog_change_events(
        "demo.personal",
        snapshot,
        reason="catalog_refresh",
    )

    events = recorder.list_events()
    event_kinds = [event.kind for event in events]
    assert event_kinds == [
        "tools_changed",
        "resources_changed",
        "prompts_changed",
        "catalog_changed",
    ]
    assert events[-1].payload["reason"] == "catalog_refresh"
    assert events[-1].payload["node_count"] == 1
    assert events[-1].payload["resource_count"] == 1
    assert events[-1].payload["prompt_count"] == 1
```

If `CatalogSnapshot` requires additional fields in this repo, inspect an existing fixture in `tests/wf_mcp/service/test_events.py` and use the same minimal shape. Do not weaken the assertion to only “some event exists.”

- [ ] **Step 2: Run the fanout test and verify it fails**

Run:

```bash
uv run pytest tests/wf_mcp/service/test_event_recorder.py::test_broker_event_recorder_records_catalog_change_fanout -q
```

Expected: fail because `record_catalog_change_events` does not exist.

- [ ] **Step 3: Implement catalog fanout**

In `src/wf_mcp/broker/service/events.py`, import:

```python
from wf_mcp.models import CatalogSnapshot
```

Add:

```python
    def record_catalog_change_events(
        self,
        connection_id: str,
        snapshot: CatalogSnapshot,
        *,
        reason: str,
    ) -> None:
        """Emit local change events that future MCP notifications can project."""
        counts = {
            "node_count": len(snapshot.nodes),
            "resource_count": len(snapshot.resources),
            "prompt_count": len(snapshot.prompts),
        }
        if snapshot.nodes:
            self.record_kind(
                "tools_changed",
                connection_id=connection_id,
                payload={"reason": reason, "node_count": counts["node_count"]},
            )
        if snapshot.resources:
            self.record_kind(
                "resources_changed",
                connection_id=connection_id,
                payload={
                    "reason": reason,
                    "resource_count": counts["resource_count"],
                },
            )
        if snapshot.prompts:
            self.record_kind(
                "prompts_changed",
                connection_id=connection_id,
                payload={"reason": reason, "prompt_count": counts["prompt_count"]},
            )
        self.record_kind(
            "catalog_changed",
            connection_id=connection_id,
            payload={"reason": reason, **counts},
        )
```

- [ ] **Step 4: Run event recorder tests**

Run:

```bash
uv run pytest tests/wf_mcp/service/test_event_recorder.py -q
```

Expected: all tests in the file pass.

- [ ] **Step 5: Run ruff**

Run:

```bash
uv run ruff check src/wf_mcp/broker/service/events.py tests/wf_mcp/service/test_event_recorder.py
```

Expected: pass.

---

## Task 3: Wire BrokerEventRecorder Into WfMcpService

**Files:**

- Modify: `src/wf_mcp/broker/service/core.py`
- Test: `tests/wf_mcp/test_events.py`
- Test: `tests/wf_mcp/service/test_event_recorder.py`

- [ ] **Step 1: Add service identity test**

Append to `tests/wf_mcp/service/test_event_recorder.py`:

```python
from wf_mcp.broker import WfMcpService
from wf_mcp.storage import FileStore

from ..test_support import local_temp_root


def test_wfmcpservice_uses_broker_event_recorder() -> None:
    bus = EventBus()
    service = WfMcpService(
        store=FileStore(local_temp_root() / "service_event_recorder"),
        event_bus=bus,
    )

    service._record_event(  # noqa: SLF001
        make_event("connection_registered", connection_id="demo.personal")
    )

    assert service.events.event_bus is bus
    assert service.list_events()[0].kind == "connection_registered"
```

- [ ] **Step 2: Run the service identity test and verify it fails**

Run:

```bash
uv run pytest tests/wf_mcp/service/test_event_recorder.py::test_wfmcpservice_uses_broker_event_recorder -q
```

Expected: fail because `service.events` does not exist.

- [ ] **Step 3: Add events field to WfMcpService**

In `src/wf_mcp/broker/service/core.py`, import:

```python
from .events import BrokerEventRecorder
```

Add dataclass field:

```python
    events: BrokerEventRecorder = field(init=False)
```

At the top of `__post_init__`, before constructing `UpstreamTransportService`, add:

```python
        self.events = BrokerEventRecorder(self.event_bus)
```

Update service construction callbacks:

```python
        self.upstream = UpstreamTransportService(
            store=self.store,
            event_sink=self.events.record_event,
            tool_executor=self.tool_executor,
        )
```

```python
            emit_event=self.events.record_event,
```

```python
            emit_event=self.events.record_event,
```

- [ ] **Step 4: Delegate event methods**

Replace:

```python
    def list_events(self) -> list[McpEvent]:
        return self.event_bus.list_events()

    def _record_event(self, event: McpEvent) -> None:
        self.event_bus.publish(event)
```

with:

```python
    def list_events(self) -> list[McpEvent]:
        return self.events.list_events()

    def _record_event(self, event: McpEvent) -> None:
        self.events.record_event(event)
```

Replace `_record_catalog_change_events` body with:

```python
        self.events.record_catalog_change_events(
            connection_id,
            snapshot,
            reason=reason,
        )
```

Keep the method signature and docstring.

- [ ] **Step 5: Run service event tests**

Run:

```bash
uv run pytest tests/wf_mcp/service/test_event_recorder.py::test_wfmcpservice_uses_broker_event_recorder tests/wf_mcp/test_events.py -q
```

Expected: pass.

- [ ] **Step 6: Run ruff**

Run:

```bash
uv run ruff check src/wf_mcp/broker/service/core.py src/wf_mcp/broker/service/events.py tests/wf_mcp/service/test_event_recorder.py
```

Expected: pass.

---

## Task 4: Update WorkflowOperationContext Event Adapter

**Files:**

- Modify: `src/wf_mcp/broker/service/workflow_operation_context.py`
- Test: `tests/wf_api/test_operation_context.py`

- [ ] **Step 1: Strengthen context event adapter test**

In `tests/wf_api/test_operation_context.py`, add or update a test:

```python
def test_context_event_recorder_uses_broker_event_recorder(tmp_path: Path) -> None:
    service = WfMcpService(store=FileStore(tmp_path / "context_events"))
    context = context_from_service(service)

    context.events.record_workflow_event(
        "workflow_artifact_saved",
        capability_id="echo",
        payload={"version": 1},
    )

    assert service.events.list_events()[-1].kind == "workflow_artifact_saved"
    assert service.events.list_events()[-1].capability_id == "echo"
```

If this file already has an equivalent `record_workflow_event` test, update its assertions to read through `service.events.list_events()` instead of only `service.list_events()`.

- [ ] **Step 2: Run the context event test**

Run:

```bash
uv run pytest tests/wf_api/test_operation_context.py::test_context_event_recorder_uses_broker_event_recorder -q
```

If the test name was updated instead of added, run the actual updated test name.

Expected: fail until the adapter stops calling private service methods, or pass if Task 3 delegates already cover it.

- [ ] **Step 3: Update WfMcpWorkflowEventRecorder**

In `src/wf_mcp/broker/service/workflow_operation_context.py`, import:

```python
from .events import BrokerEventRecorder
```

Change:

```python
class WfMcpWorkflowEventRecorder(WorkflowEventRecorder):
    """Adapter-owned event recorder backed by WfMcpService."""

    service: WfMcpService
```

to:

```python
class WfMcpWorkflowEventRecorder(WorkflowEventRecorder):
    """Adapter-owned event recorder backed by BrokerEventRecorder."""

    events: BrokerEventRecorder
```

Replace method bodies:

```python
    def record_event(self, event: Any) -> None:
        self.events.record_event(event)

    def record_workflow_event(
        self,
        event_type: str,
        *,
        capability_id: str,
        payload: dict[str, Any],
    ) -> None:
        self.events.record_kind(
            event_type,
            capability_id=capability_id,
            payload=payload,
        )
```

In `context_from_service`, change:

```python
        events=WfMcpWorkflowEventRecorder(service),
```

to:

```python
        events=WfMcpWorkflowEventRecorder(service.events),
```

- [ ] **Step 4: Run operation context tests**

Run:

```bash
uv run pytest tests/wf_api/test_operation_context.py -q
```

Expected: pass.

- [ ] **Step 5: Run ruff**

Run:

```bash
uv run ruff check src/wf_mcp/broker/service/workflow_operation_context.py tests/wf_api/test_operation_context.py
```

Expected: pass.

---

## Task 5: Clean Imports, Docs, and Verify

**Files:**

- Modify: `src/wf_mcp/broker/service/core.py`
- Modify: `src/wf_mcp/broker/service/workflow_operation_context.py`
- Modify: `docs/current_roadmap.md`
- Modify: `docs/superpowers/research/2026-06-01-wf-api-extraction-map.md` if stale.

- [ ] **Step 1: Remove stale imports**

After the move, `src/wf_mcp/broker/service/core.py` should no longer import `make_event` directly unless it is still used for local resource/local prompt/connection registration events.

If `make_event` is still used only in these service-local cases:

```python
connection_registered
resource_read_completed for local docs
prompt_get_completed for local docs
```

leave it for now. Those local cases can move in a later connection/resource admin extraction.

`src/wf_mcp/broker/service/workflow_operation_context.py` should no longer import `make_event`.

- [ ] **Step 2: Add roadmap note**

In `docs/current_roadmap.md`, under the service extraction bullets, add:

```markdown
  - Broker event recording is being separated from broker coordination.
    `BrokerEventRecorder` now owns EventBus publication, event history reads,
    simple event construction, and catalog-change fanout. `WfMcpService` keeps
    delegate methods for compatibility.
```

- [ ] **Step 3: Update extraction map if stale**

If `docs/superpowers/research/2026-06-01-wf-api-extraction-map.md` says `WfMcpService` directly owns event recording/fanout, add:

```markdown
Event recording ownership is now split: `BrokerEventRecorder` owns EventBus
publication, simple event construction, event history reads, and catalog-change
fanout. `WfMcpService` remains the coordinator and compatibility façade.
```

- [ ] **Step 4: Run focused verification**

Run:

```bash
uv run pytest tests/wf_mcp/service/test_event_recorder.py tests/wf_mcp/test_events.py tests/wf_mcp/service/test_events.py tests/wf_api/test_operation_context.py tests/wf_mcp/workflow_surface/test_deployments.py -q
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

This plan intentionally leaves these for later:

1. **Connection service extraction:** move `register_connection`, reserved-id policy, and config reconciliation.
2. **Local resource/prompt admin extraction:** move local docs event emission out of `WfMcpService.read_resource` and `render_prompt`.
3. **Final service rename:** once `WfMcpService` mostly wires implementation services, consider a clearer broker coordinator name.

---

## Self-Review

- Spec coverage: The plan extracts event recording and catalog-change fanout while preserving existing event bus compatibility and event payload shapes.
- Placeholder scan: No placeholder implementation steps are left. The one import cleanup step explicitly says when to keep `make_event` because local admin event emission remains in `WfMcpService`.
- Type consistency: `BrokerEventRecorder` consistently wraps `EventBus`; `WfMcpService.events` holds the recorder; workflow operation context depends on the recorder instead of private service methods.
