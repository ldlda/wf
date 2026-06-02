# Long-Lived Workflow API Boundary

Date: 2026-06-03

Status: design spec; implementation not started

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

wf_transport_http
  HTTP routes/controllers only
  request/response framework models
  auth/session/streaming transport policy

wf_transport_rpc
  optional JSON-RPC over HTTP/WebSocket adapter
  request/response envelope translation only

wf_api
  protocol-neutral workflow application operations
  no HTTP imports
  no MCP imports

wf_mcp
  MCP transport and upstream MCP integration
```

`wf_transport_http` should call `WorkflowApi` through the server composition. It
should not call `WfMcpService`.

HTTP is one transport adapter, not "the API." JSON-RPC over HTTP, JSON-RPC over
WebSocket, and possibly MCP can become sibling transports around the same
server/application boundary.

`wf_server` may initially be small. Its role is to prove that a non-MCP process
can construct the same application boundary with required stores and an explicit
runtime/source implementation.

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

If a reusable service currently lives under `wf_mcp.broker.service` but has no
MCP dependency, later slices may move or duplicate a protocol-neutral version.
Do not move large service sets in the first slice.

## Later Slice Pointers

### Slice 2: HTTP Transport Adapter

Add the first transport package, likely `wf_transport_http`.

This slice should expose a small route set over the existing server composition:

- health/status
- list/inspect capabilities
- run deployment
- inspect run
- read bounded trace
- resume run

It should not implement source provider management yet.

### Slice 3: CLI Remote Target

Allow `wf_cli` to target either:

- local process stores/runtime, current behavior
- remote long-lived API server

The CLI command surface should stay stable. Only context construction changes.

### Slice 4: JSON-RPC / WebSocket Transport

If HTTP REST starts becoming awkward for agents or streaming, add JSON-RPC as a
transport sibling rather than changing `WorkflowApi`.

Possible shapes:

- JSON-RPC over HTTP
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
2. HTTP framework: likely FastAPI for `wf_transport_http`, but the first server
   slice does not require choosing until route implementation starts.
3. RPC framework: undecided. JSON-RPC should be added only if it is clearly
   better for agent clients or streaming/progress.
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
