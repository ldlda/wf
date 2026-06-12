# Thesis Outline

This is a writing scaffold for a thesis/report about the workflow platform. It
should guide the argument; it is not a changelog.

## Core Argument

Agent work should be represented as typed, durable workflows. The LLM should
plan and revise workflow structure, but a deterministic runtime should own
execution, state, validation, persistence, and source binding.

The short version:

> The LLM plans. The runtime executes. Source providers expose capabilities.
> Stores preserve durable workflow state.

## 1. Problem Statement

Current agent/tool systems often let the LLM directly orchestrate side effects
through ad hoc tool calls. This creates practical problems:

- weak validation before execution
- poor resumability after interruption or process restart
- hard-to-audit tool-call traces
- limited reuse of successful procedures
- unclear boundaries between planning, execution, and provider-specific state

The thesis should frame the platform as a response to those pressures.

## 2. Thesis

The proposed model is a workflow platform for AI-assisted work:

- workflows are typed graphs
- source capabilities are exposed through explicit contracts
- deployments bind logical source requirements to concrete sources
- runs are durable stopped records
- clients interact through stable APIs/transports rather than direct runtime
  internals

This is not a claim that LLMs cannot operate tools. It is a claim that durable,
inspectable, reusable work benefits from a separate execution substrate.

## 3. Design Goals

The design goals should be stated early and then revisited in evaluation:

- deterministic execution
- typed inputs, state, outputs, and node payloads
- explicit source binding
- durable artifacts, deployments, and stopped runs
- inspectable trace slices
- resumability after interruption
- transport neutrality for CLI, server, and future UI/MCP clients
- source-provider extensibility for MCP, Python, OpenAPI, and future families

## 4. Architecture

Explain the active package boundaries:

```text
wf_cli
  -> wf_transport_rpc_http
  -> wf_server
  -> wf_api
  -> wf_core / wf_artifacts / wf_sources_*
```

Important layers:

- `wf_core`: deterministic workflow kernel
- `wf_authoring`: Python authoring helpers and `NodeSpec` creation
- `wf_api`: application surface for capabilities, drafts, artifacts,
  deployments, runs, and admin/source operations
- `wf_server`: durable server composition boundary
- `wf_transport_rpc_http`: JSON-RPC-over-HTTP transport
- `wf_sources_mcp`: MCP upstream source implementation and persistent runtime
- `wf_sources_python`: trusted in-process Python source loading
- `wf_mcp`: legacy/special-purpose MCP frontend and compatibility package

The thesis should explain why the old “everything in MCP” shape was split:
transport, source provider, workflow API, and runtime concerns are different.

## 5. Workflow Model

Describe workflows as typed graphs:

- `input_schema`: validates run input
- `state_schema`: defines workflow memory and reducer behavior
- `output_schema`: defines final result shape
- `NodeUse`: invokes named `NodeSpec`
- edges: route by declared outcomes
- reducers: merge concurrent or repeated writes safely
- interrupts: represent typed external input points
- subgraphs: compose workflows as nodes

Key distinction:

- outcome controls routing
- output carries business data

## 6. Source Model

The common boundary is `CapabilitySource`.

Source families today:

| Source | Kind | Role |
| --- | --- | --- |
| `wf.std` | `system` | built-in workflow nodes and reducers |
| `wf.recipes` | `system` | first-party workflow recipes |
| MCP sources | `connection` | upstream MCP tools/resources/prompts |
| Python sources | `python` | trusted project-local `NodeSpec` registries |

The thesis should stress that the runtime does not care where a `NodeSpec` came
from. Source-specific behavior belongs in provider packages and server
composition.

Current provider seam:

```python
class WorkflowSourceProvider(Protocol):
    def load_sources(self) -> Mapping[str, CapabilitySource]: ...
```

This seam is intentionally narrow: it covers static inventory, not runtime
pools, admin/apply, auth, or live health checks.

## 7. Implementation Vertical Slice

Use the working product path as evidence:

```text
wf config validate
  -> wf-rpc-server --config
  -> wf status
  -> wf source list
  -> wf cap list / inspect / call
  -> wf draft create-from-capability
  -> wf draft save
  -> wf deploy save / validate
  -> wf run start
  -> wf run inspect / trace / list
```

A strong demonstration is the Python source flow:

1. write `ops.py` with `@node`
2. configure `kind: "python"` source
3. validate config
4. start server
5. call `local.ops.echo`
6. create draft/artifact/deployment
7. run deployment successfully

This shows the source abstraction is not MCP-only.

## 8. Evaluation

Evaluation should use concrete evidence:

- automated tests for workflow core, API, transports, source providers, and CLI
- live smoke test against `wf-rpc-server`
- durable run/resume tests
- stateful MCP session reuse tests
- Python source workflow-run integration test
- config validation catching import/path errors before server startup

Avoid vague claims such as “robust” or “production-ready” unless backed by
specific checks.

Possible evaluation questions:

- Can a source capability be discovered, called, saved into a workflow, deployed,
  and run?
- Can an interrupted run survive process restart and resume?
- Can the same server be used through CLI and JSON-RPC transport?
- Can a new source family be added without changing `wf_core`?
- Are large/raw provider payloads bounded in CLI output?

## 9. Limitations

State limitations explicitly:

- Python sources are trusted in-process code; no sandbox yet.
- Python sources are static at server startup; no hot reload yet.
- Source provider lifecycle is early, especially for non-MCP mutable sources.
- File-backed stores are the proven storage backend; SQL/secret manager support
  is future work.
- Run deletion is not implemented.
- MCP widgets/apps are not carried through the durable workflow path.
- Crash recovery is at stopped boundaries, not arbitrary mid-node checkpoints.

Limitations make the thesis more credible. They also motivate future work.

## 10. Future Work

Likely future-work sections:

- provider lifecycle: add/update/remove/apply/reload for multiple source families
- OpenAPI source provider
- Python development reload
- production auth/secret stores
- SQL/transactional stores
- scheduler/server daemon operations
- UI/admin dashboard
- richer evaluation with real workflows and larger source catalogs

## What Not To Do

Do not make the thesis a commit history. The reader does not need every
refactor.

Do not over-center MCP. MCP is one source family and one compatibility/frontend
area, not the whole platform.

Do not claim unimplemented production properties:

- no Python sandbox
- no general provider hot reload
- no production secret manager
- no full MCP widget passthrough

The strongest version is an honest systems argument:

1. Direct LLM tool orchestration has durability and validation problems.
2. Typed workflows address those problems.
3. The implementation proves the model across local, MCP, and Python sources.
4. Remaining work is clear and bounded.
