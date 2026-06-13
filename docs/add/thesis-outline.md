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

## Research Question

Primary research question:

> How can an AI-agent-facing workflow platform represent, validate, execute, and
> persist reusable workspace automations while keeping planning separate from
> deterministic execution?

Product motivation:

> How can external AI agents help workspace operators create reusable
> automations without requiring them to write scripts, while preserving
> validation, inspection, and durable execution?

## Main Contribution

The thesis contribution is a platform architecture, not a new foundation model:

1. typed workflow artifact/deployment/run lifecycle
2. source-provider boundary for MCP, Python, and future OpenAPI sources
3. durable server/API/CLI surface that external agents can drive
4. validation and inspection mechanisms that reduce planner trial-and-error
5. next-action guidance that points an agent toward useful lifecycle operations
   without replacing validation

## Working Title

Safer current title:

> Design and Implementation of lda.chat: Infrastructure for AI Agents to Author
> and Execute Workspace Workflows

Aspirational product title:

> Design and Implementation of lda.chat: An AI Agent Platform for Authoring and
> Executing Workspace Workflows

Use the safer title if the thesis must describe exactly what exists today:
external agents such as Claude Desktop and OpenCode can drive the platform, but
`lda.chat` does not yet bundle its own autonomous agent brain. Use the
aspirational title only if the thesis explicitly frames `lda.chat` as the
platform intended to host or serve AI agents, not as a completed built-in agent.

## 1. Problem Statement

Current agent/tool systems often let the LLM directly orchestrate side effects
through ad hoc tool calls. This creates practical problems:

- weak validation before execution
- poor resumability after interruption or process restart
- hard-to-audit tool-call traces
- limited reuse of successful procedures
- unclear boundaries between planning, execution, and provider-specific state

The thesis should frame the platform as a response to those pressures.

The automation target is reusable workspace procedures, not arbitrary office
work end-to-end. Examples include document transformation, data collection,
tool/API calls, report preparation, monitoring checks, and scheduled workspace
operations.

## 2. Thesis

The proposed model is a prototype platform for AI-assisted work:

- workflows are typed graphs
- source capabilities are exposed through explicit contracts
- deployments bind logical source requirements to concrete sources
- runs are durable stopped records
- clients interact through stable APIs/transports rather than direct runtime
  internals

Natural language belongs in the authoring loop: a workspace operator can express
intent to an external LLM agent, but the reusable output should be a typed
workflow artifact and deployment rather than an opaque prompt transcript.

Be explicit about actors:

- the workflow owner wants to see useful workflow runs and outputs
- the external LLM agent may be the one driving CLI/API operations
- the developer/operator configures sources, secrets, server processes, and
  trusted Python code

The CLI should be described as agent-operable first and human-usable second. Its
structured output, status/inspect/list commands, validation commands, compact
summaries, and guarded destructive actions make it a practical surface for
external agents.

This is not a claim that LLMs cannot operate tools. It is a claim that durable,
inspectable, reusable work benefits from a separate execution substrate.

Use “prototype platform” deliberately. The implementation proves the core
lifecycle and architecture, but it is not yet a finished product with scheduling,
visual workflow editing, production secrets, general fork/gather, and broad
real-world evaluation.

Next actions and repairable validation failures should be framed as
machine-client UX. Human interfaces use buttons and affordances; an agent-facing
API needs compact structured hints, stable diagnostic fields, and suggested next
operations so an LLM agent can recover without blind probing.

## 3. Design Goals

The design goals should be stated early and then revisited in evaluation:

- deterministic execution
- validation-centered lifecycle for LLM-authored workflows
- typed inputs, state, outputs, and node payloads
- explicit source binding
- scoped workflow portability through artifact requirements and deployment
  binding contracts
- durable artifacts, deployments, and stopped runs
- inspectable trace slices
- reviewable lifecycle points for drafts, deployments, runs, diagnostics, and
  guarded destructive actions
- resumability after interruption
- transport neutrality for CLI, server, and future UI/MCP clients
- source-provider extensibility for MCP, Python, OpenAPI, and future families
- source-provider correctness, especially for external systems whose tools,
  resources, prompts, or authentication depend on initialized stateful sessions

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
- `wf_authoring`: authoring support for `NodeSpec`, drafts, wrappers, API
  surfaces, source providers, and MCP/admin tools
- `wf_api`: application surface for capabilities, drafts, artifacts,
  deployments, runs, and admin/source operations
- `wf_server`: durable server composition boundary
- `wf_transport_rpc_http`: JSON-RPC-over-HTTP transport
- `wf_sources_mcp`: MCP upstream source implementation and persistent runtime
- `wf_sources_python`: trusted in-process Python source loading
- `wf_mcp`: legacy/special-purpose MCP compatibility package

The thesis should explain why the old “everything in MCP” shape was split:
transport, source provider, workflow API, and runtime concerns are different.

Architecture spine:

- workflow core: deterministic execution semantics for graph, state, outcomes,
  trace, and resume rules
- platform domain: artifacts, deployments, runs, stores, sources, binding
  contracts, validation, and admin concepts
- workflow API surface: lifecycle operations exposed to clients
- server/transport composition: concrete stores, sources, runtimes, and
  communication mechanisms

JSON-RPC is an implementation of the Workflow API Surface. It should not be
presented as the product boundary or as the place where workflow semantics live.
`wf_server` is composition: it assembles concrete stores, sources, runtimes, and
admin surfaces into a long-lived service. It should not own workflow semantics.
`wf_authoring` is support infrastructure used by drafts, API surfaces, source
providers, and MCP tools; it is not a fifth runtime/product layer.
If MCP is discussed, distinguish upstream MCP sources from a future client-facing
MCP frontend. The former exists as a source family; the latter should not be
claimed as a completed clean platform surface.

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

Separate lifecycle objects:

- draft workspace: mutable authoring state for agent/user iteration
- workflow artifact: immutable versioned workflow definition
- deployment: binding contract from artifact version to concrete source/runtime
  context
- run: execution record with status, diagnostics, output, trace, and resumable
  stopped/interrupted state where applicable

Key distinction:

- outcome controls routing
- output carries business data

The graph model is also a safety boundary. It is not safer because it can make
all tools safe; it is safer than arbitrary generated scripts because structure,
schemas, source bindings, state, outcomes, and review points are explicit. This
is the answer to “why not just have the AI write a Playwright script?” Scripts
can be simple and maintainable, but they do not automatically provide the same
validation and lifecycle affordances.

Code ends at the source-provider boundary. A workflow can call trusted Python,
Playwright, API, MCP, or future LLM capabilities, but those should appear as
typed source capabilities. The workflow itself remains an orchestration artifact,
not an embedded code blob.

Durability is a contract over time, not just storage. Artifacts, deployments,
bindings, run records, and traces preserve workflow intent. Validation against
the current source catalog determines whether that intent is still runnable. If
a source changes incompatibly and a deployment becomes `unrunnable`, the system
has preserved the contract instead of silently drifting.

Trace claims should be grounded in the current code: run summaries expose
`trace_count`, and clients can request caller-bounded trace slices for debugging.
Do not overstate this as production observability, distributed tracing, metrics,
or OpenTelemetry support.

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

MCP should be presented as one source family and a useful stress test for
source-provider correctness, not as the platform identity.

Current provider seam:

```python
class WorkflowSourceProvider(Protocol):
    def load_sources(self) -> Mapping[str, CapabilitySource]: ...
```

This seam is intentionally narrow: it covers static inventory, not runtime
pools, admin/apply, auth, or live health checks.

For MCP, source-provider correctness includes stateful runtime behavior. A
workflow capability call should not silently turn a stateful external provider
into a fresh one-off client call when provider state is part of correctness.

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

Frame Python sources as trusted developer extensibility. They are useful because
project-local code can become typed workflow capabilities quickly, but they are
not sandboxed non-programmer plugins yet.

## 8. Evaluation

Evaluation should use concrete evidence:

- automated tests for workflow core, API, transports, source providers, and CLI
- live smoke test against `wf-rpc-server`
- durable run/resume tests
- stateful MCP session reuse tests
- MCP source-provider correctness tests covering tools, resources, prompts, and
  session reuse through the same server path
- Python source workflow-run integration test
- config validation catching import/path errors before server startup
- planner-efficiency checks: validation, source catalogs, compact output, and
  inspectable errors should reduce repeated blind LLM attempts
- next-action guidance should reduce planner uncertainty before and after
  validation calls
- attempt-count comparison on representative tasks, for example old interaction
  traces with many failed attempts versus the current structured lifecycle
- draft-validation and run-failure analysis, especially cases where old session
  or source assumptions caused repeated failed runs
- source-drift cases where old deployments become unrunnable with diagnostics
  instead of silently executing against incompatible capabilities

Avoid vague claims such as “robust” or “production-ready” unless backed by
specific checks.

Evidence package:

- architecture/code walkthrough tied to the four-layer model
- automated tests for lifecycle, validation, source providers, persistence,
  resume, stateful MCP reuse, and Python source integration
- live CLI/server smoke run
- before/after failed-attempt case study from old ad-hoc interaction to
  structured workflow lifecycle
- explicit limitations and future work

Recommended case study:

- document/report preparation, not an echo demo
- deterministic current sources first, such as Python source text transforms
- optional/future LLM summarization as a typed source capability, not required
- output should be a structured report or Markdown/JSON artifact that a workflow
  owner would plausibly want
- package the example with fixture input, Python source code, workflow config,
  store/environment setup, and CLI/server commands

Possible evaluation questions:

- Can a source capability be discovered, called, saved into a workflow, deployed,
  and run?
- Can an interrupted run survive process restart and resume?
- Can the same server be used through CLI and JSON-RPC transport?
- Can a new source family be added without changing `wf_core`?
- Are large/raw provider payloads bounded in CLI output?
- Can an external LLM agent converge on a valid workflow without spending most
  of the interaction on tool-output spam and trial-and-error?
- Does the structured surface reduce failed attempts before success compared to
  earlier ad-hoc agent/tool interaction traces?
- Do `wf draft validate`, deployment validation, and run inspection catch or
  explain the kinds of issues that previously caused repeated failed runs?
- Does deployment validation surface source drift as runnable/unrunnable state
  with diagnostics rather than silent behavior changes?

## 8.1 Positioning Against Existing Automation Platforms

The thesis should discuss the space it fits into through multiple baselines:
direct LLM tool use, manual scripts, Zapier-style automation platforms, RPA
tools, and workflow engines. The goal is not to claim feature parity with mature
products. The goal is to explain the trade-off this prototype explores.

Zapier and similar platforms are stronger today at:

- polished non-programmer UI
- large integration catalogs
- hosted scheduling and triggers
- operational maturity

Manual scripts are powerful and often faster for technical users, so the thesis
should not dismiss them. The fair comparison is accessibility and adaptability:
how much skill and maintenance effort is required before a workspace operator or
external agent can turn a repeated task into a reusable workflow?

This prototype explores a different center of gravity:

- external AI agents can drive the authoring/execution lifecycle directly
- workflows are typed graphs with explicit schemas and source bindings
- local Python, MCP, and future OpenAPI sources can share one workflow surface
- runs, traces, artifacts, and deployments are first-class inspectable records

Use the comparison to position the work, not as a claim that the prototype
outperforms existing automation products.

## 9. Limitations

State limitations explicitly:

- Python sources are trusted in-process code; no sandbox yet.
- Python sources are static at server startup; no hot reload yet.
- Source provider lifecycle is early, especially for non-MCP mutable sources.
- Workflow portability is scoped; local Python code, MCP catalogs, auth records,
  and source stores can differ between environments.
- File-backed stores are the current implementation proof for durable lifecycle;
  durability itself should not be framed as filesystem-specific.
- Auth records/admin surfaces exist as prototype plumbing, but end-to-end
  production credential handling is not verified as a core thesis claim.
- Run deletion is not implemented.
- MCP widget/resource proxying is not supported; upstream interactive widgets
  are not carried through the durable workflow path.
- Crash recovery is at stopped boundaries, not arbitrary mid-node checkpoints.
- Offline scheduling is not implemented yet.
- General fork/gather workflow control is future work.
- There is no full approval, roles, policy, or multi-user review system.

Limitations make the thesis more credible. They also motivate future work.

## 10. Future Work

Likely future-work sections:

- provider lifecycle: add/update/remove/apply/reload for multiple source families
- OpenAPI or fetch-style source provider for broader HTTP integration
- Python development reload
- LLM nodes as typed source capabilities
- production auth/secret stores
- SQL/transactional stores
- scheduler/server daemon operations
- offline scheduling for deployments
- fork/gather workflow control
- richer run rewind/time-travel debugging beyond stopped/interrupted resume
- UI/admin dashboard
- first-party workflow UI for listing, inspecting, and editing workflows
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
- no unmeasured performance or production-readiness claims

The strongest version is an honest systems argument:

1. Direct LLM tool orchestration has durability and validation problems.
2. Typed workflows address those problems.
3. The implementation proves the model across local, MCP, and Python sources.
4. Remaining work is clear and bounded.
