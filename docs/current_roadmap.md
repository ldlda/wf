# Current Roadmap

This is the short active roadmap after the core type-shape cleanup and MCP
workflow authoring cleanup pass. It is based on both the current docs and the
implementation state.

## Completed Cleanup Pass

1. **Docs index and prune**
   - Current architecture docs are separated from historical plans and scratch
     notes.
   - The active roadmap now lives here instead of being scattered through older
     planning files.

2. **MCP workflow authoring UX**
   - The operator manual categorizes workflow tools into discovery, draft
     workspace, stateless draft, artifact/deployment, run/debug, and raw escape
     hatch groups.
   - List-style tools are more compact, while inspect/run tools carry the
     detailed payloads.

3. **Wrapper creation ergonomics**
   - Wrapper draft helpers can suggest state schema, input bindings, output
     bindings, default `ok` / `error` handling, and missing decisions.
   - The end-to-end runbook documents the wrapper path from capability
     discovery through deployment/run.

4. **Run and deployment story**
   - Deployment listing is summary-first, with dedicated inspection for detail.
   - `run_deployment` returns compact status by default and exposes trace slices
     through an explicit `trace_range`.
   - Dependency validation and error output remain part of the run path.

5. **Source inventory polish**
   - `list_sources` / `inspect_source` now present source-owned capabilities
     progressively.
   - Source inventory distinguishes external sources, local workflow-facing
     sources, docs/resources, and admin-only control surfaces.

6. **Workflow API seam**
   - `wf_api.WorkflowApiSurface` is now the protocol-neutral workflow operation
     contract consumed by CLI and transport adapters.
   - `wf_api.WorkflowApi` is the process-local implementation used by MCP
     workflow tools and local CLI/server composition.
   - `wf_api` imports no `wf_mcp` modules. `WorkflowApi` composes domain
     services directly from `WorkflowOperationContext`; MCP owns only context
     construction and tool schemas.
   - Protocol-neutral helpers now live in `wf_api`: refs/constants, wrapper
     hints, next actions, raw workflow plans, runtime dependencies, saved
     subgraph preparation, and durable run lifecycle helpers. Old
     `wf_mcp.workflow_surface` helper paths remain compatibility shims.
   - The boundary is documented in
     [wf_api architecture](./wf_api_architecture.md).

## Active Next Roadmap

1. **WorkflowOperationContext simplification**
   - Completed: the duplicated top-level
     `WorkflowOperationContext.capability_sources` field was removed.
   - Keep `WorkflowSpecProvider.capability_sources` as the single source inventory
     path for `wf_api` consumers.
   - The audit is in
     [2026-06-03 WorkflowOperationContext shape audit](./superpowers/research/2026-06-03-workflow-operation-context-audit.md).

2. **Persisted run/resume spec**
   - Completed: the process-restart resume contract is defined in
     [2026-06-03 persisted run/resume contract](./superpowers/specs/2026-06-03-persisted-run-resume-contract.md).
   - It covers run records, pinned deployment/artifact/subgraph environment,
     source/capability validation, trace paging, and interrupt-only pause
     semantics.
   - Keep ordinary dead tools/sources as diagnostics or failed runs, not implicit
     pauses.

3. **Persisted run/resume implementation**
   - Implement the load/validate/resume flow behind `WorkflowRunApi`, `RunStore`,
     and `WorkflowRuntimeRunner`.
   - Do not reintroduce direct `WfMcpService` coupling into the workflow API.
   - `wf_api.durable_context` now provides a required-store guard for future
     durable frontends. It preserves the current process-local behavior while
     failing fast if artifact, draft, or run stores are missing.

4. **Durable API service shape**
   - Decide the non-MCP frontend boundary for a long-lived API process.
   - Reuse `WorkflowApi` and the focused broker services where possible.
   - Keep config/store construction and auth explicit.
   - Current design direction is recorded in
     [2026-06-03 long-lived workflow API boundary](./superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md):
     initial slices proved a lightweight local/static server and JSON-RPC
     transport; later slices add transport siblings, source providers, auth,
     streaming/progress, transactional storage, and live upstream MCP sources.
   - First slice implemented: `wf_server` can construct a local/static durable
     `WorkflowApi` without `WfMcpService`.
   - Completed: the first JSON-RPC-over-HTTP transport can expose the
     local/static `WorkflowServer` through fixed dotted methods.
   - Completed: workflow config now distinguishes client targets from server
      hosting config, the basic `wf` lifecycle can target JSON-RPC HTTP:
      capability discovery, draft workspace authoring, artifact/deployment
      operations, run, inspect, and bounded trace.
   - Completed: `wf_transport_rpc_http` is split by workflow domain. The
      public `RpcWorkflowApiClient` still satisfies `WorkflowApiSurface`, while
      client methods and server JSON-RPC registrations live in focused
      capability, draft, artifact, deployment, and run modules.
   - Completed: read-only source inventory now has a protocol-neutral
      `WorkflowSourceAdminApi` / `WorkflowSourceAdminSurface`; MCP admin source
      tools delegate through it while connection/raw MCP operations remain
      broker-owned.
   - Completed: read-only source inventory is exposed through JSON-RPC HTTP and
      `wf source list` / `wf source inspect`.
   - Completed: read-only admin/config sibling surface covers connection
      inventory, connection status, and broker/server events. Keep it separate
      from `WorkflowApiSurface`; this is platform management, not workflow
      lifecycle.
   - Completed: read-only admin/config now has a neutral `WorkflowAdminApi` /
      `WorkflowAdminSurface`, is exposed through JSON-RPC HTTP, and is available
      through `wf admin connections`, `wf admin statuses`, and
      `wf admin events`.
   - Mutating source/connection config commands now target the store-backed
      source registry plan instead of config files. Config can bootstrap sources,
      while server-owned dynamic source changes need validated registry writes.
   - The store-backed source registry design is recorded in
      [2026-06-03 store-backed source registry](./superpowers/specs/2026-06-03-store-backed-source-registry-design.md).
   - First source registry implementation slices complete: validated registry
      models, `FileSourceRegistryStore`, generic `wf_api` registry mechanics,
      MCP entry conversion, and startup merge are implemented.
   - Source registry startup merge is implemented: absent registry preserves
      config-only behavior, registry-only entries hydrate as dynamic connections,
      and config entries shadow same-id registry entries with an event.
    - Config shadowing is the v1 conservative behavior, not the final ownership
      model. The planned follow-up is explicit config ownership policy:
      `locked` config entries stay operator-owned, while `seed` entries
      bootstrap missing store entries and then let the store own later admin
      changes.
    - Completed: config ownership policy is implemented for MCP broker config
      connections: `locked` entries stay operator-owned, while `seed` entries
      bootstrap missing store entries and then let the store own later admin
      changes.
   - Historical source registry slice planning is archived in
      [2026-06-03 source registry next slices](./historical/superpowers/plans/2026-06-03-source-registry-next-slices.md):
      desired-registry admin reads and safe mutation commands are complete.
   - Completed: MCP-backed `WorkflowServer` construction is available through
      `wf_mcp.broker.server.build_workflow_server_from_config`. JSON-RPC can now
      expose real MCP-backed workflow, source-admin, admin, and desired source
      registry surfaces without making `wf_server` import `wf_mcp`.
   - Completed: desired-registry admin read plumbing is available through
      `WorkflowSourceRegistryApi`, JSON-RPC methods
      (`workflow.admin.source_registry.list` / `.inspect`), and CLI commands
      (`wf admin registry list` / `wf admin registry inspect`). Local/static
      servers report unavailable instead of empty; concrete MCP-backed
      `WorkflowServer` construction is now available through
      `wf_mcp.broker.server`.
   - Completed: desired-registry mutation operations are available through
      `WorkflowSourceRegistryApi` (add/update/enable/disable/remove),
      JSON-RPC methods (`workflow.admin.source_registry.add` / `.update` /
      `.enable` / `.disable` / `.remove`), and CLI commands
      (`wf admin registry add` / `update` / `enable` / `disable` / `remove`)
      for targets that expose the registry-admin surface. Mutations target
      persisted desired registry state only; config files, auth records, and
      catalog snapshots are not mutated. Config-shadowed add is rejected in v1.
      Remove requires `--confirm` in CLI; local/static servers report
      unavailable.
   - Completed: `wf-rpc-server --mcp-config wf_mcp.config.json` starts the
      JSON-RPC transport over an MCP-backed `WorkflowServer`, making the remote
      CLI path usable with MCP sources and desired source registry operations.
- Next concrete platform slices:
  - Wider `wf_config` source model: migrate MCP broker config concepts into the
    neutral server config instead of preserving `wf_mcp.config.json` as a
    peer forever. `wf_config.server.sources[]` already exists as a
    discriminated union, but only `stdlib` is implemented today. Add MCP source
    variants that carry source id, provider/account/profile, ownership policy,
    transport shape, auth reference, and metadata. The old MCP broker config
    becomes a compatibility input that normalizes into the wider config model.
    After that, `wf-rpc-server --config ...` can build MCP-backed sources from
    neutral config and `--mcp-config` can be deprecated or treated as a legacy
    alias.
    `McpSourceRegistryEntry` already has most of the target shape; the one
    ownership field comes from legacy `ConnectionConfig.source_config_ownership`.
     When migrating, carry that policy into the neutral MCP source variant with a
     clearer name such as `config_ownership` or `ownership`, rather than leaking
     the old connection-centric field name.
    First slice complete: `wf_config.server.sources[]` now accepts
    `kind: "mcp"` entries with stdio/http transport, auth reference, metadata,
    enabled flag, and `locked` / `seed` ownership policy. Runtime composition
    from these entries is the next slice.
    Runtime bridge complete: neutral `kind: "mcp"` source entries can now build
    the MCP-backed `WorkflowServer`. `--mcp-config` remains supported as a
    legacy compatibility path while new configs should prefer
    `server.sources[]`.
  - Transport package boundary cleanup follows the config migration. The current
    `wf-rpc-server --mcp-config` hookup proves the product path but makes
    `wf_transport_rpc_http.cli` import `wf_mcp.broker`, tripping the existing
    import-direction guard. The durable fix is not a permanent split launcher;
    it is making `wf_config` wide enough that the RPC server can compose from
    neutral config while MCP-specific adapters stay selected by source kind.
    Completed: `wf_transport_rpc_http` no longer imports `wf_mcp`; server
    composition from neutral or legacy MCP config lives behind `wf_server.config`.
  - Legacy config migration: add a converter from old `wf_mcp.config.json`
    (`store_root`, `connections[]`) into the wider `wf_config` shape
    (`server.store`, `server.sources[]`). `server.store` is already a
    discriminated union (`kind: "filesystem"` today, future SQL/store backends
    later), so the conversion should map old `store_root` to
    `server.store.root` without inventing a parallel store field. Old MCP HTTP
    metadata values such as `http`, `streamable-http`, `streamable_http`, and
    `sse` should normalize into the neutral HTTP source transport while
    preserving enough metadata for MCP/FastMCP compatibility. `sse` is legacy
    protocol shape, but keep conversion support because FastMCP deployments may
    still use it.
    Completed: `wf config migrate-mcp` converts legacy broker config files into
    neutral workflow config files without mutating the original.
  - Manual product smoke: run `wf-rpc-server --mcp-config ...`, point
    `wf --url ...` at it, and capture real CLI/server UX gaps before adding
    more architecture.
   - Source registry apply/reload: decide and implement how persisted registry
     mutations affect the running source catalog. Prefer an explicit
     apply/reload operation before automatic live remount.
   - Completed: desired source registry mutations can now be applied explicitly
     through `wf admin registry apply` / `workflow.admin.source_registry.apply`.
     V1 apply reconciles registry state into the current server connection/source
     graph; it does not auto-apply mutations, mutate config files, or remount
     MCP proxy providers.
   - Completed: persisted resume across server rebuild is covered through the
     MCP-backed JSON-RPC path. A neutral-config `WorkflowServer` can start an
     interrupting run, be rebuilt from the same filesystem stores, inspect the
     interrupted run, and resume it to completion through `RpcWorkflowApiClient`.
   - Completed: MCP upstream source runtime cleanup now starts with a typed
     `McpSourceConnection` seam in `wf_sources_mcp`, not by moving
     `runtime/factory.py` as-is. The active plan was
     [2026-06-07 MCP source connection seam](./historical/superpowers/plans/2026-06-07-mcp-source-connection-seam.md).
   - Completed: shared MCP session opener exists in `wf_sources_mcp.client`.
     One-shot adapter (`McpSdkAdapter`) and persistent runtime
     (`PersistentSessionFactory`) both use it.
    - Completed: persistent MCP runtime moved to `wf_sources_mcp.runtime`.
      `PersistentMcpSession`, `PersistentSessionFactory`, `McpRuntimePool`,
      and `connection_runtime_fingerprint` are now canonical in
      `wf_sources_mcp.runtime`; `wf_mcp.runtime.*` are compatibility shims.
      Runtime remains tool-call-only. The completed plan was
      [2026-06-07 MCP runtime package move](./historical/superpowers/plans/2026-06-07-mcp-runtime-package-move.md).
    - Completed: one-shot MCP SDK adapter moved to `wf_sources_mcp.sdk.adapter`.
      `McpSdkAdapter` is now canonical in `wf_sources_mcp`; `wf_mcp.sdk.*`
      remains a compatibility shim for old imports. Persistent runtime is still
      tool-call-only.
  - Auth/source secrets boundary: keep registry desired state separate from
    upstream credentials, and surface missing auth as validation diagnostics.
    The contract is now specified in
    [2026-06-06 auth/source secrets boundary](./superpowers/specs/2026-06-06-auth-source-secrets-boundary.md):
    sources carry `auth_ref`, runtime resolves through an auth store interface,
    and the current filesystem auth files are only one adapter.
    First implementation slice complete: neutral auth records/store protocol
    exist in `wf_api`, MCP runtime auth resolution prefers explicit `auth_ref`
    with legacy connection-id fallback, and MCP payload interpretation is
    isolated in provider-specific adapter helpers.
    Second implementation slice complete: missing explicit auth refs now surface
    as `auth_not_found` diagnostics in live source checks and source registry
    apply summaries.
    Third implementation slice complete: read-only auth admin summaries are
    available through MCP-backed server admin, JSON-RPC, and CLI. Summaries show
    ids, schemes, metadata, and payload keys only; secret payload values remain
    hidden.
    Fourth implementation slice complete: local/dev auth records can be saved and
    deleted through neutral admin, JSON-RPC, and `wf admin auth`. This is still not
    a production secret manager or OAuth flow; payload values are accepted only as
    write inputs and never returned.
    Not done: auth is still compatibility-grade. There is no OAuth flow,
    production secret manager, provider-specific display model, or
    full removal of the legacy MCP auth record shape yet.
  - Role-specific server stores: the current neutral config has one
    `server.store` root that backs workflow records, desired source registry,
    catalog/cache snapshots, and local/dev auth records. The next config slice
    should add optional `server.stores.*` overrides while preserving
    `server.store` as the fallback for every missing role. First implementation
    should stay filesystem-only; secret managers, SQL, and object stores are
    later backend implementations.
    First role-specific store slice complete: neutral config now accepts optional
    `server.stores.workflow`, `server.stores.auth`,
    `server.stores.source_registry`, and `server.stores.catalog_cache`
    filesystem overrides. Missing roles still fall back to `server.store`.
    Follow-up complete: MCP compatibility auth and catalog/cache stores are now
    split at the service boundary. `FileStore` remains as a compatibility
    wrapper, while neutral config role roots can drive `FileAuthStore` and
    `FileCatalogStore` separately.
  - Completed: `wf run watch` starts run progress UX with polling over existing
    `inspect_run` and optional bounded `read_run_trace`. SSE/WebSocket/MCP
    progress remains deferred until polling UX proves insufficient.
  - Completed: CLI remote error formatting now routes expected operation and
    HTTP transport failures through compact Typer/Click errors by default.
    `wf --verbose ...` preserves raw exception behavior for debugging.
  - MCP package split direction: keep separating "MCP as a client transport"
    from "MCP as an upstream workflow source provider." The future shape is
    likely `wf_transport_mcp` for exposing workflow/admin surfaces to MCP
    clients, and `wf_sources_mcp` for discovering/invoking upstream MCP servers
    as workflow capabilities. The current `wf_mcp` package still contains both
    roles plus compatibility entrypoints; new server/transport work should avoid
    depending on that combined facade.
      First `wf_sources_mcp` slice complete: MCP auth helpers and focused
      auth/catalog stores now live in `wf_sources_mcp`, with `wf_mcp` compatibility
      shims preserved. Runtime/session/source-registry moves remain future slices.
      Keep `wf_mcp` re-export shims for compatibility and add import-direction
      tests so `wf_sources_mcp` does not depend on workflow/admin surface,
      frontend server, or proxy modules.
      Second `wf_sources_mcp` slice complete: MCP desired source registry
     models, file store, and conversion helpers now live in
     `wf_sources_mcp.source_registry`, with `wf_mcp.source_registry` retained
     as a compatibility shim.
      Third `wf_sources_mcp` slice complete: upstream MCP catalog/discovery DTOs
     and catalog snapshot dumping now live in `wf_sources_mcp.catalog`, with
     `wf_mcp.capabilities` and `wf_mcp.catalog.models` retained as shims.
       Fourth `wf_sources_mcp` slice complete: upstream SDK protocol/result
      types (`BackendAdapter`, `ToolExecutor`, `ToolCallResult`) now live in
      `wf_sources_mcp.sdk`, with `wf_mcp.sdk` and `wf_mcp.runtime.protocols`
      retained as compatibility shims.
      Fifth `wf_sources_mcp` slice complete: MCP SDK conversion helpers now live
      in `wf_sources_mcp.sdk.converters`, with `wf_mcp.sdk.converters` retained
      as a compatibility shim.
    The `wf-mcp` script is now a legacy/special-purpose MCP entrypoint, not the
    preferred durable workflow server. New product paths should target
    `wf-rpc-server` plus neutral `wf_config`/`wf_server` composition, then keep
    shrinking `wf_mcp` toward upstream MCP source utilities, MCP transport
    adapters, proxy/debug compatibility, and old entrypoint shims.
    MCP UI/App metadata is source metadata only for now. Do not advertise widget
    or MCP Apps support through workflow transports until a dedicated MCP
    frontend transport owns iframe hosting, `ui://` resources, app-only tool
    calls, and bridge semantics. Raw proxy/debug paths may expose upstream MCP
    behavior explicitly, but that is not the durable workflow surface.
- Cleanup candidate: consolidate store/source registry id validation patterns
      (`SOURCE_REGISTRY_ID_PATTERN`, `STORE_ID_PATTERN`) only after another package
      needs the same rule. Today they intentionally stay close to their stores.
   - Longer term: make the MCP frontend an adapter over these neutral workflow,
      source-admin, and config-admin surfaces so the old `wf_mcp` server entry
      point can shrink or retire.

5. **CLI/API alignment**
   - Completed for the basic lifecycle: selected `wf` commands can target local
     process-backed stores/runtime or JSON-RPC HTTP through the same
     `WorkflowApiSurface`.
   - Current alignment notes are recorded in
     [2026-06-03 CLI/API alignment notes](./superpowers/specs/2026-06-03-cli-api-alignment-notes.md).
   - Completed: no workflow lifecycle command imports
     `load_local_cli_context_from_typer`; `wf docs`, `wf schema`, and
     `wf explain` remain static/local utilities for now.
   - Preserve the current local CLI path until server source registry/auth/admin
     operations are proven remotely.

6. **Workflow primitive polish**
   - Return to native subgraph polish, fork/gather, foreach follow-ups, and graph
     authoring UX after the durability/platform path is stable.

## Runtime and Platform Roadmap

- Scheduler foundation decision record:
  [ADR 0001](./adr/0001-scheduler-foundation-before-concurrent-foreach.md).
- Concurrent foreach policy decision record:
  [ADR 0002](./adr/0002-concurrent-foreach-policy-and-barrier-commits.md).
- Native subgraph design spec:
  [2026-05-24 native subgraphs](./superpowers/specs/2026-05-24-native-subgraphs-design.md).
- **Native subgraphs / graph-as-node**: core has `SubgraphNode`, structural
  `WorkflowRef`, workflow-level outcomes plus explicit `EndNode` termination,
  authoring helpers (`subgraph_ref` / `WorkflowBuilder.subgraph`), and artifact
  reference conversion helpers. Core can now execute a prepared local child
  workflow through an isolated child scope/lineage, preserve its trace entries,
  map child output through the boundary, and route by the child's terminal
  outcome. Prepared child interrupts now bubble through a typed internal route
  and resume inside child scope while the public request identifies the parent
  subgraph boundary. The workflow platform now resolves non-interrupting saved
  child artifact refs into native prepared dependencies; descendant logical
  capabilities inherit the root deployment binding environment, and missing or
  cyclic saved children fail validation before a run starts. Wrapper helpers
  currently run child workflows as ordinary nodes; native
  `SubgraphNode` is now the graph-as-node path for prepared children.
  `WorkflowBuilder.prepare_subgraph()` and `WorkflowBuilder.resume()` make the
  local runnable/resumable path available without core-runtime plumbing.
  Saved interrupting artifacts can now pause and resume through
  `run_deployment`/`resume_run` across handler/server recreation by restoring
  stopped checkpoints and pinned root/child artifact definitions.
- **Concurrent foreach**: implemented in core with explicit scheduling,
  reducer/merge semantics, item error policy, async handler batching, and
  quiescent interrupt behavior. Remaining work is polish and future reuse of
  its barrier/lineage machinery by native subgraphs and fork/gather. Current
  lineage progress includes ordered `StateWrite` records, `LineageStateView`,
  foreach item `lineage_id`s, nested foreach lineage identity, root
  `RuntimeScope` / `LineageState` storage, scope-aware reads, and non-root write
  buffering. New concurrent foreach item writes are stored in
  `RunState.lineages`, while `ForeachBarrierState` keeps scheduling/result
  metadata and compatibility patches. Scope-root commits now apply to both the
  root workflow and prepared native child scopes through the explicit
  scope/lineage commit helper.
- **Durable run history and resume**: the design is recorded in
  [2026-05-26 durable workflow runs](./superpowers/specs/2026-05-26-durable-workflow-runs-and-resume-design.md).
  A validated `RunState` codec and dedicated run/checkpoint store now persist
  interrupted, completed, and failed stopped snapshots. Stable `run_id` values
  support compact `inspect_run` and bounded `read_run_trace` reads. Resume
  revalidates its pinned dependency environment and reports `blocked` without
  consuming input when a required source is unavailable. Ordinary live
  tool/source failures remain failed runs, not implicit pauses.
- **OpenAPI capability sources**: raw OpenAPI operations can be represented as
  workflow-facing capabilities using the OpenAPI document as the source of
  truth. Runtime execution now follows the `openapi-core` plan: public payloads
  keep OpenAPI names, generic `httpx` builds requests, and `openapi-core`
  validates/unmarshals requests and responses. Generated Python client parsing
  is explicitly retired. See
  [OpenAPI capability sources](./openapi_capability_source.md).
- **Protocol-native long-running runs**: investigate MCP tasks/progress
  notifications for long-running workflow execution. Avoid inventing a custom
  "start" convention unless protocol-native behavior is insufficient.
- **Dynamic saved workflows as tools**: defer until the stable run/inspect
  surface is strong. Many MCP clients do not refresh tool lists reliably, so
  `wf.workflow.run_deployment` remains the dependable front door.
- **Dashboard/source controls**: future UI should consume the same source
  inventory and deployment metadata instead of reverse-engineering MCP tools.
- **Workflow API extraction**: completed staged extraction context is archived in
  [wf_api extraction roadmap](./historical/superpowers/plans/2026-06-01-wf-api-extraction-roadmap.md).
  Protocol-neutral operation context and domain services now exist behind
  `wf_api`; MCP tool schemas and tool registration stay in `wf_mcp`.
  - Workflow store ownership is explicit: entrypoints construct/inject `WorkflowStores`; `WfMcpService` no longer guesses stores from the MCP store root.
  - Double-delegation has been removed: CLI and MCP workflow tools construct
    `WorkflowApi(context_from_service(service))` directly. `WorkflowSurfaceHandlers`
    remains only as a temporary compatibility shim for older imports.
  - `WfMcpService` is being reduced into injected implementation services. Source
    registry and catalog projection now live in `SourceCatalogService`; the old
    service methods remain as compatibility delegates for MCP broker callers.
  - Workflow runtime execution is being separated from broker coordination.
    `WorkflowRuntimeService` now owns plan compilation, dependency preparation,
    run, and resume; `WfMcpService` keeps delegate methods for compatibility.
  - Upstream MCP transport is being separated from broker coordination.
    `UpstreamTransportService` now owns adapter registration, auth persistence,
    catalog refresh I/O, resource/prompt reads, raw method/notification calls,
    generated-tool executor selection, and live source diagnostics.
  - Broker event recording is being separated from broker coordination.
    `BrokerEventRecorder` now owns EventBus publication, event history reads,
    simple event construction, and catalog-change fanout. `WfMcpService` keeps
    delegate methods for compatibility.
  - Connection ownership now lives in `ConnectionService`: it owns the broker
    `ConnectionRegistry`, reserved connection-id rejection, `register_connection`,
    and `sync_connections_from_config`. `WfMcpService.connections` remains a
    compatibility property while source hydration still belongs to
    `SourceCatalogService`.
  - MCP model ownership is being compartmentalized. `wf_mcp.broker.models` owns
    broker/connection config dataclasses, `wf_mcp.catalog.models` owns catalog
    snapshots, and `wf_mcp.auth` owns the legacy MCP auth record plus adapter
    helpers. `wf_mcp.models` remains a compatibility facade for older imports.
  - Several reusable implementation pieces still live in `wf_mcp` because they
    are MCP-shaped today (`source_registry.py`, `broker/server.py`, and focused
    `broker/service/*` services). The next config migration should make the
    split explicit: neutral config/registry mechanics belong in `wf_config`,
    `wf_api`, `wf_server`, or another platform package; MCP-specific transport,
    adapter, and upstream session behavior stays in `wf_mcp`.

Frame stress points remaining for native subgraphs and future fork/gather:

- `RunState.current_frame_id` remains the selected execution cursor even though
  concurrent foreach now schedules multiple child frames. Native subgraphs
  must preserve that cursor model while owning a nested child execution scope.
- `ExecutionFrame.metadata` has typed foreach access paths, but subgraphs still
  need typed child-workflow ownership and completion metadata rather than new
  ad hoc dictionary fields.
- Subgraph frames need child workflow identity/version/deployment binding, not
  just a generic metadata dictionary.
- `RunState.current_node_id` duplicates the current frame's node id for
  convenience. Any multi-frame scheduler must either keep that as a selected
  cursor or replace it with an explicit scheduling view.

## Why This Order

The MCP workflow authoring path is now usable enough for real testing. The next
bottleneck is runtime/platform correctness: optional per-use-site child
deployment overrides, protocol-native progress reporting, and stronger durable
run operations beyond stopped checkpoints. Concurrent foreach, native saved
child execution, and durable interrupt resume now supply scheduler/lineage
precedent. Those remaining pieces should come before adding more high-level
authoring sugar.
