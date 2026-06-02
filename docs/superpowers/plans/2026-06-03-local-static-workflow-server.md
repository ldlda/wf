# Local Static Workflow Server Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the first long-lived server composition slice: construct and use `WorkflowApi` from required stores and local/static workflow sources without constructing `WfMcpService`.

**Architecture:** This slice introduces `wf_server` as a process-composition package, not a transport package. It proves the server can run persisted deployments through `WorkflowApi` with file stores, `wf.std` capabilities, and static Python `NodeSpec`s. HTTP/JSON-RPC/WebSocket/MCP transports are later adapters over this server boundary.

**Tech Stack:** Python 3.14, pytest, Pydantic v2, `wf_api`, `wf_artifacts`, `wf_core`, `wf_authoring`, `wf_platform`.

---

## File Map

- Create `src/wf_api/local_sources.py`
  - Own protocol-neutral local workflow sources: `wf.std`, `wf.recipes`, spec qualification, and qualified-spec lookup.
- Modify `src/wf_api/__init__.py`
  - Export local source helpers needed by server composition.
- Modify `src/wf_mcp/broker/service/builtins.py`
  - Convert to compatibility re-export shim from `wf_api.local_sources`.
- Create `src/wf_server/__init__.py`
  - Public exports for first-slice server composition.
- Create `src/wf_server/context.py`
  - `WorkflowServer`
  - `WorkflowServerConfig`
  - `StaticWorkflowSpecProvider`
  - `LocalWorkflowRuntimeRunner`
  - `InMemoryWorkflowEventRecorder`
  - `build_local_static_workflow_server`
- Create `tests/wf_api/test_local_sources.py`
  - Verify moved `wf.std` helpers and MCP compatibility shim identity.
- Create `tests/wf_server/test_local_static_server.py`
  - Verify server composition, no `WfMcpService` import, run/inspect/trace over `WorkflowApi`.
- Modify `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`
  - Mark first-slice implementation status after code lands.
- Modify `docs/current_roadmap.md`
  - Add completion note for local/static server composition.

Out of scope:

- No HTTP routes.
- No JSON-RPC/WebSocket transport.
- No live upstream MCP sources.
- No OpenAPI dynamic source provider.
- No auth/tenancy.
- No transactional store.
- No CLI remote targeting.

---

## Task 1: Move Local Workflow Sources Into wf_api

**Files:**

- Create: `src/wf_api/local_sources.py`
- Modify: `src/wf_api/__init__.py`
- Modify: `src/wf_mcp/broker/service/builtins.py`
- Create: `tests/wf_api/test_local_sources.py`

- [ ] **Step 1: Write failing tests for canonical local source helpers**

Create `tests/wf_api/test_local_sources.py`:

```python
from __future__ import annotations

from wf_api.local_sources import (
    BUILTIN_SOURCE_ID,
    RECIPE_SOURCE_ID,
    builtin_sources,
    get_qualified_spec,
    qualify_spec,
)
from wf_authoring import constant


def test_builtin_sources_expose_workflow_stdlib() -> None:
    sources = builtin_sources()

    assert BUILTIN_SOURCE_ID == "wf.std"
    assert RECIPE_SOURCE_ID == "wf.recipes"
    assert "wf.std" in sources
    assert "wf.std.constant" in sources["wf.std"].capabilities.node_specs
    assert "wf.std.replace" in sources["wf.std"].capabilities.reducers


def test_get_qualified_spec_resolves_planner_visible_spec() -> None:
    sources = builtin_sources()

    spec = get_qualified_spec(sources, "wf.std.constant")

    assert spec.name == "wf.std.constant"
    assert spec.outcomes == ("ok",)


def test_qualify_spec_scopes_authoring_node_name() -> None:
    qualified = qualify_spec("custom.local", constant)

    assert qualified.name == "custom.local.constant"
    assert qualified.input_model is constant.input_model
    assert qualified.output_model is constant.output_model


def test_mcp_builtin_module_reexports_canonical_helpers() -> None:
    from wf_mcp.broker.service import builtins as mcp_builtins

    assert mcp_builtins.BUILTIN_CONNECTION_ID == BUILTIN_SOURCE_ID
    assert mcp_builtins.BUILTIN_SOURCE_ID == BUILTIN_SOURCE_ID
    assert mcp_builtins.builtin_sources is builtin_sources
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
uv run pytest tests/wf_api/test_local_sources.py -q
```

Expected:

```text
FAIL with ModuleNotFoundError: No module named 'wf_api.local_sources'
```

- [ ] **Step 3: Implement `wf_api.local_sources`**

Create `src/wf_api/local_sources.py`:

```python
from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from wf_authoring import NodeSpec, coalesce, concat, constant, default_if_none
from wf_authoring import extract_field, filter_items, filter_items_present, first_item
from wf_authoring import first_item_maybe, first_item_or_none, is_empty, last_item
from wf_authoring import last_item_or_none, length, node, pick_key, pick_path
from wf_authoring import project_fields, rename_fields, runtime_error, truthy
from wf_authoring import extract_text_content
from wf_core.runtime.ops.merges import DEFAULT_REDUCER_DEFINITIONS
from wf_platform import (
    CapabilityBuckets,
    CapabilitySource,
    SourcePermissions,
    SourceVisibility,
)

if TYPE_CHECKING:
    from wf_core import ReducerSpec

BUILTIN_SOURCE_ID = "wf.std"
"""Internal source id for workflow standard-library node specs."""

BUILTIN_CONNECTION_ID = BUILTIN_SOURCE_ID
"""Compatibility alias for older MCP broker code."""

MCP_SOURCE_ID = "wf.mcp"
"""Reserved source id for future workflow-safe MCP utility node specs."""

RECIPE_SOURCE_ID = "wf.recipes"
"""Internal source id for first-party composed workflow recipes."""

AUTHORING_STD_SPECS: tuple[NodeSpec[Any, Any], ...] = (
    coalesce,
    default_if_none,
    constant,
    pick_key,
    pick_path,
    project_fields,
    rename_fields,
    truthy,
    runtime_error,
    first_item,
    first_item_or_none,
    first_item_maybe,
    last_item,
    last_item_or_none,
    length,
    is_empty,
    filter_items,
    filter_items_present,
    extract_field,
    concat,
)
"""Existing authoring ops exposed through the workflow stdlib."""

RECIPE_SPECS: tuple[NodeSpec[Any, Any], ...] = (extract_text_content,)
"""Composed first-party recipes exposed as workflow-facing capabilities."""


def qualify_node_name(source_id: str, local_name: str) -> str:
    """Return one source-qualified node name without assuming MCP connections."""
    if not source_id:
        raise ValueError("source_id must not be empty")
    if not local_name:
        raise ValueError("local node name must not be empty")
    return f"{source_id}.{local_name}"


def qualify_spec(source_id: str, spec: NodeSpec[Any, Any]) -> NodeSpec[Any, Any]:
    """Return a copy of a spec with its node name scoped to a source."""
    return NodeSpec(
        name=qualify_node_name(source_id, spec.name),
        input_model=spec.input_model,
        output_model=spec.output_model,
        outcomes=spec.outcomes,
        fn=spec.fn,
        description=spec.description,
        is_async=spec.is_async,
        accepts_context=spec.accepts_context,
        input_schema_contract=spec.input_schema_contract,
        output_schema_contract=spec.output_schema_contract,
    )


def get_qualified_spec(
    sources: Mapping[str, CapabilitySource],
    qualified_name: str,
) -> NodeSpec[Any, Any]:
    """Resolve a namespaced node spec from enabled planner-visible sources."""
    for source in sources.values():
        if not source.enabled or not source.visibility.planner:
            continue
        spec = source.capabilities.node_specs.get(qualified_name)
        if spec is not None:
            return spec
    raise KeyError(f"unknown qualified node {qualified_name!r}")


def _qualified_specs(
    source_id: str,
    specs: tuple[NodeSpec[Any, Any], ...],
) -> dict[str, NodeSpec[Any, Any]]:
    """Return specs with authoring names rewritten under one source id."""
    local_specs = [
        node(spec, name=spec.name.removeprefix("authoring.")) for spec in specs
    ]
    qualified_specs = [qualify_spec(source_id, spec) for spec in local_specs]
    return {spec.name: spec for spec in qualified_specs}


def builtin_specs() -> dict[str, NodeSpec[Any, Any]]:
    """Return primitive built-in NodeSpecs available to raw workflow plans."""
    return _qualified_specs(BUILTIN_SOURCE_ID, AUTHORING_STD_SPECS)


def recipe_specs() -> dict[str, NodeSpec[Any, Any]]:
    """Return composed first-party recipe specs."""
    return _qualified_specs(RECIPE_SOURCE_ID, RECIPE_SPECS)


def builtin_reducers() -> dict[str, ReducerSpec]:
    """Return built-in reducers owned by the workflow standard library."""
    return {
        definition.spec.name: definition.spec
        for definition in DEFAULT_REDUCER_DEFINITIONS.values()
    }


def builtin_reducer_definitions():
    """Return executable built-in reducers for trusted runtime dependency wiring."""
    return dict(DEFAULT_REDUCER_DEFINITIONS)


def builtin_sources() -> dict[str, CapabilitySource]:
    """Return all local workflow-facing capability sources."""
    return {
        BUILTIN_SOURCE_ID: CapabilitySource(
            id=BUILTIN_SOURCE_ID,
            kind="system",
            capabilities=CapabilityBuckets(
                node_specs=builtin_specs(),
                reducers=builtin_reducers(),
                reducer_definitions=builtin_reducer_definitions(),
            ),
            visibility=SourceVisibility(
                planner=True,
                mcp_client=True,
                admin_dashboard=True,
            ),
            permissions=SourcePermissions(safe_for_workflow=True),
            description="Workflow standard-library nodes.",
        ),
        RECIPE_SOURCE_ID: CapabilitySource(
            id=RECIPE_SOURCE_ID,
            kind="system",
            capabilities=CapabilityBuckets(node_specs=recipe_specs()),
            visibility=SourceVisibility(
                planner=True,
                mcp_client=True,
                admin_dashboard=True,
            ),
            permissions=SourcePermissions(safe_for_workflow=True),
            description="First-party workflow recipes composed from standard nodes.",
        ),
    }


__all__ = [
    "AUTHORING_STD_SPECS",
    "BUILTIN_CONNECTION_ID",
    "BUILTIN_SOURCE_ID",
    "MCP_SOURCE_ID",
    "RECIPE_SOURCE_ID",
    "RECIPE_SPECS",
    "builtin_reducer_definitions",
    "builtin_reducers",
    "builtin_sources",
    "builtin_specs",
    "get_qualified_spec",
    "qualify_node_name",
    "qualify_spec",
    "recipe_specs",
]
```

- [ ] **Step 4: Export local source helpers from wf_api**

Modify `src/wf_api/__init__.py`:

```python
from .local_sources import builtin_sources, get_qualified_spec, qualify_spec
```

Add to `__all__`:

```python
"builtin_sources",
"get_qualified_spec",
"qualify_spec",
```

- [ ] **Step 5: Convert MCP builtins to a shim**

Replace `src/wf_mcp/broker/service/builtins.py` with:

```python
"""Compatibility exports for workflow local sources.

Canonical local workflow source helpers live in `wf_api.local_sources` so
non-MCP process hosts can construct `wf.std` without importing broker internals.
"""

from __future__ import annotations

from wf_api.local_sources import (
    AUTHORING_STD_SPECS,
    BUILTIN_CONNECTION_ID,
    BUILTIN_SOURCE_ID,
    MCP_SOURCE_ID,
    RECIPE_SOURCE_ID,
    RECIPE_SPECS,
    builtin_reducer_definitions,
    builtin_reducers,
    builtin_sources,
    builtin_specs,
    get_qualified_spec,
    qualify_node_name,
    qualify_spec,
    recipe_specs,
)

__all__ = [
    "AUTHORING_STD_SPECS",
    "BUILTIN_CONNECTION_ID",
    "BUILTIN_SOURCE_ID",
    "MCP_SOURCE_ID",
    "RECIPE_SOURCE_ID",
    "RECIPE_SPECS",
    "builtin_reducer_definitions",
    "builtin_reducers",
    "builtin_sources",
    "builtin_specs",
    "get_qualified_spec",
    "qualify_node_name",
    "qualify_spec",
    "recipe_specs",
]
```

- [ ] **Step 6: Run local source tests**

Run:

```bash
uv run pytest tests/wf_api/test_local_sources.py tests/wf_mcp/service/test_catalog.py -q
```

Expected:

```text
all selected tests pass
```

- [ ] **Step 7: Commit Task 1**

```bash
git add src/wf_api/local_sources.py src/wf_api/__init__.py src/wf_mcp/broker/service/builtins.py tests/wf_api/test_local_sources.py
git commit -m "refactor: move workflow local sources to wf_api"
```

---

## Task 2: Add wf_server Composition Package

**Files:**

- Create: `src/wf_server/__init__.py`
- Create: `src/wf_server/context.py`
- Create: `tests/wf_server/test_local_static_server.py`

- [ ] **Step 1: Write failing server composition tests**

Create `tests/wf_server/test_local_static_server.py`:

```python
from __future__ import annotations

import ast
import asyncio
from pathlib import Path

from wf_api.models import RawWorkflowPlan
from wf_core import END
from wf_server import build_local_static_workflow_server


def _constant_plan() -> RawWorkflowPlan:
    return RawWorkflowPlan.model_validate(
        {
            "name": "server_constant",
            "input_schema": {"type": "object", "properties": {}},
            "state_schema": {
                "type": "object",
                "properties": {
                    "result": {"type": "string", "reducer": "wf.std.replace"}
                },
            },
            "output_schema": {
                "type": "object",
                "properties": {"result": {"type": "string"}},
                "required": ["result"],
            },
            "outcomes": ["ok"],
            "start": "constant",
            "nodes": [
                {
                    "id": "constant",
                    "type": "node",
                    "node": "wf.std.constant",
                    "input": [
                        {
                            "value": "hello from server",
                            "target": {"root": "local", "parts": ["value"]},
                        }
                    ],
                    "output": [
                        {
                            "source": {"root": "local", "parts": ["value"]},
                            "target": {"root": "state", "parts": ["result"]},
                        }
                    ],
                }
            ],
            "edges": [{"from": "constant", "outcome": "ok", "to": END}],
            "output": [
                {
                    "path": {"root": "state", "parts": ["result"]},
                    "target": {"root": "local", "parts": ["result"]},
                }
            ],
        }
    )


def test_wf_server_context_imports_no_wfmcp_service() -> None:
    path = Path("src/wf_server/context.py")
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            if node.module == "wf_mcp.broker" or node.module.endswith(".core"):
                violations.append(f"{node.lineno}: from {node.module} import ...")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in {"wf_mcp.broker", "wf_mcp.broker.service.core"}:
                    violations.append(f"{node.lineno}: import {alias.name}")

    assert violations == []


def test_local_static_server_runs_deployment_and_persists_run(tmp_path) -> None:
    server = build_local_static_workflow_server(tmp_path / "store")
    api = server.api
    plan = _constant_plan()

    artifact_result = asyncio.run(
        api.create_artifact_from_plan(
            artifact_id="server_constant",
            version=1,
            title="Server Constant",
            plan=plan,
            outcomes=["ok"],
            source_bindings={"wf.std": "wf.std"},
        )
    )
    deployment_result = asyncio.run(
        api.save_deployment(
            {
                "id": "server_constant.default",
                "artifact_id": "server_constant",
                "artifact_version": 1,
                "bindings": [{"logical_source": "wf.std", "concrete_source": "wf.std"}],
            }
        )
    )
    run_result = asyncio.run(
        api.run_deployment(
            deployment_id="server_constant.default",
            workflow_input={},
        )
    )

    assert artifact_result["artifact_id"] == "server_constant"
    assert deployment_result["deployment_id"] == "server_constant.default"
    assert run_result["status"] == "completed"
    assert run_result["output"]["result"] == "hello from server"
    assert isinstance(run_result["run_id"], str)
    assert server.stores.run_store.get_run(run_result["run_id"]).id == run_result["run_id"]


def test_local_static_server_inspects_and_reads_bounded_trace(tmp_path) -> None:
    server = build_local_static_workflow_server(tmp_path / "store")
    api = server.api
    plan = _constant_plan()
    asyncio.run(
        api.create_artifact_from_plan(
            artifact_id="server_trace",
            version=1,
            title="Server Trace",
            plan=plan.model_copy(update={"name": "server_trace"}),
            outcomes=["ok"],
            source_bindings={"wf.std": "wf.std"},
        )
    )
    asyncio.run(
        api.save_deployment(
            {
                "id": "server_trace.default",
                "artifact_id": "server_trace",
                "artifact_version": 1,
                "bindings": [{"logical_source": "wf.std", "concrete_source": "wf.std"}],
            }
        )
    )
    run_result = asyncio.run(
        api.run_deployment(deployment_id="server_trace.default", workflow_input={})
    )

    summary = asyncio.run(api.inspect_run(run_id=run_result["run_id"]))
    trace = asyncio.run(
        api.read_run_trace(
            run_id=run_result["run_id"],
            trace_range=server.trace_range(start=0, limit=1),
        )
    )

    assert "trace" not in summary
    assert summary["trace_count"] >= 1
    assert trace["trace_start"] == 0
    assert trace["trace_limit"] == 1
    assert len(trace["trace"]) == 1
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
uv run pytest tests/wf_server/test_local_static_server.py -q
```

Expected:

```text
FAIL with ModuleNotFoundError: No module named 'wf_server'
```

- [ ] **Step 3: Implement `wf_server.context`**

Create `src/wf_server/context.py`:

```python
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from wf_api import WorkflowApi, durable_workflow_api
from wf_api.local_sources import builtin_sources, get_qualified_spec
from wf_api.models import RawWorkflowPlan, TraceRange
from wf_api.operation_context import (
    WorkflowEventRecorder,
    WorkflowOperationContext,
    WorkflowRuntimeRunner,
    WorkflowSpecProvider,
)
from wf_api.runtime_dependencies import resolve_runtime_dependencies
from wf_api.saved_subgraphs import (
    SavedSubgraphTree,
    prepare_saved_subgraphs,
    resolve_saved_subgraph_tree,
)
from wf_api.stores import WorkflowStores, file_workflow_stores
from wf_artifacts import WorkflowArtifact, WorkflowDeployment
from wf_authoring import NodeSpec
from wf_core import (
    NodeUse,
    RunState,
    Workflow,
    execute_workflow_result_async,
    resume_workflow_result_async,
)
from wf_platform import CapabilitySource


@dataclass(frozen=True, slots=True)
class WorkflowServerConfig:
    """Configuration for the first local/static workflow server slice."""

    store_root: Path


@dataclass(slots=True)
class InMemoryWorkflowEventRecorder(WorkflowEventRecorder):
    """Small process-local event sink for server composition tests."""

    events: list[dict[str, Any]] = field(default_factory=list)

    def record_event(self, event: object) -> None:
        self.events.append({"kind": "adapter_event", "event": event})

    def record_workflow_event(
        self,
        event_type: str,
        *,
        capability_id: str,
        payload: dict[str, Any],
    ) -> None:
        self.events.append(
            {
                "kind": event_type,
                "capability_id": capability_id,
                "payload": payload,
            }
        )


@dataclass(frozen=True, slots=True)
class StaticWorkflowSpecProvider(WorkflowSpecProvider):
    """Source provider for local/static server capabilities."""

    sources: Mapping[str, CapabilitySource]

    @property
    def capability_sources(self) -> Mapping[str, CapabilitySource]:
        return self.sources

    def get_qualified_spec(self, qualified_name: str) -> NodeSpec[Any, Any]:
        return get_qualified_spec(self.sources, qualified_name)


@dataclass(slots=True)
class LocalWorkflowRuntimeRunner(WorkflowRuntimeRunner):
    """Run workflow plans against local/static source catalogs."""

    specs: StaticWorkflowSpecProvider
    artifact_store: Any

    def compile_plan(
        self,
        plan: RawWorkflowPlan,
        node_name_bindings: dict[str, str] | None = None,
    ) -> Workflow:
        node_defs: dict[str, Any] = {}
        bindings = node_name_bindings or {}
        for step in plan.nodes:
            if not isinstance(step, NodeUse):
                continue
            qualified_name = bindings.get(step.node, step.node)
            spec = self.specs.get_qualified_spec(qualified_name)
            node_defs[qualified_name] = spec.to_node_def()

        nodes = []
        for node in plan.nodes:
            node_payload = node.model_dump(by_alias=True)
            if isinstance(node, NodeUse):
                node_payload["node"] = bindings.get(node.node, node.node)
            nodes.append(node_payload)

        return Workflow.model_validate(
            {
                "name": plan.name,
                "input_schema": plan.input_schema,
                "state_schema": plan.state_schema,
                "output_schema": plan.output_schema,
                "output": [
                    binding.model_dump(mode="json") for binding in plan.output
                ],
                "outcomes": plan.outcomes,
                "start": plan.start,
                "node_defs": [node.model_dump() for node in node_defs.values()],
                "nodes": nodes,
                "edges": [edge.model_dump(by_alias=True) for edge in plan.edges],
            }
        )

    def prepare_workflow_runtime(
        self,
        plan: RawWorkflowPlan,
        *,
        deployment: WorkflowDeployment | None,
        artifact: WorkflowArtifact | None,
        saved_subgraph_tree: SavedSubgraphTree | None = None,
    ) -> tuple[Workflow, dict[str, Any], dict[str, Any], dict[str, Any]]:
        plan_node_names = [
            node.node for node in plan.nodes if isinstance(node, NodeUse)
        ]
        runtime_artifact = artifact or WorkflowArtifact(
            id=plan.name,
            version=1,
            title=plan.name,
            input_schema=plan.input_schema,
            output_schema=plan.output_schema,
            outcomes=("completed",),
            plan=plan.model_dump(mode="json", by_alias=True),
        )
        dependencies = resolve_runtime_dependencies(
            artifact=runtime_artifact,
            deployment=deployment,
            sources=self.specs.capability_sources,
            plan_node_names=plan_node_names,
        )
        prepared_subgraphs = {}
        if saved_subgraph_tree is not None:
            prepared_subgraphs = prepare_saved_subgraphs(
                tree=saved_subgraph_tree,
                deployment=deployment,
                sources=self.specs.capability_sources,
                compile_plan=self.compile_plan,
            )
        elif artifact is not None and self.artifact_store is not None:
            tree = resolve_saved_subgraph_tree(
                root_artifact=artifact,
                artifact_store=self.artifact_store,
            )
            prepared_subgraphs = prepare_saved_subgraphs(
                tree=tree,
                deployment=deployment,
                sources=self.specs.capability_sources,
                compile_plan=self.compile_plan,
            )
        workflow = self.compile_plan(plan, dependencies.node_name_bindings)
        return (
            workflow,
            dependencies.node_registry,
            dependencies.reducers,
            prepared_subgraphs,
        )

    async def run_workflow_from_plan(
        self,
        plan: RawWorkflowPlan,
        workflow_input: dict[str, Any],
        deployment: WorkflowDeployment | None = None,
        artifact: WorkflowArtifact | None = None,
        saved_subgraph_tree: SavedSubgraphTree | None = None,
    ) -> RunState:
        workflow, registry, reducers, prepared_subgraphs = (
            self.prepare_workflow_runtime(
                plan,
                deployment=deployment,
                artifact=artifact,
                saved_subgraph_tree=saved_subgraph_tree,
            )
        )
        return await execute_workflow_result_async(
            workflow,
            workflow_input,
            registry,
            reducers=reducers,
            subgraphs=prepared_subgraphs,
        )

    async def resume_workflow_from_plan(
        self,
        plan: RawWorkflowPlan,
        run: RunState,
        *,
        resume_payload: dict[str, Any],
        resume_outcome: str,
        deployment: WorkflowDeployment | None = None,
        artifact: WorkflowArtifact | None = None,
        saved_subgraph_tree: SavedSubgraphTree | None = None,
    ) -> RunState:
        workflow, registry, reducers, prepared_subgraphs = (
            self.prepare_workflow_runtime(
                plan,
                deployment=deployment,
                artifact=artifact,
                saved_subgraph_tree=saved_subgraph_tree,
            )
        )
        return await resume_workflow_result_async(
            workflow,
            run,
            registry,
            resume_payload=resume_payload,
            resume_outcome=resume_outcome,
            reducers=reducers,
            subgraphs=prepared_subgraphs,
        )


@dataclass(frozen=True, slots=True)
class WorkflowServer:
    """First-slice long-lived server composition without transport concerns."""

    config: WorkflowServerConfig
    stores: WorkflowStores
    context: WorkflowOperationContext
    api: WorkflowApi
    events: InMemoryWorkflowEventRecorder

    @staticmethod
    def trace_range(*, start: int, limit: int) -> TraceRange:
        return TraceRange(start=start, limit=limit)


def build_local_static_workflow_server(root: str | Path) -> WorkflowServer:
    """Build a durable local/static workflow server composition."""
    config = WorkflowServerConfig(store_root=Path(root))
    stores = file_workflow_stores(config.store_root)
    events = InMemoryWorkflowEventRecorder()
    specs = StaticWorkflowSpecProvider(builtin_sources())
    runtime = LocalWorkflowRuntimeRunner(
        specs=specs,
        artifact_store=stores.artifact_store,
    )
    context = WorkflowOperationContext(
        artifact_store=stores.artifact_store,
        draft_workspace_store=stores.draft_workspace_store,
        run_store=stores.run_store,
        events=events,
        specs=specs,
        runtime=runtime,
        live_sources=None,
    )
    api = durable_workflow_api(context)
    return WorkflowServer(
        config=config,
        stores=stores,
        context=context,
        api=api,
        events=events,
    )
```

- [ ] **Step 4: Implement `wf_server.__init__`**

Create `src/wf_server/__init__.py`:

```python
from __future__ import annotations

from .context import (
    InMemoryWorkflowEventRecorder,
    LocalWorkflowRuntimeRunner,
    StaticWorkflowSpecProvider,
    WorkflowServer,
    WorkflowServerConfig,
    build_local_static_workflow_server,
)

__all__ = [
    "InMemoryWorkflowEventRecorder",
    "LocalWorkflowRuntimeRunner",
    "StaticWorkflowSpecProvider",
    "WorkflowServer",
    "WorkflowServerConfig",
    "build_local_static_workflow_server",
]
```

- [ ] **Step 5: Run server tests**

Run:

```bash
uv run pytest tests/wf_server/test_local_static_server.py -q
```

Expected:

```text
3 passed
```

- [ ] **Step 6: Run import-direction sanity checks**

Run:

```bash
rg -n "WfMcpService|WorkflowSurfaceHandlers" src/wf_server
```

Expected:

```text
no matches
```

Then run:

```bash
uv run pytest tests/wf_api/test_import_direction.py -q
```

Expected:

```text
1 passed
```

- [ ] **Step 7: Commit Task 2**

```bash
git add src/wf_server tests/wf_server
git commit -m "feat: add local static workflow server"
```

---

## Task 3: Verify Existing MCP Path Still Works

**Files:**

- Verify compatibility only; no intended source changes unless tests fail.

- [ ] **Step 1: Run MCP service/catalog tests**

Run:

```bash
uv run pytest tests/wf_mcp/service/test_catalog.py tests/wf_mcp/service/test_workflow_runtime.py -q
```

Expected:

```text
all selected tests pass
```

- [ ] **Step 2: Run workflow surface run tests**

Run:

```bash
uv run pytest tests/wf_mcp/workflow_surface/test_runs.py tests/wf_mcp/test_saved_subgraphs.py -q
```

Expected:

```text
all selected tests pass
```

- [ ] **Step 3: If imports fail, fix only compatibility shims**

If MCP tests fail because symbols moved from `wf_mcp.broker.service.builtins`,
add missing re-export names to the shim. Do not reintroduce duplicate stdlib
source implementation under `wf_mcp`.

- [ ] **Step 4: Commit compatibility fix if needed**

Only if Step 3 changed files:

```bash
git add src/wf_mcp/broker/service/builtins.py
git commit -m "fix: preserve mcp builtin source compatibility"
```

---

## Task 4: Document First Slice Status

**Files:**

- Modify: `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`
- Modify: `docs/current_roadmap.md`

- [ ] **Step 1: Update long-lived API spec first-slice status**

In `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`, under `## First Slice`, add this paragraph after the proof bullets:

```markdown
Implementation status:

- `wf_server.build_local_static_workflow_server()` constructs a durable
  `WorkflowApi` with required file-backed stores, local `wf.std`/`wf.recipes`
  sources, and a local runtime runner.
- This first slice has no transport adapter. Clients still call the in-process
  `WorkflowApi` in tests; HTTP/JSON-RPC/WebSocket/MCP transport adapters are
  later slices.
```

- [ ] **Step 2: Update current roadmap**

In `docs/current_roadmap.md`, under `Durable API service shape`, add:

```markdown
- First slice implemented: `wf_server` can construct a local/static durable
  `WorkflowApi` without `WfMcpService`. Transport adapters remain future work.
```

- [ ] **Step 3: Run docs sanity check**

Run:

```bash
rg -n "build_local_static_workflow_server|wf_server|transport adapters remain" docs
```

Expected:

```text
matches in long-lived API spec and current roadmap
```

- [ ] **Step 4: Commit Task 4**

```bash
git add docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md docs/current_roadmap.md
git commit -m "docs: record local static workflow server slice"
```

---

## Task 5: Final Verification

**Files:**

- Verify all touched code/tests/docs.

- [ ] **Step 1: Run focused tests**

Run:

```bash
uv run pytest tests/wf_api/test_local_sources.py tests/wf_server/test_local_static_server.py tests/wf_api/test_import_direction.py -q
```

Expected:

```text
all selected tests pass
```

- [ ] **Step 2: Run relevant API/MCP suites**

Run:

```bash
uv run pytest tests/wf_api tests/wf_mcp/service/test_catalog.py tests/wf_mcp/service/test_workflow_runtime.py tests/wf_mcp/workflow_surface/test_runs.py tests/wf_mcp/test_saved_subgraphs.py -q
```

Expected:

```text
all selected tests pass
```

- [ ] **Step 3: Run ruff**

Run:

```bash
uv run ruff check src/wf_api src/wf_server src/wf_mcp/broker/service/builtins.py tests/wf_api tests/wf_server
uv run ruff format --check src/wf_api src/wf_server src/wf_mcp/broker/service/builtins.py tests/wf_api tests/wf_server
```

Expected:

```text
All checks passed
```

- [ ] **Step 4: Run basedpyright**

Run:

```bash
uv run basedpyright --level error
```

Expected:

```text
0 errors, 0 warnings, 0 notes
```

Known caveat: this repo may still exit nonzero with the workspace enumeration
warning even when it reports `0 errors`.

- [ ] **Step 5: Report**

Report:

```text
Implemented first local/static workflow server slice:
- moved local workflow source helpers to wf_api
- added wf_server process composition without WfMcpService
- proved run/inspect/trace through WorkflowApi
- preserved MCP builtin compatibility

Verification:
- focused tests: ...
- relevant suites: ...
- ruff: ...
- basedpyright: ...
```

---

## Later Slice Pointers

These are intentionally not part of this implementation plan:

1. **Transport adapter plan**
   - Add `wf_transport_http` or equivalent.
   - Start with health, run deployment, inspect run, read trace, resume run.
   - Keep routes thin over `WorkflowApi`.

2. **CLI remote target plan**
   - Let `wf_cli` choose local server composition or remote transport client.
   - Keep command names stable.

3. **Source provider plan**
   - Add explicit provider interfaces for static Python specs, OpenAPI sources,
     and upstream MCP sources.
   - Avoid making "source" mean "MCP connection."

4. **Live upstream MCP source plan**
   - Add connection lifecycle, auth, catalog refresh, source liveness, and
     side-effect failure semantics to the long-lived server only after local
     server + transport are proven.

5. **Transactional store plan**
   - Add SQLite/Postgres or similar for multi-process safety and compare-and-swap
     resume.

---

## Self-Review

Spec coverage:

- Client/transport/server/runner/source flow is represented by `wf_server` +
  later transport slices.
- First slice is local/static only, as requested.
- `WfMcpService` is not used by `wf_server`.
- Required stores are enforced through `durable_workflow_api`.
- MCP/OpenAPI/live source support is explicitly deferred.

Placeholder scan:

- No placeholder implementation steps.
- Every task includes exact file paths and test commands.

Type consistency:

- Uses current `WorkflowApi`, `WorkflowOperationContext`, `WorkflowStores`,
  `RawWorkflowPlan`, and `TraceRange` names.
- `wf_server` is the process-composition package; transports are later siblings.
