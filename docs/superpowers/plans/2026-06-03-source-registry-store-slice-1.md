# Source Registry Store Slice 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add validated source registry models and a filesystem store for desired server-owned source configuration, without wiring it into startup or mutation commands yet.

**Architecture:** The new registry is desired configuration state and stays separate from existing auth/catalog storage. Models live in `wf_mcp` for this first slice because current connection/source registry semantics are still MCP-provider-specific; the file-store interface is small enough to move later. Runtime merge, RPC/CLI mutation, and config reconciliation are explicitly deferred.

**Tech Stack:** Python 3.14, Pydantic v2, existing `wf_mcp.connections.parse_connection_id`, existing `RESERVED_CONNECTION_IDS`, pytest, ruff, basedpyright.

---

## Scope

In scope:

- Typed `SourceRegistryFile` model.
- Typed `McpSourceRegistryEntry` model.
- Typed `StdioSourceTransport` and `HttpSourceTransport` models.
- Duplicate id validation.
- Reserved id validation.
- ID validation using existing connection id rules.
- `SourceRegistryStore` protocol.
- `FileSourceRegistryStore` using `<store_root>/source_registry.json`.
- Atomic filesystem writes.
- Tests for load missing file, save/load round trip, validation errors, and path.

Out of scope:

- Startup merge with config.
- Runtime hydration from registry.
- Mutating API/CLI/RPC commands.
- Auth record changes.
- Catalog deletion or cleanup.
- SQL/remote stores.

## File Structure

- Create `src/wf_mcp/source_registry.py`
  - Pydantic models and validation.
  - Protocol and file store.
  - No dependency on `WfMcpService`.

- Modify `src/wf_mcp/storage/__init__.py`
  - No change in this slice unless the implementor decides a store export is needed.
  - Prefer exporting from `wf_mcp.source_registry`, not overloading `wf_mcp.storage`.

- Create `tests/wf_mcp/test_source_registry.py`
  - Direct model/store tests.

- Modify `docs/current_roadmap.md`
  - Mark Slice 1 complete after implementation.

---

### Task 1: Add failing source registry model tests

**Files:**
- Create: `tests/wf_mcp/test_source_registry.py`

- [ ] **Step 1: Write model validation tests**

Create `tests/wf_mcp/test_source_registry.py`:

```python
from __future__ import annotations

import pytest

from wf_mcp.source_registry import (
    HttpSourceTransport,
    McpSourceRegistryEntry,
    SourceRegistryFile,
    StdioSourceTransport,
)


def _entry(source_id: str = "github.work") -> McpSourceRegistryEntry:
    return McpSourceRegistryEntry(
        id=source_id,
        provider="github",
        account="work",
        transport=StdioSourceTransport(
            command="npx",
            args=("-y", "@modelcontextprotocol/server-github"),
            env={"GITHUB_TOKEN": "${GITHUB_TOKEN}"},
        ),
        auth_ref=source_id,
        metadata={"purpose": "tests"},
    )


def test_source_registry_entry_keeps_identity_and_transport_structural() -> None:
    entry = _entry()

    assert entry.id == "github.work"
    assert entry.provider == "github"
    assert entry.account == "work"
    assert entry.profile is None
    assert entry.transport.kind == "stdio"
    assert entry.transport.command == "npx"
    assert entry.auth_ref == "github.work"


def test_source_registry_accepts_http_transport() -> None:
    entry = McpSourceRegistryEntry(
        id="github.http",
        provider="github",
        account="work",
        transport=HttpSourceTransport(url="https://example.test/mcp"),
    )

    assert entry.transport.kind == "http"
    assert str(entry.transport.url) == "https://example.test/mcp"


def test_source_registry_rejects_duplicate_ids() -> None:
    with pytest.raises(ValueError, match="duplicate source id 'github.work'"):
        SourceRegistryFile(sources=[_entry("github.work"), _entry("github.work")])


def test_source_registry_rejects_reserved_ids() -> None:
    with pytest.raises(ValueError, match="reserved"):
        _entry("wf.admin")


def test_source_registry_rejects_unsafe_ids() -> None:
    with pytest.raises(ValueError, match="connection id"):
        _entry("../bad")
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
uv run pytest tests/wf_mcp/test_source_registry.py -q
```

Expected: FAIL because `wf_mcp.source_registry` does not exist yet.

---

### Task 2: Implement source registry models

**Files:**
- Create: `src/wf_mcp/source_registry.py`
- Test: `tests/wf_mcp/test_source_registry.py`

- [ ] **Step 1: Add models and validators**

Create `src/wf_mcp/source_registry.py`:

```python
from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Annotated, Literal, Protocol

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, field_validator, model_validator

from .connections import parse_connection_id
from .shared.names import RESERVED_CONNECTION_IDS


class SourceRegistryModel(BaseModel):
    """Base model for persisted source registry state; reject misspelled fields."""

    model_config = ConfigDict(extra="forbid")


class StdioSourceTransport(SourceRegistryModel):
    kind: Literal["stdio"] = "stdio"
    command: str = Field(min_length=1)
    args: tuple[str, ...] = ()
    env: dict[str, str] = Field(default_factory=dict)


class HttpSourceTransport(SourceRegistryModel):
    kind: Literal["http"] = "http"
    url: AnyHttpUrl
    headers: dict[str, str] = Field(default_factory=dict)


SourceTransport = Annotated[
    StdioSourceTransport | HttpSourceTransport,
    Field(discriminator="kind"),
]


class McpSourceRegistryEntry(SourceRegistryModel):
    """Desired MCP source configuration persisted by server-owned mutation."""

    id: str
    kind: Literal["mcp"] = "mcp"
    enabled: bool = True
    provider: str = Field(min_length=1)
    account: str = Field(min_length=1)
    profile: str | None = None
    transport: SourceTransport
    auth_ref: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        parse_connection_id(value)
        if value in RESERVED_CONNECTION_IDS:
            raise ValueError(f"source id {value!r} is reserved")
        return value


class SourceRegistryFile(SourceRegistryModel):
    version: Literal[1] = 1
    sources: list[McpSourceRegistryEntry] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_unique_source_ids(self) -> SourceRegistryFile:
        seen: set[str] = set()
        for source in self.sources:
            if source.id in seen:
                raise ValueError(f"duplicate source id {source.id!r}")
            seen.add(source.id)
        return self

    def source_map(self) -> dict[str, McpSourceRegistryEntry]:
        return {source.id: source for source in self.sources}


class SourceRegistryStore(Protocol):
    """Persistence boundary for desired server-owned source configuration."""

    def load_registry(self) -> SourceRegistryFile:
        """Return the stored registry, or an empty registry when absent."""
        ...

    def save_registry(self, registry: SourceRegistryFile) -> None:
        """Persist one validated registry atomically."""
        ...
```

- [ ] **Step 2: Run model tests**

Run:

```bash
uv run pytest tests/wf_mcp/test_source_registry.py -q
```

Expected: model tests PASS except store tests are not added yet.

---

### Task 3: Add failing file store tests

**Files:**
- Modify: `tests/wf_mcp/test_source_registry.py`

- [ ] **Step 1: Append file store tests**

Append:

```python
from pathlib import Path

from wf_mcp.source_registry import FileSourceRegistryStore


def test_file_source_registry_store_loads_empty_registry_when_missing(
    tmp_path: Path,
) -> None:
    store = FileSourceRegistryStore(tmp_path)

    registry = store.load_registry()

    assert registry.version == 1
    assert registry.sources == []
    assert store.path == tmp_path / "source_registry.json"


def test_file_source_registry_store_round_trips_registry(tmp_path: Path) -> None:
    store = FileSourceRegistryStore(tmp_path)
    registry = SourceRegistryFile(sources=[_entry("github.work")])

    store.save_registry(registry)
    loaded = store.load_registry()

    assert loaded.source_map()["github.work"].provider == "github"
    assert loaded.source_map()["github.work"].transport.kind == "stdio"


def test_file_source_registry_store_validates_loaded_registry(tmp_path: Path) -> None:
    store = FileSourceRegistryStore(tmp_path)
    store.path.write_text(
        '{"version": 1, "sources": [{"id": "wf.admin", "provider": "wf", '
        '"account": "admin", "transport": {"kind": "stdio", "command": "x"}}]}',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="reserved"):
        store.load_registry()
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
uv run pytest tests/wf_mcp/test_source_registry.py -q
```

Expected: FAIL because `FileSourceRegistryStore` does not exist yet.

---

### Task 4: Implement file store

**Files:**
- Modify: `src/wf_mcp/source_registry.py`
- Test: `tests/wf_mcp/test_source_registry.py`

- [ ] **Step 1: Add file store implementation**

Append to `src/wf_mcp/source_registry.py`:

```python
class FileSourceRegistryStore:
    """Filesystem implementation for desired source registry state."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> Path:
        return self.root / "source_registry.json"

    def load_registry(self) -> SourceRegistryFile:
        if not self.path.exists():
            return SourceRegistryFile()
        data = json.loads(self.path.read_text(encoding="utf-8"))
        return SourceRegistryFile.model_validate(data)

    def save_registry(self, registry: SourceRegistryFile) -> None:
        # Validate again at the store boundary so callers cannot persist stale or
        # partially constructed model-like objects after mutation.
        validated = SourceRegistryFile.model_validate(
            registry.model_dump(mode="json")
        )
        payload = json.dumps(validated.model_dump(mode="json"), indent=2)
        tmp_path = self.path.with_name(f"{self.path.name}.tmp")
        tmp_path.write_text(payload, encoding="utf-8")
        tmp_path.replace(self.path)
```

- [ ] **Step 2: Add `__all__`**

At the bottom of `src/wf_mcp/source_registry.py`, add:

```python
__all__ = [
    "FileSourceRegistryStore",
    "HttpSourceTransport",
    "McpSourceRegistryEntry",
    "SourceRegistryFile",
    "SourceRegistryStore",
    "SourceTransport",
    "StdioSourceTransport",
]
```

- [ ] **Step 3: Run tests**

Run:

```bash
uv run pytest tests/wf_mcp/test_source_registry.py -q
```

Expected: PASS.

---

### Task 5: Documentation and verification

**Files:**
- Modify: `docs/current_roadmap.md`

- [ ] **Step 1: Update roadmap**

In `docs/current_roadmap.md`, near the store-backed source registry note, add:

```markdown
- First source registry implementation slice complete: validated registry
  models plus `FileSourceRegistryStore` exist, but startup merge and mutation
  commands are still deferred.
```

- [ ] **Step 2: Run verification**

Run:

```bash
uv run pytest tests/wf_mcp/test_source_registry.py -q
uv run ruff check src/wf_mcp/source_registry.py tests/wf_mcp/test_source_registry.py
uv run ruff format --check src/wf_mcp/source_registry.py tests/wf_mcp/test_source_registry.py
uv run basedpyright --level error src/wf_mcp/source_registry.py tests/wf_mcp/test_source_registry.py
```

Expected:

- pytest PASS
- ruff check PASS
- ruff format PASS
- basedpyright 0 errors

- [ ] **Step 3: Commit**

```bash
git add src/wf_mcp/source_registry.py tests/wf_mcp/test_source_registry.py docs/current_roadmap.md
git commit -m "feat: add source registry file store"
```

---

## Self-Review

- Spec coverage: Slice 1 only is covered: models, validation, file store, tests, docs.
- Placeholder scan: no TBD/TODO placeholders.
- Type consistency: `SourceRegistryFile`, `McpSourceRegistryEntry`, `SourceRegistryStore`, and `FileSourceRegistryStore` names are consistent.
- Deferred work is explicit: startup merge, runtime hydration, RPC/CLI mutation, and auth/catalog cleanup are not part of this slice.
