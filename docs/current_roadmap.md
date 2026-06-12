# Current Roadmap

This is the live, short roadmap. Completed implementation plans and long slice
history live under [`historical/`](historical/). Current architecture references:

- [`wf_api_architecture.md`](wf_api_architecture.md): workflow API, server,
  transport, and source package boundaries.
- [`project_map.md`](project_map.md): package map and entrypoints.
- [`wf_cli.md`](wf_cli.md): current CLI usage.

## Current Product Shape

```text
wf_cli
  -> local WorkflowApi or wf_transport_rpc_http.RpcWorkflowApiClient
  -> wf_server.WorkflowServer
  -> wf_api.WorkflowApi / admin surfaces
  -> wf_core / wf_artifacts / wf_sources_mcp
```

The durable product path is now `wf-rpc-server` plus neutral `wf_config` /
`wf_server` composition. The old `wf-mcp` script remains a legacy/special-purpose
MCP entrypoint and compatibility surface.

## Priority 1: Product Smoke And Status UX

The platform is usable enough to test as a product. Next work should focus on
clear operator feedback before adding more architecture.

- Completed: `wf status` is a compact read-only target/server status command,
  including durable run counts and the latest run summary when available.
- Completed: a real CLI smoke pass against `wf-rpc-server --config wf.config.json`
  is captured in
  [`2026-06-09 product smoke RPC CLI`](superpowers/research/2026-06-09-product-smoke-rpc-cli.md).
- Completed: `wf artifact inspect` now accepts `--version` as an alias for the
  positional version argument.
- Completed: `wf artifact delete <artifact_id> <version> --confirm` deletes
  unreferenced artifact versions and rejects versions still referenced by
  deployments. Implementation:
  [`wf artifact delete`](historical/superpowers/plans/2026-06-09-wf-artifact-delete.md).
- Completed: `wf draft delete <workspace_id> --confirm` exposes existing draft
  workspace deletion as a safe CLI command. Implementation:
  [`wf draft delete CLI/RPC`](historical/superpowers/plans/2026-06-09-wf-draft-delete-cli-rpc.md).
- Completed: bounded RPC CLI smoke runbook with cleanup commands:
  [`RPC CLI smoke runbook`](runbooks/rpc-cli-smoke.md).
- Completed: automated RPC CLI smoke example:
  [`RPC CLI smoke example`](historical/superpowers/plans/2026-06-09-rpc-cli-smoke-example.md).
- Next docs/ergonomics cleanup: make `cap call` output safer for humans without
  changing default JSON semantics. Implementation:
  [`cap call output safety`](historical/superpowers/plans/2026-06-09-cap-call-output-safety.md).
- Keep status read-only; do not mutate registry, auth, config, or stores.

## Priority 2: Durable Run/Resume Hardening

The v1 durable run and resume path exists, including persisted interrupted runs,
bounded trace reads, dependency revalidation, and process-rebuild resume tests.
Remaining hardening should focus on correctness under real server use.

- Completed: same-process `resume_run` calls are serialized per run id.
  Implementation:
  [`resume run concurrency guard`](historical/superpowers/plans/2026-06-09-resume-run-concurrency-guard.md).
- Completed: store-level locking/transaction expectations are documented for
  current file stores and future transactional stores:
  [`store transaction boundary`](superpowers/specs/2026-06-09-store-transaction-boundary.md).
- Completed: paged `wf run list` exposes compact persisted stopped-run
  summaries without trace or checkpoint state. Implementation:
  [`run list API/RPC/CLI`](historical/superpowers/plans/2026-06-11-run-list-api-rpc-cli.md).
- Preserve existing semantics: broken pinned dependencies return blocked
  readiness and diagnostics; ordinary live tool/source failures are failed runs,
  not implicit pauses.
- Active specs:
  - [`persisted run/resume contract`](superpowers/specs/2026-06-03-persisted-run-resume-contract.md)
  - [`durable workflow runs and resume`](superpowers/specs/2026-05-26-durable-workflow-runs-and-resume-design.md)

## Priority 3: Source/Auth/Config Polish

Source registry, neutral MCP source config, role-specific stores, and local/dev
auth admin are implemented. The next work is polish, not new broad surfaces.

- Keep config bootstrap separate from mutable store-backed source registry state.
- Keep auth payload values write-only; display summaries must show metadata and
  payload keys only.
- Keep role-specific stores filesystem-only until a real SQL/secret-manager slice
  is planned.
- New source families should follow the generic runtime source lifecycle rather
  than being forced through MCP `ConnectionConfig`:
  [`runtime source lifecycle`](superpowers/specs/2026-06-09-runtime-source-lifecycle.md).
- Completed: static config `kind: "python"` sources can load trusted local
  `NodeSpec` registries and expose them through WorkflowServer. Implementation:
  [`static Python sources`](historical/superpowers/plans/2026-06-11-static-python-sources.md).
- Completed: `wf config validate` preflights neutral workflow config files,
  including config-relative path resolution and trusted static Python source
  imports. MCP sources are shape-validated only; live upstream checks remain a
  server/status concern.
- Completed: Python source operator docs and RPC integration coverage now prove
  `ops.py` source config, capability call, draft artifact creation, deployment,
  and workflow run. Runbook:
  [`Python source`](runbooks/python-source.md).
- Completed: server startup policy moved to `wf_server.cli`; JSON-RPC HTTP
  remains in `wf_transport_rpc_http`:
  [`server CLI and transport boundary`](superpowers/specs/2026-06-10-server-cli-transport-boundary.md).
- Deferred auth work: OAuth/OIDC, production secret manager integration,
  encrypted-at-rest file format, and provider-specific display models.
- Active specs:
  - [`workflow config targets and sources`](superpowers/specs/2026-06-03-workflow-config-targets-and-sources.md)
  - [`store-backed source registry`](superpowers/specs/2026-06-03-store-backed-source-registry-design.md)
  - [`runtime source lifecycle`](superpowers/specs/2026-06-09-runtime-source-lifecycle.md)
  - [`server CLI and transport boundary`](superpowers/specs/2026-06-10-server-cli-transport-boundary.md)
  - [`auth/source secrets boundary`](superpowers/specs/2026-06-06-auth-source-secrets-boundary.md)

## Priority 4: MCP Package Split Finish Line

`wf_sources_mcp` now owns upstream MCP source implementation pieces: ids,
registry DTOs, auth/catalog stores, discovery/catalog DTOs, SDK adapter/facade,
runtime pool, schema helpers, tool events, wrappers, and adapter lookup.

Next split work should be selective:

- Avoid new dependencies on the combined `wf_mcp` facade from durable server or
  transport packages.
- Keep `wf_mcp` compatibility shims until callers are retired deliberately.
- Move only pieces with clear package ownership. Do not move proxy/UI/App
  metadata support into workflow transports by accident.
- MCP UI/App metadata remains source/proxy metadata only; do not advertise MCP
  Apps/widget support through durable workflow transports yet.

## Priority 5: Runtime/Core Polish Later

Core runtime foundations for native subgraphs, concurrent foreach, lineage state,
and durable stopped-run resume exist. Return here after product/server UX is
stable.

- Native subgraph polish: optional per-use-site child deployment overrides and
  clearer child trace inspection.
- Concurrent foreach polish: reuse barrier/lineage machinery for future
  fork/gather.
- Protocol-native progress: investigate MCP tasks/progress or WebSocket/SSE only
  after polling `wf run watch` proves insufficient.
- OpenAPI sources: continue from [`openapi capability sources`](openapi_capability_source.md)
  when a real non-MCP source is needed.

## Recently Completed Platform Milestones

- `WorkflowApiSurface` is the protocol-neutral workflow operation contract.
- `wf_transport_rpc_http` exposes local/static and MCP-backed `WorkflowServer`
  over JSON-RPC HTTP.
- `wf` can target local or remote workflow APIs for capability discovery, draft
  authoring, artifact/deployment operations, run, inspect, bounded trace,
  resume, and `cap call`.
- Desired source registry reads, mutations, and explicit apply/reload are exposed
  through JSON-RPC and CLI.
- Neutral `wf_config` can express MCP sources, role-specific filesystem stores,
  and client/server target separation.
- `wf config migrate-mcp` converts legacy broker configs to neutral workflow
  config without mutating the original.
- `McpRuntimePool` is shared for stateful upstream MCP operations and has
  JSON-RPC E2E coverage proving session reuse across workflow runs.
- `wf run watch` provides polling-based progress UX.
- CLI expected errors are compact by default; `wf --verbose ...` preserves raw
  tracebacks for debugging.

## Historical References

- [`wf_api extraction roadmap`](historical/superpowers/plans/2026-06-01-wf-api-extraction-roadmap.md)
- [`source registry next slices`](historical/superpowers/plans/2026-06-03-source-registry-next-slices.md)
- [`MCP source connection seam`](historical/superpowers/plans/2026-06-07-mcp-source-connection-seam.md)
- [`MCP runtime RPC session reuse E2E`](historical/superpowers/plans/2026-06-08-mcp-runtime-rpc-session-reuse-e2e.md)
