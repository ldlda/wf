# wf_api Extraction Map

## Executive Summary

`WorkflowSurfaceHandlers` (`src/wf_mcp/workflow_surface/handlers.py:104`) is a 1,130-line application-service class that owns all workflow-facing operations: capability discovery, artifact CRUD, draft workspace management, deployment validation, and durable run lifecycle. It currently depends on `WfMcpService` (`src/wf_mcp/broker/service/core.py:79`) via a single `self.service` field, but only uses a narrow slice of that 960-line god object.

The extraction seam is clean: `WorkflowSurfaceHandlers` touches ~6 distinct capabilities of `WfMcpService` (artifact store, draft store, run store, capability sources, workflow execution, event bus). None of these require MCP transport, connection adapters, or proxy machinery. The class is already used protocol-neutrally by `wf_cli` via `CliContext` (`src/wf_cli/context.py:14`).

**Recommended first slice:** Option B — introduce a `WorkflowApi` facade backed by a small `WorkflowApiBackend` ports object, adapt `WfMcpService` into it, then move the facade to `wf_api`. This avoids the large-class move (Option A) and the premature domain split (Option C).

## Public Operation Inventory

### WorkflowSurfaceHandlers — Public Methods

| Method | Line | Category | Input Parameters | Return Shape | Direct Dependencies | Callers/Tests |
|--------|------|----------|-----------------|--------------|--------------------|--------------------|
| `list_artifacts` | 110 | artifacts | `query`, `kind`, `cursor`, `limit` | `{nodes, next_cursor, total}` | `self.service.artifact_store`, `self.service.workflow_artifact_catalog_entry` | `tools.py:49`, `artifacts.py:41`, `test_artifacts.py:11` |
| `list_capabilities` | 147 | capabilities | `query`, `source_id`, `cursor`, `limit` | `{capabilities, next_cursor, total}` | `self.service.capability_sources` | `tools.py:91`, `caps.py:41`, `test_capabilities.py:20` |
| `inspect_capability` | 193 | capabilities | `qualified_name` | capability contract dict | `self.service.capability_sources` | `tools.py:132`, `caps.py:65`, `test_capabilities.py:102` |
| `call_capability` | 213 | capabilities | `qualified_name`, `payload`, `deployment_id` | `{qualified_name, source_id, kind, deployment_id, outcome, output, diagnostics}` | `self.service._get_qualified_spec`, `self.service.capability_sources`, `self.service.run_workflow_from_plan`, `self.service.artifact_store` | `tools.py:144`, `test_capabilities.py:50`, `test_wrappers.py:69` |
| `save_artifact` | 416 | artifacts | `artifact` dict | `{artifact_id, version, saved}` | `self.service.artifact_store`, `self.service._record_event` | `tools.py:162` |
| `create_artifact_from_plan` | 437 | artifacts | `artifact_id`, `version`, `title`, `plan`, `outcomes`, `kind`, `description`, `required_capabilities`, `source_bindings`, `created_from_catalog_version` | `{artifact_id, version, saved}` | `self.service.artifact_store`, `self.service._record_event` | `tools.py:186`, `test_wrappers.py:15` |
| `validate_draft` | 492 | drafts | `draft` dict | `{status, diagnostics, compiled_plan}` | (none — pure wf_artifacts) | `tools.py:170`, `test_drafts.py:23` |
| `compile_draft` | 498 | drafts | `draft` dict | `{compiled_plan, required_capabilities}` | `self.service` (via `_required_capabilities_for_plan`) | `tools.py:178` |
| `create_artifact_from_draft` | 511 | drafts/artifacts | `artifact_id`, `version`, `title`, `draft`, `outcomes`, `kind`, `description`, `required_capabilities`, `source_bindings`, `created_from_catalog_version` | `{artifact_id, version, saved, required_logical_sources, suggested_bindings}` | `self.service.artifact_store`, `self.service._record_event` | `tools.py:229`, `test_drafts.py:61` |
| `patch_draft` | 570 | drafts | `draft`, `patch` | patched draft dict | (none — pure wf_artifacts) | `tools.py:269` |
| `list_draft_workspaces` | 583 | draft workspaces | (none) | `{workspaces}` | `self.service.draft_workspace_store` | `tools.py:280`, `test_drafts.py` |
| `create_draft_workspace` | 593 | draft workspaces | `workspace_id`, `draft`, `title` | workspace summary | `self.service.draft_workspace_store` | `tools.py:293`, `test_drafts.py` |
| `get_draft_workspace` | 607 | draft workspaces | `workspace_id`, `include_draft` | workspace summary | `self.service.draft_workspace_store` | `tools.py:309`, `test_drafts.py` |
| `delete_draft_workspace` | 619 | draft workspaces | `workspace_id` | `{workspace_id, deleted, status}` | `self.service.draft_workspace_store` | `tools.py:325`, `test_drafts.py` |
| `validate_draft_workspace` | 627 | draft workspaces | `workspace_id` | workspace summary | `self.service.draft_workspace_store` | `tools.py:360`, `test_drafts.py` |
| `patch_draft_workspace` | 641 | draft workspaces | `workspace_id`, `revision`, `patch` | workspace summary | `self.service.draft_workspace_store` | `tools.py:341`, `test_drafts.py` |
| `set_draft_name` | 655 | draft workspaces | `workspace_id`, `revision`, `name` | workspace summary | (delegates to `patch_draft_workspace`) | `tools.py:372`, `test_drafts.py` |
| `set_draft_route` | 668 | draft workspaces | `workspace_id`, `revision`, `step_id`, `outcome`, `target` | workspace summary | (delegates to `patch_draft_workspace`) | `tools.py:386`, `test_drafts.py` |
| `set_step_input_map` | 692 | draft workspaces | `workspace_id`, `revision`, `step_id`, `input_map` | workspace summary | (delegates to `patch_draft_workspace`) | `tools.py:405`, `test_drafts.py` |
| `set_step_output_map` | 712 | draft workspaces | `workspace_id`, `revision`, `step_id`, `output_map` | workspace summary | (delegates to `patch_draft_workspace`) | `tools.py:425`, `test_drafts.py` |
| `create_minimal_draft_workspace` | 732 | draft workspaces | `workspace_id`, `name`, `capability_name`, schemas, bindings | workspace summary | `self.service.draft_workspace_store` (via `_draft_store`), `self.service._get_qualified_spec` (via `_outcomes_for_capability`) | `tools.py:446`, `test_drafts.py` |
| `create_draft_workspace_from_capability` | 802 | draft workspaces | `workspace_id`, `capability_name`, optional schemas/bindings | workspace summary + wrapper_hints + next_actions | (delegates to `inspect_capability` + `create_minimal_draft_workspace`) | `tools.py:474`, `test_drafts.py` |
| `create_artifact_from_workspace` | 847 | artifacts | `workspace_id`, `artifact_id`, `version`, `title`, `outcomes`, `kind`, `description`, `required_capabilities`, `source_bindings`, `created_from_catalog_version` | save result or validation error | `self.service.draft_workspace_store` | `tools.py:502`, `test_drafts.py` |
| `create_wrapper_from_workspace` | 884 | artifacts | same as above (without `kind`) | save result | (delegates to `create_artifact_from_workspace` with `kind="wrapper"`) | `tools.py:536`, `test_drafts.py` |
| `inspect_artifact` | 917 | artifacts | `artifact_id`, `version` | full artifact dict | `self.service.artifact_store` | `tools.py:563`, `test_artifacts.py:58` |
| `list_deployments` | 925 | deployments | (none) | `{deployments}` | `self.service.artifact_store` | `tools.py:577`, `test_deployments.py` |
| `inspect_deployment` | 935 | deployments | `deployment_id` | full deployment dict | `self.service.artifact_store` | `tools.py:585`, `test_deployments.py` |
| `save_deployment` | 942 | deployments | `deployment` dict | `{deployment_id, artifact_id, artifact_version, saved}` | `self.service.artifact_store`, `self.service._record_event` | `tools.py:593`, `test_deployments.py` |
| `delete_deployment` | 965 | deployments | `deployment_id` | `{deployment_id, deleted}` | `self.service.artifact_store`, `self.service._record_event` | `tools.py:604`, `test_deployments.py` |
| `validate_deployment` | 979 | deployments | `deployment_id`, `live_check` | `{deployment_id, artifact_id, artifact_version, status, diagnostics, next_actions}` | `self.service.artifact_store`, `self.service.capability_sources`, `self.service.connections`, `self.service.adapters`, `self.service.load_auth` | `tools.py:617`, `test_deployments.py:39` |
| `run_deployment` | 1010 | runs | `deployment_id`, `workflow_input`, `trace_range` | run payload dict | `self.service.artifact_store`, `self.service.run_workflow_from_plan`, `self.service.run_store` | `tools.py:650`, `test_runs.py:40` |
| `resume_run` | 1074 | runs | `run_id`, `resume_payload`, `resume_outcome`, `trace_range` | run payload dict | `self.service.run_store`, `self.service.resume_workflow_from_plan`, `self.service.capability_sources` | `tools.py:681`, `test_runs.py` |
| `inspect_run` | 1154 | runs | `run_id` | run payload dict | `self.service.run_store` | `tools.py:712`, `test_runs.py:78` |
| `read_run_trace` | 1172 | runs | `run_id`, `trace_range` | run payload dict with trace | `self.service.run_store` | `tools.py:722`, `test_runs.py:79` |

### Private Methods

| Method | Line | Notes |
|--------|------|-------|
| `_wrapper_artifact_for_capability_name` | 272 | helper for wrapper resolution |
| `_wrapper_capability_summaries` | 297 | projects wrappers into capability discovery |
| `_wrapper_capability_detail` | 340 | NodeSpec-like contract for wrappers |
| `_call_wrapper_artifact` | 371 | executes wrapper through workflow runner |
| `_draft_store` | 578 | accessor for `self.service.draft_workspace_store` |
| `_outcomes_for_capability` | 911 | delegates to `self.service._get_qualified_spec` |
| `_run_store` | 1196 | accessor for `self.service.run_store` |
| `_deployment_validation` | 1202 | shared validation logic for deployment operations |

### Module-Level Private Helpers

| Function | Line | Used By | Dependencies |
|----------|------|---------|-------------|
| `_available_sources` | 1238 | `_deployment_validation`, `resume_run`, `_live_source_diagnostics` | `service.capability_sources` |
| `_live_source_diagnostics` | 1277 | `validate_deployment` | `service.connections`, `service.adapters`, `service.load_auth` |
| `_required_live_sources` | 1326 | `_live_source_diagnostics` | (pure) |
| `_required_capabilities_for_plan` | 1341 | `compile_draft` | `service` (for `_observed_node_specs`) |
| `_required_capability_payloads` | 1373 | multiple | (pure) |
| `_suggested_self_bindings` | 1382 | `create_artifact_from_draft` | (pure) |
| `_observed_node_specs` | 1389 | `create_artifact_from_plan`, `create_artifact_from_draft`, `_required_capabilities_for_plan` | `service.capability_sources` |
| `_schema_field_names` | 1400 | `list_capabilities` | (pure) |
| `_draft_input_maps` | 1408 | `create_minimal_draft_workspace` | (pure) |
| `_draft_output_map` | 1436 | `create_minimal_draft_workspace` | (pure) |
| `_draft_input_bindings_payload` | 1449 | `create_minimal_draft_workspace`, `set_step_input_map` | (pure) |
| `_draft_output_bindings_payload` | 1463 | `create_minimal_draft_workspace`, `set_step_output_map` | (pure) |
| `_graph_path_payload` | 1471 | multiple | (pure) |
| `_local_path_payload` | 1476 | multiple | (pure) |
| `_state_path_payload` | 1480 | multiple | (pure) |
| `_escape_json_pointer` | 1484 | draft patch helpers | (pure) |
| `_draft_name_from_capability` | 1489 | `create_draft_workspace_from_capability` | (pure) |
| `_source_id_for_capability` | 1494 | `call_capability` | (pure) |
| `_capability_name` | 1505 | `_available_sources` | (pure) |
| `_artifact_capability_id` | 1516 | multiple | (pure) |
| `_raw_plan_from_artifact` | 1526 | `run_deployment`, `resume_run`, `_call_wrapper_artifact` | (pure) |
| `_plan_field` | 1543 | `_raw_plan_from_artifact` | (pure) |
| `_plan_nodes` | 1553 | `_required_capabilities_for_plan` | (pure) |
| `_run_payload` | 1558 | `run_deployment`, `resume_run`, `inspect_run`, `read_run_trace` | (pure) |
| `_interrupt_payload` | 1608 | `_run_payload` | (pure) |
| `_deployment_summary` | 1621 | `list_deployments` | (pure) |

## WfMcpService Dependency Inventory

### Members Accessed from WorkflowSurfaceHandlers

| Member | Type | Accessed Via | Usage Count | Category |
|--------|------|-------------|-------------|----------|
| `artifact_store` | `WorkflowArtifactStore \| None` | `self.service.artifact_store` | ~25 | artifact storage |
| `draft_workspace_store` | `DraftWorkspaceStore \| None` | `self.service.draft_workspace_store` | ~8 | draft storage |
| `run_store` | `RunStore \| None` | `self.service.run_store` | ~5 | run storage |
| `capability_sources` | `dict[str, CapabilitySource]` | `self.service.capability_sources` | ~8 | source/capability inventory |
| `_get_qualified_spec(qualified_name)` | `NodeSpec` | `self.service._get_qualified_spec(...)` | 3 | **private helper** |
| `_record_event(event)` | `None` | `self.service._record_event(...)` | 7 | **private helper** (event bus) |
| `run_workflow_from_plan(...)` | `RunState` | `self.service.run_workflow_from_plan(...)` | 3 | workflow execution |
| `resume_workflow_from_plan(...)` | `RunState` | `self.service.resume_workflow_from_plan(...)` | 1 | workflow execution |
| `workflow_artifact_catalog_entry(artifact)` | `WorkflowArtifactCatalogEntry` | `self.service.workflow_artifact_catalog_entry(...)` | 1 | artifact projection |
| `connections` | `ConnectionRegistry` | `self.service.connections` | 1 | **MCP-specific** (live source check) |
| `adapters` | `dict[str, BackendAdapter]` | `self.service.adapters` | 1 | **MCP-specific** (live source check) |
| `load_auth(connection_id)` | `AuthRecord \| None` | `self.service.load_auth(...)` | 1 | **MCP-specific** (live source check) |

Source/catalog ownership is now split: `WfMcpService` coordinates broker runtime
state, while `SourceCatalogService` owns capability source maps, planner catalog
projection, snapshot hydration, and local docs lookup.

Workflow runtime ownership is now split: `WorkflowRuntimeService` owns plan
compilation, dependency preparation, run, and resume. `WfMcpService` remains the
broker coordinator and compatibility façade.

Event recording ownership is now split: `BrokerEventRecorder` owns EventBus
publication, simple event construction, event history reads, and catalog-change
fanout. `WfMcpService` remains the coordinator and compatibility façade.

Connection registration/config reload reconciliation is now owned by
`wf_mcp.broker.service.connection_service.ConnectionService`. The service owns
the `ConnectionRegistry`; `WfMcpService.connections` is only a compatibility
property.

### WfMcpService Members NOT Used by WorkflowSurfaceHandlers

These members of `WfMcpService` (`src/wf_mcp/broker/service/core.py`) are NOT accessed by `WorkflowSurfaceHandlers`:

- `store` (MCP catalog/auth storage)
- `default_catalog_max_age_seconds`
- `include_builtin_specs`
- `tool_executor`
- `event_bus` (only accessed indirectly via `_record_event`)
- `register_connection`
- `sync_connections_from_config`
- `register_adapter`
- `_tool_executor_for`
- `save_auth`
- `register_specs`
- `get_catalog`
- `get_planner_catalog`
- `list_sources`
- `list_source_summaries`
- `inspect_source`
- `list_available_specs`
- `get_connection_snapshot`
- `connection_statuses`
- `list_resources`
- `list_prompts`
- `get_resource`
- `get_prompt`
- `read_resource`
- `invoke_method`
- `send_notification`
- `render_prompt`
- `_local_documentation_resource`
- `_local_documentation_prompt`
- `refresh_connection_catalog`
- `compile_plan`
- `_prepare_workflow_runtime`
- `register_capability_source`
- `_hydrate_connection_source_from_snapshot`
- `_spec_from_snapshot_entry`
- `_record_catalog_change_events`

## Protocol-Neutral vs MCP-Specific Dependencies

| Dependency | Package Today | MCP-Specific? | Should Live In |
|-----------|---------------|---------------|----------------|
| `WorkflowArtifactStore` | `wf_artifacts` | No | `wf_artifacts` (already there) |
| `DraftWorkspaceStore` | `wf_artifacts` | No | `wf_artifacts` (already there) |
| `RunStore` | `wf_artifacts` | No | `wf_artifacts` (already there) |
| `CapabilitySource` | `wf_platform` | No | `wf_platform` (already there) |
| `EventBus` / `McpEvent` | `wf_mcp.events` | **Renamed** but protocol-neutral | `wf_api.events` or rename to `wf_platform.events` |
| `make_event` | `wf_mcp.events` | Protocol-neutral | Move to `wf_api` or `wf_platform` |
| `matches_query` | `wf_mcp.shared.listing` | Protocol-neutral | `wf_api.shared` or `wf_platform` |
| `paged_list_payload` | `wf_mcp.shared.listing` | Protocol-neutral | `wf_api.shared` or `wf_platform` |
| `page_items` | `wf_platform` | No | `wf_platform` (already there) |
| `RawWorkflowPlan` | `wf_mcp.models` | No | `wf_api.models` or `wf_core` |
| `ConnectionRegistry` | `wf_mcp.connections` | **Yes** (MCP connection model) | stays in `wf_mcp` |
| `ConnectionConfig` | `wf_mcp.models` | **Yes** (MCP connection model) | stays in `wf_mcp` |
| `BackendAdapter` | `wf_mcp.sdk` | **Yes** (MCP adapter protocol) | stays in `wf_mcp` |
| `require_adapter` | `wf_mcp.broker.service.adapters` | **Yes** (MCP adapter lookup) | stays in `wf_mcp` |
| `AuthRecord` | `wf_mcp.models` | **Yes** (MCP auth model) | stays in `wf_mcp` |
| `Store` / `FileStore` | `wf_mcp.storage` | **Yes** (MCP catalog/auth storage) | stays in `wf_mcp` |
| `WorkflowArtifact`, `WorkflowDeployment`, etc. | `wf_artifacts` | No | `wf_artifacts` (already there) |
| `CapabilityRef`, `CapabilitySource` | `wf_platform` | No | `wf_platform` (already there) |
| `NodeSpec`, `build_async_registry` | `wf_authoring` | No | `wf_authoring` (already there) |
| `RuntimeContext` | `wf_core` | No | `wf_core` (already there) |
| `InputBinding`, `OutputBinding` | `wf_core.models.steps` | No | `wf_core` (already there) |
| `GraphSourcePath`, `LocalPath`, `StatePath` | `wf_core.paths` | No | `wf_core` (already there) |
| `TraceRange` | `wf_mcp.workflow_surface.models` | No | `wf_api.models` |
| `NextActions` | `wf_mcp.workflow_surface.next_actions` | No | `wf_api.next_actions` |
| `SavedSubgraphTree` | `wf_mcp.workflow_surface.saved_subgraphs` | No | `wf_api.saved_subgraphs` |
| `resolve_runtime_dependencies` | `wf_mcp.workflow_surface.runtime_dependencies` | No | `wf_api.runtime_dependencies` |
| `wrapper_hints_for_capability` | `wf_mcp.workflow_surface.wrapper_hints` | No | `wf_api.wrapper_hints` |
| `parse_workflow_surface_capability_id` | `wf_mcp.workflow_surface.refs` | No | `wf_api.refs` |
| `run_lifecycle` helpers | `wf_mcp.workflow_surface.run_lifecycle` | No | `wf_api.run_lifecycle` |
| `constants` | `wf_mcp.workflow_surface.constants` | No | `wf_api.constants` |
| `create_pinned_environment` | `wf_mcp.workflow_surface.run_lifecycle` | No | `wf_api.run_lifecycle` |

### Summary Classification

**Protocol-neutral (should move to `wf_api`):**

- All `wf_artifacts` types and functions
- All `wf_platform` types
- All `wf_authoring` types
- All `wf_core` types
- `EventBus` / `McpEvent` / `make_event` (rename from "Mcp" to generic)
- `matches_query`, `paged_list_payload` (listing utilities)
- `RawWorkflowPlan`
- `TraceRange`, `NextActions`, `SavedSubgraphTree`, `resolve_runtime_dependencies`, `wrapper_hints`, `refs`, `run_lifecycle`, `constants`

**MCP-specific (stays in `wf_mcp`):**

- `ConnectionRegistry`, `ConnectionConfig`
- `BackendAdapter`, `require_adapter`
- `AuthRecord`
- `Store`, `FileStore` (MCP catalog/auth persistence)
- `BrokerConfig`, `build_service_from_config`
- All proxy/MCP transport/session code
- `FastMCP` tool registration (`register_workflow_tools`)

## Extraction Options

### Option A: Move Class First

Move `WorkflowSurfaceHandlers` to `wf_api.service.WorkflowApi`, keep same constructor accepting `WfMcpService`.

**Pros:**

- Minimal code changes — just move the file, update imports
- Tests keep passing with import-only changes
- No new abstractions

**Cons:**

- `wf_api` would still depend on `WfMcpService` (a `wf_mcp` type)
- Circular dependency risk: `wf_api` → `wf_mcp` → `wf_api` (if `wf_mcp` tools import from `wf_api`)
- Doesn't actually decouple from MCP — just relocates the code
- Makes future FastAPI adapter harder because the service dependency is still monolithic

### Option B: Introduce API Facade with Ports (Recommended)

Create `WorkflowApi` that depends on a smaller `WorkflowApiBackend`/ports object instead of all `WfMcpService`, then adapt `WfMcpService` into that backend.

**Pros:**

- Clean dependency direction: `wf_api` → ports/interfaces, `wf_mcp` → adapts `WfMcpService` into ports
- `wf_cli` can also adapt its own backend (or reuse the `wf_mcp` adapter)
- FastAPI later becomes just another adapter over the same ports
- Testable in isolation — mock the ports
- Incremental: can introduce ports one domain at a time

**Cons:**

- More upfront work — need to define the port interface
- Risk of over-abstracting if ports are too fine-grained
- Need to decide what `WorkflowApiBackend` actually exposes

### Option C: Split Handlers by Domain First

Split capabilities/drafts/artifacts/deployments/runs into separate classes before moving packages.

**Pros:**

- Each domain class is smaller and easier to reason about
- Could enable partial extraction (move artifacts first, then drafts, etc.)
- Better separation of concerns regardless of extraction

**Cons:**

- Large refactor with many test changes
- Still coupled to `WfMcpService` until ports are introduced
- May create artificial boundaries — some operations span domains (e.g., `create_artifact_from_workspace` touches both drafts and artifacts)
- Doesn't solve the packaging problem by itself

## Recommended First Slice

**Option B: Introduce API facade with ports, starting with a minimal port surface.**

### Why

1. The dependency direction is the core problem. `WorkflowSurfaceHandlers` currently reaches into `WfMcpService` for ~6 distinct capabilities. Extracting without ports just moves the coupling.

2. The port surface is small. Looking at the actual accesses, the port interface needs:
   - `artifact_store: WorkflowArtifactStore | None`
   - `draft_workspace_store: DraftWorkspaceStore | None`
   - `run_store: RunStore | None`
   - `capability_sources: dict[str, CapabilitySource]`
   - `get_qualified_spec(qualified_name: str) -> NodeSpec`
   - `record_event(event: McpEvent) -> None`
   - `run_workflow_from_plan(plan, input, ...) -> RunState`
   - `resume_workflow_from_plan(plan, run, ...) -> RunState`
   - `workflow_artifact_catalog_entry(artifact) -> WorkflowArtifactCatalogEntry`

3. The live-source-check (`_live_source_diagnostics`) is the only MCP-specific operation. It can stay in `wf_mcp` as an extension or be gated behind a protocol-neutral `liveness_check` callback.

### First Slice Steps

1. Define `WorkflowApiBackend` protocol in `wf_api/backend.py` with the ~9 members above.
2. Create `WorkflowApi` in `wf_api/service.py` that takes `WorkflowApiBackend` instead of `WfMcpService`.
3. Move `WorkflowSurfaceHandlers` logic into `WorkflowApi` (rename or keep as alias).
4. Create `WfMcpServiceBackendAdapter` in `wf_mcp` that adapts `WfMcpService` → `WorkflowApiBackend`.
5. Update `wf_mcp.workflow_surface.tools` to create `WorkflowApi(WfMcpServiceBackendAdapter(service))`.
6. Update `wf_cli.context` to create `WorkflowApi(WfMcpServiceBackendAdapter(service))`.
7. Move protocol-neutral helpers (`matches_query`, `paged_list_payload`, `make_event`, etc.) to `wf_api` or `wf_platform`.
8. Keep `register_workflow_tools` in `wf_mcp` (it's the MCP tool registration layer).

## Proposed Package Shape

### First Slice (extraction)

```
src/wf_api/
    __init__.py              # public API: WorkflowApi, WorkflowApiBackend
    backend.py               # WorkflowApiBackend protocol
    service.py               # WorkflowApi (renamed WorkflowSurfaceHandlers)
    models.py                # TraceRange, NextActions, RunPayload, etc.
    refs.py                  # parse_workflow_surface_capability_id
    constants.py             # DEFAULT_CALL_STEP_ID, outcomes, etc.
    next_actions.py          # NextActions model
    saved_subgraphs.py       # SavedSubgraphTree, resolve/validate
    run_lifecycle.py         # create_pinned_environment, persist_stopped_run, etc.
    runtime_dependencies.py  # resolve_runtime_dependencies
    wrapper_hints.py         # wrapper_hints_for_capability
```

### Later Slices

```
src/wf_api/
    shared/
        listing.py           # matches_query, paged_list_payload (or move to wf_platform)
    events.py                # EventBus, make_event (rename from McpEvent)
```

### What Stays in wf_mcp

```
src/wf_mcp/
    workflow_surface/
        tools.py             # register_workflow_tools (MCP tool registration)
        __init__.py          # re-exports for backward compat
    broker/
        service/
            core.py          # WfMcpService (unchanged)
            adapters.py      # WfMcpServiceBackendAdapter (NEW)
    connections.py            # ConnectionRegistry
    models.py                # ConnectionConfig, AuthRecord, BrokerConfig, CatalogSnapshot
    storage/                 # Store, FileStore
    sdk/                     # BackendAdapter
    events/                  # EventBus, McpEvent (wf_mcp-specific event bus)
    shared/                  # names, errors, pagination (MCP-specific utilities)
    proxy/                   # MCP proxy mounts
    server/                  # MCP server construction
    runtime/                 # ToolExecutor
    admin_surface/           # admin tools
```

### What Stays in wf_cli

```
src/wf_cli/
    context.py               # CliContext now uses WorkflowApi instead of WorkflowSurfaceHandlers
    commands/                 # unchanged — they call context.handlers.X()
```

## Test Coverage

### Tests That Protect the Extraction

| Test File | Lines | Coverage Area |
|-----------|-------|---------------|
| `tests/wf_mcp/workflow_surface/test_artifacts.py` | 71 | list_artifacts, inspect_artifact, paging, filtering |
| `tests/wf_mcp/workflow_surface/test_capabilities.py` | 206 | list_capabilities, inspect_capability, call_capability, wrapper capabilities |
| `tests/wf_mcp/workflow_surface/test_drafts.py` | 723 | validate_draft, compile_draft, create_artifact_from_draft, draft workspaces (CRUD, patch, name, route, input/output maps), create_minimal_draft_workspace, create_draft_workspace_from_capability, create_artifact_from_workspace, create_wrapper_from_workspace |
| `tests/wf_mcp/workflow_surface/test_deployments.py` | 282 | validate_deployment, live_check, save_deployment, delete_deployment |
| `tests/wf_mcp/workflow_surface/test_runs.py` | 423 | run_deployment, resume_run, inspect_run, read_run_trace, interrupts, reducers, saved subgraphs |
| `tests/wf_mcp/workflow_surface/test_wrappers.py` | 172 | create_artifact_from_plan (wrapper), call_capability (wrapper), logical refs |
| `tests/wf_mcp/workflow_surface/test_next_actions.py` | 148 | NextActions model behavior |
| `tests/wf_mcp/workflow_surface/conftest.py` | 380 | Shared fixtures: handlers(), artifact(), echo_artifact(), echo_draft(), etc. |
| `tests/wf_cli/test_context.py` | 33 | load_cli_context builds service and handlers |
| `tests/wf_cli/test_app.py` | 88 | CLI help output (smoke tests) |
| `tests/wf_cli/test_run_deploy.py` | 218 | CLI deploy validate, run start, run inspect, run trace |
| `tests/wf_cli/test_discovery_lifecycle.py` | 370 | CLI cap list, artifact list, draft create-from-capability, deploy save, render formats |
| `tests/wf_cli/test_explain.py` | 174 | explain command (diagnostic code lookup) |
| `tests/wf_mcp/test_workflow_surface_refs.py` | — | parse_workflow_surface_capability_id |
| `tests/wf_mcp/test_workflow_wrapper_hints.py` | — | wrapper_hints_for_capability |
| `tests/wf_mcp/test_saved_subgraphs.py` | — | SavedSubgraphTree resolution and validation |

### Missing Tests Needed Before Extraction

- **Integration test for `WorkflowApi` with a mock backend**: Verify that `WorkflowApi` works correctly when given a `WorkflowApiBackend` that is NOT `WfMcpService`. This catches accidental coupling.
- **Test that `wf_cli` works with the new `WorkflowApi` path**: The existing `test_run_deploy.py` uses `patch("wf_cli.commands.runs.load_cli_context", ...)` — need to verify the patching surface doesn't change unexpectedly.
- **Negative test for live-source-check separation**: Verify that `validate_deployment(live_check=True)` still works after the MCP-specific liveness probe is decoupled.

## Things To Keep In wf_mcp For Now

- MCP transport/proxy/runtime/session code (`src/wf_mcp/proxy/`, `src/wf_mcp/server/`, `src/wf_mcp/runtime/`)
- FastMCP registration tools (`src/wf_mcp/workflow_surface/tools.py` — `register_workflow_tools`)
- Connection adapters (`src/wf_mcp/sdk/`, `src/wf_mcp/broker/service/adapters.py`)
- Connection registry (`src/wf_mcp/connections.py`)
- Broker server construction (`src/wf_mcp/broker/server.py`, `src/wf_mcp/broker/config.py`)
- MCP-specific auth (`src/wf_mcp/models.py:AuthRecord`)
- MCP catalog storage (`src/wf_mcp/storage/`)
- Admin surface (`src/wf_mcp/admin_surface/`)
- MCP event bus (`src/wf_mcp/events/`) — may need a protocol-neutral fork
- Discovery/refresh (`src/wf_mcp/broker/discovery.py`)

## Risks And Open Questions

### Circular Import Risks

- **Current**: `wf_mcp.workflow_surface.handlers` imports from `wf_mcp.broker.service` (type-checking only via `TYPE_CHECKING`). No circular import today.
- **After extraction**: `wf_api.service` must NOT import from `wf_mcp`. The `WfMcpServiceBackendAdapter` lives in `wf_mcp` and imports from `wf_api`. Direction: `wf_mcp` → `wf_api`, never reverse.
- **Risk**: The `live_source_diagnostics` helper currently imports `require_adapter` from `wf_mcp.broker.service.adapters`. This must stay in `wf_mcp` or be passed as a callback.

### Private Method Dependencies

- `self.service._get_qualified_spec(qualified_name)` — used 3 times. This is a private method on `WfMcpService`. Must become a port method.
- `self.service._record_event(event)` — used 7 times. This is a private method. Must become a port method (or the event bus itself becomes a port).

### Store Ownership

- `wf_artifacts` owns workflow store protocols and file-backed implementations.
- `wf_api.stores.WorkflowStores` groups the artifact, draft workspace, and run stores as protocol-neutral API dependencies.
- MCP config construction creates file-backed workflow stores from `BrokerConfig.store_root` and injects them into `WfMcpService`.
- `WfMcpService.__post_init__` no longer creates workflow stores from its MCP `Store`; direct service tests must inject stores when they exercise workflow persistence.
- Future HTTP/API entrypoints should construct or receive the same `WorkflowStores` bundle instead of importing `wf_mcp`.

### Naming Confusion

- `McpEvent` / `EventBus` — the name says "Mcp" but the event system is protocol-neutral. Rename to `DomainEvent` / `EventBus` or move to `wf_platform`.
- `WorkflowSurfaceHandlers` — the name suggests MCP surface. Rename to `WorkflowApi`.
- `wf_mcp.workflow_surface` — the package name implies MCP. The extracted package becomes `wf_api`.

### Tests That Monkeypatch `wf_cli.commands.*.load_cli_context`

- `tests/wf_cli/test_run_deploy.py` patches `wf_cli.commands.deployments.load_cli_context`, `wf_cli.commands.runs.load_cli_context`
- `tests/wf_cli/test_discovery_lifecycle.py` patches `wf_cli.commands.caps.load_cli_context`, `tests/wf_cli/test_discovery_lifecycle.py` patches multiple command modules
- These patches inject `_load_cli_context_with_specs` which calls `load_cli_context` then `register_specs`. After extraction, `load_cli_context` will construct `WorkflowApi` instead of `WorkflowSurfaceHandlers`. The patches should still work as long as `CliContext.handlers` remains the same attribute name.

### FastAPI Implications

- The `WorkflowApiBackend` port pattern makes FastAPI trivial: create a `FastApiBackendAdapter` that provides the same stores/sources/execution without MCP.
- The MCP-specific live-source-check can be an opt-in dependency injected into the API.
- `RawWorkflowPlan` should move to `wf_api.models` or `wf_core` so FastAPI can use it without importing `wf_mcp`.

### Other Weirdness

- `WorkflowSurfaceHandlers._wrapper_artifact_for_capability_name` uses `parse_workflow_surface_capability_id` from `wf_mcp.workflow_surface.refs`. This parser understands the `workflow.<id>.v<version>` naming convention. It's protocol-neutral and should move to `wf_api.refs`.
- `_available_sources` (line 1238) is a module-level function that takes `WfMcpService` directly. It should take the port interface instead, or become a method on `WorkflowApi`.
- `_live_source_diagnostics` (line 1277) is the only function that needs MCP adapters/connections. It should be injected as an optional callback or stay as a `wf_mcp` extension.

## Suggested Next Plan

1. **Define the port interface** (`WorkflowApiBackend`) in a new `src/wf_api/backend.py`. Start with the 9 members identified above.
2. **Create `WorkflowApi`** in `src/wf_api/service.py` by copying `WorkflowSurfaceHandlers` and changing `self.service: WfMcpService` to `self.backend: WorkflowApiBackend`.
3. **Create adapter** in `src/wf_mcp/broker/service/adapters.py` (or a new file) that wraps `WfMcpService` into `WorkflowApiBackend`.
4. **Update consumers** (`wf_mcp.workflow_surface.tools`, `wf_cli.context`) to use `WorkflowApi(WfMcpServiceBackendAdapter(service))`.
5. **Move protocol-neutral modules** (`next_actions`, `saved_subgraphs`, `run_lifecycle`, `runtime_dependencies`, `wrapper_hints`, `refs`, `constants`, `models`) to `wf_api`.
6. **Move listing utilities** (`matches_query`, `paged_list_payload`) to `wf_platform` or `wf_api.shared`.
7. **Rename event types** from `McpEvent` to `DomainEvent` (or create a protocol-neutral fork).
8. **Run full test suite** — all existing tests must pass with import-only changes.
9. **Update `CliContext`** to use `WorkflowApi` instead of `WorkflowSurfaceHandlers`.
10. **Add integration test** for `WorkflowApi` with a mock backend (not `WfMcpService`).
11. **Define store ownership** before extracting service construction: remove implicit workflow-store creation from `WfMcpService.__post_init__`, add config/API hooks for injected stores, and update tests to pass stores explicitly.

### Dependency Graph After Extraction

```
wf_api (new)
  ├── depends on: wf_artifacts, wf_platform, wf_authoring, wf_core
  └── defines: WorkflowApiBackend (protocol), WorkflowApi (implementation)

wf_mcp
  ├── depends on: wf_api, wf_artifacts, wf_platform, wf_authoring, wf_core
  ├── adapts: WfMcpService → WorkflowApiBackend
  ├── registers: FastMCP tools via register_workflow_tools (uses WorkflowApi)
  └── owns: connections, adapters, proxy, server, admin, MCP events, MCP storage

wf_cli
  ├── depends on: wf_api, wf_mcp (for service construction)
  ├── uses: WorkflowApi via CliContext
  └── owns: CLI commands, formatting, I/O
```
