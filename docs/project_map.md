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
For running and auditing external-agent workflow challenges, see
[`agent challenge evaluation`](runbooks/agent-challenge-evaluation.md).
For verified Python 3.14 dependency constraints and their removal criteria, see
[`dependency compatibility`](runbooks/dependency-compatibility.md).

## Packages

| Package | Purpose | Usual callers |
| --- | --- | --- |
| `wf_core` | Deterministic workflow kernel: models, validation, runtime, run state, traces, interrupts, foreach, and path/state operations. | Runtime users, `wf_authoring`, workflow adapters. |
| `wf_authoring` | Ergonomic workflow construction: `@node`, `NodeSpec`, builder DSL, conditions, path helpers, reusable ops, subgraph nodes. | Humans, tests, future LLM workflow builders. |
| `wf_api` | Workflow application surface over core/artifacts/platform: capabilities, drafts, artifacts, deployments, runs, and source/admin surfaces. | `wf_cli`, `wf_server`, JSON-RPC clients, future transports. |
| `wf_server` | Durable server composition boundary around `WorkflowApi` plus optional admin/source-registry surfaces. Owns the `wf-rpc-server` startup CLI/policy. | Transport packages and server startup code. |
| `wf_transport_rpc_http` | JSON-RPC-over-HTTP app/client and compatibility CLI shim. | Remote `wf` clients and local server smoke tests. |
| `wf_client` | Async-native Python client for capability discovery, local authoring, immutable artifacts, deployments, and durable runs. | Python applications and notebooks using a workflow server. |
| `wf_sources_mcp` | MCP-as-upstream-source implementation: ids, registry DTOs, auth/catalog stores, discovery, SDK client/facade, runtime pool, wrappers. | `wf_server`, broker glue, MCP source tests. |
| `wf_mcp` | MCP frontend/compatibility package: legacy `wf-mcp` entrypoints, broker glue, proxy/admin tools, and shims while extraction continues. | Compatibility callers and MCP transport work. |
| `wf_cli` | Command-line frontend over local or remote workflow APIs. | Humans, scripts, agent skills. |
| `wf_contract_manifest` | Tooling that normalizes the composed workflow OpenRPC document into the checked transport-neutral contract manifest and detects drift. | Python and TypeScript contract generation and tests. |
| `@lda/workflow-rpc` | Effect RPC client boundary plus generated compile-time inventory and raw wire types for all manifest operations. It includes a fail-closed representative JSON Schema-to-Effect translator; runtime decoders and supported operations remain authored subsets. | Web console, Hono server, future TypeScript workflow clients. |
| `@lda/presentation-sync` | Shared, bounded wire contract for ephemeral LAN presentation rooms. | Browser `@lda/console` and Hono `@lda/web-server`. |
| `@lda/console` | React console with a persistent routed shell, loopback connection flow, capability discovery and schema-generated direct-call playground, bounded capability-backed draft authoring with canonical mutation handling, and routed artifact/deployment/run exploration. | Browser users and the built `@lda/web-server` static host. |
| `@lda/web-server` | Hono API/static server that enforces the browser operation policy, proxies typed workflow reads, serves `console/dist`, and owns presentation room transport. | Browser `@lda/console` and local workflow operators. |

The TypeScript presentation synchronization boundary is deliberately narrow.
`@lda/web-server` owns room creation, membership, revision ordering, expiry,
presence, and termination. `@lda/console` owns storyboard and navigation
semantics and publishes only canonical hashes through
`@lda/presentation-sync`; no storyboard data or workflow operation enters the
room service. Browser workflow operations remain behind the Hono server and
can continue to reach a loopback-only workflow RPC server.

The console workspace boundary is `web/apps/console/src/workspace`. Its
`domain/` clients own capability, draft-workspace, and lifecycle read contracts;
route modules consume those clients through the evidence-aware read executor
instead of calling transport operation strings directly. `ConsoleShell` owns
the persistent connection header, lifecycle navigation, and operation-evidence
ledger while `/console/*` route modules own their read-only page projections.
The Discover route's capability playground uses the same write executor for
explicit, acknowledged direct calls. It resolves supported local JSON Schema
references for generated forms and retains bounded, redacted target-bearing
evidence; a direct call does not create workflow lifecycle records.
The selected-step authoring boundary keeps canonical bindings in
`src/wf_core/models/input_bindings.py`; the console's recursive expression
projection and controls live in
`web/apps/console/src/workspace/authoring/input-expression-editor.ts` and
`InputExpressionControl.tsx`. These editors emit one expression binding for a
constructed array or object rather than synthetic indexed targets.
`authoring-contract-models.ts` and `authoring-contract-client.ts` carry the
revision-scoped, backend-owned inventory used by the graph's derived Input,
State, Output, and Outcomes projections. `WorkflowContractInspector.tsx`
edits those workflow-level contracts through the existing focused draft
mutations; `AuthoringPathPicker.tsx` offers normal grouped choices first and an
explicit Advanced custom-path fallback. The inventory may advertise
node-scoped runtime context only for a selected step where conservative
execution-scope analysis proves it applicable. It does not make context a
permanent graph node or expose it as a final workflow-output source.

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
- `wf_api.models`: canonical transport-neutral request and result models shared
  by process-local surfaces and remote transports. Legacy `wf_mcp` DTOs are
  compatibility contracts, not a second source of truth.
- `wf_server.WorkflowServer`: durable workflow server composition object.
- `wf_transport_rpc_http.RpcWorkflowApiClient`: JSON-RPC client implementing
  the workflow/admin surfaces over HTTP.
- `wf_client.App`: transport-independent async Python facade over capabilities,
  authored workflows, saved artifacts, deployments, and durable runs.
- `wf_transport_rpc_http.create_rpc_app`: JSON-RPC HTTP adapter over an existing
  `WorkflowServer`.
- `wf_sources_mcp.McpRuntimePool`: persistent MCP source runtime for stateful
  upstream tools/resources/prompts.
- `wf_mcp`: MCP-specific frontend and compatibility package.
- `wf-mcp`: legacy/special-purpose MCP script from `pyproject.toml`.
- `wf-rpc-server`: preferred durable workflow server script for CLI/API clients,
  implemented by `wf_server.cli`.
- `python -m wf_contract_manifest write|check`: regenerate or verify
  `contracts/workflow-api.manifest.json` from the real composed workflow server.
- `pnpm --dir web --filter @lda/workflow-rpc contract:write|contract:check`:
  regenerate or verify the checked TypeScript wire inventory and raw types.
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
- `examples/browser_click_workflow/` is a serial browser-click workflow
  example with bounded before/after snapshots and full lifecycle tests.

### Python client walkthrough

The Python client is intended for an application that already has a running
workflow server. Hypothetically, an application that wants to turn a constant
capability into a durable run would use this complete call shape; the schema
arguments may be JSON Schema dictionaries or the application's schema model
values:

```python
from wf_client import App
from wf_authoring import input_from, input_value, output_to, state_path

app = App.from_http_jsonrpc("http://localhost:8765/rpc")
capability = await app.capability("wf.std.constant")
graph = app.new_workflow(
    "example",
    input_schema={"type": "object", "properties": {}},
    state_schema={"type": "object", "properties": {"value": {"type": "string"}}},
    output_schema={
        "type": "object",
        "properties": {"value": {"type": "string"}},
        "required": ["value"],
    },
)
step = graph.use(
    capability,
    id="constant",
    input=[input_value("value", "hello")],
    output=[output_to("value", state_path("value"))],
)
end = graph.end("ok", id="end_ok")
graph.set_entry_point(step)
graph.connect(step, "ok", end)
graph.set_output([input_from(state_path("value"), "value")])
validation = await graph.validate()
validation.raise_for_errors()
artifact = await graph.save(version=1)
run = await artifact.run({})
```

The graph is a local, mutable builder. `validate()` checks its structure locally
and then asks the server to validate the serialized plan. `save()` persists an
immutable artifact version; it does not deploy or execute the graph.
`artifact.run()` selects or creates a deployment, validates its source bindings,
and starts a durable run. The returned run is a loaded snapshot; call
`refresh()`, `resume()`, or bounded `trace(start=..., limit=...)` when more
server state is needed.

Draft workspaces are intentionally not part of `wf_client`. They are a separate
server/admin surface and must be explicitly enabled when composing a server.
- `examples/agent_challenges/` contains reusable opencode challenge harnesses
  for evaluating whether agents can use the public workflow CLI/server path.

## Documentation

- [`docs/thesis/system-design-implementation.md`](thesis/system-design-implementation.md)
  — formal thesis/system-design draft.
- [`docs/thesis/evidence-index.md`](thesis/evidence-index.md) — claim-to-evidence
  map for the thesis draft.
- [`docs/runbooks/agent-challenge-evaluation.md`](runbooks/agent-challenge-evaluation.md)
  — operator runbook for challenge trials, manual audits, and report
  interpretation.

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
