# Current roadmap

This roadmap records the product shape, active implementation order, and
constraints that must survive future work. Completed narratives and executable
plans live under [`historical/`](historical/).

Use these references for orientation:

- [`project_map.md`](project_map.md): package map and entry points
- [`wf_api_architecture.md`](wf_api_architecture.md): application programming
  interface (API), server, transport, and source boundaries
- [`wf_core_architecture.md`](wf_core_architecture.md): workflow model and
  runtime architecture
- [`wf_cli.md`](wf_cli.md): current command-line interface (CLI) usage

## Current product shape

The durable product path uses a neutral server composition behind local or
remote clients:

```text
wf_client / wf_cli / web console
  -> local WorkflowApi or JSON-RPC client
  -> wf_server.WorkflowServer
  -> wf_api application and administration surfaces
  -> wf_core / wf_artifacts / source providers
```

`wf-rpc-server` is the durable remote entry point. The old `wf-mcp` entry point
remains a legacy or special-purpose Model Context Protocol (MCP) surface.

The Python client covers capability discovery, local graph authoring, remote
validation, immutable artifact save, deployment selection, and durable runs.
Draft workspaces remain a separate administration surface. The primary saved
workflow lifecycle stays:

```text
author -> validate -> save artifact -> deploy -> run -> inspect or resume
```

## Active runtime sequence

The next three slices build on the foreach control-region, scheduler, lineage,
and barrier foundations in this order.

### 1. Review and merge structured runtime context

The implementation plan is ready and its feature branch is under review:

- [`structured runtime context design`](superpowers/specs/2026-09-04-structured-runtime-context-design.md)
- [`structured runtime context implementation plan`](historical/superpowers/plans/2026-09-04-structured-runtime-context.md)

This slice gives runtime code, expressions, validation, and authoring references
one model for run data and same-scope foreach activations. Subgraphs continue to
cross an explicit input boundary rather than inheriting a parent's context.

### 2. Add a persisted run step budget

After structured context is stable, implement the proposed run-wide limit:

- [`run step budget design`](superpowers/specs/2026-09-04-run-step-budget-design.md)

The budget must cover every frame and subgraph scope in one run, survive
checkpoint and resume, and stop valid but non-terminating graph cycles with a
clear runtime failure.

### 3. Implement explicit fork and gather

Reuse the scheduler, activation, lineage, and reducer-aware barrier machinery:

- [`ADR-0006: explicit fork and topology-driven gather`](adr/0006-explicit-fork-and-topology-driven-gather.md)

Outcomes continue to choose one transition. Forks create concurrent branch
activations. Gathers wait on declared incoming topology, merge compatible
lineages according to policy, and emit one continuation.

## Runtime work after fork and gather

Defer these slices until the active sequence exposes a concrete need:

- Add optional per-use child deployment overrides and clearer child trace
  inspection for native subgraphs
- Investigate protocol-native progress or streaming only if polling through
  `wf run watch` proves inadequate
- Continue [`OpenAPI capability sources`](openapi_capability_source.md) when a
  real non-MCP source requires them

## Durable platform constraints

These rules describe current boundaries. New work should preserve them.

### Run and resume correctness

Persisted interrupted runs, bounded trace reads, dependency revalidation,
process-rebuild resume, and same-process resume serialization exist.

- Broken pinned dependencies produce blocked readiness and diagnostics
- Live tool or source failures produce failed runs, not implicit pauses
- Store-level concurrency must follow the
  [`store transaction boundary`](superpowers/specs/2026-06-09-store-transaction-boundary.md)
- The current contracts are
  [`persisted run and resume`](superpowers/specs/2026-06-03-persisted-run-resume-contract.md)
  and
  [`durable workflow runs`](superpowers/specs/2026-05-26-durable-workflow-runs-and-resume-design.md)

### Source, authentication, and configuration boundaries

Source registry state, static configuration, runtime source sessions, and
authentication records remain separate concerns.

- Keep configuration bootstrap separate from mutable source registry state
- Keep secret payload values write-only; inspection may expose metadata and
  payload keys
- Keep role-specific stores filesystem-backed until a real database or secret
  manager slice is planned
- Add new source families through the generic
  [`runtime source lifecycle`](superpowers/specs/2026-06-09-runtime-source-lifecycle.md)
  instead of forcing them through MCP connection configuration
- Preserve the
  [`server and transport boundary`](superpowers/specs/2026-06-10-server-cli-transport-boundary.md)

Current source contracts:

- [`workflow configuration and sources`](superpowers/specs/2026-06-03-workflow-config-targets-and-sources.md)
- [`store-backed source registry`](superpowers/specs/2026-06-03-store-backed-source-registry-design.md)
- [`authentication and source secrets`](superpowers/specs/2026-06-06-auth-source-secrets-boundary.md)

### MCP package ownership

`wf_sources_mcp` owns upstream MCP source implementation. Keep durable server
and transport packages independent of the combined `wf_mcp` facade. Retain
compatibility shims only for real callers, move code only when ownership is
clear, and keep MCP application or widget metadata out of durable workflow
transports.

## Established runtime baseline

The active sequence can assume these foundations:

- Native subgraph scopes and durable return to the parent node
- Concurrent foreach with activation barriers and reducer-aware lineage merges
- Validated foreach back-edges with one static control region per node use
- Durable stopped-run inspection and resume
- Python client reconstruction of capabilities, artifacts, deployments, and
  runs through the API

The current foreach return contract is
[`foreach back-edge design`](superpowers/specs/2026-09-04-foreach-back-edge-design.md).

## Historical entry points

Use these completed roadmaps when implementation history matters:

- [`API extraction roadmap`](historical/superpowers/plans/2026-06-01-wf-api-extraction-roadmap.md)
- [`source registry slices`](historical/superpowers/plans/2026-06-03-source-registry-next-slices.md)
- [`MCP source connection seam`](historical/superpowers/plans/2026-06-07-mcp-source-connection-seam.md)
- [`MCP runtime session reuse`](historical/superpowers/plans/2026-06-08-mcp-runtime-rpc-session-reuse-e2e.md)
