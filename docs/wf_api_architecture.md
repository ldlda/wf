# wf_api Architecture Boundary

`wf_api` is the process-local workflow application service layer. It is not just
a DTO wrapper around `wf_core`, and it is not an MCP transport package.

The package owns workflow-facing application operations that combine execution,
saved artifacts, deployment validation, authoring guidance, progressive payloads,
and run lifecycle policy into a stable API that CLI, MCP, and future HTTP
frontends can share.

## Responsibility Map

| Package | Responsibility |
| --- | --- |
| `wf_core` | Workflow execution semantics: graph models, runtime state, scheduler, path/state mapping, interrupts, subgraphs, foreach, and run-state codec. |
| `wf_artifacts` | Saved definitions and persistence contracts: workflow artifacts, deployments, draft workspaces, run records, checkpoints, artifact/deployment validation models. |
| `wf_platform` | Shared capability/source concepts and platform-facing contracts such as capability refs, source inventory models, documentation source models, and JSON schema helpers. |
| `wf_api` | Application workflows over core/artifacts/platform: capability discovery, wrapper hints, draft editing, artifact/deployment operations, run/resume operations, next actions, and progressive response shaping. |
| `wf_mcp` | MCP-specific transport, tool schemas, upstream MCP adapters, broker services, proxy/admin tools, config reload, and `WorkflowApi` context construction for MCP. |
| future `wf_http` | HTTP transport over `wf_api`, not a reimplementation of workflow business logic. |
| `wf_cli` | CLI frontend over `wf_api`; it may run locally against process-local stores or later target an HTTP backend. |

## What Belongs In wf_api

`wf_api` should contain code that is:

- protocol-neutral between MCP, CLI, and future HTTP
- workflow-application policy rather than low-level graph execution
- response shaping for human/LLM clients, such as compact list payloads and
  bounded trace slices
- authoring guidance, such as wrapper hints and next actions
- orchestration across `wf_core`, `wf_artifacts`, and `wf_platform`
- durable run lifecycle policy over `RunStore` and `WorkflowRuntimeRunner`

Examples that belong in `wf_api`:

- `WorkflowApi`
- `WorkflowCapabilityApi`
- `WorkflowDraftApi`
- `WorkflowArtifactApi`
- `WorkflowDeploymentApi`
- `WorkflowRunApi`
- wrapper hints
- next actions
- runtime dependency resolution
- saved subgraph preparation helpers
- run lifecycle helpers such as `persist_stopped_run()` and
  `validate_pinned_resume_environment()`

## What Does Not Belong In wf_api

`wf_api` must not contain:

- MCP SDK calls
- FastMCP tool/resource/prompt registration
- MCP content block models or MCP schema workarounds
- broker config file mutation
- upstream MCP session/runtime management
- proxy mounting or reload logic
- local process service construction that assumes `WfMcpService`
- scheduler/execution semantics that belong in `wf_core`
- persistence model definitions that belong in `wf_artifacts`

The hard import rule remains:

```text
wf_mcp -> wf_api is allowed
wf_api -> wf_mcp is forbidden
```

## WorkflowOperationContext

`WorkflowOperationContext` is the adapter seam that lets `wf_api` stay
transport-neutral.

Current shape:

```python
WorkflowOperationContext(
    artifact_store=...,
    draft_workspace_store=...,
    run_store=...,
    events=...,
    specs=...,
    runtime=...,
    live_sources=...,
)
```

Important rules:

- Source inventory goes through `context.specs.capability_sources`.
- Qualified node lookup goes through `context.specs.get_qualified_spec()`.
- Runtime execution goes through `context.runtime`.
- Workflow events go through `context.events.record_workflow_event()`.
- Optional live source checks go through `context.live_sources`.
- Stores are still optional for MCP/test compatibility, but durable API
  frontends should construct stricter contexts with required stores.

Do not add a catch-all `service` field to the context. If a domain API needs a
new dependency, add a narrow protocol or explicit field.

## Domain Services

`WorkflowApi` composes focused domain APIs:

```text
WorkflowApi
  capabilities: WorkflowCapabilityApi
  drafts: WorkflowDraftApi
  artifacts: WorkflowArtifactApi
  deployments: WorkflowDeploymentApi
  runs: WorkflowRunApi
```

These domain services are allowed to return `dict[str, Any]` payloads because
they define application-facing response contracts consumed by multiple
frontends. Internally, they should prefer typed models from `wf_core`,
`wf_artifacts`, and `wf_platform`, then serialize at the boundary.

## Relationship To wf_core

`wf_core` is lower-level than `wf_api`.

`wf_api` may:

- compile or validate workflow-facing requests into core/artifact models
- call runtime runners that execute core workflows
- shape run traces and diagnostics for clients

`wf_api` must not:

- decide scheduler semantics
- mutate `RunState` internals directly
- add graph node semantics
- encode MCP/client-specific behavior into core execution

If a behavior changes how workflows execute, it probably belongs in `wf_core`
or in an explicit runtime dependency injected into `wf_core`, not in `wf_api`.

## Relationship To wf_artifacts

`wf_artifacts` owns durable definitions and storage contracts. `wf_api` owns
operations over them.

Examples:

- `WorkflowArtifact`, `WorkflowDeployment`, `WorkflowRunRecord`, and
  `RunCheckpoint` belong in `wf_artifacts`.
- `create_artifact_from_plan`, `save_deployment`, `run_deployment`, and
  `resume_run` application flows belong in `wf_api`.

`wf_api` should not define parallel persistence models for the same durable
concepts. If a response needs a different shape, create response payload helpers
or next actions rather than duplicating the storage model.

## Relationship To wf_mcp

`wf_mcp` adapts MCP into `wf_api`.

Current MCP path:

```text
wf_mcp.workflow_surface.tools
  -> WorkflowApi(context_from_service(service))
  -> wf_api domain service
  -> WorkflowOperationContext protocol
  -> focused broker service / store / runtime implementation
```

MCP-specific concerns stay outside `wf_api`:

- tool schema names and safe tool names
- MCP resources/prompts-as-tools registration
- upstream MCP source liveness checks
- FastMCP notifications
- MCP content block normalization
- broker connection config/reload

## Future HTTP/API Boundary

A future HTTP API should reuse `WorkflowApi`, not copy MCP handlers.

Expected shape:

```text
wf_http route/controller
  -> WorkflowApi(required_store_context)
  -> wf_api domain services
```

The HTTP layer should own:

- request/response framework models
- auth/session policy
- API routing
- streaming/progress transport if needed
- construction of a durable `WorkflowOperationContext`

The HTTP layer should not own:

- workflow validation semantics
- run resume semantics
- wrapper hint policy
- deployment dependency validation

## Current Roadmap Implication

The next implementation work should follow this order:

1. Harden persisted run/resume contract tests in `wf_api`.
2. Introduce a stricter required-store context/factory for durable API surfaces.
3. Design the durable HTTP/API frontend around `WorkflowApi`.
4. Align CLI so it can target either local process stores or the future HTTP API.

Workflow primitives such as fork/gather and additional authoring sugar should
resume after the durability/platform boundary is stable.
