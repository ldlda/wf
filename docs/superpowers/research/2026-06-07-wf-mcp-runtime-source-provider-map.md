# WF MCP Runtime & Source Provider Map

Date: 2026-06-07

> **Historical note (2026-06-08):** This research snapshot predates the
> `wf_sources_mcp` extraction slices completed on 2026-06-08. Several blockers
> called out below have since moved: source ID helpers live in
> `wf_sources_mcp.ids`, MCP runtime/SDK/client code lives in `wf_sources_mcp`,
> and broker DTO construction helpers live in `wf_mcp.source_registry`.

## Executive Summary

`wf_mcp` is a monolith containing four distinct responsibilities that should become separate packages:

1. **MCP source provider runtime** (transport opening, session pooling, auth) -- belongs in `wf_sources_mcp`
2. **MCP frontend transport** (FastMCP server, proxy mounts, MCP tool registration) -- belongs in a future `wf_transport_mcp`
3. **Broker service layer** (connection catalog, discovery, source catalog, workflow runtime) -- stays in `wf_mcp` or becomes `wf_server`
4. **Compatibility shims** (re-export modules, `WfMcpService` facade) -- remains in `wf_mcp` until callers migrate

The critical blocker is `ConnectionConfig` (defined at `src/wf_mcp/broker/models.py:37`). This dataclass is consumed by `wf_sources_mcp.sdk.protocols`, `wf_sources_mcp.auth`, `wf_sources_mcp.source_registry`, `wf_sources_mcp.storage.store`, the runtime factory, the adapter, the pool, and every broker service. Until `ConnectionConfig` moves to a neutral package or is replaced by a typed protocol, extraction is blocked.

The next safe slice is **Slice 0: Define a `SourceConnection` protocol in `wf_sources_mcp`** so runtime/session code stops depending on the broker DTO. After that, the transport-opening logic in `runtime/factory.py` and `sdk/adapter.py` can merge into `wf_sources_mcp.sdk` without dragging the broker layer along.

---

## Package Responsibility Map

### `wf_sources_mcp` (source provider core)

Owns: MCP source provider identity, auth, catalog entries, storage, and the SDK adapter/executor protocols.

| Module | Responsibility | Status |
|--------|---------------|--------|
| `auth.py` | MCP auth record, env/header extraction, diagnostic helpers | Canonical. Has TYPE_CHECKING dep on `wf_mcp.broker.models.ConnectionConfig`. |
| `sdk/protocols.py` | `BackendAdapter`, `ToolExecutor`, `ToolCallResult` | Canonical. Has TYPE_CHECKING dep on `ConnectionConfig`. |
| `sdk/converters.py` | MCP tool/resource/prompt conversion | Canonical. No `wf_mcp` deps. |
| `catalog/models.py` | `CatalogSnapshot`, `dump_catalog_snapshot` | Canonical. No `wf_mcp` deps. |
| `catalog/entries.py` | `CatalogNodeEntry`, `CatalogResourceEntry`, `CatalogPromptEntry`, `DiscoveredTool`, etc. | Canonical. No `wf_mcp` deps. |
| `source_registry.py` | `McpSourceRegistryEntry`, `SourceRegistryFile`, conversion helpers | Canonical. Imports `parse_connection_id` from `wf_mcp.connections` and `RESERVED_CONNECTION_IDS` from `wf_mcp.shared.names`. TYPE_CHECKING dep on `ConnectionConfig`. |
| `storage/store.py` | `AuthStore`, `CatalogStore`, `FileAuthStore`, `FileCatalogStore` | Canonical. `FileCatalogStore._connection_path` imports `parse_connection_id` from `wf_mcp.connections` at runtime. |

### Future `wf_transport_mcp` (MCP frontend transport)

Owns: FastMCP server creation, proxy mounting, MCP tool/resource/prompt registration, admin tool registration, workflow surface tool registration.

| Module | Responsibility | Status |
|--------|---------------|--------|
| `proxy/runtime.py` | `ProxyRuntime` -- mount upstream MCP connections into FastMCP | `wf_mcp` internal. Depends on `BrokerConfig`, `ConnectionConfig`, `EventBus`, `BrokerConfigManager`. |
| `proxy/mounts.py` | `ProxyMountRegistry`, `create_proxy_mount`, `ResilientFastMCPProxy` | `wf_mcp` internal. Depends on `BrokerConfig`, `ConnectionConfig`, FastMCP. |
| `proxy/tools.py` | Proxy tool listing/filtering | `wf_mcp` internal. |
| `proxy/safe_names.py` | `SafeToolNames` transform | `wf_mcp` internal. FastMCP transform. |
| `proxy/admin.py` | Proxy admin tools | `wf_mcp` internal. |
| `server/core.py` | `create_server`, `run_server`, `create_server_client` | `wf_mcp` entrypoint. Wires broker service + proxy + workflow surface + admin surface. |
| `admin_surface/tools.py` | `register_service_admin_tools` | `wf_mcp` internal. |
| `admin_surface/handlers/*.py` | Admin tool handlers | `wf_mcp` internal. |
| `workflow_surface/tools.py` | `register_workflow_tools` | `wf_mcp` internal. |
| `workflow_surface/*.py` | Workflow tool models, handlers, lifecycle | `wf_mcp` internal. |
| `shared/names.py` | `ProxyNamespace`, `ADMIN_NAMESPACE`, `RESERVED_CONNECTION_IDS`, namespace helpers | `wf_mcp` internal. FastMCP-specific. |
| `cli.py` | CLI entrypoint | `wf_mcp` entrypoint. |

### `wf_server` / `wf_api` (server core)

Owns: Workflow API, operation context, artifact management, deployment, run lifecycle.

Already extracted. These packages consume `wf_sources_mcp` types and `wf_mcp.broker.service.WfMcpService` through `wf_api.WorkflowApi` and `wf_api.WorkflowRuntimeAdapter`.

### Legacy `wf_mcp` (broker + compatibility shims)

Owns: Connection registry, broker config, broker service coordination, events, and all compatibility re-export shims.

| Module | Responsibility | Status |
|--------|---------------|--------|
| `broker/models.py` | `ConnectionConfig`, `BrokerConfig`, `BrokerStoreRoots`, `SourceConfigOwnership` | **The core blocker.** All other packages depend on this. |
| `broker/service/core.py` | `WfMcpService` -- compatibility coordinator | Facade. Delegates to focused services. |
| `broker/service/connection_service.py` | `ConnectionService` | Focused service. Depends on `ConnectionConfig`, `SourceCatalogService`. |
| `broker/service/source_catalog.py` | `SourceCatalogService` | Focused service. Depends on `ConnectionConfig`, `McpEvent`, `NodeSpec`. |
| `broker/service/upstream_transport.py` | `UpstreamTransportService` | Focused service. Depends on `ConnectionConfig`, `BackendAdapter`, `ToolExecutor`. |
| `broker/service/workflow_runtime.py` | `WorkflowRuntimeService` | Focused service. Depends on `SourceCatalogService`. |
| `broker/service/content_access.py` | `ContentAccessService` | Focused service. |
| `broker/service/events.py` | `BrokerEventRecorder` | Focused service. Depends on `McpEvent`. |
| `broker/service/adapters.py` | `require_adapter` | Helper. |
| `broker/discovery.py` | `discover_connection_capabilities`, `specs_from_discovered_tools` | Broker logic. |
| `broker/catalog.py` | `snapshot_from_specs`, `CombinedCatalog` | Broker catalog projection. |
| `broker/config.py` | `build_service_from_config`, `load_broker_config`, `broker_config_from_workflow_config` | Config construction. |
| `connections.py` | `ConnectionRegistry`, `parse_connection_id`, `qualify_node_name` | Broker connection registry. |
| `auth.py` | Re-export shim from `wf_sources_mcp.auth` | Compatibility. |
| `models.py` | Re-export shim aggregating broker models | Compatibility. |
| `source_registry.py` | Re-export shim from `wf_sources_mcp.source_registry` | Compatibility. |
| `capabilities.py` | Re-export shim from `wf_sources_mcp.catalog.entries` | Compatibility. |
| `runtime/protocols.py` | Re-export shim from `wf_sources_mcp.sdk` | Compatibility. |
| `events/bus.py` | `EventBus`, `InMemoryEventSink` | Broker-local event fanout. |
| `events/models.py` | `McpEvent`, `make_event` | Broker event model. |

---

## Current Dependency Blockers

### Blocker 1: `ConnectionConfig` origin

**File:** `src/wf_mcp/broker/models.py:37-44`

```python
@dataclass(slots=True)
class ConnectionConfig:
    id: str
    server: str
    account: str
    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)
    source_config_ownership: SourceConfigOwnership = "locked"
```

This DTO is imported by:

| Consumer | Import path | Import type |
|----------|------------|-------------|
| `wf_sources_mcp.auth` | `wf_mcp.broker.models.ConnectionConfig` | `TYPE_CHECKING` |
| `wf_sources_mcp.sdk.protocols` | `wf_mcp.broker.models.ConnectionConfig` | `TYPE_CHECKING` |
| `wf_sources_mcp.source_registry` | `wf_mcp.models.ConnectionConfig` | `TYPE_CHECKING` |
| `wf_sources_mcp.storage.store` | (none directly, but `FileCatalogStore._connection_path` calls `parse_connection_id` from `wf_mcp.connections`) | runtime |
| `wf_mcp.runtime.factory` | `wf_mcp.models.ConnectionConfig` | runtime |
| `wf_mcp.sdk.adapter` | `wf_mcp.models.ConnectionConfig` | runtime |
| `wf_mcp.runtime.pool` | `wf_mcp.models.ConnectionConfig` | runtime |
| `wf_mcp.runtime.session` | `wf_mcp.models.ConnectionConfig` | runtime |
| `wf_mcp.workflow.wrappers` | `wf_mcp.models.ConnectionConfig` | runtime |
| `wf_mcp.broker.discovery` | `wf_mcp.models.ConnectionConfig` | runtime |
| `wf_mcp.broker.service.*` | `wf_mcp.models.ConnectionConfig` | runtime |
| `wf_mcp.proxy.mounts` | `wf_mcp.models.ConnectionConfig` | runtime |
| `wf_mcp.proxy.runtime` | (indirectly via `BrokerConfig`) | runtime |

**Impact:** Until `ConnectionConfig` moves to a neutral package (or `wf_sources_mcp` defines its own protocol), the runtime code in `wf_sources_mcp` cannot be independent of `wf_mcp`.

### Blocker 2: `parse_connection_id` origin

**File:** `src/wf_mcp/connections.py:11-25`

Used by:

- `wf_sources_mcp.source_registry` (runtime import, line 32)
- `wf_sources_mcp.storage.store` (runtime import inside `_connection_path`, line 132)
- `wf_mcp.connections` (canonical home)

**Impact:** `wf_sources_mcp` has a runtime import dependency on `wf_mcp` for connection ID validation. This function should move to a neutral package or `wf_sources_mcp`.

### Blocker 3: `RESERVED_CONNECTION_IDS` origin

**File:** `src/wf_mcp/shared/names.py:25`

```python
RESERVED_CONNECTION_IDS = frozenset({ADMIN_NAMESPACE, "wf.mcp"})
```

Used by:

- `wf_sources_mcp.source_registry` (runtime import, line 33)
- `wf_mcp.broker.service.connection_service` (runtime import, line 14)

**Impact:** `wf_sources_mcp` imports from `wf_mcp.shared.names` which transitively imports FastMCP transforms (line 8-15 of `shared/names.py`). This creates an unwanted dependency chain.

### Blocker 4: `McpSdkAdapter` transport-opening duplication

**Files:**

- `src/wf_mcp/runtime/factory.py:43-90` (`_create_with_stack`)
- `src/wf_mcp/sdk/adapter.py:34-75` (`_session`)

Both methods contain nearly identical logic for:

- Reading `connection.metadata["transport"]` to select stdio vs streamable HTTP
- Creating `StdioServerParameters` and calling `stdio_client`
- Creating `httpx.AsyncClient` and calling `streamable_http_client`
- Creating `ClientSession` and calling `session.initialize()`
- Applying auth via `mcp_auth_env` / `mcp_auth_headers`

The difference: factory.py owns the session long-term (persistent actor pattern), while adapter.py opens/closes per call (one-shot pattern).

**Impact:** This duplication means both files must be updated together when transport handling changes. They should share a transport-opening helper.

### Blocker 5: `BrokerConfig` in proxy/runtime

**File:** `src/wf_mcp/proxy/runtime.py:73-85`

`ProxyRuntime.__init__` takes `BrokerConfig` directly and reads `config.connections`. The proxy layer is a frontend transport concern that should not depend on the broker config DTO.

**Impact:** Proxy runtime cannot move to `wf_transport_mcp` until it consumes a transport-neutral config shape.

### Blocker 6: `McpEvent` coupling

**File:** `src/wf_mcp/events/models.py`

`McpEvent` is used by:

- `UpstreamTransportService` (event_sink)
- `SourceCatalogService` (emit_event)
- `BrokerEventRecorder` (event_bus)
- `broker/catalog.py` (indirectly through event callbacks)
- `workflow/wrappers.py` (emit_event callback)

**Impact:** `McpEvent` is broker-specific. If source provider code needs to emit events, it should use a protocol or a neutral event type. Currently `wf_sources_mcp` does not import `McpEvent` directly, which is good.

---

## Detailed Findings by Worker Scope

### Worker 1: Runtime/Session Findings

#### Where is MCP session opening duplicated?

The transport-opening logic appears in two places:

1. **`runtime/factory.py:43-90`** (`PersistentSessionFactory._create_with_stack`):
   - Opens stdio or streamable HTTP transport
   - Creates `ClientSession`
   - Calls `session.initialize()`
   - Returns session owned by `AsyncExitStack`
   - Used for persistent long-lived sessions (actor pattern)

2. **`sdk/adapter.py:34-75`** (`McpSdkAdapter._session`):
   - Opens stdio or streamable HTTP transport
   - Creates `ClientSession`
   - Calls `session.initialize()`
   - Yields session in async context manager
   - Used for one-shot per-call sessions (discovery, admin operations)

Both import from the same MCP SDK modules:

- `mcp.client.stdio.StdioServerParameters`, `stdio_client`
- `mcp.client.streamable_http.streamable_http_client`
- `mcp.client.session.ClientSession`
- `wf_sources_mcp.auth.mcp_auth_env`, `mcp_auth_headers`

#### Which client operations are supported by one-shot adapter but not persistent runtime?

The `BackendAdapter` protocol (`wf_sources_mcp.sdk.protocols:26-88`) defines:

- `list_tools`, `list_resources`, `list_prompts`
- `get_connection_metadata`
- `read_resource`, `get_prompt`
- `invoke_method`, `send_notification`
- `call_tool`

The `PersistentMcpSession` (`runtime/session.py:19-49`) only exposes:

- `call_tool`
- `close`

The `McpRuntimePool` (`runtime/pool.py:43-96`) only exposes:

- `get_session` (returns `PersistentMcpSession`)
- `call_tool`
- `close_connection`, `close_all`

**Missing from persistent runtime:** `list_tools`, `list_resources`, `list_prompts`, `get_connection_metadata`, `read_resource`, `get_prompt`, `invoke_method`, `send_notification`.

This is intentional -- persistent sessions exist for workflow execution (tool calls only). Discovery and admin operations use one-shot adapters. However, this means the persistent runtime cannot replace the adapter for all operations.

#### What common `McpClientSession` / `McpClientSessionFactory` interface should exist?

Both factory.py and adapter.py share:

1. Transport selection logic (stdio vs streamable HTTP)
2. Auth application (env vars for stdio, headers for HTTP)
3. Session creation and initialization

A shared `open_mcp_session` helper should:

- Accept a connection descriptor (transport type, command/url, env/headers) and optional auth
- Return an initialized `ClientSession` (or yield it)
- Be used by both `PersistentSessionFactory._create_with_stack` and `McpSdkAdapter._session`

The connection descriptor should NOT be `ConnectionConfig` directly -- it should be a transport-specific DTO that `ConnectionConfig` can convert to.

#### What blocks moving this code to `wf_sources_mcp`?

1. `ConnectionConfig` dependency (Blocker 1)
2. `McpEvent` event callbacks in `PersistentSessionFactory` (the `_SessionOwner._run` method does not emit events, but the pool and factory are used by `broker/config.py` which wires events)
3. The `PersistentMcpSession` dataclass holds `connection: ConnectionConfig` and `auth: AuthRecord` -- the `AuthRecord` is already in `wf_sources_mcp`, but `ConnectionConfig` is not

**Recommendation:** Define a `SourceConnection` protocol in `wf_sources_mcp.sdk.protocols` that captures the transport fields `ConnectionConfig` exposes to runtime code. The factory/pool/session code should consume this protocol, not the concrete DTO.

### Worker 2: Broker/Upstream Findings

#### What is truly MCP-source-provider logic vs broker/catalog projection logic?

**MCP-source-provider logic** (belongs in `wf_sources_mcp`):

- Transport opening (stdio, streamable HTTP) -- currently in `factory.py` and `adapter.py`
- Auth application (env vars, headers) -- already in `wf_sources_mcp.auth`
- `BackendAdapter` protocol and `ToolExecutor` protocol -- already in `wf_sources_mcp.sdk`
- `ToolCallResult` dataclass -- already in `wf_sources_mcp.sdk`
- `DiscoveredTool`, `DiscoveredResource`, `DiscoveredPrompt` -- already in `wf_sources_mcp.catalog`
- `CatalogSnapshot` and catalog entries -- already in `wf_sources_mcp.catalog`
- Auth/catalog storage -- already in `wf_sources_mcp.storage`
- Source registry models -- already in `wf_sources_mcp.source_registry`

**Broker/catalog projection logic** (stays in `wf_mcp`):

- `UpstreamTransportService` -- wraps `BackendAdapter` with auth loading, event recording, catalog refresh orchestration
- `SourceCatalogService` -- manages `CapabilitySource` registrations, catalog hydration, source inventory
- `discover_connection_capabilities` -- orchestrates adapter calls and wraps results
- `specs_from_discovered_tools` -- wraps discovered tools into `NodeSpec` with event emission
- `snapshot_from_specs` -- builds `CatalogSnapshot` from `NodeSpec` dict
- `CombinedCatalog` -- aggregates snapshots across connections
- `ConnectionService` -- connection registry lifecycle
- `BrokerEventRecorder` -- broker event fanout
- `ConnectionConfig`, `BrokerConfig`, `BrokerStoreRoots` -- broker config DTOs

#### What should move to `wf_sources_mcp`?

1. **Transport-opening helper** (`open_mcp_session` or similar) -- extract from `factory.py` and `adapter.py`
2. **`parse_connection_id`** and **`RESERVED_CONNECTION_IDS`** -- move from `wf_mcp.connections` and `wf_mcp.shared.names`
3. **`SourceConnection` protocol** -- new, replacing `ConnectionConfig` in runtime code

#### What should stay in broker compatibility wiring?

1. `UpstreamTransportService` -- it orchestrates broker-specific concerns (events, catalog store, adapter registry)
2. `SourceCatalogService` -- it manages `CapabilitySource` which is `wf_platform`-level
3. `ConnectionService` -- it manages `ConnectionRegistry` which is broker-specific
4. `WfMcpService` -- the compatibility facade
5. All `broker/config.py` construction logic

#### Where are events/catalog/source_catalog dependencies preventing extraction?

- `UpstreamTransportService.refresh_connection_catalog` (lines 203-275) takes `source_catalog: SourceCatalogService` and `record_catalog_change_events` callback. This is broker orchestration, not source provider logic.
- `SourceCatalogService.register_specs` takes `record_catalog_change_events` callback. This is broker event wiring.
- `SourceCatalogService.spec_from_snapshot_entry` (lines 257-298) rebuilds executable `NodeSpec` from stored snapshots, routing calls through `tool_executor_for()`. This is broker hydration, not source provider logic.

None of these prevent `wf_sources_mcp` from owning transport opening -- they just cannot move with it.

### Worker 3: Config/Source/Auth Findings

#### What connection/auth/source DTOs are still too coupled to `wf_mcp`?

1. **`ConnectionConfig`** (`wf_mcp.broker.models:37-44`) -- the primary blocker. Every runtime and broker module depends on it.

2. **`BrokerConfig`** (`wf_mcp.broker.models:47-55`) -- holds `store_root`, `connections`, `store_roots`. Used by proxy/runtime, server/core, broker/config. This is broker-specific and should stay.

3. **`BrokerStoreRoots`** (`wf_mcp.broker.models:11-33`) -- filesystem roots for stores. Broker-specific.

4. **`SourceConfigOwnership`** (`wf_mcp.broker.models:7`) -- `Literal["locked", "seed"]`. Also defined in `wf_config.models:73`. The broker version should be the canonical one since it controls runtime behavior.

5. **`AuthRecord`** (`wf_sources_mcp.auth:22-25`) -- already canonical in `wf_sources_mcp`. The `wf_mcp.auth` module is a re-export shim.

#### What neutral or MCP-source-specific config object should runtime/session code consume instead of `ConnectionConfig.metadata`?

The runtime code (`factory.py`, `adapter.py`) reads these fields from `ConnectionConfig.metadata`:

| Field | Used by | Purpose |
|-------|---------|---------|
| `transport` | `factory.py:49`, `adapter.py:40` | Transport type selector (`"stdio"` or `"streamable_http"`) |
| `command` | `factory.py:56`, `adapter.py:42` | Stdio command |
| `args` | `factory.py:57`, `adapter.py:43` | Stdio arguments |
| `env` | `factory.py:51`, `adapter.py:44` | Stdio environment variables |
| `cwd` | `factory.py:59`, `adapter.py:45` | Stdio working directory |
| `url` | `factory.py:71`, `adapter.py:62` | HTTP transport URL |

A `SourceTransport` union type already exists in `wf_sources_mcp.source_registry:53-69`:

```python
class StdioSourceTransport(SourceRegistryBaseModel):
    kind: Literal["stdio"] = "stdio"
    command: str
    args: tuple[str, ...] = ()
    env: dict[str, str] = Field(default_factory=dict)

class HttpSourceTransport(SourceRegistryBaseModel):
    kind: Literal["http"] = "http"
    url: AnyHttpUrl
    headers: dict[str, str] = Field(default_factory=dict)
```

The runtime code should consume a `SourceConnection` protocol that exposes:

- `id: str`
- `transport: StdioSourceTransport | HttpSourceTransport` (or a discriminated union)
- No `metadata: dict[str, Any]` bag

This would eliminate the `connection.metadata.get("transport", "stdio")` pattern scattered across `factory.py` and `adapter.py`.

#### What temporary dependencies remain and how should they be removed?

| Dependency | From | To | How to remove |
|-----------|------|-----|---------------|
| `parse_connection_id` | `wf_sources_mcp.source_registry:32` | `wf_mcp.connections` | Move `parse_connection_id` to `wf_sources_mcp` or a shared `wf_id` package. |
| `RESERVED_CONNECTION_IDS` | `wf_sources_mcp.source_registry:33` | `wf_mcp.shared.names` | Move constant to `wf_sources_mcp.source_registry` or shared package. Remove `wf_mcp.shared.names` import that transitively pulls FastMCP. |
| `ConnectionConfig` TYPE_CHECKING | `wf_sources_mcp.auth:18` | `wf_mcp.broker.models` | Replace with `SourceConnection` protocol. |
| `ConnectionConfig` TYPE_CHECKING | `wf_sources_mcp.sdk.protocols:16` | `wf_mcp.broker.models` | Replace with `SourceConnection` protocol. |
| `ConnectionConfig` TYPE_CHECKING | `wf_sources_mcp.source_registry:36` | `wf_mcp.models` | Replace with `SourceConnection` protocol or keep as converter-only. |
| `parse_connection_id` runtime | `wf_sources_mcp.storage.store:132` | `wf_mcp.connections` | Move function to `wf_sources_mcp`. |

### Worker 4: Frontend/Compat Findings

#### What is MCP frontend transport vs old compatibility facade?

**MCP frontend transport** (FastMCP server + proxy + tool registration):

- `server/core.py` -- creates `FastMCP` server, wires everything
- `proxy/runtime.py` -- `ProxyRuntime` mounts upstream connections as FastMCP proxies
- `proxy/mounts.py` -- `ProxyMountRegistry`, `create_proxy_mount`, `ResilientFastMCPProxy`
- `proxy/tools.py` -- proxy tool listing/filtering
- `proxy/safe_names.py` -- `SafeToolNames` transform for strict clients
- `admin_surface/tools.py` -- registers `wf.admin.*` tools on the server
- `workflow_surface/tools.py` -- registers `wf.workflow.*` tools on the server
- `shared/names.py` -- `ProxyNamespace`, `ADMIN_NAMESPACE`, namespace helpers

**Old compatibility facade** (re-export shims and `WfMcpService`):

- `auth.py` -- re-exports from `wf_sources_mcp.auth`
- `models.py` -- re-exports broker models
- `capabilities.py` -- re-exports from `wf_sources_mcp.catalog.entries`
- `source_registry.py` -- re-exports from `wf_sources_mcp.source_registry`
- `runtime/protocols.py` -- re-exports from `wf_sources_mcp.sdk`
- `broker/service/core.py` -- `WfMcpService` facade

#### What should eventually become `wf_transport_mcp`?

1. `server/core.py` -- `create_server`, `run_server`
2. `proxy/runtime.py` -- `ProxyRuntime`
3. `proxy/mounts.py` -- proxy mount logic
4. `proxy/tools.py` -- proxy tool helpers
5. `proxy/safe_names.py` -- `SafeToolNames`
6. `proxy/admin.py` -- proxy admin tools
7. `admin_surface/tools.py` -- admin tool registration
8. `admin_surface/handlers/*.py` -- admin tool handlers
9. `workflow_surface/tools.py` -- workflow tool registration
10. `workflow_surface/models.py` -- workflow tool models
11. `shared/names.py` -- namespace helpers (minus `RESERVED_CONNECTION_IDS`)
12. `cli.py` -- CLI entrypoint

#### What should remain as legacy `wf_mcp` entrypoints/shims?

1. `auth.py` -- re-export shim (keep until all callers import from `wf_sources_mcp.auth`)
2. `models.py` -- re-export shim (keep until all callers import from `wf_mcp.broker.models` directly)
3. `capabilities.py` -- re-export shim (keep until all callers import from `wf_sources_mcp.catalog`)
4. `source_registry.py` -- re-export shim (keep until all callers import from `wf_sources_mcp.source_registry`)
5. `runtime/protocols.py` -- re-export shim (keep until all callers import from `wf_sources_mcp.sdk`)
6. `runtime/__init__.py` -- re-export `McpRuntimePool`, `PersistentMcpSession`, etc. (keep for backward compat)

#### What should not be touched during upstream-source extraction?

1. `workflow_surface/*` -- workflow tools are MCP-frontend, not source-provider
2. `admin_surface/*` -- admin tools are MCP-frontend, not source-provider
3. `proxy/*` -- proxy mounting is MCP-frontend transport
4. `server/core.py` -- server creation is MCP-frontend
5. `cli.py` -- CLI entrypoint
6. `events/*` -- broker-local event system
7. `broker/service/workflow_runtime.py` -- workflow execution coordination
8. `broker/service/content_access.py` -- resource/prompt access
9. `workflow/wrappers.py` -- NodeSpec wrapping (uses `ToolExecutor` protocol, which is correct)

---

## Recommended Next Slices

Ordered smallest-safe-first.

### Slice 0: Define `SourceConnection` protocol in `wf_sources_mcp`

**Goal:** Break the TYPE_CHECKING dependency from `wf_sources_mcp.sdk.protocols` and `wf_sources_mcp.auth` on `wf_mcp.broker.models.ConnectionConfig` by defining a transport-level protocol that captures what runtime code actually needs.

**Files likely touched:**

- `src/wf_sources_mcp/sdk/protocols.py` -- add `SourceConnection` protocol, update `BackendAdapter` and `ToolExecutor` signatures
- `src/wf_sources_mcp/auth.py` -- update `auth_ref_for_connection` and `connection_auth_diagnostic` to accept protocol
- `src/wf_sources_mcp/source_registry.py` -- update TYPE_CHECKING import
- `src/wf_mcp/broker/models.py` -- make `ConnectionConfig` implement the protocol (no structural change needed, just verify compatibility)

**Tests likely needed:**

- Protocol conformance test: `ConnectionConfig` satisfies `SourceConnection`
- Verify `BackendAdapter` and `ToolExecutor` protocols still typecheck with `ConnectionConfig`

**What must NOT change:**

- `ConnectionConfig` fields/shape
- `BackendAdapter` method signatures (only the type of `connection` parameter changes)
- Any broker service code
- Any proxy/server code

**Migration/shim strategy:**

- `SourceConnection` is a new protocol, not a replacement. `ConnectionConfig` already satisfies it structurally.
- Existing `TYPE_CHECKING` imports in `wf_sources_mcp` become `SourceConnection` protocol imports.
- If any runtime code needs fields beyond the protocol (e.g., `source_config_ownership`), those stay on `ConnectionConfig` and are accessed through a cast or separate parameter.

---

### Slice 1: Move `parse_connection_id` and `RESERVED_CONNECTION_IDS` to `wf_sources_mcp`

**Goal:** Remove the runtime import dependency from `wf_sources_mcp` on `wf_mcp.connections` and `wf_mcp.shared.names`.

**Files likely touched:**

- `src/wf_sources_mcp/source_registry.py` -- replace imports, move validation logic
- `src/wf_sources_mcp/storage/store.py` -- replace `parse_connection_id` import
- `src/wf_mcp/connections.py` -- make `parse_connection_id` a re-export shim
- `src/wf_mcp/shared/names.py` -- make `RESERVED_CONNECTION_IDS` a re-export shim (or keep in `source_registry`)
- `src/wf_mcp/broker/service/connection_service.py` -- update import path

**Tests likely needed:**

- Existing tests for `parse_connection_id` should still pass
- Verify `FileCatalogStore._connection_path` still validates connection IDs

**What must NOT change:**

- Validation logic (same regex, same error messages)
- `RESERVED_CONNECTION_IDS` values
- Any broker service behavior

**Migration/shim strategy:**

- Move `CONNECTION_ID_PATTERN`, `parse_connection_id` to `wf_sources_mcp.source_registry` or a new `wf_sources_mcp.validation` module.
- `wf_mcp.connections` becomes a re-export shim: `from wf_sources_mcp.source_registry import parse_connection_id`
- `RESERVED_CONNECTION_IDS` moves to `wf_sources_mcp.source_registry` (it's already imported there).
- `wf_mcp.shared.names` keeps its own copy or re-exports.
- `wf_mcp.shared.names` can remove the FastMCP import from the top-level module (move `ProxyNamespace` and FastMCP-specific code to a separate submodule if needed).

---

### Slice 2: Extract `open_mcp_session` transport helper to `wf_sources_mcp`

**Goal:** Eliminate the transport-opening duplication between `runtime/factory.py` and `sdk/adapter.py` by extracting a shared helper.

**Files likely touched:**

- New: `src/wf_sources_mcp/sdk/transport.py` -- `open_mcp_session` async context manager
- `src/wf_mcp/runtime/factory.py` -- use `open_mcp_session` in `_create_with_stack`
- `src/wf_mcp/sdk/adapter.py` -- use `open_mcp_session` in `_session`

**Tests likely needed:**

- Unit test for `open_mcp_session` with mock transport
- Verify `PersistentSessionFactory` still creates persistent sessions correctly
- Verify `McpSdkAdapter` still creates one-shot sessions correctly
- Test error handling (unsupported transport, auth failures)

**What must NOT change:**

- `PersistentMcpSession` API
- `McpRuntimePool` behavior
- `McpSdkAdapter` method signatures
- Any broker service code
- Event emission patterns

**Migration/shim strategy:**

- `open_mcp_session` accepts a `SourceConnection` (from Slice 0) and `AuthRecord | None`.
- Returns an async context manager yielding `ClientSession`.
- Both `factory.py` and `adapter.py` call this helper instead of duplicating transport logic.
- The factory wraps it in `AsyncExitStack` for persistent ownership; the adapter uses it directly as a context manager.

---

### Slice 3: Move `PersistentSessionFactory`, `PersistentMcpSession`, `McpRuntimePool` to `wf_sources_mcp`

**Goal:** Move the persistent MCP runtime into the source provider package where it belongs.

**Files likely touched:**

- New: `src/wf_sources_mcp/runtime/__init__.py` -- package init
- New: `src/wf_sources_mcp/runtime/factory.py` -- moved from `wf_mcp/runtime/factory.py`
- New: `src/wf_sources_mcp/runtime/session.py` -- moved from `wf_mcp/runtime/session.py`
- New: `src/wf_sources_mcp/runtime/pool.py` -- moved from `wf_mcp/runtime/pool.py`
- `src/wf_mcp/runtime/__init__.py` -- becomes re-export shim
- `src/wf_mcp/runtime/factory.py` -- becomes re-export shim
- `src/wf_mcp/runtime/session.py` -- becomes re-export shim
- `src/wf_mcp/runtime/pool.py` -- becomes re-export shim
- `src/wf_mcp/broker/config.py` -- update import path
- `src/wf_mcp/broker/service/core.py` -- update import path (if any)

**Tests likely needed:**

- All existing `test_stateful_runtime.py` tests must pass unchanged
- Verify `CrashingSessionFactory` subclass still works
- Verify `McpRuntimePool` fingerprint logic still works

**What must NOT change:**

- `PersistentMcpSession` API (connection, auth, call_tool, close)
- `McpRuntimePool` API (get_session, call_tool, close_connection, close_all)
- `PersistentSessionFactory.create` signature
- `connection_runtime_fingerprint` function
- Any event emission or broker orchestration

**Migration/shim strategy:**

- `wf_mcp.runtime` becomes a re-export shim: `from wf_sources_mcp.runtime import ...`
- `wf_mcp.runtime.protocols.ToolExecutor` already re-exports from `wf_sources_mcp.sdk`
- Tests import from `wf_mcp.runtime` still work via shims
- `broker/config.py` can update to import from `wf_sources_mcp.runtime` directly

---

### Slice 4: Move `McpSdkAdapter` to `wf_sources_mcp.sdk`

**Goal:** Consolidate the one-shot MCP adapter into the source provider SDK.

**Files likely touched:**

- New: `src/wf_sources_mcp/sdk/adapter.py` -- moved from `wf_mcp/sdk/adapter.py`
- `src/wf_mcp/sdk/adapter.py` -- becomes re-export shim
- `src/wf_mcp/sdk/__init__.py` -- update re-exports
- `src/wf_mcp/broker/config.py` -- update import path
- `src/wf_mcp/server/core.py` -- update import path

**Tests likely needed:**

- Existing `test_sdk_adapter.py` tests must pass
- Verify `McpSdkAdapter` still implements `BackendAdapter`

**What must NOT change:**

- `McpSdkAdapter` method signatures
- `BackendAdapter` protocol
- Any broker service code

**Migration/shim strategy:**

- `wf_mcp.sdk.adapter.McpSdkAdapter` re-exports from `wf_sources_mcp.sdk.adapter`
- `wf_mcp.sdk.__init__` keeps exporting `McpSdkAdapter`

---

### Slice 5: Introduce `SourceConnection` dataclass in `wf_sources_mcp` (optional, future)

**Goal:** Replace the `metadata: dict[str, Any]` bag in `ConnectionConfig` with a typed transport DTO for source-provider code.

**Files likely touched:**

- `src/wf_sources_mcp/source_registry.py` -- add `SourceConnection` dataclass
- `src/wf_mcp/runtime/factory.py` -- accept `SourceConnection` instead of `ConnectionConfig`
- `src/wf_mcp/sdk/adapter.py` -- accept `SourceConnection` instead of `ConnectionConfig`
- `src/wf_mcp/runtime/pool.py` -- accept `SourceConnection` in fingerprint
- Conversion helpers in `wf_sources_mcp.source_registry`

**Tests likely needed:**

- Conversion test: `ConnectionConfig` -> `SourceConnection`
- Round-trip test for fingerprint stability
- Verify `McpRuntimePool` fingerprint changes correctly

**What must NOT change:**

- `ConnectionConfig` shape (it's still the broker DTO)
- Broker service behavior
- Proxy/server behavior

**Migration/shim strategy:**

- `SourceConnection` is a new typed DTO in `wf_sources_mcp`.
- `ConnectionConfig` gains a `to_source_connection() -> SourceConnection` method or a standalone converter.
- Runtime code (`factory.py`, `adapter.py`, `pool.py`) accepts `SourceConnection`.
- `McpRuntimePool` fingerprint uses `SourceConnection` fields.
- This slice is optional if Slices 0-4 are sufficient.

---

### Slice 6: Clean up `wf_mcp` re-export shims (final)

**Goal:** Remove all compatibility re-export shims from `wf_mcp` once all callers import from canonical packages.

**Files likely touched:**

- `src/wf_mcp/auth.py` -- delete or leave empty
- `src/wf_mcp/capabilities.py` -- delete or leave empty
- `src/wf_mcp/source_registry.py` -- delete or leave empty
- `src/wf_mcp/runtime/protocols.py` -- delete or leave empty
- `src/wf_mcp/runtime/__init__.py` -- simplify
- `src/wf_mcp/models.py` -- simplify
- `src/wf_mcp/__init__.py` -- simplify

**Tests likely needed:**

- Verify all existing imports still work (or update them)
- `test_compat_imports.py` should pass or be updated

**What must NOT change:**

- Any runtime behavior
- Any broker service behavior

**Migration/shim strategy:**

- This is the final cleanup after all other slices are complete.
- Search for all `from wf_mcp.auth import` etc. and update to canonical paths.
- Leave shims in place for one release cycle, then remove.

---

## Should `runtime/factory.py` Move Now?

**No.** A typed client/session seam must come first.

Reasons:

1. `PersistentSessionFactory._create_with_stack` reads `connection.metadata["transport"]`, `connection.metadata["command"]`, etc. These are `dict[str, Any]` bag accesses that should be replaced by typed protocol access.
2. `PersistentMcpSession` holds `connection: ConnectionConfig` directly. If factory moves to `wf_sources_mcp`, it drags `ConnectionConfig` (and therefore `wf_mcp.broker.models`) into the source provider package at runtime.
3. The `PersistentSessionFactory.create` method returns `PersistentMcpSession` which stores `connection: ConnectionConfig`. Without the protocol, this creates a circular import.

**Correct order:**

1. Slice 0: Define `SourceConnection` protocol
2. Slice 1: Move `parse_connection_id` / `RESERVED_CONNECTION_IDS`
3. Slice 2: Extract `open_mcp_session` helper
4. Slice 3: Move runtime code to `wf_sources_mcp`
5. Slice 4: Move adapter to `wf_sources_mcp.sdk`
6. Slice 5: (Optional) Typed `SourceConnection` dataclass
7. Slice 6: Clean up shims

---

## Test Coverage Summary

Existing tests relevant to the extraction:

| Test file | What it covers | Extraction impact |
|-----------|---------------|-------------------|
| `tests/wf_mcp/test_stateful_runtime.py` | `McpRuntimePool`, `PersistentMcpSession`, `PersistentSessionFactory`, `CrashingSessionFactory` | Must pass unchanged through Slices 0-4 |
| `tests/wf_mcp/test_sdk_adapter.py` | `McpSdkAdapter` one-shot operations | Must pass unchanged through Slices 0-4 |
| `tests/wf_mcp/test_compat_imports.py` | Re-export shim compatibility | Must pass through Slice 6 |
| `tests/wf_mcp/test_workflow_wrappers.py` | `wrap_discovered_tool` with `ToolExecutor` | Must pass unchanged |
| `tests/wf_mcp/test_store.py` | `FileCatalogStore._connection_path` uses `parse_connection_id` | Must pass after Slice 1 |
| `tests/wf_mcp/service/test_connection_service.py` | `ConnectionService` | Unaffected |
| `tests/wf_mcp/service/test_source_registry_admin.py` | Source registry admin tools | Unaffected |
| `tests/wf_mcp/service/test_events.py` | `BrokerEventRecorder` | Unaffected |
| `tests/wf_mcp/service/test_workflow_runtime.py` | `WorkflowRuntimeService` | Unaffected |

---

## Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| Circular import if `wf_sources_mcp` imports `ConnectionConfig` at runtime | High | Use TYPE_CHECKING + protocol pattern (Slice 0) |
| Breaking re-export shims during move | Medium | Keep shims in place, update canonical imports first |
| `McpRuntimePool` fingerprint behavioral change | Medium | Preserve exact same fingerprint computation after move |
| `FileCatalogStore` breaking after `parse_connection_id` move | Low | Move function, keep re-export, run `test_store.py` |
| FastMCP transitive import in `shared/names.py` | Low | Move `RESERVED_CONNECTION_IDS` first, then clean `shared/names.py` |
