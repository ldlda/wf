# Long-Lived Workflow API Boundary

Date: 2026-06-03

Status: Slices 1-5 implemented. `wf_server` provides
`build_local_static_workflow_server`; `wf_mcp.broker.server` can adapt MCP
broker config/services into the neutral `WorkflowServer`; `wf_transport_rpc_http`
provides JSON-RPC methods and client support; `wf_cli` has target-aware context;
and `wf_config` owns neutral config models. WebSocket transport, auth,
streaming/progress, database backend, and live source hot reload remain future
work.

Related:

- [wf_api architecture](../../wf_api_architecture.md)
- [wf_mcp architecture](../../wf_mcp_architecture.md)
- [Persisted run/resume contract](./2026-06-03-persisted-run-resume-contract.md)
- [Current roadmap](../../current_roadmap.md)

## Purpose

Define the boundary for a long-lived workflow API process that clients can
connect to and use for workflow authoring, deployment, run, inspect, trace, and
resume operations.

The goal is not "HTTP for its own sake." The goal is a durable server process
that can run workflows as well as the current local CLI/MCP process, while
keeping workflow semantics in `wf_api` and transport/session details outside it.

## Core Decision

Introduce a process-host layer before introducing HTTP details.

Recommended package shape:

```text
wf_server
  long-lived process composition
  required store construction
  source/catalog/runtime/event implementation wiring
  durable WorkflowOperationContext construction

wf_transport_rpc_http
  JSON-RPC 2.0 over HTTP endpoint/controller
  request/response envelope translation
  auth/session/streaming transport policy

wf_api
  protocol-neutral workflow application operations
  no HTTP imports
  no MCP imports

wf_mcp
  MCP transport and upstream MCP integration
```

`wf_mcp` is intentionally treated as a combined compatibility package in this
diagram, not as the desired final boundary. It currently contains two different
roles:

- MCP as a client transport: an MCP client connects to workflow/admin surfaces.
- MCP as an upstream source provider: workflows discover and invoke external MCP
  servers as capability sources.

Those roles should separate over time. A future `wf_transport_mcp` can expose
the same `WorkflowServer` / `wf_api` surfaces to MCP clients, while a future
`wf_sources_mcp` can own upstream MCP discovery, sessions, tool invocation,
resource/prompt access, and FastMCP-specific provider behavior.

### MCP Source Provider Package Direction

`wf_sources_mcp` is the target package for MCP-as-upstream-source code. It should
own behavior required to turn external MCP servers into workflow capability
sources:

- MCP auth interpretation for stdio/http transports
- desired MCP source registry models and conversion into runtime connection
  records
- source catalog snapshot cache stores
- upstream discovery and tool/resource/prompt invocation adapters
- stateful MCP runtime/session management
- FastMCP-specific compatibility behavior

`wf_sources_mcp` must not own workflow lifecycle APIs, MCP frontend tool schemas,
or old `wf-mcp` entrypoint behavior. Those belong to `wf_api`, transport
packages, or compatibility shims.

First slices should move leaf modules only and leave `wf_mcp` re-export shims:

1. Complete: MCP auth helpers and focused auth/catalog stores moved to
   `wf_sources_mcp`, with `wf_mcp` shims preserved.
2. Complete: MCP source registry models/conversion moved to `wf_sources_mcp.source_registry`, with `wf_mcp.source_registry` retained as a shim.
3. Complete: upstream MCP catalog/discovery DTOs moved to `wf_sources_mcp.catalog`, with `wf_mcp.capabilities` and `wf_mcp.catalog.models` retained as shims.
4. Complete: upstream SDK protocol/result types moved to `wf_sources_mcp.sdk`, with `wf_mcp.sdk` and `wf_mcp.runtime.protocols` retained as shims.
5. Complete: MCP SDK conversion helpers moved to `wf_sources_mcp.sdk.converters`, with `wf_mcp.sdk.converters` retained as a shim.
6. Complete: shared MCP session opener in `wf_sources_mcp.client`. One-shot
   adapter (`McpSdkAdapter`) and persistent runtime
   (`PersistentSessionFactory`) both use `open_mcp_session`.
7. Complete: persistent MCP runtime (`PersistentMcpSession`,
   `PersistentSessionFactory`, `McpRuntimePool`,
   `connection_runtime_fingerprint`) moved to `wf_sources_mcp.runtime`, with
   `wf_mcp.runtime.*` retained as compatibility shims. Runtime remains
   tool-call-only. Next slice is moving `McpSdkAdapter` to
   `wf_sources_mcp.sdk.adapter`.
8. Upstream transport/discovery/session services.

Each slice should add import-direction tests so the new source-provider package
does not depend on `wf_mcp.workflow_surface`, `wf_mcp.admin_surface`,
`wf_mcp.server`, or `wf_mcp.proxy`. Temporary imports from broker model shims are
acceptable only when documented in the slice plan; the direction is to replace
them with protocol/DTO seams before moving runtime services.

`wf_transport_rpc_http` should call `WorkflowApi` through the server
composition. It should not call `WfMcpService`.

HTTP is one transport adapter, not "the API." JSON-RPC over HTTP, JSON-RPC over
WebSocket, and possibly MCP can become sibling transports around the same
server/application boundary. Server composition should be driven by the wider
neutral `wf_config` model, including source definitions; MCP broker config is a
legacy/source-specific input to normalize, not a permanent peer config family.

`wf_server` may initially be small. Its role is to prove that a non-MCP process
can construct the same application boundary with required stores and an explicit
runtime/source implementation.

## MCP UI/App Support Policy

MCP UI metadata is not workflow-server capability by itself. Upstream MCP tools
may expose `_meta.ui` / `ui://...` resources, but rendering those resources is a
host/frontend responsibility, not a workflow runtime responsibility.

Until a dedicated MCP frontend transport owns the full host behavior, do not
advertise MCP Apps/UI support to clients. Supporting it requires more than
passing metadata through:

- serving `ui://` resources and any dependent assets from a stable origin
- sandboxed iframe hosting
- a JSON-RPC `postMessage` / app bridge
- app-only tool visibility and calls
- CSP/domain policy
- widget state and teardown semantics

`wf_sources_mcp` / current upstream MCP source code may preserve UI metadata as
observed source metadata, but it must not imply that `wf_server` can render or
host widgets. `wf_transport_mcp` may later implement a real host bridge. Raw
MCP proxy/debug modes can expose upstream behavior explicitly, but that path is
not the durable workflow surface.

## Why Not Wrap WfMcpService

`WfMcpService` is still a compatibility facade for MCP broker concerns:

- connection config/reload
- upstream MCP adapter/session management
- catalog refresh
- content access
- event recording
- runtime execution
- source inventory

It is being decomposed into focused services, but its public shape still carries
MCP process assumptions. Building HTTP on top of it would recreate the coupling
that `wf_api` extraction just removed.

The long-lived API should depend on the same lower-level concepts as MCP, not on
the MCP facade itself.

## First Slice

First slice should be lightweight and local/static.

It should prove:

- a long-lived process can construct a durable `WorkflowApi`
- artifact, draft, and run stores are required up front
- a client can connect and call workflow operations
- deployment run/inspect/trace/resume semantics match local behavior
- no direct dependency on `WfMcpService`

Implementation status:

- Slice 1 complete: `wf_server.build_local_static_workflow_server()` constructs a durable
  `WorkflowApi` with required file-backed stores, local `wf.std`/`wf.recipes`
  sources, and a local runtime runner.
- Slice 2 complete: `wf_transport_rpc_http` provides JSON-RPC 2.0 over HTTP via
  `create_rpc_app(server)` and the `wf-rpc-server` CLI.
- Slice 3 complete: `wf_cli` supports target-aware context with `--local`,
  `--url`, and `--timeout` overrides, and works with remote RPC targets for
  capability and run commands.
- Slice 4 complete: `wf_mcp.broker.server.build_workflow_server_from_config()`
  returns a neutral `WorkflowServer` backed by MCP broker runtime services,
  including source registry admin and platform admin surfaces.
- Slice 5 complete: `wf-rpc-server --mcp-config <path>` starts JSON-RPC over an
  MCP-backed `WorkflowServer`; `--store-root` remains local/static-only.

Model slice complete when `wf_config.server.sources[]` accepts `kind: "mcp"`
entries. The next slice converts those neutral source entries into MCP
broker runtime connections and server composition.

Runtime bridge complete when `wf-rpc-server --config <path>` can compose an
MCP-backed server from neutral `server.sources[]` entries. `--mcp-config`
remains a compatibility alias until existing users migrate.

First slice should not include:

- live upstream MCP source management
- OpenAPI dynamic source registration
- auth beyond a stub or disabled mode
- streaming/progress
- transactional database backend
- multi-worker concurrency guarantees
- config hot reload

Acceptable first-slice source support:

- broker-local workflow stdlib capabilities such as `wf.std`
- saved workflow artifacts/deployments from the configured store
- explicitly registered local NodeSpecs when the server process starts

This is enough to prove the server can run real workflows and durable resumes
without dragging upstream source lifecycle into the first implementation.

## Runtime and Store Boundary

The server process should construct:

```text
WorkflowStores
  artifact_store
  draft_workspace_store
  run_store

WorkflowOperationContext
  artifact_store
  draft_workspace_store
  run_store
  events
  specs
  runtime
  live_sources=None or local-only checker

WorkflowApi
```

The context must pass `require_workflow_stores()` before being exposed through
the long-lived API.

Current config exposes one default `server.store` root. The server then fans it
out into workflow stores, auth records, source registry state, and catalog/cache
state. That is acceptable for the first durable server path, but the boundary
should not assume every persistence role always shares one backend.

Future config should support optional role-specific store overrides:

```text
server.store              default for every missing role
server.stores.workflow    artifacts, deployments, drafts, runs, traces
server.stores.auth        auth records or secret-manager references
server.stores.sources     desired source registry entries
server.stores.catalog     source catalog/cache snapshots
```

The compatibility rule is: if a role store is absent, use `server.store`. First
implementation should keep overrides filesystem-only; SQL, object storage, and
secret-manager adapters are later backend implementations.

The first server runtime may reuse existing implementation classes when they do
not require MCP-specific behavior. If reuse would require constructing
`WfMcpService`, that is the wrong dependency direction.

## Transport Contract

Every transport should follow the same shape:

```text
transport request
  -> decode/validate transport envelope
  -> call WorkflowApi method
  -> encode transport response
```

Transport adapters own:

- route names, method names, or JSON-RPC method names
- request parsing
- response serialization
- auth/session headers or connection identity
- streaming/progress mechanics

Transport adapters must not own:

- deployment validation semantics
- run/resume state transitions
- trace paging semantics
- wrapper hint policy
- source dependency validation

## Client Contract

Clients should be able to perform the same workflow lifecycle remotely that they
can perform locally:

```text
list/inspect capabilities
create/patch/validate draft workspace
save artifact
save/validate deployment
run deployment
inspect run
read bounded trace
resume interrupted run
delete deployment
```

Response payloads should preserve current `wf_api` semantics:

- list operations stay compact
- inspect operations return detail
- run responses return compact status plus trace metadata
- trace entries require explicit bounded range
- interrupted runs expose resume next actions
- blocked resume returns diagnostics without consuming input

Transport field names may differ only when transport conventions require it.
They must not change workflow status meanings.

## Error and Failure Semantics

The long-lived server must preserve the persisted run/resume contract:

- invalid deployment dependencies before start return `unrunnable`
- completed, failed, and interrupted stopped states are persisted
- only interrupted runs can resume
- broken pinned dependencies before resume return `blocked`
- dead live tools/sources fail the run; they do not become implicit interrupts

First slice can ignore live source death because it does not include live
upstream sources. Later slices must preserve the same no-implicit-pause rule.

## Package Boundary Rules

Hard rules:

- `wf_api` must not import transports, `wf_server`, or `wf_mcp`.
- transport packages may import `wf_api` and `wf_server`.
- `wf_server` may import `wf_api`, `wf_artifacts`, `wf_platform`, and selected
  reusable implementation services.
- `wf_server` should not import `wf_mcp.broker.WfMcpService`.
- `wf_mcp` may continue constructing `WorkflowApi` through its existing
  MCP-specific context adapter.
- A future MCP transport mounted through `wf_server` must still keep upstream
  MCP source execution separate from transport request handling.
- Do not add new generic server or transport code that depends on the combined
  `wf_mcp` facade. If it needs MCP-specific upstream behavior, isolate that as a
  source-provider adapter; if it needs to expose workflow operations to MCP
  clients, isolate that as a transport adapter.

If a reusable service currently lives under `wf_mcp.broker.service` but has no
MCP dependency, later slices may move or duplicate a protocol-neutral version.
Do not move large service sets in the first slice.

## Later Slice Pointers

### Slice 2: JSON-RPC HTTP Transport Adapter

Add the first transport package as JSON-RPC 2.0 over HTTP, likely
`wf_transport_rpc_http`.

This is preferred over REST for the first remote CLI/server path because CLI and
agent clients want stable operation names more than resource-shaped URLs. The
method names should be dotted strings, matching the mental model already used by
MCP/admin tool names without inheriting MCP's dynamic tool-list behavior.

Proposed initial method names:

```text
workflow.capabilities.list
workflow.capabilities.inspect
workflow.drafts.create_from_capability
workflow.drafts.patch
workflow.drafts.validate
workflow.artifacts.save
workflow.deployments.save
workflow.deployments.validate
workflow.runs.start
workflow.runs.inspect
workflow.runs.trace
workflow.runs.resume
```

This slice should expose a small method set over the existing server
composition:

- health/status
- list/inspect capabilities
- run deployment
- inspect run
- read bounded trace
- resume run

It should not implement source provider management yet.

Implementation status:

- `wf_transport_rpc_http.create_rpc_app(server)` exposes a fixed JSON-RPC
  method set over an existing `wf_server.WorkflowServer`.
- `wf-rpc-server --store-root <path>` and `wf-rpc-server --config <path>` start
  the local/static server over `/rpc`.
- Remote `wf` CLI targeting is implemented through `wf_config` and target-aware
  context in `wf_cli`.
- Auth, streaming/progress, and live upstream MCP source management remain
  future work.

Preferred implementation dependency:

```bash
uv add fastapi-jsonrpc uvicorn
```

`fastapi-jsonrpc` is the recommended server library for this slice because it
keeps JSON-RPC 2.0 dispatch, errors, and docs near FastAPI/Pydantic instead of
requiring a local hand-rolled dispatcher.

Client-side CLI code can use `httpx` directly for now. A typed client wrapper
can be added when the method set stabilizes.

Guardrails:

- Do not dynamically register saved workflows as JSON-RPC methods.
- Do not add a JSON-RPC equivalent of MCP `tools/list` as the primary execution
  surface.
- Do not require client session state to run or resume workflows.
- Keep durable state addressed by explicit ids: `artifact_id`, `deployment_id`,
  `run_id`.
- Keep trace reads bounded by explicit range.
- Define request/response models explicitly with Pydantic; do not pass raw
  arbitrary dicts through the transport layer when a stable request shape is
  known.

### Slice 3: CLI Remote Target

Allow `wf_cli` to target either:

- local process stores/runtime, current behavior
- remote long-lived API server

The CLI command surface should stay stable. Only context construction changes.

### Slice 4: WebSocket Transport

If JSON-RPC over HTTP starts becoming awkward for streaming/progress, add a
WebSocket transport sibling rather than changing `WorkflowApi`.

Possible shapes:

- JSON-RPC over WebSocket
- future MCP transport over the same server-owned `WorkflowApi`

### Slice 5: Source Providers

Add explicit source-provider interfaces for long-lived server use.

Possible providers:

- static local NodeSpecs
- saved workflow capability sources
- OpenAPI capability source catalogs
- upstream MCP connection catalogs

This slice should avoid making "source" mean "MCP connection." MCP is one
source provider, not the source model.

Future package direction:

```text
wf_transport_mcp
  exposes WorkflowServer / wf_api operations to MCP clients

wf_sources_mcp
  consumes upstream MCP servers as workflow capability sources

wf_mcp
  compatibility package until old MCP entrypoints can shrink or retire
```

Current MCP-backed server status:

- MCP-backed `WorkflowServer` construction is implemented.
- `wf-rpc-server --mcp-config <path>` can serve JSON-RPC over that server.
- Source registry read/mutation APIs are reachable remotely when the target
  exposes `source_registry_admin`.
- Boundary caveat: the first `--mcp-config` hook intentionally proved the
  product path quickly, but it currently makes the transport CLI import
  `wf_mcp.broker`. That violates the original transport-package boundary and
  the existing import-direction guard. Treat this as a cleanup slice, not the
  desired final shape. The intended cleanup is to widen `wf_config` so MCP
  sources are configured through `server.sources[]`, with `wf_mcp.config.json`
  handled as compatibility input.

Next implementation slices should be:

1. Wider `wf_config` source model. Add an MCP source config variant under
   `server.sources[]` that can express the current broker connection shape:
   source id, provider/account/profile, `locked` / `seed` ownership, stdio/http
   transport, auth reference, enabled flag, and metadata. Keep legacy
   `wf_mcp.config.json` parsing as a compatibility adapter into the wider
   config, not as the future primary shape.
   `McpSourceRegistryEntry` already expresses most of this shape. The
   `locked` / `seed` policy currently lives on legacy
   `ConnectionConfig.source_config_ownership`; migrate that as a neutral source
   ownership/config policy field, not as a connection-specific name.
2. Transport package boundary cleanup. Keep JSON-RPC method/app/client modules
   transport-only. After `wf_config` can describe MCP sources, `wf-rpc-server
   --config ...` should compose MCP-backed sources from neutral config and the
   `--mcp-config` path can become deprecated/legacy.
   Completed when `tests/wf_transport_rpc_http/test_import_direction.py` passes
   and the RPC transport CLI imports only `wf_config`, `wf_server`, and transport
   modules for server construction.
3. Legacy MCP config migration. Provide an explicit converter from old
   `wf_mcp.config.json` into `WorkflowConfigFile`: `store_root` maps to
   `server.store` (`StoreConfig` is already a discriminated union; currently
   only `kind: "filesystem"` exists), and each legacy connection maps to a
   `kind: "mcp"` source. Preserve `source_config_ownership` as the neutral
   `ownership` field. Normalize old HTTP-like transport metadata
   (`http`, `streamable-http`, `streamable_http`, `sse`) into the neutral HTTP
   MCP source transport while preserving compatibility metadata where needed.
   `sse` remains legacy/deprecated, but conversion support is intentional
   because FastMCP can still expose it.
   Completed when `wf config migrate-mcp <legacy> --output <workflow-config>`
   writes a neutral config that can be used by `wf-rpc-server --config`.
4. Manual product smoke with the real CLI/server commands. Record UX/runtime
   gaps before broadening architecture.
5. Completed: source registry apply/reload semantics. Registry mutation updates
   desired persisted state, and explicit apply reconciles that state into the
   current server connection/source graph without mutating config files.
6. Completed: persisted resume across server restart. The MCP-backed JSON-RPC
   regression rebuilds a neutral-config server from the same stores, inspects an
   interrupted run, and resumes it from the stored checkpoint and pinned
   dependency environment.

### Slice 6: Auth and Tenancy

Define who can read/write artifacts, deployments, runs, and auth records.

Do not store upstream credentials as plain JSON in production mode. The local
file store can remain a development backend.

### Slice 7: Streaming and Progress

Expose long-running run progress through a protocol-native channel:

- HTTP streaming/SSE/WebSocket for HTTP/RPC transports
- MCP progress/tasks for MCP if practical

Do not bloat `run_deployment` responses with full traces or live logs.

### Slice 8: Transactional Store Backend

Add SQLite/Postgres or another transactional backend for run records,
checkpoints, artifacts, deployments, and possibly catalogs.

This slice should handle:

- compare-and-swap resume
- multi-process safety
- atomic writes
- retention policy

### Slice 9: Live Upstream MCP Sources

Add upstream MCP source management to the long-lived server only after the local
server path is proven.

This needs explicit policies for:

- connection lifecycle
- auth records
- catalog refresh
- source liveness
- session failure
- side-effectful tool calls

## Open Questions

1. Package name: `wf_server` is the recommended process-composition package,
   but the exact name can change before implementation.
2. HTTP framework: likely FastAPI under `fastapi-jsonrpc`.
3. RPC framework: use `fastapi-jsonrpc` for the first JSON-RPC-over-HTTP slice
   unless evaluation finds a blocking issue.
4. Source-provider extraction: some reusable code currently lives in
   `wf_mcp.broker.service`; first slice should avoid moving it unless a small
   dependency-free helper is obviously needed.
5. Storage backend: first slice can use file stores; production remote API needs
   a transactional backend later.

## Non-Goals

- Do not redesign `WorkflowApi`.
- Do not move MCP upstream session management into `wf_api`.
- Do not make transport routes call `WorkflowSurfaceHandlers`.
- Do not require dynamic tools to represent saved workflows.
- Do not implement retry/timeout policy.
- Do not treat external source failure as a pause.
- Do not implement fork/gather or new workflow primitives in this server slice.

## Success Criteria

First implementation plan should be considered successful when:

- a process-local server composition can construct `WorkflowApi` without
  `WfMcpService`
- required stores are enforced
- a connected client can run a deployment and inspect/read trace for the run
- persisted run semantics match the local `WorkflowRunApi` tests
- docs clearly state which source capabilities are first-slice only and which
  are future work
