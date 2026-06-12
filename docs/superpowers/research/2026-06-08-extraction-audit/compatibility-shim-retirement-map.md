# Compatibility Shim Retirement Map

**Date:** 2026-06-08
**Scope:** `wf_mcp` → `wf_sources_mcp` re-export shims, `wf_mcp` → `wf_api` extraction shims
**Goal:** Decide what can stay indefinitely, what can be deprecated, and what has no callers.

---

## Shim Module Inventory

### 1. Pure Re-export Shims (wf_sources_mcp → wf_mcp)

These modules exist **solely** to re-export canonical symbols from `wf_sources_mcp`. No additional logic.

| Shim Module | Canonical Module | Re-exported Symbols | Prod Callers | Test Callers |
|---|---|---|---|---|
| `wf_mcp.auth` | `wf_sources_mcp.auth` | `AuthRecord`, `auth_missing_diagnostic`, `auth_ref_for_connection`, `connection_auth_diagnostic`, `mcp_auth_env`, `mcp_auth_from_neutral`, `mcp_auth_headers`, `neutral_auth_from_mcp` | `wf_mcp.models`, `wf_mcp.broker.discovery`, `wf_mcp.broker.service.source_registry_admin` | `test_auth.py`, `test_compat_imports.py`, `service/test_events.py`, `service/test_upstream_transport.py`, `workflow_surface/conftest.py`, `test_stateful_runtime.py`, `test_support.py`, `service/conftest.py`, `test_workflow_wrappers.py`, `test_broker_server.py`, `service/test_auth_admin.py` |
| `wf_mcp.capabilities` | `wf_sources_mcp.catalog.entries` | `CatalogNodeEntry`, `CatalogPromptEntry`, `CatalogResourceEntry`, `DiscoveredPrompt`, `DiscoveredResource`, `DiscoveredTool` | `wf_mcp.broker.discovery` (DiscoveredTool), `wf_mcp.broker.service.core` (via wf_sources_mcp directly) | `test_compat_imports.py`, `service/conftest.py`, `test_stateful_runtime.py`, `test_support.py`, `test_sdk_adapter.py`, `test_workflow_wrappers.py`, `service/test_event_recorder.py`, `workflow_surface/conftest.py`, `workflow_surface/test_deployments.py`, `test_deployment_api.py` |
| `wf_mcp.catalog.__init__` | `wf_sources_mcp.catalog` (via `.models`) | `CatalogSnapshot`, `dump_catalog_snapshot` | `wf_mcp.broker.discovery` (DiscoveredTool via wf_sources_mcp directly) | `test_compat_imports.py` |
| `wf_mcp.catalog.models` | `wf_sources_mcp.catalog.models` | `CatalogSnapshot`, `dump_catalog_snapshot` | `wf_mcp.models` | `test_compat_imports.py`, `test_workflow_config_bridge.py` |
| `wf_mcp.sdk.__init__` | `wf_sources_mcp.sdk` | `BackendAdapter`, `McpSdkAdapter`, `PromptRuntime`, `ResourceRuntime`, `StatefulMcpRuntime`, `ToolCallResult`, `ToolRuntime` | `wf_mcp.broker.config`, `wf_mcp.broker.server`, `wf_mcp.server.core` (all via wf_sources_mcp directly) | `test_compat_imports.py`, `test_sdk_adapter.py`, `test_deployment_api.py`, `service/conftest.py`, `service/test_events.py`, `test_stateful_runtime.py`, `test_workflow_wrappers.py`, `workflow_surface/conftest.py`, `workflow_surface/test_deployments.py` |
| `wf_mcp.sdk.base` | `wf_sources_mcp.sdk` | `BackendAdapter`, `PromptRuntime`, `ResourceRuntime`, `StatefulMcpRuntime`, `ToolCallResult`, `ToolRuntime` | (none - only test_compat_imports) | `test_compat_imports.py` |
| `wf_mcp.sdk.adapter` | `wf_sources_mcp.sdk.adapter` | `McpSdkAdapter` | `wf_mcp.broker.server`, `wf_mcp.server.core` (via wf_sources_mcp directly) | `test_compat_imports.py`, `test_sdk_adapter.py` |
| `wf_mcp.sdk.converters` | `wf_sources_mcp.sdk.converters` | `prompt_to_discovered`, `resource_to_discovered`, `tool_result_to_call_result`, `tool_to_discovered`, `workflow_output_schema_from_mcp_tool_schema` | (none - only test_compat_imports) | `test_compat_imports.py`, `test_sdk_converters.py` |
| `wf_mcp.storage.__init__` | `wf_sources_mcp.storage` | `AuthStore`, `CatalogStore`, `FileAuthStore`, `FileCatalogStore`, `FileStore`, `Store` | `wf_mcp.broker.config`, `wf_mcp.broker.service.core`, `wf_mcp.broker.service.auth_admin`, `wf_mcp.broker.service.upstream_transport` (all via wf_sources_mcp directly) | `test_compat_imports.py`, `test_admin_auth_rpc.py`, `test_mcp_backed_server_rpc.py`, `test_auth.py`, `test_store.py`, `test_mcp_workflow_server.py`, `service/conftest.py`, `service/test_upstream_transport.py`, `service/test_connection_service.py`, `service/test_catalog.py`, `service/test_events.py`, `service/test_auth_admin.py`, `workflow_surface/conftest.py`, `workflow_surface/test_runs.py`, `workflow_surface/test_wrappers.py` |
| `wf_mcp.storage.store` | `wf_sources_mcp.storage.store` | `AuthStore`, `CatalogStore`, `FileAuthStore`, `FileCatalogStore`, `FileStore`, `Store` | `wf_mcp.broker.service.auth_admin` (AuthStore via wf_sources_mcp directly) | `test_compat_imports.py` |
| `wf_mcp.runtime.factory` | `wf_sources_mcp.runtime.factory` | `PersistentSessionFactory` | `wf_mcp.broker.config` (via wf_sources_mcp directly) | `test_compat_imports.py`, `test_stateful_runtime.py` |
| `wf_mcp.runtime.pool` | `wf_sources_mcp.runtime.pool` | `McpRuntimePool`, `SessionFactory`, `connection_runtime_fingerprint` | `wf_mcp.broker.config` (via wf_sources_mcp directly) | `test_compat_imports.py`, `test_stateful_runtime.py` |
| `wf_mcp.runtime.session` | `wf_sources_mcp.runtime.session` | `PersistentMcpSession`, `RawToolCaller` | (none - only test_compat_imports) | `test_compat_imports.py`, `test_stateful_runtime.py` |
| `wf_mcp.runtime.protocols` | `wf_sources_mcp.sdk` | `ToolExecutor` | (none - only test_compat_imports) | `test_compat_imports.py` |
| `wf_mcp.broker.catalog` | `wf_sources_mcp.catalog` | `CombinedCatalog`, `snapshot_from_specs` | `wf_mcp.broker.__init__` (re-exports) | `test_compat_imports.py` |
| `wf_mcp.broker.service.adapters` | `wf_sources_mcp.adapters` | `AdapterLookupRef`, `LegacyAdapterRef`, `SourceAdapterRef`, `require_adapter` | `wf_mcp.broker.service.upstream_transport` (via wf_sources_mcp directly) | `test_compat_imports.py` |
| `wf_mcp.workflow.wrappers` | `wf_sources_mcp.tool_wrappers` (+ `schema_models`) | `wrap_discovered_tool`, `_model_from_schema` | `wf_mcp.workflow.__init__` (re-exports) | `test_compat_imports.py`, `test_workflow_wrappers.py`, `test_stateful_runtime.py` |
| `wf_mcp.workflow.__init__` | `wf_mcp.workflow.wrappers` | `wrap_discovered_tool` | (none outside wf_mcp) | `test_compat_imports.py`, `test_stateful_runtime.py`, `test_workflow_wrappers.py` |

### 2. Shim + Local Logic (wf_sources_mcp → wf_mcp)

These modules re-export from canonical but also contain **additional local code** that must be preserved or migrated.

| Shim Module | Canonical Module | Local Code | Prod Callers | Test Callers |
|---|---|---|---|---|
| `wf_mcp.connections` | `wf_sources_mcp.ids` | `ConnectionRegistry` class, `qualify_node_name` function | `wf_mcp.broker.service.core`, `wf_mcp.broker.service.connection_service`, `wf_mcp.broker.service.source_registry_admin` | `test_compat_imports.py`, `test_store.py`, `service/test_upstream_transport.py`, `service/test_connection_service.py`, `service/test_source_registry_admin.py` |
| `wf_mcp.source_registry` | `wf_sources_mcp.source_registry` | `registry_entry_to_connection_config`, `workflow_mcp_source_to_connection_config` | `wf_mcp.broker.config`, `wf_mcp.broker.service.connection_service` | `test_compat_imports.py`, `test_mcp_workflow_server.py`, `test_broker_server.py`, `service/test_connection_service.py`, `service/test_source_registry_admin.py`, `test_source_registry.py`, `server/test_docs.py` |
| `wf_mcp.runtime.__init__` | `wf_sources_mcp.runtime` (+ local `ToolExecutor`) | Re-exports `ToolExecutor` from `wf_sources_mcp.sdk` alongside runtime types | `wf_mcp.broker.service.core`, `wf_mcp.broker.service.upstream_transport` (via wf_sources_mcp directly) | `test_compat_imports.py`, `service/test_connection_service.py`, `service/test_events.py`, `service/test_source_registry_admin.py`, `test_workflow_wrappers.py` |
| `wf_mcp.models` | `wf_mcp.auth` + `wf_mcp.broker.models` + `wf_api.models` + `wf_sources_mcp.catalog.models` | Aggregator shim: re-exports `AuthRecord`, `BrokerConfig`, `BrokerStoreRoots`, `ConnectionConfig`, `SourceConfigOwnership`, `RawWorkflowPlan`, `CatalogSnapshot`, `dump_catalog_snapshot` | (none outside wf_mcp) | **Heavy**: 50+ test files import from this module |

### 3. wf_api Extraction Shims (wf_api → wf_mcp.workflow_surface)

Code extracted from `wf_mcp.workflow_surface` to `wf_api`. These shims preserve backward compatibility.

| Shim Module | Canonical Module | Re-exported Symbols | Prod Callers | Test Callers |
|---|---|---|---|---|
| `wf_mcp.workflow_surface.run_lifecycle` | `wf_api.run_lifecycle` | `create_pinned_environment`, `has_blocking_diagnostics`, `load_stored_run`, `mark_resume_blocked`, `persist_stopped_run`, `restore_interrupted_run`, `validate_pinned_resume_environment` | (none outside wf_mcp) | `test_run_lifecycle_extraction.py` |
| `wf_mcp.workflow_surface.saved_subgraphs` | `wf_api.saved_subgraphs` | `SavedSubgraphTree`, `direct_wrapper_interrupt_diagnostic`, `prepare_saved_subgraphs`, `resolve_saved_subgraph_tree`, `saved_subgraph_tree_from_snapshots`, `validate_saved_subgraph_tree` | (none outside wf_mcp) | `test_saved_subgraphs_extraction.py` |
| `wf_mcp.workflow_surface.runtime_dependencies` | `wf_api.runtime_dependencies` | `RuntimeDependencies`, `resolve_runtime_dependencies` | (none outside wf_mcp) | `test_runtime_dependencies_extraction.py` |
| `wf_mcp.workflow_surface.next_actions` | `wf_api.next_actions` | `NextActionPatchExample`, `NextActions`, `NextActionTool` | (none outside wf_mcp) | `test_next_actions.py` (line 164) |

---

## Analysis: Which Shims Are Still Needed for Public Compatibility

### Shims with production callers INSIDE wf_mcp (still needed internally)

These shims are imported by other `wf_mcp` modules. They are "needed" but the callers could switch to canonical.

| Shim | Internal Callers (within wf_mcp) |
|---|---|
| `wf_mcp.auth` | `wf_mcp.models`, `wf_mcp.broker.discovery`, `wf_mcp.broker.service.source_registry_admin` |
| `wf_mcp.connections` | `wf_mcp.broker.service.core`, `wf_mcp.broker.service.connection_service`, `wf_mcp.broker.service.source_registry_admin` |
| `wf_mcp.source_registry` | `wf_mcp.broker.config`, `wf_mcp.broker.service.connection_service` |
| `wf_mcp.models` | `wf_mcp.broker.discovery`, `wf_mcp.broker.service.core`, `wf_mcp.broker.service.source_catalog`, `wf_mcp.broker.service.upstream_transport`, `wf_mcp.broker.service.connection_service`, `wf_mcp.broker.service.source_registry_admin` |
| `wf_mcp.runtime.__init__` | (only test callers) |
| `wf_mcp.workflow.wrappers` | `wf_mcp.workflow.__init__` |

### Shims with NO production callers (outside wf_mcp and test_compat_imports)

These shims exist solely for the test_compat_imports.py regression suite. They can be deprecated.

| Shim | Notes |
|---|---|
| `wf_mcp.sdk.base` | Only caller is `test_compat_imports.py` |
| `wf_mcp.sdk.converters` | Only caller is `test_compat_imports.py` + `test_sdk_converters.py` |
| `wf_mcp.runtime.protocols` | Only caller is `test_compat_imports.py` |
| `wf_mcp.runtime.session` | Only caller is `test_compat_imports.py` |
| `wf_mcp.storage.store` | Only caller is `test_compat_imports.py` |
| `wf_mcp.broker.service.adapters` | Only caller is `test_compat_imports.py` |

---

## Which Shims Are Only Used by Tests

| Shim | Test-Only Callers |
|---|---|
| `wf_mcp.sdk.base` | `test_compat_imports.py` |
| `wf_mcp.sdk.converters` | `test_compat_imports.py`, `test_sdk_converters.py` |
| `wf_mcp.runtime.protocols` | `test_compat_imports.py` |
| `wf_mcp.runtime.session` | `test_compat_imports.py`, `test_stateful_runtime.py` |
| `wf_mcp.storage.store` | `test_compat_imports.py` |
| `wf_mcp.broker.service.adapters` | `test_compat_imports.py` |
| `wf_mcp.workflow_surface.run_lifecycle` | `test_run_lifecycle_extraction.py` |
| `wf_mcp.workflow_surface.saved_subgraphs` | `test_saved_subgraphs_extraction.py` |
| `wf_mcp.workflow_surface.runtime_dependencies` | `test_runtime_dependencies_extraction.py` |
| `wf_mcp.workflow_surface.next_actions` | `test_next_actions.py` (line 164) |

---

## Which Imports in Production Should Be Switched to Canonical Paths

These are `wf_mcp` modules (not shims) that import from `wf_sources_mcp` directly but could instead import through the shim or vice versa. The inconsistency means some internal callers use the shim while the "real" code uses canonical. This is fine architecturally but creates confusion.

### Production imports currently going through shims (should switch to canonical)

| File | Current Import | Should Import From |
|---|---|---|
| `wf_mcp.models` | `from wf_mcp.auth import AuthRecord` | `from wf_sources_mcp.auth import AuthRecord` |
| `wf_mcp.broker.discovery` | `from ..auth import AuthRecord` | `from wf_sources_mcp.auth import AuthRecord` |
| `wf_mcp.broker.service.source_registry_admin` | `from ...auth import AuthRecord, connection_auth_diagnostic` | `from wf_sources_mcp.auth import AuthRecord, connection_auth_diagnostic` |
| `wf_mcp.broker.service.source_catalog` | `from ...connections import ConnectionConfig, qualify_node_name` | Keep as-is (ConnectionConfig is broker-specific) |
| `wf_mcp.broker.service.core` | `from ...connections import ConnectionRegistry` | Keep as-is (ConnectionRegistry is broker-specific) |
| `wf_mcp.broker.service.connection_service` | `from wf_mcp.source_registry import connection_config_to_registry_entry, registry_entry_to_connection_config` | Keep as-is (these are broker-specific conversion helpers) |
| `wf_mcp.broker.service.connection_service` | `from wf_sources_mcp.source_registry import SourceRegistryFile, SourceRegistryStore` | Already canonical |
| `wf_mcp.broker.service.events` | `from wf_sources_mcp.catalog.models import CatalogSnapshot` | Already canonical |
| `wf_mcp.broker.config` | `from wf_sources_mcp.runtime import ...` | Already canonical |
| `wf_mcp.broker.config` | `from wf_sources_mcp.sdk import McpSdkAdapter` | Already canonical |
| `wf_mcp.broker.server` | `from wf_sources_mcp.sdk import McpSdkAdapter` | Already canonical |
| `wf_mcp.broker.server` | `from wf_sources_mcp.source_registry import FileSourceRegistryStore, SourceRegistryStore` | Already canonical |
| `wf_mcp.server.core` | `from wf_sources_mcp.sdk import McpSdkAdapter` | Already canonical |
| `wf_mcp.server.core` | `from wf_sources_mcp.source_registry import FileSourceRegistryStore` | Already canonical |

### Production imports that are already canonical (no change needed)

- `wf_mcp.broker.config` → `wf_sources_mcp.runtime`, `wf_sources_mcp.sdk`, `wf_sources_mcp.source_registry`, `wf_sources_mcp.storage`
- `wf_mcp.broker.server` → `wf_sources_mcp.sdk`, `wf_sources_mcp.source_registry`
- `wf_mcp.broker.service.core` → `wf_sources_mcp.auth`, `wf_sources_mcp.catalog`, `wf_sources_mcp.sdk`, `wf_sources_mcp.source_registry`, `wf_sources_mcp.storage`
- `wf_mcp.broker.service.source_catalog` → `wf_sources_mcp.auth`, `wf_sources_mcp.catalog`, `wf_sources_mcp.connections`, `wf_sources_mcp.schema_models`, `wf_sources_mcp.sdk`, `wf_sources_mcp.storage`
- `wf_mcp.broker.service.upstream_transport` → `wf_sources_mcp.adapters`, `wf_sources_mcp.auth`, `wf_sources_mcp.catalog`, `wf_sources_mcp.connections`, `wf_sources_mcp.discovery`, `wf_sources_mcp.sdk`, `wf_sources_mcp.storage`
- `wf_mcp.broker.service.auth_admin` → `wf_sources_mcp.storage`
- `wf_mcp.broker.service.source_registry_admin` → `wf_sources_mcp.connections`, `wf_sources_mcp.source_registry`
- `wf_mcp.broker.discovery` → `wf_sources_mcp.catalog`, `wf_sources_mcp.connections`, `wf_sources_mcp.discovery`, `wf_sources_mcp.sdk`, `wf_sources_mcp.tool_events`
- `wf_mcp.shared.names` → `wf_sources_mcp.ids` (one constant)
- `wf_mcp.workflow.wrappers` → `wf_sources_mcp.schema_models`, `wf_sources_mcp.tool_wrappers`

---

## Recommended Next Cleanup Slice

### Slice 1: Switch internal callers to canonical imports (low risk)

**Goal:** Remove internal `wf_mcp` code that imports through shims when canonical is available.

1. `wf_mcp.models`: Change `from wf_mcp.auth import AuthRecord` → `from wf_sources_mcp.auth import AuthRecord`
2. `wf_mcp.broker.discovery`: Change `from ..auth import AuthRecord` → `from wf_sources_mcp.auth import AuthRecord`
3. `wf_mcp.broker.service.source_registry_admin`: Change `from ...auth import AuthRecord, connection_auth_diagnostic` → `from wf_sources_mcp.auth import AuthRecord, connection_auth_diagnostic`

These three changes remove the internal dependency chain where `wf_mcp.broker.service.*` imports through `wf_mcp.auth` (shim) instead of directly from `wf_sources_mcp.auth` (canonical).

### Slice 2: Deprecate test-only shims

**Goal:** Mark shims that have NO production callers (only test_compat_imports) as deprecated.

Candidates:

- `wf_mcp.sdk.base`
- `wf_mcp.sdk.converters`
- `wf_mcp.runtime.protocols`
- `wf_mcp.runtime.session`
- `wf_mcp.storage.store`
- `wf_mcp.broker.service.adapters`

These can be marked with a `# DEPRECATED: import from wf_sources_mcp directly` comment and removed once test_compat_imports.py is updated.

### Slice 3: Deprecate wf_api extraction shims

**Goal:** Mark `wf_mcp.workflow_surface.{run_lifecycle, saved_subgraphs, runtime_dependencies, next_actions}` as deprecated.

These are already extraction-complete shims. The test files (`test_*_extraction.py`) verify they point to canonical. They can be removed once no external callers remain.

### Slice 4: Consolidate `wf_mcp.models` (high impact, medium risk)

**Goal:** `wf_mcp.models` is the highest-traffic shim (50+ test files). It aggregates `AuthRecord`, `BrokerConfig`, `ConnectionConfig`, `CatalogSnapshot`, `RawWorkflowPlan`, etc.

- `BrokerConfig`, `ConnectionConfig`, `BrokerStoreRoots`, `SourceConfigOwnership` are broker-specific DTOs — they should stay in `wf_mcp.broker.models` (already canonical).
- `AuthRecord` comes from `wf_sources_mcp.auth` via `wf_mcp.auth` shim.
- `CatalogSnapshot`, `dump_catalog_snapshot` come from `wf_sources_mcp.catalog.models` via `wf_mcp.catalog.models` shim.
- `RawWorkflowPlan` comes from `wf_api.models`.

**Recommended:** Keep `wf_mcp.models` as a convenience aggregator for tests, but update the imports within it to use canonical paths. New production code should import from `wf_mcp.broker.models` or `wf_sources_mcp.*` directly.

---

## Summary Table

| Category | Count | Action |
|---|---|---|
| Pure re-export shims (wf_sources_mcp) | 17 modules | Deprecate test-only ones (6); keep rest for now |
| Shim + local logic (wf_sources_mcp) | 4 modules | Keep (local code is broker-specific) |
| wf_api extraction shims | 4 modules | Deprecate (extraction complete) |
| Non-shim modules (own implementation) | ~30+ modules | No action needed |

**Total shim modules:** 21
**Shims with zero production callers:** 6 (+ 4 wf_api extraction shims)
**Shims with internal-only callers:** 11
**Shims with external (non-wf_mcp) callers:** 0 (all external callers are test files)
