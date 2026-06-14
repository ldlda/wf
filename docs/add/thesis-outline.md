# Thesis Outline

This is a writing scaffold for a thesis/report about the workflow platform. It
should guide the argument; it is not a changelog.

The final document should read like a formal system design and implementation
report. Keep detailed command transcripts and long CLI outputs in appendices or
linked runbooks; inline chapters should show only the commands/results needed to
support the argument.

## Core Argument

External LLM agents are useful workflow authors and operators, but durable
workspace automation needs a typed execution substrate. Artifacts, deployments,
source bindings, validation, runs, traces, and resumability should be owned by
the platform, not improvised through raw tool-call loops.

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

## Evidence Strategy

Use one representative workspace case study as the narrative spine: a
document/report preparation workflow backed by local fixtures and trusted Python
sources. The case study should read or receive a small document-like input,
extract structured information such as action items or sections, normalize the
result, and produce report-shaped JSON or Markdown. MCP-backed sources can be
secondary evidence, but the thesis-critical demo should not depend on remote
MCP auth, quota, or provider availability.

The case study should exist as a runnable example, not only prose. Target shape:
`examples/report_workflow/ops.py`, `input.md`, `wf.config.json`, a short
`README.md`, and commands for config validation, server startup, capability
calls, draft/artifact/deployment creation, run, inspect, and trace.

Keep the thesis-critical path deterministic. Do not require an LLM call inside
the case-study workflow. LLM nodes can be discussed as future work or an
optional variant, but the evidence path should be reproducible without model
credentials, cost, or output variance.

Prefer typed report JSON as the primary output, with Markdown rendering optional
later. A useful output contract is:

```json
{
  "title": "Weekly Project Update",
  "summary": "...",
  "action_items": [
    {"owner": "Alice", "task": "Prepare demo config", "due": "Friday"}
  ],
  "risks": ["..."],
  "followups": ["..."]
}
```

This makes schemas and validation visible in the case study.

Use CLI lifecycle commands for the thesis narrative because they demonstrate the
agent-operable surface. Tests may seed `RawWorkflowPlan` objects directly when
that makes assertions tighter, but the case-study runbook should show config
validation, server startup, capability inspection/call, draft or artifact
creation, deployment save/validate, run start, run inspect, run trace, and run
list.

Support that case study with platform evidence: automated tests, CLI/server
smoke runs, source-provider examples, run persistence/resume checks, source
drift producing unrunnable deployments, stateful MCP session reuse, and a small
failed-attempt case study showing how validation/diagnostics reduced blind
retries.

Do not frame the evaluation as a broad user study unless that study actually
exists. The evidence claim is that the prototype demonstrates the architecture
and workflow lifecycle under controlled examples.

Do not make runtime throughput a central claim. The project targets planner
efficiency and operational clarity: fewer blind retries through typed contracts,
validation, diagnostics, compact outputs, and traces. Performance optimization
is future work unless backed by explicit measurements.

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
- platform sources with fixed process-provided identities, separate from
  configured workspace/account sources
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

Auth should be described as prototype source-readiness plumbing, not a completed
production secret system. The implementation includes typed auth records, OAuth
refresh-token support, source auth diagnostics, and MCP auth binding. This is
enough to show how credentials participate in source readiness and diagnostics,
but encrypted-at-rest storage, production secret-manager integration, and broad
provider verification remain future work.

## 4. Positioning And Related Systems

Keep this section short and category-oriented. The goal is to position the
system, not to claim full feature parity with mature platforms.

Compare against:

- direct LLM tool orchestration: flexible but weak durability and validation
- generated scripts: simple and maintainable for some tasks, but lifecycle
  affordances are manual
- Zapier/RPA/workflow automation platforms: mature integrations and scheduling,
  but less agent-native typed authoring/repair flow in this prototype's terms
- LangGraph-style agent graphs/durable agents: adjacent durability ideas, but a
  different emphasis from source-provider-backed reusable workspace workflows
- MCP: useful protocol for tools/resources/prompts, but not itself the workflow
  artifact/deployment/run lifecycle

## 5. Architecture

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

Use package names as implementation evidence, not as the main argument. The
conceptual architecture should lead: workflow core, platform domain, workflow
API surface, server/transport composition, and source providers. Package names
then show how those concepts were implemented in this codebase.

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

MCP is an important source-provider case study, not the product identity. It
demonstrates why source-provider correctness matters: a source may require
persistent sessions, auth context, catalog refresh, resources, and prompt
inventory. The platform treats MCP as one source family behind the workflow
boundary, not as the whole architecture.

## 6. Workflow Model

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

The graph model improves the safety posture by making automation structure
explicit. Node contracts, source requirements, state writes, outcomes,
validation gates, and trace records are visible before and after execution. It
does not guarantee safe behavior from provider code, credentials, or external
side effects.

Use generated scripts as a serious baseline, not a strawman. Scripts can be
simpler and maintainable for many tasks. The platform argument is that reusable
workspace automation benefits from lifecycle affordances that scripts do not
automatically provide: typed validation, source binding, artifact/deployment
separation, run records, resumability, trace inspection, and repairable
diagnostics.

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

## 7. Source Model

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

Use precise vocabulary:

- tools are provider-native operations, such as MCP tools
- workflow capabilities are `NodeSpec` contracts callable from graphs
- resources are source-owned addressable content; a URI is meaningful only with
  its owning source
- prompts are source-owned prompt/template inventory; rendering may be stateful

Platform sources such as `wf.std` and `wf.source` are process-provided and do
not require deployment self-bindings. Configured sources such as MCP, Python,
and future OpenAPI sources remain explicit server/operator choices.

`wf.source.read_resource` is the current explicit dereference helper: workflows
pass inert resource refs by value, then the helper resolves the logical source
through runtime/platform context and returns bounded text. Prompt rendering is
deliberately not a workflow helper yet; keep it in future work unless the thesis
adds a concrete graph use case, argument schema, and bounded output policy.

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

## 8. Implementation Vertical Slice

Use the working product path as evidence:

```text
wf config validate
  -> wf-rpc-server --config
  -> wf status
  -> wf source list
  -> wf source resources / prompts
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

Use diagrams as first-class explanation, especially Mermaid diagrams that can be
rendered by the existing document generation flow. Each major part should have
at least one diagram that explains its role and boundaries before code excerpts
or package names appear. Prefer diagrams for:

- main architecture spine:

  ```mermaid
  flowchart LR
    Owner[Workflow Owner] --> Agent[External LLM Agent]
    Agent --> CLI[wf CLI]
    CLI --> Transport[JSON-RPC Transport]
    Transport --> Server[WorkflowServer]
    Server --> API[Workflow API Surface]
    API --> Core[Workflow Core]
    API --> Platform[Artifacts / Deployments / Runs]
    Server --> Sources[Source Providers]
    Sources --> Builtins[Platform Sources]
    Sources --> MCP[MCP Sources]
    Sources --> Python[Python Sources]
  ```

- layer architecture: CLI/transport/server/API/core/source providers
- workflow core: schemas, nodes, outcomes, reducers, trace, interrupts/resume
- platform domain: draft workspaces, artifacts, deployments, source inventory,
  validation diagnostics, run records
- lifecycle: draft -> artifact -> deployment -> run -> trace/list/resume
- source resolution: logical source -> deployment binding/platform context ->
  concrete source/runtime
- source-provider comparison: built-in, MCP, Python, future OpenAPI
- runtime call path: cap call/run -> Workflow API -> source runtime/client

Use source excerpts sparingly. Include small snippets for key seams such as the
artifact/deployment/run lifecycle shape, `CapabilitySource`, the
`WorkflowSourceProvider` protocol, a compact Python source `@node` example, and
selected CLI/JSON responses. Avoid long file listings; the implementation
chapter should explain the architecture, not reproduce the repository.

Frame Python sources as trusted developer extensibility. They are useful because
project-local code can become typed workflow capabilities quickly, but they are
not sandboxed non-programmer plugins yet.

## 9. Evaluation

Evaluation should use concrete evidence:

- automated tests for workflow core, API, transports, source providers, and CLI
- live smoke test against `wf-rpc-server`
- durable run/resume tests
- stateful MCP session reuse tests
- MCP source-provider correctness tests covering tools, resources, prompts, and
  session reuse through the same server path
- Python source workflow-run integration test
- bounded source inventory and resource-read tests, especially to avoid raw
  provider payload spam
- OAuth refresh-token/auth-binding tests for HTTP MCP sources, with Google Drive
  MCP treated as manual smoke coverage rather than a regression fixture
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
- current agent/tool evaluation with a small repeat count. A practical prototype
  target is five end-to-end attempts where free or commodity LLM agents try to
  use the CLI/API surface to complete the deterministic case study. Report
  pass/fail counts, failure categories, and whether diagnostics were actionable;
  do not present this as a statistical reliability benchmark.

For the agent/tool evaluation, success means end-to-end completion: the agent
creates or selects a valid workflow artifact/deployment and completes a run whose
output matches the expected typed report schema and key content. Merely calling
a capability, producing a draft, or returning freeform text outside the schema is
not success.

Count failures explicitly. Useful categories include:

- config/setup failure
- source discovery or source binding failure
- draft validation failure
- deployment validation failure
- run failure
- output schema/content mismatch
- excessive manual intervention
- agent gave up or looped without progress

Track autonomous and assisted success separately. Autonomous success means the
agent completes the task with only the initial prompt/runbook. Assisted success
means completion after limited documented help such as confirming that the
server is running or pointing at the intended config path. Manual artifact edits,
code fixes, or changing the expected output should count as failures for
autonomous evaluation.

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
- Can platform sources such as `wf.std` be used without self-bindings while
  configured sources still require explicit bindings?
- Can source resources be referenced by logical source and dereferenced only
  through an explicit bounded helper?
- Can an external LLM agent converge on a valid workflow without spending most
  of the interaction on tool-output spam and trial-and-error?
- Does the structured surface reduce failed attempts before success compared to
  earlier ad-hoc agent/tool interaction traces?
- Do `wf draft validate`, deployment validation, and run inspection catch or
  explain the kinds of issues that previously caused repeated failed runs?
- Does deployment validation surface source drift as runnable/unrunnable state
  with diagnostics rather than silent behavior changes?

## 9.1 Positioning Against Existing Automation Platforms

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

## 10. Limitations

State limitations explicitly:

- Python sources are trusted in-process code; no sandbox yet.
- Python sources are static at server startup; no hot reload yet.
- Source provider lifecycle is early, especially for non-MCP mutable sources.
- Workflow portability is scoped; local Python code, MCP catalogs, auth records,
  and source stores can differ between environments.
- The prototype has not been evaluated against a broad external provider catalog
  or a large user study.
- File-backed stores are the current implementation proof for durable lifecycle;
  durability itself should not be framed as filesystem-specific.
- Auth records/admin surfaces exist as prototype plumbing, but end-to-end
  production credential handling is not verified as a core thesis claim.
- Run deletion is not implemented.
- MCP widget/resource proxying is not supported; upstream interactive widgets
  are not carried through the durable workflow path.
- Crash recovery is at stopped boundaries, not arbitrary mid-node checkpoints.
- Offline scheduling is not implemented yet.
- There is no visual workflow editor yet.
- There is no bundled autonomous agent brain.
- General fork/gather workflow control is future work.
- There is no full approval, roles, policy, or multi-user review system.

Limitations make the thesis more credible. They also motivate future work.

## 11. Future Work

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

## 12. Conclusion

Restate the core argument: external LLM agents can author and operate workflows,
but the durable workflow lifecycle should live in a typed platform substrate.
Summarize what the implementation proves: artifacts, deployments, runs,
validation, source providers, server/API/CLI surfaces, and reproducible evidence
across built-in, MCP, and Python sources.

## Appendices

Keep long operational material out of the main argument:

- reproducible command transcript for the case study
- smoke-test commands and abbreviated outputs
- selected config files
- generated workflow/artifact/deployment examples
- test/evidence index

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
