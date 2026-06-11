# Static Python Sources Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add static config-driven Python workflow sources so local/project Python `NodeSpec`s can be exposed through `WorkflowServer`, `wf cap list`, `wf cap call`, and workflow runs without MCP.

**Architecture:** `wf_authoring` continues to own `NodeSpec` and `@node`. New package `wf_sources_python` owns module/object loading and projection into `CapabilitySource`. `wf_config` gains `kind: "python"` source entries, and `wf_server.config` composes Python sources into the local/static `WorkflowServer` path.

**Tech Stack:** Python 3.14, Pydantic v2 discriminated unions, `importlib`, `wf_authoring.NodeSpec`, `wf_platform.CapabilitySource`, pytest/pytest-asyncio, ruff, basedpyright.

---

## File Structure

- Create `src/wf_sources_python/__init__.py`
  - Public exports for `PythonSourceConfigLike`, `load_python_source`, `python_capability_source`.
- Create `src/wf_sources_python/loader.py`
  - Import `module`, resolve `registry`, normalize supported registry shapes.
- Create `tests/wf_sources_python/test_loader.py`
  - Unit tests for loading mappings, sequences, callables, qualification, and errors.
- Modify `src/wf_config/models.py`
  - Add `PythonSourceConfig` to `SourceConfig` union.
- Modify `src/wf_config/__init__.py`
  - Export `PythonSourceConfig`.
- Modify `src/wf_server/context.py`
  - Let `build_local_static_workflow_server(...)` accept extra capability sources.
- Modify `src/wf_server/config.py`
  - Detect `kind: "python"` sources and pass loaded sources to local/static server construction.
- Modify tests:
  - `tests/wf_config/test_config_models.py`
  - `tests/wf_server/test_config_composition.py`
  - Add or update an RPC/client smoke test proving `cap call` works.
- Modify docs:
  - `docs/current_roadmap.md`
  - `docs/superpowers/specs/2026-06-11-python-source-provider.md`

---

## Task 1: Config Model

**Files:**

- Modify: `src/wf_config/models.py`
- Modify: `src/wf_config/__init__.py`
- Modify: `tests/wf_config/test_config_models.py`

- [ ] **Step 1: Add failing config test**

Add to `tests/wf_config/test_config_models.py`:

```python
def test_workflow_config_parses_python_source() -> None:
    config = WorkflowConfigFile.model_validate(
        {
            "version": 1,
            "server": {
                "sources": [
                    {
                        "kind": "python",
                        "id": "local.ops",
                        "module": "tests.fixtures.python_source_ops",
                        "registry": "registry",
                    }
                ]
            },
        }
    )

    source = config.server.sources[0]
    assert source.kind == "python"
    assert source.id == "local.ops"
    assert source.module == "tests.fixtures.python_source_ops"
    assert source.registry == "registry"
```

- [ ] **Step 2: Run failing test**

Run:

```bash
uv run pytest tests/wf_config/test_config_models.py::test_workflow_config_parses_python_source -q
```

Expected: fail because `PythonSourceConfig` is not in the source union.

- [ ] **Step 3: Add `PythonSourceConfig`**

In `src/wf_config/models.py`, add after `StdlibSourceConfig`:

```python
class PythonSourceConfig(WorkflowConfigModel):
    """Static config for trusted in-process Python workflow sources."""

    kind: Literal["python"] = "python"
    id: str
    enabled: bool = True
    module: str = Field(min_length=1)
    registry: str = Field(default="registry", min_length=1)

    @field_validator("id")
    @classmethod
    def validate_source_id(cls, value: str) -> str:
        if not re.fullmatch(SOURCE_ID_PATTERN, value):
            raise ValueError(
                "source id must start with alphanumeric or underscore and contain "
                "only [A-Za-z0-9_.-]"
            )
        if "." not in value:
            raise ValueError("source id must look like '<namespace>.<name>'")
        return value
```

Update `SourceConfig`:

```python
SourceConfig = Annotated[
    StdlibSourceConfig | PythonSourceConfig | McpSourceConfig,
    Field(discriminator="kind"),
]
```

Update `src/wf_config/__init__.py` to export `PythonSourceConfig`.

- [ ] **Step 4: Run config tests**

Run:

```bash
uv run pytest tests/wf_config/test_config_models.py -q
```

Expected: pass.

- [ ] **Step 5: Commit config slice**

Run:

```bash
git add src/wf_config/models.py src/wf_config/__init__.py tests/wf_config/test_config_models.py
git commit -m "feat: add python source config model"
```

---

## Task 2: Python Source Loader

**Files:**

- Create: `src/wf_sources_python/__init__.py`
- Create: `src/wf_sources_python/loader.py`
- Create: `tests/wf_sources_python/test_loader.py`
- Create: `tests/fixtures/python_source_ops.py`

- [ ] **Step 1: Add fixture module**

Create `tests/fixtures/python_source_ops.py`:

```python
from __future__ import annotations

from pydantic import BaseModel

from wf_authoring import node


class EchoInput(BaseModel):
    text: str


class EchoOutput(BaseModel):
    echoed: str


@node(name="echo")
def echo(payload: EchoInput) -> EchoOutput:
    return EchoOutput(echoed=payload.text)


@node(name="authoring.upper")
def upper(payload: EchoInput) -> EchoOutput:
    return EchoOutput(echoed=payload.text.upper())


registry = [echo, upper]
```

- [ ] **Step 2: Add failing loader tests**

Create `tests/wf_sources_python/test_loader.py`:

```python
from __future__ import annotations

import pytest

from wf_sources_python import load_python_source


def test_load_python_source_from_sequence_registry() -> None:
    source = load_python_source(
        source_id="local.ops",
        module="tests.fixtures.python_source_ops",
        registry="registry",
    )

    assert source.id == "local.ops"
    assert source.kind == "python"
    assert set(source.capabilities.node_specs) == {
        "local.ops.echo",
        "local.ops.upper",
    }
    assert source.permissions.safe_for_workflow is True


def test_load_python_source_rejects_missing_registry() -> None:
    with pytest.raises(ValueError, match="missing registry object"):
        load_python_source(
            source_id="local.ops",
            module="tests.fixtures.python_source_ops",
            registry="missing",
        )


def test_load_python_source_rejects_non_node_spec() -> None:
    with pytest.raises(TypeError, match="expected NodeSpec"):
        load_python_source(
            source_id="local.ops",
            module="math",
            registry="pi",
        )
```

- [ ] **Step 3: Run failing tests**

Run:

```bash
uv run pytest tests/wf_sources_python/test_loader.py -q
```

Expected: fail because `wf_sources_python` does not exist.

- [ ] **Step 4: Implement loader**

Create `src/wf_sources_python/loader.py`:

```python
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from importlib import import_module
from typing import Any, Protocol

from wf_authoring import NodeSpec, node
from wf_platform import (
    CapabilityBuckets,
    CapabilitySource,
    SourcePermissions,
    SourceVisibility,
)


class PythonSourceConfigLike(Protocol):
    id: str
    module: str
    registry: str
    enabled: bool


def load_python_source(
    *,
    source_id: str,
    module: str,
    registry: str = "registry",
    enabled: bool = True,
) -> CapabilitySource:
    """Load a trusted in-process Python source from a module registry object."""
    module_obj = import_module(module)
    if not hasattr(module_obj, registry):
        raise ValueError(f"missing registry object {registry!r} in module {module!r}")
    raw_registry = getattr(module_obj, registry)
    if callable(raw_registry) and not isinstance(raw_registry, NodeSpec):
        raw_registry = raw_registry()
    specs = _coerce_specs(raw_registry)
    qualified = [_qualify_spec(source_id, spec) for spec in specs]
    names = [spec.name for spec in qualified]
    if len(names) != len(set(names)):
        raise ValueError(f"duplicate NodeSpec names in Python source {source_id!r}")
    return CapabilitySource(
        id=source_id,
        kind="python",
        enabled=enabled,
        capabilities=CapabilityBuckets(
            node_specs={spec.name: spec for spec in qualified},
        ),
        visibility=SourceVisibility(
            planner=True,
            mcp_client=True,
            admin_dashboard=True,
        ),
        permissions=SourcePermissions(safe_for_workflow=True),
        description=f"Python source loaded from {module}:{registry}.",
    )


def python_capability_source(config: PythonSourceConfigLike) -> CapabilitySource:
    return load_python_source(
        source_id=config.id,
        module=config.module,
        registry=config.registry,
        enabled=config.enabled,
    )


def _coerce_specs(raw_registry: object) -> list[NodeSpec[Any, Any]]:
    if isinstance(raw_registry, Mapping):
        values = list(raw_registry.values())
    elif isinstance(raw_registry, Sequence) and not isinstance(raw_registry, str):
        values = list(raw_registry)
    else:
        values = [raw_registry]

    specs: list[NodeSpec[Any, Any]] = []
    for value in values:
        if not isinstance(value, NodeSpec):
            raise TypeError(f"expected NodeSpec in Python source registry, got {type(value).__name__}")
        specs.append(value)
    return specs


def _qualify_spec(source_id: str, spec: NodeSpec[Any, Any]) -> NodeSpec[Any, Any]:
    local_name = spec.name.removeprefix("authoring.")
    if local_name.startswith(f"{source_id}."):
        return spec
    return node(spec, name=f"{source_id}.{local_name}")
```

Create `src/wf_sources_python/__init__.py`:

```python
from __future__ import annotations

from .loader import PythonSourceConfigLike, load_python_source, python_capability_source

__all__ = [
    "PythonSourceConfigLike",
    "load_python_source",
    "python_capability_source",
]
```

- [ ] **Step 5: Run loader tests**

Run:

```bash
uv run pytest tests/wf_sources_python/test_loader.py -q
```

Expected: pass.

- [ ] **Step 6: Commit loader slice**

Run:

```bash
git add src/wf_sources_python tests/wf_sources_python tests/fixtures/python_source_ops.py
git commit -m "feat: add python source loader"
```

---

## Task 3: Compose Python Sources Into Local WorkflowServer

**Files:**

- Modify: `src/wf_server/context.py`
- Modify: `src/wf_server/config.py`
- Modify: `tests/wf_server/test_config_composition.py`

- [ ] **Step 1: Add failing server composition test**

Add to `tests/wf_server/test_config_composition.py`:

```python
from wf_config import PythonSourceConfig


def test_workflow_config_with_python_source_exposes_capability(tmp_path) -> None:
    config = WorkflowConfigFile.model_validate(
        {
            "version": 1,
            "server": {
                "store": {"kind": "filesystem", "root": str(tmp_path / "store")},
                "sources": [
                    {
                        "kind": "python",
                        "id": "local.ops",
                        "module": "tests.fixtures.python_source_ops",
                        "registry": "registry",
                    }
                ],
            },
        }
    )

    server = build_workflow_server_from_workflow_config(config)

    assert "local.ops" in server.specs.capability_sources
    assert (
        "local.ops.echo"
        in server.specs.capability_sources["local.ops"].capabilities.node_specs
    )
```

Use existing imports in that file; only add missing names.

- [ ] **Step 2: Run failing test**

Run:

```bash
uv run pytest tests/wf_server/test_config_composition.py::test_workflow_config_with_python_source_exposes_capability -q
```

Expected: fail because Python sources are ignored or unsupported.

- [ ] **Step 3: Extend `build_local_static_workflow_server`**

In `src/wf_server/context.py`, update `build_local_static_workflow_server` to accept extra sources:

```python
def build_local_static_workflow_server(
    store_root: Path,
    *,
    extra_sources: Mapping[str, CapabilitySource] | None = None,
) -> WorkflowServer:
```

Inside the function, merge sources after built-ins:

```python
    sources = builtin_sources()
    if extra_sources:
        overlap = set(sources) & set(extra_sources)
        if overlap:
            raise ValueError(f"duplicate workflow source ids: {sorted(overlap)}")
        sources.update(extra_sources)
```

Use `sources` where the function currently passes `builtin_sources()` into `StaticWorkflowSpecProvider`.

- [ ] **Step 4: Wire Python sources in `wf_server.config`**

In `src/wf_server/config.py`, import:

```python
from wf_sources_python import python_capability_source
```

Add helper:

```python
def _python_sources(config: WorkflowConfigFile) -> dict[str, CapabilitySource]:
    return {
        source.id: python_capability_source(source)
        for source in config.server.sources
        if getattr(source, "kind", None) == "python"
    }
```

Import `CapabilitySource` from `wf_platform` for the return annotation.

In `build_workflow_server_from_workflow_config`, change:

```python
    return build_local_static_workflow_server(store.root)
```

to:

```python
    return build_local_static_workflow_server(
        store.root,
        extra_sources=_python_sources(config),
    )
```

- [ ] **Step 5: Run server composition tests**

Run:

```bash
uv run pytest tests/wf_server/test_config_composition.py tests/wf_server/test_local_static_server.py -q
```

Expected: pass.

- [ ] **Step 6: Commit composition slice**

Run:

```bash
git add src/wf_server/context.py src/wf_server/config.py tests/wf_server/test_config_composition.py
git commit -m "feat: compose python sources in workflow server"
```

---

## Task 4: Prove CLI/RPC Capability Call And Workflow Run

**Files:**

- Modify: `tests/wf_transport_rpc_http/test_app.py` or `tests/wf_server/test_config_composition.py`

- [ ] **Step 1: Add RPC capability call test**

Add to `tests/wf_transport_rpc_http/test_app.py`:

```python
async def test_rpc_calls_python_source_capability(tmp_path) -> None:
    config = WorkflowConfigFile.model_validate(
        {
            "version": 1,
            "server": {
                "store": {"kind": "filesystem", "root": str(tmp_path / "store")},
                "sources": [
                    {
                        "kind": "python",
                        "id": "local.ops",
                        "module": "tests.fixtures.python_source_ops",
                        "registry": "registry",
                    }
                ],
            },
        }
    )
    server = build_workflow_server_from_workflow_config(config)
    app = create_rpc_app(server)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        listed = await _rpc(
            client,
            "workflow.capabilities.list",
            {"source_id": "local.ops", "limit": 10},
        )
        called = await _rpc(
            client,
            "workflow.capabilities.call",
            {
                "qualified_name": "local.ops.echo",
                "payload": {"text": "hello python"},
            },
        )

    assert listed["result"]["total"] == 2
    assert called["result"]["outcome"] == "ok"
    assert called["result"]["output"] == {"echoed": "hello python"}
```

Add imports if missing:

```python
from wf_config import WorkflowConfigFile
from wf_server.config import build_workflow_server_from_workflow_config
```

- [ ] **Step 2: Run RPC test**

Run:

```bash
uv run pytest tests/wf_transport_rpc_http/test_app.py::test_rpc_calls_python_source_capability -q
```

Expected: pass.

- [ ] **Step 3: Add workflow run test if not covered by capability call**

If the capability call test passes but does not exercise deployment execution, add a direct server/API run test in `tests/wf_server/test_config_composition.py`:

```python
async def test_python_source_capability_runs_in_deployment(tmp_path) -> None:
    config = WorkflowConfigFile.model_validate(
        {
            "version": 1,
            "server": {
                "store": {"kind": "filesystem", "root": str(tmp_path / "store")},
                "sources": [
                    {
                        "kind": "python",
                        "id": "local.ops",
                        "module": "tests.fixtures.python_source_ops",
                    }
                ],
            },
        }
    )
    server = build_workflow_server_from_workflow_config(config)
    await server.api.create_artifact_from_capability(
        artifact_id="python_echo",
        version=1,
        capability_name="local.ops.echo",
        title="Python Echo",
        input_map={"text": "input.text"},
        output_map={"echoed": "state.echoed"},
        source_bindings={"local.ops": "local.ops"},
        outcomes=("ok",),
    )
    await server.api.save_deployment(
        {
            "id": "python_echo.default",
            "artifact_id": "python_echo",
            "artifact_version": 1,
            "bindings": [{"logical_source": "local.ops", "concrete_source": "local.ops"}],
        }
    )

    result = await server.api.run_deployment(
        deployment_id="python_echo.default",
        workflow_input={"text": "run me"},
    )

    assert result["status"] == "completed"
    assert result["output"]["echoed"] == "run me"
```

If `create_artifact_from_capability` has a different signature, follow the existing closest test in `tests/wf_api/test_capability_api.py` or `tests/wf_transport_rpc_http/test_app.py`.

- [ ] **Step 4: Run focused integration tests**

Run:

```bash
uv run pytest tests/wf_sources_python tests/wf_config/test_config_models.py tests/wf_server/test_config_composition.py tests/wf_transport_rpc_http/test_app.py::test_rpc_calls_python_source_capability -q
```

Expected: pass.

- [ ] **Step 5: Commit integration slice**

Run:

```bash
git add tests/wf_transport_rpc_http/test_app.py tests/wf_server/test_config_composition.py
git commit -m "test: prove python source capabilities over rpc"
```

---

## Task 5: Docs And Verification

**Files:**

- Modify: `docs/current_roadmap.md`
- Modify: `docs/superpowers/specs/2026-06-11-python-source-provider.md`
- Move: `docs/superpowers/plans/2026-06-11-static-python-sources.md` to `docs/historical/superpowers/plans/2026-06-11-static-python-sources.md`

- [ ] **Step 1: Update roadmap**

In `docs/current_roadmap.md`, under Priority 3, add:

```markdown
- Completed: static config `kind: "python"` sources can load trusted local
  `NodeSpec` registries and expose them through WorkflowServer. Implementation:
  [`static Python sources`](historical/superpowers/plans/2026-06-11-static-python-sources.md).
```

- [ ] **Step 2: Update spec status**

In `docs/superpowers/specs/2026-06-11-python-source-provider.md`, change:

```markdown
Status: planned first non-MCP source family
```

to:

```markdown
Status: first static config slice implemented
```

Add:

```markdown
## Implementation Status

Implemented:

- `wf_config` accepts `server.sources[]` entries with `kind: "python"`.
- `wf_sources_python` loads trusted in-process `NodeSpec` registries from
  `module:registry`.
- `wf_server.config` composes Python sources into local/static servers.
- Capability listing/calling works over JSON-RPC.

Still deferred:

- mutable source registry/apply support
- hot reload
- reducer exports
- sandboxing/untrusted code
```

- [ ] **Step 3: Move completed plan**

Run:

```bash
git mv docs/superpowers/plans/2026-06-11-static-python-sources.md docs/historical/superpowers/plans/2026-06-11-static-python-sources.md
```

- [ ] **Step 4: Run verification**

Run:

```bash
uv run pytest tests/wf_sources_python tests/wf_config/test_config_models.py tests/wf_server/test_config_composition.py tests/wf_server/test_local_static_server.py tests/wf_transport_rpc_http/test_app.py -q
uv run ruff check src/wf_sources_python src/wf_config src/wf_server tests/wf_sources_python tests/wf_config/test_config_models.py tests/wf_server/test_config_composition.py tests/wf_transport_rpc_http/test_app.py
uv run ruff format --check src/wf_sources_python src/wf_config src/wf_server tests/wf_sources_python tests/wf_config/test_config_models.py tests/wf_server/test_config_composition.py tests/wf_transport_rpc_http/test_app.py
uv run basedpyright --level error src/wf_sources_python src/wf_config src/wf_server tests/wf_sources_python tests/wf_config/test_config_models.py tests/wf_server/test_config_composition.py tests/wf_transport_rpc_http/test_app.py
git diff --check
```

Expected:

- Tests pass.
- Ruff passes.
- Basedpyright reports 0 errors for changed files.
- `git diff --check` reports no whitespace errors; CRLF warnings on Windows are acceptable.

- [ ] **Step 5: Final commit**

Run:

```bash
git add src tests docs
git commit -m "docs: record static python source support"
```

If earlier task commits were skipped, use one final commit instead:

```bash
git add src tests docs
git commit -m "feat: add static python sources"
```

---

## Acceptance Criteria

- `wf_config` parses `kind: "python"` source entries.
- `wf_sources_python` imports a trusted module registry and projects `NodeSpec`s under the configured source id.
- `wf_server.config` includes Python sources in local/static `WorkflowServer` construction.
- Built-in `wf.std` and `wf.recipes` remain unchanged.
- No `wf_mcp` dependency is introduced.
- `workflow.capabilities.list` and `workflow.capabilities.call` work for Python source capabilities over JSON-RPC.
- Docs make clear this is trusted in-process code and not hot-reloaded or registry-mutable yet.

