# Source Registry Next Slices Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the source registry toward a generic platform/API boundary, then wire startup merge and finally mutation without locking MCP-specific assumptions into `wf_api`.

**Architecture:** Split generic registry mechanics from MCP-specific source entries. `wf_api` should own the generic registry file/store concepts once they no longer import MCP validators. `wf_mcp` should own MCP source entry models and conversion into `ConnectionConfig` / broker services. Startup merge happens after the split so config-vs-store precedence is implemented against the right abstractions.

**Tech Stack:** Python 3.14, Pydantic v2, existing `wf_mcp.source_registry`, `wf_api`, `wf_config`, `WfMcpService`, pytest, ruff, basedpyright.

---

## Current State

Slice 1 created `src/wf_mcp/source_registry.py` with:

- `SourceRegistryModel`
- `StdioSourceTransport`
- `HttpSourceTransport`
- `McpSourceRegistryEntry`
- `SourceRegistryFile`
- `SourceRegistryStore`
- `FileSourceRegistryStore`

This is useful and tested, but still MCP-shaped:

- id validation uses `wf_mcp.connections.parse_connection_id`
- reserved ids come from `wf_mcp.shared.names`
- source entry type is `McpSourceRegistryEntry`
- transport definitions are MCP transports

Slice 2A then moved generic registry mechanics to `wf_api.source_registry`,
while `wf_mcp.source_registry` kept MCP-specific entries and transports. Slice
2B added `registry_entry_to_connection_config()`.

The next executable slice is startup merge:
`docs/superpowers/plans/2026-06-03-source-registry-startup-merge.md`.

## Slice Order

1. **Slice 2A: Generic Registry Mechanics**
   - **Status: complete.**
   - Move generic validation/store/file mechanics to `wf_api`.
   - Keep MCP entry/transport validation in `wf_mcp`.
   - Prefer boring helpers over deep Pydantic generics where that keeps the
     boundary easier to type-check.
   - Do not change runtime behavior.

2. **Slice 2B: MCP Entry Conversion**
   - **Status: complete.**
   - Add conversion helpers between `McpSourceRegistryEntry` and
     `ConnectionConfig`.
   - Keep config merge out of scope.

3. **Slice 3: Startup Merge**
   - **Status: complete.**
   - Load registry at broker/server startup.
   - Merge config and registry with config precedence.
   - Emit events/diagnostics for shadowed registry entries.

4. **Slice 4: Read Desired Registry Through Admin**
   - **Status: complete.**
   - Expose desired registry entries separately from observed source inventory.
   - `WorkflowSourceRegistryApi` provides neutral read-only access.
   - JSON-RPC methods `workflow.admin.source_registry.list` / `.inspect`.
   - CLI commands `wf admin registry list` / `wf admin registry inspect`.
   - Local/static servers report unavailable instead of empty.
   - Concrete MCP-backed `WorkflowServer` construction remains future work.

5. **Slice 5: Mutation Commands**
   - **Status: complete.**
   - Add add/update/enable/disable/remove operations.
   - Use registry store, validation, and atomic writes.
   - Keep auth/catalog cleanup deferred.
   - JSON-RPC/CLI calls work for targets that expose the registry-admin surface;
     local/static servers report unavailable and concrete MCP-backed
     `WorkflowServer` construction remains future work.

6. **Slice 6: Config Ownership Policy**
   - **Status: planned.**
   - Replace implicit config-shadowing with explicit `locked` / `seed`
     ownership policy.
   - `locked` config entries remain operator-owned and shadow/reject registry
     mutation for the same id.
   - `seed` config entries bootstrap missing store entries, then the store owns
     later admin changes.
   - Update startup merge diagnostics and registry admin payloads so users can
     see why a source is mutable or shadowed.

---

## Slice 2A: Generic Registry Mechanics

### Goal

Move generic registry store mechanics out of `wf_mcp` without pretending MCP
source entries are generic.

### Target Shape

Create `src/wf_api/source_registry.py` with protocol-neutral mechanics only:

```python
from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Generic, Protocol, TypeVar
from uuid import uuid4

from pydantic import BaseModel, ConfigDict


class SourceRegistryBaseModel(BaseModel):
    """Base model for persisted source registry state; reject misspelled fields."""

    model_config = ConfigDict(extra="forbid")


SOURCE_REGISTRY_ID_PATTERN = r"^[A-Za-z0-9_][A-Za-z0-9_.-]*$"


def validate_source_registry_id(value: str) -> str:
    """Validate ids that are safe as registry keys and filesystem path segments.

    This helper intentionally does not parse provider/account meaning. MCP can
    layer stricter `parse_connection_id` validation on top while other future
    source families can reuse the safe-id rule.
    """

    if not re.fullmatch(SOURCE_REGISTRY_ID_PATTERN, value):
        raise ValueError(
            "source id must start with alphanumeric or underscore and contain "
            "only [A-Za-z0-9_.-]"
        )
    return value


def validate_unique_source_ids(entries: list[object]) -> None:
    """Reject duplicate `id` fields without owning the entry model shape."""

    seen: set[str] = set()
    for entry in entries:
        source_id = getattr(entry, "id", None)
        if not isinstance(source_id, str):
            raise ValueError("source registry entries must expose string id")
        if source_id in seen:
            raise ValueError(f"duplicate source id {source_id!r}")
        seen.add(source_id)


RegistryT = TypeVar("RegistryT", bound=BaseModel)


class SourceRegistryStore(Protocol[RegistryT]):
    def load_registry(self) -> RegistryT: ...

    def save_registry(self, registry: RegistryT) -> None: ...


class AtomicJsonRegistryStore(Generic[RegistryT]):
    """Filesystem implementation for small desired-registry documents."""

    def __init__(
        self,
        root: Path,
        *,
        filename: str,
        registry_type: type[RegistryT],
        empty_factory: Callable[[], RegistryT],
        corrupt_label: str,
    ) -> None:
        self.root = root
        self.filename = filename
        self.registry_type = registry_type
        self.empty_factory = empty_factory
        self.corrupt_label = corrupt_label
        self.root.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> Path:
        return self.root / self.filename

    def load_registry(self) -> RegistryT:
        if not self.path.exists():
            return self.empty_factory()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{self.corrupt_label} is corrupted: {self.path}") from exc
        return self.registry_type.model_validate(data)

    def save_registry(self, registry: RegistryT) -> None:
        validated = self.registry_type.model_validate(registry.model_dump(mode="json"))
        payload = json.dumps(validated.model_dump(mode="json"), indent=2)
        tmp_path = self.path.with_name(f"{self.path.name}.{uuid4().hex}.tmp")
        tmp_path.write_text(payload, encoding="utf-8")
        tmp_path.replace(self.path)
```

Then `src/wf_mcp/source_registry.py` should import these generic pieces and keep:

- `StdioSourceTransport`
- `HttpSourceTransport`
- `SourceTransport`
- `McpSourceRegistryEntry`
- `SourceRegistryFile` or `McpSourceRegistryFile` as the MCP registry document
  model, using `validate_unique_source_ids(self.sources)`
- `FileSourceRegistryStore` as the MCP concrete store wrapper around
  `AtomicJsonRegistryStore[SourceRegistryFile]`

### Tests

Move generic tests to `tests/wf_api/test_source_registry.py`:

- safe id validation accepts normal registry ids and rejects unsafe ids
- duplicate id helper rejects repeated ids using a fake entry object
- missing file returns empty generic registry
- save/load round trip
- corrupted JSON wraps as `ValueError`

Keep MCP tests in `tests/wf_mcp/test_source_registry.py`:

- MCP id validation
- reserved id rejection
- stdio/http transport models
- `McpFileSourceRegistryStore` round trip

### Acceptance Criteria

- `wf_api.source_registry` imports no `wf_mcp`.
- Existing `wf_mcp.source_registry` public behavior remains compatible.
- Tests pass.
- No startup/runtime behavior changes.

---

## Slice 2B: MCP Entry Conversion

### Goal

Add explicit conversion helpers so startup merge can convert registry entries
into broker connection configs without duplicating field logic.

Status: complete. The implemented helper preserves entry metadata, `auth_ref`,
profile, transport details, and a `source_registry` marker.

### New Helpers

In `src/wf_mcp/source_registry.py`:

```python
def registry_entry_to_connection_config(
    entry: McpSourceRegistryEntry,
) -> ConnectionConfig:
    return ConnectionConfig(
        id=entry.id,
        server=entry.provider,
        account=entry.account,
        enabled=entry.enabled,
        metadata={
            **entry.metadata,
            "auth_ref": entry.auth_ref,
            "profile": entry.profile,
            "transport": entry.transport.model_dump(mode="json"),
            "source_registry": True,
        },
    )
```

And optionally:

```python
def connection_config_to_registry_entry(
    connection: ConnectionConfig,
) -> McpSourceRegistryEntry | None:
    ...
```

Only add reverse conversion if an implementation needs it. Do not guess unknown
transport metadata.

### Tests

- registry entry converts to `ConnectionConfig`
- provider/account/profile/transport metadata are preserved
- disabled entry creates disabled connection config

### Acceptance Criteria

- Conversion is explicit and tested.
- No startup/runtime behavior changes yet.

---

## Slice 3: Startup Merge

### Goal

Load desired dynamic registry state during service construction and merge it
with config-defined connections/sources.

### Merge Rules

1. Built-in reserved ids always win.
2. Config-defined entries win over registry entries with the same id.
3. Registry entries fill ids not present in config.

### Implementation Direction

- Broker config construction should create a `McpFileSourceRegistryStore`.
- `WfMcpService` or `ConnectionService` should accept an optional registry store.
- On startup/reload:
  - load config connections
  - load registry entries
  - convert registry entries to `ConnectionConfig`
  - merge with config precedence
  - register merged connections
  - emit an event for registry entries shadowed by config

### Tests

- absent registry preserves current config-only behavior
- registry-only connection appears after service construction
- config shadows same-id registry entry
- invalid registry fails startup clearly
- disabled registry source hydrates disabled

### Acceptance Criteria

- Existing legacy config behavior is unchanged when no registry file exists.
- Dynamic registry entries persist across service recreation.
- Shadowed entries do not silently override config.

---

## Slice 4: Read Desired Registry Through Admin

### Goal

Expose desired registry entries distinctly from observed source inventory.

Status: complete for API/transport/CLI plumbing. `WorkflowSourceRegistryApi`
provides neutral read-only access. JSON-RPC methods
`workflow.admin.source_registry.list` / `.inspect` are registered. CLI commands
`wf admin registry list` / `wf admin registry inspect` are available for targets
that expose the surface. Local/static servers report
`source_registry_unavailable`. Concrete MCP-backed `WorkflowServer` construction
remains future work.

### Why

`wf source list` currently reports runtime/observed source inventory. Registry
entries are desired server-owned configuration. Users need both views when a
source exists in registry but is disabled, shadowed, or not hydrated.

### Candidate Commands

- `wf admin registry list`
- `wf admin registry inspect SOURCE_ID`

or:

- `wf source registry list`
- `wf source registry inspect SOURCE_ID`

Pick one naming shape in the implementation plan.

### Acceptance Criteria

- Desired registry view is not confused with observed source inventory.
- Shadowed/disabled state is visible.
- No mutation yet.

---

## Slice 5: Mutation Commands

### Goal

Add safe registry mutation.

Status: complete. Implementation:
[2026-06-04 source registry mutations](../plans/2026-06-04-source-registry-mutations.md).

### Operations

- add source
- update source
- enable source
- disable source
- remove source

### Rules

- Validate full registry before commit.
- Write atomically.
- Do not mutate config files.
- Do not delete auth/catalog files in v1.
- Prefer disable over remove for sources referenced by deployments.
- Optional live validation can be a flag, not required for save.

### Acceptance Criteria

- RPC methods exist.
- CLI commands exist.
- Mutations persist across process restart for targets backed by a registry
  store; local/static servers report unavailable.
- Validation errors are actionable.

---

## Self-Review

- This is a multi-slice roadmap, not a single execution plan for all mutation work.
- Slice 2A is the immediate next implementation target and resolves the location problem.
- Startup merge is intentionally after generic/MCP split and conversion helpers.
- Config ownership policy is intentionally after mutation commands, because it
  changes precedence semantics rather than introducing persistence.
