# wf_config MCP Source Model Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a neutral `kind: "mcp"` source variant to `wf_config.server.sources[]` so MCP source definitions can live in the wider workflow config model.

**Architecture:** Keep this slice pure `wf_config`: no imports from `wf_mcp`, no server construction changes, no runtime behavior changes. The new config shape should intentionally mirror `wf_mcp.source_registry.McpSourceRegistryEntry`, with the legacy `ConnectionConfig.source_config_ownership` policy renamed to a neutral config/source field.

**Tech Stack:** Pydantic v2 discriminated unions, `AnyHttpUrl`, existing `tests/wf_config/test_config_models.py`.

---

## File Structure

- Modify `src/wf_config/models.py`: add transport config models, `McpSourceConfig`, and include it in the existing `SourceConfig` union.
- Modify `src/wf_config/__init__.py`: export the new config types.
- Modify `tests/wf_config/test_config_models.py`: add model parsing/validation tests for MCP sources.
- Modify `docs/current_roadmap.md` and `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`: mark this slice complete after implementation.

## Current Context

Current neutral config has:

```python
class StdlibSourceConfig(WorkflowConfigModel):
    kind: Literal["stdlib"]
    id: Literal["wf.std", "wf.recipes"]


SourceConfig = Annotated[
    StdlibSourceConfig,
    Field(discriminator="kind"),
]
```

MCP’s desired source shape already exists at `src/wf_mcp/source_registry.py` as `McpSourceRegistryEntry`, but that module imports MCP-specific validators and models. Do not import it into `wf_config`.

The source id rule to mirror is currently in `src/wf_mcp/connections.py`:

```python
CONNECTION_ID_PATTERN = r"^[A-Za-z0-9_][A-Za-z0-9_.-]*$"
```

and MCP ids must look like `<provider>.<account>`.

## Task 1: Add MCP Source Config Tests

**Files:**
- Modify: `tests/wf_config/test_config_models.py`

- [ ] **Step 1: Add imports**

Update the import block from `wf_config` to include the new classes that will be implemented:

```python
from wf_config import (
    FilesystemStoreConfig,
    HttpSourceTransportConfig,
    LocalTargetConfig,
    McpSourceConfig,
    RpcHttpTargetConfig,
    RpcHttpTransportConfig,
    StdioSourceTransportConfig,
    StdlibSourceConfig,
    WorkflowConfigFile,
    load_workflow_config,
)
```

- [ ] **Step 2: Add stdio MCP source parsing test**

Append this test:

```python
def test_workflow_config_parses_mcp_stdio_source() -> None:
    config = WorkflowConfigFile.model_validate(
        {
            "version": 1,
            "server": {
                "sources": [
                    {
                        "kind": "mcp",
                        "id": "everything.default",
                        "enabled": True,
                        "provider": "everything",
                        "account": "default",
                        "profile": "dev",
                        "ownership": "seed",
                        "transport": {
                            "kind": "stdio",
                            "command": "uvx",
                            "args": ["mcp-server-everything"],
                            "env": {"DEBUG": "1"},
                        },
                        "auth_ref": "auth.everything.default",
                        "metadata": {"description": "Everything test server"},
                    }
                ]
            },
        }
    )

    source = config.server.sources[0]
    assert isinstance(source, McpSourceConfig)
    assert source.id == "everything.default"
    assert source.enabled is True
    assert source.provider == "everything"
    assert source.account == "default"
    assert source.profile == "dev"
    assert source.ownership == "seed"
    assert isinstance(source.transport, StdioSourceTransportConfig)
    assert source.transport.command == "uvx"
    assert source.transport.args == ("mcp-server-everything",)
    assert source.transport.env == {"DEBUG": "1"}
    assert source.auth_ref == "auth.everything.default"
    assert source.metadata["description"] == "Everything test server"
```

- [ ] **Step 3: Add HTTP MCP source parsing test**

Append this test:

```python
def test_workflow_config_parses_mcp_http_source() -> None:
    config = WorkflowConfigFile.model_validate(
        {
            "version": 1,
            "server": {
                "sources": [
                    {
                        "kind": "mcp",
                        "id": "context7.default",
                        "provider": "context7",
                        "account": "default",
                        "transport": {
                            "kind": "http",
                            "url": "http://127.0.0.1:3000/mcp",
                            "headers": {"X-Test": "yes"},
                        },
                    }
                ]
            },
        }
    )

    source = config.server.sources[0]
    assert isinstance(source, McpSourceConfig)
    assert source.enabled is True
    assert source.ownership == "locked"
    assert isinstance(source.transport, HttpSourceTransportConfig)
    assert str(source.transport.url) == "http://127.0.0.1:3000/mcp"
    assert source.transport.headers == {"X-Test": "yes"}
```

- [ ] **Step 4: Add validation tests**

Append these tests:

```python
def test_workflow_config_rejects_mcp_source_without_provider_account_shape() -> None:
    with pytest.raises(ValidationError, match="source id must look like"):
        WorkflowConfigFile.model_validate(
            {
                "version": 1,
                "server": {
                    "sources": [
                        {
                            "kind": "mcp",
                            "id": "everything",
                            "provider": "everything",
                            "account": "default",
                            "transport": {"kind": "stdio", "command": "uvx"},
                        }
                    ]
                },
            }
        )


def test_workflow_config_rejects_unsafe_mcp_source_id() -> None:
    with pytest.raises(ValidationError, match="source id must start"):
        WorkflowConfigFile.model_validate(
            {
                "version": 1,
                "server": {
                    "sources": [
                        {
                            "kind": "mcp",
                            "id": ".hidden.default",
                            "provider": "hidden",
                            "account": "default",
                            "transport": {"kind": "stdio", "command": "uvx"},
                        }
                    ]
                },
            }
        )


def test_workflow_config_rejects_duplicate_source_ids_across_kinds() -> None:
    with pytest.raises(ValidationError, match="duplicate source id"):
        WorkflowConfigFile.model_validate(
            {
                "version": 1,
                "server": {
                    "sources": [
                        {"kind": "stdlib", "id": "wf.std"},
                        {
                            "kind": "mcp",
                            "id": "wf.std",
                            "provider": "wf",
                            "account": "std",
                            "transport": {"kind": "stdio", "command": "uvx"},
                        },
                    ]
                },
            }
        )
```

- [ ] **Step 5: Run tests and verify failure**

Run:

```bash
uv run pytest tests/wf_config/test_config_models.py -q
```

Expected: fail with import errors for `McpSourceConfig`, `StdioSourceTransportConfig`, and `HttpSourceTransportConfig`.

## Task 2: Implement Neutral MCP Source Config Models

**Files:**
- Modify: `src/wf_config/models.py`

- [ ] **Step 1: Add imports**

Update imports:

```python
import re
from pathlib import Path
from typing import Annotated, Literal
```

- [ ] **Step 2: Add ownership and source id constants**

Place after `ServerTransportConfig`:

```python
SourceConfigOwnership = Literal["locked", "seed"]
SOURCE_ID_PATTERN = r"^[A-Za-z0-9_][A-Za-z0-9_.-]*$"
```

- [ ] **Step 3: Add transport models**

Place before `StdlibSourceConfig`:

```python
class StdioSourceTransportConfig(WorkflowConfigModel):
    kind: Literal["stdio"] = "stdio"
    command: str = Field(min_length=1)
    args: tuple[str, ...] = ()
    env: dict[str, str] = Field(default_factory=dict)


class HttpSourceTransportConfig(WorkflowConfigModel):
    kind: Literal["http"] = "http"
    url: AnyHttpUrl
    headers: dict[str, str] = Field(default_factory=dict)


SourceTransportConfig = Annotated[
    StdioSourceTransportConfig | HttpSourceTransportConfig,
    Field(discriminator="kind"),
]
```

- [ ] **Step 4: Add MCP source model**

Place after `StdlibSourceConfig`:

```python
class McpSourceConfig(WorkflowConfigModel):
    """Neutral config shape for MCP-backed workflow capability sources.

    This intentionally mirrors `wf_mcp.source_registry.McpSourceRegistryEntry`
    without importing MCP modules. `ownership` carries the old
    `ConnectionConfig.source_config_ownership` policy with neutral terminology.
    """

    kind: Literal["mcp"] = "mcp"
    id: str
    enabled: bool = True
    provider: str = Field(min_length=1)
    account: str = Field(min_length=1)
    profile: str | None = None
    ownership: SourceConfigOwnership = "locked"
    transport: SourceTransportConfig
    auth_ref: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("id")
    @classmethod
    def validate_source_id(cls, value: str) -> str:
        if not re.fullmatch(SOURCE_ID_PATTERN, value):
            raise ValueError(
                "source id must start with alphanumeric or underscore and contain "
                "only [A-Za-z0-9_.-]"
            )
        if "." not in value:
            raise ValueError("source id must look like '<provider>.<account>'")
        provider, account = value.split(".", 1)
        if not provider or not account:
            raise ValueError("source id must look like '<provider>.<account>'")
        return value
```

- [ ] **Step 5: Extend SourceConfig union**

Replace the existing union with:

```python
SourceConfig = Annotated[
    StdlibSourceConfig | McpSourceConfig,
    Field(discriminator="kind"),
]
```

- [ ] **Step 6: Run tests**

Run:

```bash
uv run pytest tests/wf_config/test_config_models.py -q
```

Expected: pass.

## Task 3: Export New Config Types

**Files:**
- Modify: `src/wf_config/__init__.py`

- [ ] **Step 1: Add imports**

Update the import block to include:

```python
    HttpSourceTransportConfig,
    McpSourceConfig,
    SourceConfigOwnership,
    SourceTransportConfig,
    StdioSourceTransportConfig,
```

- [ ] **Step 2: Add `__all__` entries**

Add:

```python
    "HttpSourceTransportConfig",
    "McpSourceConfig",
    "SourceConfigOwnership",
    "SourceTransportConfig",
    "StdioSourceTransportConfig",
```

- [ ] **Step 3: Run tests**

Run:

```bash
uv run pytest tests/wf_config/test_config_models.py -q
```

Expected: pass.

## Task 4: Document Slice Completion

**Files:**
- Modify: `docs/current_roadmap.md`
- Modify: `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`

- [ ] **Step 1: Update roadmap**

In `docs/current_roadmap.md`, under the "Wider `wf_config` source model" bullet, append:

```markdown
    First slice complete: `wf_config.server.sources[]` now accepts
    `kind: "mcp"` entries with stdio/http transport, auth reference, metadata,
    enabled flag, and `locked` / `seed` ownership policy. Runtime composition
    from these entries is the next slice.
```

- [ ] **Step 2: Update spec**

In `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`, under the Slice 1 text, append:

```markdown
   Model slice complete when `wf_config.server.sources[]` accepts `kind: "mcp"`
   entries. The next slice converts those neutral source entries into MCP
   broker runtime connections and server composition.
```

- [ ] **Step 3: Run docs diff**

Run:

```bash
git diff -- docs/current_roadmap.md docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md
```

Expected: only the completion notes above.

## Task 5: Final Verification and Commit

**Files:**
- All touched files from prior tasks.

- [ ] **Step 1: Run focused tests**

Run:

```bash
uv run pytest tests/wf_config/test_config_models.py -q
```

Expected: all tests pass.

- [ ] **Step 2: Run lint/type checks**

Run:

```bash
uv run ruff check src/wf_config tests/wf_config
uv run basedpyright --level error src/wf_config tests/wf_config
```

Expected: both pass with 0 errors.

- [ ] **Step 3: Commit**

Run:

```bash
git add src/wf_config tests/wf_config docs/current_roadmap.md docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md
git commit -m "feat: add mcp source config model"
```

## Self-Review Checklist

- This plan does not import `wf_mcp` into `wf_config`.
- This plan does not change runtime behavior.
- The ownership field is neutral (`ownership`), while docs explain its legacy origin.
- Duplicate source id validation continues to work across all source kinds.
