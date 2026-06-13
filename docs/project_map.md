# Project Map

This repository has workflow kernel, API/server, transport, source, CLI, examples,
and tests packages. The older MCP package still exists, but new durable client
paths should go through `wf_server` plus transport/source packages.

For the source-provider-specific map and source/tool/capability terminology, see
[`source_architecture.md`](source_architecture.md).
For source provider setup examples, see
[`source_provider_guide.md`](source_provider_guide.md).

For a presentation-oriented summary of the current product path and demo flow,
see [`workflow platform presentation`](add/2026-06-workflow-platform-presentation.md).

## Packages

| Package | Purpose | Usual callers |
| --- | --- | --- |
| `wf_core` | Deterministic workflow kernel: models, validation, runtime, run state, traces, interrupts, foreach, and path/state operations. | Runtime users, `wf_authoring`, workflow adapters. |
| `wf_authoring` | Ergonomic workflow construction: `@node`, `NodeSpec`, builder DSL, conditions, path helpers, reusable ops, subgraph nodes. | Humans, tests, future LLM workflow builders. |
| `wf_api` | Workflow application surface over core/artifacts/platform: capabilities, drafts, artifacts, deployments, runs, and source/admin surfaces. | `wf_cli`, `wf_server`, JSON-RPC clients, future transports. |
| `wf_server` | Durable server composition boundary around `WorkflowApi` plus optional admin/source-registry surfaces. Owns the `wf-rpc-server` startup CLI/policy. | Transport packages and server startup code. |
| `wf_transport_rpc_http` | JSON-RPC-over-HTTP app/client and compatibility CLI shim. | Remote `wf` clients and local server smoke tests. |
| `wf_sources_mcp` | MCP-as-upstream-source implementation: ids, registry DTOs, auth/catalog stores, discovery, SDK client/facade, runtime pool, wrappers. | `wf_server`, broker glue, MCP source tests. |
| `wf_mcp` | MCP frontend/compatibility package: legacy `wf-mcp` entrypoints, broker glue, proxy/admin tools, and shims while extraction continues. | Compatibility callers and MCP transport work. |
| `wf_cli` | Command-line frontend over local or remote workflow APIs. | Humans, scripts, agent skills. |

## Important Entry Points

- `wf_core`: public kernel facade for common runtime/model imports.
- `wf_core.runtime`: `execute_workflow`, `resume_workflow`, `step_workflow`,
  and async variants.
- `wf_core.models`: concrete Pydantic workflow model package.
- `wf_core.validation`: structural workflow validation.
- `wf_authoring`: public authoring facade.
- `wf_authoring.WorkflowBuilder`: graph construction.
- `wf_authoring.node`: typed Python function to `NodeSpec`.
- [`docs/wf_authoring_control_flow.md`](wf_authoring_control_flow.md): when to
  use `branch`, `handle`, `match`, `when`, and `choose`.
- `wf_api.WorkflowApi`: process-local workflow application facade.
- `wf_server.WorkflowServer`: durable workflow server composition object.
- `wf_transport_rpc_http.RpcWorkflowApiClient`: JSON-RPC client implementing
  the workflow/admin surfaces over HTTP.
- `wf_transport_rpc_http.create_rpc_app`: JSON-RPC HTTP adapter over an existing
  `WorkflowServer`.
- `wf_sources_mcp.McpRuntimePool`: persistent MCP source runtime for stateful
  upstream tools/resources/prompts.
- `wf_mcp`: MCP-specific frontend and compatibility package.
- `wf-mcp`: legacy/special-purpose MCP script from `pyproject.toml`.
- `wf-rpc-server`: preferred durable workflow server script for CLI/API clients,
  implemented by `wf_server.cli`.
- `wf_mcp.broker.WfMcpService.get_catalog()`: backend MCP catalog snapshots.
- `wf_mcp.broker.WfMcpService.get_planner_catalog()`: backend snapshots plus
  broker-local workflow sources such as `wf.std` and `wf.mcp`.

## Examples

- `examples/demo_workflow.py` contains the declared demo workflow and demo node
  registry used by `main.py` and workflow tests. It is intentionally outside
  `wf_core` so the kernel package does not carry fixture/demo code.
- `examples/authoring_control_flow.py` demonstrates `WorkflowBuilder.branch`,
  `handle`, `match`, `when`, `choose`, and `use_ref` with executable examples.
- `examples/wrapper_status_route.py` and `examples/wrapper_normalization.py`
  show two wrapper styles: routing on provider status fields, and converting
  provider status fields into workflow outcomes.
- `examples/mcp_workflow_surface.py` shows the fixture-style MCP workflow path:
  discover a backend tool, create a draft artifact, save a deployment, and run
  it while wiring the generated `ok` and `error` outcomes.
- `examples/rpc_cli_smoke.py` spawns `wf-rpc-server`, runs the bounded CLI
  lifecycle from the RPC CLI smoke runbook, and cleans up. Use
  `--keep-temp` to preserve the generated config/store on failure.

## Tests

- `tests/authoring`: builder, node decorator, ops, async runtime, subgraph, and
  demo workflow comparisons.
- `tests/wf_mcp`: MCP SDK adapter, broker, proxy, storage, CLI, and
  naming behavior.
- `tests/rewrite`: local rewrite/port experiments that should keep exercising
  real user ergonomics.
- `tests/fixtures`: test-only helper servers and fixtures.

## Verification Commands

```powershell
uv run --with pytest pytest -q
uv run ruff check src tests main.py examples
uv run basedpyright src\wf_core tests\authoring tests\rewrite examples main.py --level error
```

Use `uv run --env-file .env --with pytest pytest -q` when live MCP-backed tests
need local environment configuration.

## Where To Add Things

- Add new executable workflow semantics in `wf_core.runtime` / `wf_core.runtime.ops`.
- Add new graph/model syntax in `wf_core.models`, then validate it in
  `wf_core.validation`.
- Add author convenience helpers in `wf_authoring`, not `wf_core`.
- Add upstream MCP source/provider behavior in `wf_sources_mcp`.
- Keep `wf_mcp` changes limited to MCP frontend/broker/proxy compatibility
  unless the work is explicitly retiring old callers.
- Add durable workflow server behavior in `wf_server` or transport packages, not
  the legacy `wf-mcp` entrypoint.
- Add broker-local workflow utilities as `WfMcpService` spec sources, not as
  fake MCP connections.
- Add runnable examples in `examples`.
- Add test-only servers or helpers in `tests/fixtures`.
