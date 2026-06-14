# Workflow Runtime Context

This context defines the core workflow runtime language used by `wf_core`,
`wf_authoring`, and the MCP-facing workflow platform.

## Language

**lda.chat**:
An AI agent platform for authoring and executing workspace workflows.
_Avoid_: Chatbot, MCP server

**Agent-Compatible Infrastructure**:
A platform surface that external AI agents can use to author, validate, run, and
inspect workflows without bundling a specific agent brain.
_Avoid_: Built-in autonomous agent, chatbot implementation

**AI Agent Platform**:
The broader product framing for `lda.chat` when discussing the intended user
experience and ecosystem role. Use carefully today because the platform is
currently driven by external agents rather than a bundled autonomous agent.
_Avoid_: Claiming `lda.chat` already contains the agent brain

**Workspace Operator**:
The human beneficiary and controller of workspace automation.
_Avoid_: End user, consumer user

**Workflow Owner**:
The human who wants the workflow to exist, run, and produce useful output. They
may review the workflow result without directly operating the CLI or API; an
external LLM agent can drive those surfaces for them.
_Avoid_: Assuming the CLI user and product beneficiary are always the same actor

**Workspace**:
A user-controlled digital work environment where office-style work happens,
including files, tools, services, credentials, and project context exposed
through approved capability sources.
_Avoid_: Filesystem directory, user account

**LLM Agent**:
An external AI agent, such as Claude Desktop or OpenCode, that can use the
platform surfaces to plan, edit, validate, and invoke workflow operations.
_Avoid_: Built-in agent brain, chatbot

**Workspace Workflow**:
A reusable, typed procedure for digital work in a workspace, represented as a
graph with schemas, state, outcomes, source bindings, and durable run records.
_Avoid_: Sequence of tool calls, prompt chain

**Durable Workflow Contract**:
The persisted workflow intent across time: artifact, deployment bindings,
validation against current sources, run records, and traces. Persistence keeps
the objects; validation determines whether the current environment can still run
them. A deployment becoming unrunnable after incompatible source changes is a
contract-preserving outcome, not silent failure.
_Avoid_: Treating durability as only file persistence or tying it to one store
implementation

**Source Drift**:
Change in a source catalog, capability contract, provider availability, or source
binding after an artifact or deployment was created. Source drift is a normal
lifecycle state surfaced through validation and diagnostics, not an unexpected
crash.
_Avoid_: Assuming old deployments remain runnable forever

**Workflow Artifact**:
An immutable, versioned workflow definition saved from authoring state. It
captures the workflow graph and declared requirements, but it is not itself a
live execution.
_Avoid_: Mutable draft, run record

**Workflow Deployment**:
A binding from a workflow artifact version to concrete source/runtime context.
Deployment validation determines whether the artifact can currently run.
_Avoid_: Artifact version, draft workspace, incidental runtime config

**Binding Contract**:
The deployment-level mapping from logical workflow requirements to concrete
sources or runtime context. Binding contracts make workflows portable across
workspaces/accounts while allowing validation to detect missing, disabled, or
incompatible sources.
_Avoid_: Ad-hoc environment variables, hidden source lookup

**Platform Source**:
A process-provided source with a fixed identity, such as `wf.std` or
`wf.source`. Platform sources can satisfy workflow requirements without
deployment self-bindings because their logical source id is also their concrete
source id, and deployments should not override them with custom bindings.
_Avoid_: Configured account source, user-installed provider

**Configured Source**:
A server/operator-selected source such as an MCP connection, trusted Python
module registry, or future OpenAPI provider. Configured sources are where
deployment bindings, source registry state, auth refs, catalog cache, and
health diagnostics matter most.
_Avoid_: Built-in standard library source

**Source Inventory**:
The listable capabilities owned by a source: workflow-callable `NodeSpec`s,
provider-native tools, resources, prompts, and related metadata. Inventory
inspection is not the same as invoking a tool, reading a resource, or rendering
a prompt.
_Avoid_: Assuming list equals execute

**Source Resource Ref**:
An inert pass-by-value reference to source-owned content, carrying a logical
source and provider URI. The URI is not globally meaningful by itself; runtime
must resolve the logical source through deployment/platform context before a
helper such as `wf.source.read_resource` can dereference it.
_Avoid_: Resource Ref as the canonical term, bare URI, immediate content fetch

**Prompt Inventory**:
Source-owned prompt/template names and metadata. Listing prompts is safe
inventory; rendering a prompt is an upstream operation that may be stateful and
needs a concrete graph use case, argument schema, and bounded output policy
before becoming a workflow helper.
_Avoid_: Source Prompt Ref as premature symmetry, treating prompt list entries
as already-rendered text

**Workflow Portability**:
The goal that a workflow artifact can describe logical requirements separately
from concrete source/account bindings. Portability is scoped: deployments bind
artifacts to a specific workspace environment, and local Python code, MCP
catalogs, auth records, and source stores may still differ between environments.
_Avoid_: Universal run-anywhere portability

**Draft Workspace**:
Mutable workflow authoring state where an agent or user can patch, validate, and
iterate before saving an immutable artifact.
_Avoid_: Deployed workflow

**Workflow Run**:
An execution record for a deployment, including status, diagnostics, output,
trace, and resumable stopped/interrupted state where applicable.
_Avoid_: Artifact, deployment

**Run Resume**:
A supporting durable-execution capability where stopped or interrupted workflow
state can be inspected and continued later. It proves the lifecycle is more than
final-output storage, but it is not yet full time-travel debugging.
_Avoid_: Full LangGraph-style time travel

**Run Trace**:
A bounded debug record attached to a workflow run. Current claims should be based
on code-supported trace counts and caller-bounded trace slices for debugging,
not broad production observability.
_Avoid_: Distributed tracing, metrics platform, OpenTelemetry claims

**Evidence-Backed Claim**:
A thesis claim grounded in implemented code, tests, live smoke runs, examples, or
clearly marked future work. The current project stage is making the platform
good and correct; making it fast is later unless performance is measured.
_Avoid_: Unmeasured performance, reliability, security, or production-readiness
claims

**Evidence Package**:
The thesis evidence set: architecture/code walkthrough tied to the four-layer
model, automated tests, live smoke runs, source-provider examples, run
persistence/resume checks, stateful MCP reuse checks, Python source integration,
and a small failed-attempt case study.
_Avoid_: Large user study claims without the study

**Case Study Workflow**:
A concrete representative workflow used in the thesis evidence package. Prefer a
document/report preparation task over toy echo tools: parse or transform a small
document, extract key points or action items, and produce structured report
output. It should run deterministically with current sources; LLM enhancement can
be future or optional.
_Avoid_: Echo-only demos, flaky external services

**Reproducible Example Environment**:
A small runnable example bundle for thesis evidence: fixture input files, source
provider code, workflow config, store directory setup, and CLI/server commands.
It should let the case study be rerun without relying on hidden local state.
_Avoid_: Screenshot-only demo, undocumented local setup

**Representative Workspace Task**:
A recurring digital work pattern such as document processing, project or
repository monitoring, data/report preparation, or scheduled workspace
operations.
_Avoid_: Generic business process, arbitrary web task

**Automation Platform Baseline**:
An existing workflow automation product, such as Zapier, used as a comparison
point for maturity, speed, usability, integrations, and scheduling.
_Avoid_: Direct competitor claim, full feature parity

**Prototype Platform Substrate**:
The implemented backend, API, CLI, source-provider, and durable workflow
lifecycle that external agents or future UI surfaces can drive.
_Avoid_: Final conversational product, complete user interface

**Prototype Platform**:
A usable but incomplete platform implementation that demonstrates the core
workflow lifecycle and source-provider model. It is not yet a full product
because scheduling, visual workflow editing, production auth/secret storage,
general fork/gather, richer source lifecycle, and broad evaluation remain
future work.
_Avoid_: Production-ready product, finished agent app

**Platform Architecture Contribution**:
The thesis contribution: separating external-agent planning from typed workflow
execution through artifact/deployment/run lifecycle, source-provider boundaries,
durable API/CLI/server surfaces, and validation/inspection mechanisms that
reduce planner trial-and-error.
_Avoid_: Framing the work as only another automation tool or AI model

**Automation Baseline**:
A comparison point used to position the prototype. Direct LLM tool use, manual
scripts, and mature platforms such as Zapier or RPA systems expose different
trade-offs: durability and reuse, accessibility and adaptability, or integration
and operational maturity.
_Avoid_: Treating one baseline as the entire problem space

**Workflow Automation Accessibility**:
The goal of making reusable workflow automation available without requiring the
workspace operator to hand-code scripts or manually chain tools.
_Avoid_: Fully automatic correctness, no-review automation

**Offline Scheduling**:
Future execution of deployed workspace workflows without an active chat or
interactive session.
_Avoid_: Background prompt, cron job

**Workflow Visualization**:
Future UI support for inspecting, editing, and explaining workflow graphs
visually.
_Avoid_: Current runtime feature, trace log

**LLM Node**:
A workflow node that calls an LLM as one capability inside the graph, rather
than making the whole runtime itself an LLM loop.
_Avoid_: Built-in planner, hidden agent loop

**Deterministic Execution Substrate**:
The workflow control layer that validates schemas, routes outcomes, commits
state, records trace, and persists runs predictably even when individual
capabilities call nondeterministic tools, APIs, Python code, or LLMs.
_Avoid_: Deterministic external tools, deterministic LLM output

**Planner Efficiency**:
The degree to which the platform reduces LLM trial-and-error when creating or
running workflows. Typed schemas, source catalogs, validation errors, dry
checks, inspectable traces, compact CLI output, and reusable artifacts should
help an external LLM agent converge without spending excessive tokens probing
blindly.
Representative evidence includes fewer failed attempts before a valid workflow
is created and run.
_Avoid_: Assuming an LLM planner is cheap enough to brute-force the workflow

**Failed Workflow Attempt**:
An agent action that tries to advance workflow creation or execution but cannot
be reused because it hits an avoidable structural, validation, source-binding,
configuration, session, or runtime issue. Examples include failed draft
validation, non-runnable deployments, source/session failures, and run failures
caused by incorrect workflow structure or provider assumptions.
_Avoid_: Counting deliberate exploration or user clarification as workflow
failure

**Validation-Centered Workflow Lifecycle**:
The product principle that LLM-authored workflows should move through explicit
validation gates before and after execution. Config validation, capability
contracts, draft validation, deployment validation, run inspection, and output
safety reduce blind trial-and-error and make workflow automation reviewable.
_Avoid_: Treating validation as a convenience check after implementation

**Next Actions**:
Advisory lifecycle guidance returned to clients and LLM agents to suggest the
next useful operation, such as validating a draft, patching a workspace, saving
an artifact, or inspecting a run. Next actions guide planner behavior but do not
replace validation authority.
_Avoid_: Treating next actions as hard permission checks

**Machine-Client UX**:
API and CLI response design for LLM agents and other programmatic clients. It
uses compact structured payloads, stable fields, diagnostics, and next actions
instead of relying on prose or oversized raw provider output.
_Avoid_: Assuming only human-readable UI needs interaction design

**Agent-Operable CLI**:
A CLI designed so external LLM agents can drive workflow lifecycle operations
predictably through structured output, compact summaries, validation commands,
status/inspect/list operations, and guarded destructive actions. Humans can use
it, but it is not only a human terminal UI.
_Avoid_: Treating the CLI as the workflow runtime

**Workflow API Surface**:
The application contract for workflow lifecycle operations: capabilities,
drafts, artifacts, deployments, runs, admin/source operations, validation,
inspection, and next actions. Process-local clients, JSON-RPC, future MCP
frontends, and UI backends can implement or consume this surface.
_Avoid_: Treating JSON-RPC as the product boundary

**Transport Adapter**:
An implementation that exposes the Workflow API Surface over a specific
communication mechanism, such as process-local calls or JSON-RPC-over-HTTP.
Transport adapters should not define workflow semantics.
_Avoid_: Putting workflow behavior in the transport

**Four-Layer Platform Model**:
The canonical architecture split: workflow core, platform domain, workflow API
surface, and server/transport composition. The core owns execution semantics;
the platform domain owns artifacts, deployments, runs, sources, bindings,
validation, stores, and admin concepts; the API surface exposes lifecycle
operations; server/transport composition wires concrete stores, sources,
runtimes, and communications.
_Avoid_: Collapsing server, API, platform, and core into one layer

**Authoring Support**:
Helper libraries and tools that create workflow specs, node specs, drafts, and
wrapper structures for API surfaces, source providers, and MCP/admin tools.
Authoring support feeds the platform domain but is not a separate runtime layer
and does not own workflow semantics.
_Avoid_: Treating authoring helpers as the execution engine

**Repairable Validation Failure**:
A validation failure that identifies what failed, where it failed, why it
matters, and what the caller can try next. It should help an LLM agent patch the
workflow instead of causing another blind probe.
_Avoid_: Tracebacks, generic bad-request messages, silent rejection

**Graph Safety Boundary**:
The safety argument that a typed workflow graph is easier to validate, inspect,
reuse, and constrain than arbitrary generated code. The graph model limits where
logic lives and makes source bindings, schemas, state, and outcomes explicit.
This does not make external tools, trusted Python sources, or credentials safe
by default.
_Avoid_: Claiming workflow graphs eliminate all automation risk

**Code Boundary**:
Code belongs behind source providers and capabilities. A workflow should
orchestrate typed capabilities through graph structure, bindings, outcomes,
state, and interrupts; it should not embed arbitrary code directly. Future
escape hatches such as unsafe Python or LLM nodes should still appear as source
capabilities.
_Avoid_: Treating a workflow as an opaque script blob

**LLM Node**:
A future source capability that calls an LLM for a bounded task such as
summarization, classification, extraction, or controlled looping. It should have
typed inputs, outputs, and outcomes like other capabilities.
_Avoid_: Hidden LLM orchestration engine

**Source-Provider Correctness**:
The requirement that a source provider preserve the behavior expected by the
external system it represents. Some providers are not meaningfully stateless:
they may depend on initialized sessions, created resources, authentication
context, or provider-local state. Workflow execution should not silently degrade
those sources into one-off calls when stateful behavior is part of correctness.
_Avoid_: Treating all capability calls as independent stateless requests

**MCP Source**:
An MCP-backed source family that exposes upstream tools, resources, and prompts
through the workflow source boundary. MCP is a source integration and stress
test for source-provider correctness; it is not the identity of the whole
platform.
_Avoid_: Treating `lda.chat` as only an MCP server or MCP proxy

**MCP Frontend**:
A future transport/frontend role where external MCP clients could operate the
Workflow API Surface. This is distinct from MCP Source, which consumes upstream
MCP servers as workflow capabilities. The current thesis should not claim the
new platform already has a clean MCP frontend.
_Avoid_: Confusing upstream MCP sources with client-facing MCP transport

**MCP Widget Proxying**:
Proxying upstream MCP UI resources/widgets, iframe metadata, and related client
resource behavior through the platform. This is not supported now because it
requires protocol-specific UI/resource handling beyond ordinary workflow
capabilities.
_Avoid_: Claiming durable workflows preserve upstream MCP interactive widgets

**First-Party Workflow UI**:
A future UI surface owned by the platform, such as listing, inspecting, and
editing workflows or deployments. This is different from proxying upstream MCP
widgets.
_Avoid_: Treating first-party workflow UI as MCP widget passthrough

**Reviewable Lifecycle**:
The current human-in-the-loop property: drafts, deployments, runs, diagnostics,
traces, and guarded destructive commands create review points before or after
execution. This is not a full approval, policy, roles, or multi-user review
system.
_Avoid_: Enterprise approval workflow

**Auth Plumbing**:
Prototype support for auth records, source auth diagnostics, and admin surfaces.
Auth matters for source readiness, but production secret management and verified
end-to-end credential workflows are not thesis-core claims yet.
_Avoid_: Production secret manager, fully verified auth system

**Python Source**:
A trusted project-local source family that exposes Python-authored `NodeSpec`
registries as workflow capabilities. Python sources provide developer
extensibility and prove the source model is not MCP-only, but they are not
sandboxed non-programmer plugins yet.
_Avoid_: Safe end-user extension, arbitrary untrusted code

**OpenAPI Source**:
A future source family that could expose HTTP/OpenAPI operations as typed
workflow capabilities. It would broaden integration coverage, but MCP and Python
sources are already enough to demonstrate the source-provider boundary.
_Avoid_: Claiming HTTP/OpenAPI source support exists today

**Natural-Language Authoring**:
Using natural language as the way a workspace operator communicates intent to an
external LLM agent. The durable result should be a typed workflow graph and
deployment, not an opaque prompt transcript.
_Avoid_: Treating natural language as the execution model

**Reusable Workspace Procedure**:
A repeatable digital-work procedure that can be represented as a typed workflow:
transforming documents, collecting data, calling tools or APIs, preparing
reports, monitoring changes, or running scheduled checks. The platform automates
these procedures rather than claiming to solve arbitrary office work end-to-end.
_Avoid_: Arbitrary job completion, one-off tool click

**Offline Scheduling**:
Future execution of deployed workflows without an active chat or CLI session.
Persisted deployments and server-side execution make scheduling plausible, but
scheduling itself is not implemented yet.
_Avoid_: Claiming production background scheduling exists today

**Fork/Gather Workflow Control**:
Future workflow control for parallel branches and explicit gather/join behavior.
The current product should not claim general fork/gather orchestration yet.
_Avoid_: Treating current foreach or serial graph execution as full parallel
workflow orchestration

**Scheduler Foundation**:
The runtime model that selects runnable frames and advances workflow execution without assuming there is only one active cursor.
_Avoid_: Foreach feature, concurrent foreach implementation

**Frame**:
An execution cursor for one active portion of a workflow run.
_Avoid_: Thread, task

**Frame Set**:
The collection of lifecycle frames owned by a run, including pending, running, interrupted, and completed frames until cleanup rules remove them.
_Avoid_: Running frames

**Runnable Frame**:
A pending frame that the scheduler may select for the next deterministic runtime step.
_Avoid_: Active frame, async task

**Ready Queue**:
The ordered list of runnable frame identifiers that defines deterministic scheduling order.
_Avoid_: Frame scan, implicit dict order

**Foreach Policy**:
The future runtime configuration that decides concurrent foreach admission, item failure handling, and quiescence behavior.
_Avoid_: Parallel flag

**Blocked Frame**:
A live frame that is waiting on child frame completion or an external resume event and is not currently runnable.
_Avoid_: Callback, sleeping thread

**Block Reason**:
Typed metadata describing what a blocked frame is waiting for.
_Avoid_: Ad hoc metadata flag

**Interrupt**:
A run-level pause requested by one frame that waits for external input before any more workflow scheduling happens.
_Avoid_: Per-frame prompt queue, background prompt

**Runtime Failure**:
An execution failure that stops scheduling unless a future policy explicitly handles it.
_Avoid_: Error outcome

**Trace**:
An append-only chronological record of executed workflow steps.
_Avoid_: Sorted report, graph view

**Reducer**:
A named merge rule that combines multiple writes to the same state path.
_Avoid_: Last writer wins

**State Patch**:
A validated set of state writes produced by one executed step before it is committed to run state.
_Avoid_: Partial mutation

**State Visibility**:
The committed state a frame may read based on workflow topology and completed upstream work.
_Avoid_: Shared live object

**Lineage Isolation**:
The rule that a concurrent child frame sees parent-visible state plus its own ancestor writes, but not sibling branch writes.
_Avoid_: Global committed state

**Barrier**:
A merge boundary that waits for multiple child or upstream frames and combines their lineage patches before continuation.
_Avoid_: Noop join

**Gather Node**:
A future graph step that exposes an explicit barrier for waiting on multiple branches and merging their results.
_Avoid_: Promise.all node, converge node

**Lineage Token**:
A future runtime marker for one branch lineage that can be consumed and merged by gather-style barriers.
_Avoid_: Edge id

**Run**:
One execution attempt of a workflow with input, state, frames, trace, and final output.
_Avoid_: Job, invocation

## Relationships

- A **Run** owns one or more **Frames**.
- A **Frame Set** is the source of truth for runtime cursors.
- The **Scheduler Foundation** selects one **Runnable Frame** at a time in the
  first pass.
- The **Ready Queue** defines which **Runnable Frame** is selected next.
- A **Blocked Frame** is intentionally absent from the **Ready Queue** until
  the child/event it waits on wakes it.
- A **Blocked Frame** should carry a **Block Reason** so deadlocks and wakeups
  are explainable.
- Concurrent foreach and native subgraphs depend on the **Scheduler Foundation**.
- Concurrent foreach requires a **Foreach Policy** before public support is
  enabled.
- Future concurrent foreach should be bounded by default. `max_active` and
  `max_outstanding` prevent one workflow from spawning unbounded MCP, HTTP,
  browser, or external service calls.
- Future concurrency-specific foreach settings should live in a nested
  policy object rather than expanding `ForeachNode` with many top-level fields.
- Item error handling is foreach-wide, not concurrent-only. Today, serial
  foreach supports `fail`; concurrent foreach supports `fail`, `skip`, and
  `collect`. Future serial foreach can reuse the same `skip`/`collect` policy
  shape when its execution path is upgraded.
- `collect` item error policy must declare an explicit destination for
  structured item errors. Collected errors should be ordered by item index, not
  async completion order.
- Item error policy handles runtime failures inside an item frame, such as
  thrown handler errors, schema failures, runtime-error utility nodes, or
  invalid graph execution. It does not intercept normal graph outcomes like
  `error` when those outcomes are routed.
- A collected or skipped item failure should leave that item frame `FAILED`.
  The foreach parent/barrier decides whether that failed child is handled and
  whether the run may continue.
- `skip` item error policy writes no hidden state. Failed frame status and
  trace/observability are the record; use `collect` when structured error state
  is needed.
- `collect` writes structured item error records before emitting an aggregate
  error outcome. Records include item index, frame id, failing node id, error
  type/message, and the item value when it can be represented safely.
- `collect` destinations must be state array fields. The foreach barrier writes
  the full ordered error list once, so users should not expect per-item append
  writes. Authoring and MCP validation should surface this clearly.
- `completed_with_errors` is the canonical foreach aggregate outcome when all
  items have finished but one or more item failures were handled by `collect` or
  `skip`.
- `completed_with_errors` is barrier aggregate vocabulary, not foreach-only.
  Future explicit barriers may emit it when handled branch failures occurred.
- Aggregate control-flow outcomes use result nouns/adjectives such as `done`,
  `completed_with_errors`, and optionally `failed`. Policy actions use verbs
  such as `fail`.
- If a foreach policy can emit `completed_with_errors`, validation should treat
  it as a required routable outcome. Users may route it to the same target as
  `done` explicitly.
- `collect` writes an empty list to its destination when all items succeed and
  emits `done`. It emits `completed_with_errors` only when at least one item
  failure was collected.
- `skip` emits `completed_with_errors` when one or more item failures were
  skipped. It emits `done` only when all items succeed.
- Concurrent `fail` item policy should stop scheduling new items, drain already
  started jobs to a quiescent point, capture their results safely, and then fail
  the run. It should not assume hard cancellation is safe.
- After `fail` trips, drained sibling results are for trace/observability and
  cleanup only. They should not commit normal state progress after the failure
  boundary.
- Foreach modes that continue after item failure, such as `collect` and `skip`,
  should buffer item state patches until the foreach barrier completes. Future
  concurrent foreach should always use barrier-buffered commits.
- Serial `fail` may keep immediate commits for compatibility. Commit strategy
  should be extracted into runtime helpers instead of being smeared through
  foreach execution code.
- Barrier-buffered commits should store pending state patches/results, not full
  state snapshots. Patch creation and commit must extract/reuse the existing
  node output validation, output binding, and reducer logic rather than creating
  a second write system.
- Foreach barrier commits should merge item results in item index order, not
  completion order. Reducer behavior such as list appends should therefore be
  deterministic.
- Successful item results may exist as pending barrier results before commit,
  but they are not visible as workflow state until the barrier commits.
- Pending barrier results must live in resumable `RunState`/frame metadata, not
  only in trace. Trace records history; runtime state is what resume/checkpoint
  uses.
- Concurrent item frames need lineage-local pending state: later nodes in the same
  item lineage can read earlier pending patches from that item, while sibling
  items cannot. The exact aggregate output API for committing item results to
  parent state is deferred.
- Lineage-local state should be represented as patch overlays over parent-visible
  state, not deep-copied full state snapshots.
- Patch overlays conceptually belong to lineage tokens, not execution frames.
  A scoped foreach implementation may start by storing them in item/parent
  metadata, but future Fork/Gather needs first-class lineage ownership.
- `RunState.state` remains committed parent/global state. Future frame execution
  should resolve reads against a frame-specific visible state view built from
  committed state plus visible lineage overlays.
- At a barrier, missing reducer means default replace only for single-writer
  paths. Multiple sibling lineages writing the same path require an explicit
  reducer; otherwise barrier commit raises a runtime error with writer details.
- Barrier conflict detection should use the same write-overlap rules as normal
  state writes. Ancestor/descendant writes from different lineages are conflicts
  unless an explicit merge strategy covers them.
- Reducers at barriers apply incrementally in deterministic lineage order by
  default: item index order for foreach, declared branch token order for future
  gather. Completion-order merging is a possible explicit barrier policy, not
  reducer behavior.
- Collected error records follow the same barrier merge order policy. The
  default is deterministic lineage order.
- Trace `state_changes` should mean committed state changes only. Do not encode
  pending barrier patches there unless a future typed trace field is added.
- Foreach may keep implicit barrier/iteration state on the foreach parent frame
  because it owns item spawning and refill. General branch convergence should
  become an explicit **Gather Node** later. Shared barrier merge/result helpers
  should prevent foreach and future barriers from duplicating patch ordering,
  conflict checks, and failure aggregation.
- Future Fork/Gather needs **Lineage Tokens**, not raw edge ids. A fork produces
  branch lineage tokens; a gather consumes a declared set of tokens and produces
  a new merged token. This supports partial gathers such as merging branches
  `a+b` before later merging with `c`.
- Explicit Fork/Gather is deferred until lineage tokens are designed. Parallel
  foreach remains the nearer target because its implicit lineage tokens are item
  indexes owned by one foreach activation.
- Future foreach metadata should evolve into inherited structured lineage
  context. Alias lookup such as `context.document` can remain authoring sugar,
  but runtime metadata should preserve nested foreach lineage without flat key
  collisions.
- Nested active foreach aliases should not shadow each other. Alias collisions
  in inherited context scope should be validation errors.
- Core runtime context should be structural, not alias-first. Foreach lineage
  should be addressable through paths such as `context.foreach.<id>.index`;
  `wf_authoring` can provide ergonomic alias helpers such as
  `context_path(foreach_ref("docs").index)`.
- Python `RuntimeContext` should eventually expose typed structured foreach
  context, such as `ctx.foreach["docs"].index`, while serialized frame metadata
  remains JSON-compatible dictionaries.
- Structured foreach context keys should be foreach node ids. The `as_` alias is
  authoring sugar for current item access, not the canonical runtime key.
- `wf_authoring.WorkflowBuilder.foreach(...)` should eventually return a richer
  ref exposing context selectors such as `.item` and `.index`, so users do not
  hand-write `context.foreach.<id>...` paths.
- Normal node authors should receive foreach values through mapped input.
  Inspecting `RuntimeContext.foreach` is an advanced escape hatch for nodes that
  genuinely need index/frame/lineage context.
- `as_` remains useful ergonomic sugar and human-readable trace/docs context,
  but structured foreach refs should be preferred for non-trivial authoring.
- Future foreach policy shape should validate cross-field rules: `collect`
  requires `collect_to`, non-collect actions forbid `collect_to`,
  `mode="concurrent"` requires a concurrent policy, and `mode="serial"` forbids
  a concurrent policy. Deprecated top-level `on_item_error` may parse into the
  nested item error policy, but canonical dumps should use the nested shape.
- `ForeachConcurrentPolicy` should split limits into `max_active` and
  `max_outstanding`. Defaults are `max_active=4` and `max_outstanding=20`;
  validation requires `max_outstanding >= max_active`. Ready or running item
  frames consume active capacity; blocked item frames consume outstanding
  capacity but not active capacity.
- A blocked non-interrupt item frame frees active capacity and may let foreach
  start another item when `max_outstanding` also has room. A run-level interrupt
  still stops scheduling.
- The foreach parent frame owns refill decisions. Scheduler wakes/schedules
  frames; foreach-specific policy decides whether to start more children,
  finish, or fail.
- When an item frame becomes blocked, it frees active capacity only for its
  nearest foreach capacity owner. Future item metadata should identify that
  owner rather than waking arbitrary ancestors.
- Foreach capacity is local correctness policy, not total process protection.
  Future runtime should also have basic global run limits in `wf_core`; source-
  or tool-specific limits belong in the platform layer.
- A future global `wf_core` runtime limit should count active node handler calls,
  not all active frames. Control-flow frames are scheduler work; node calls are
  the expensive external/user-code execution boundary.
- Global node-call limits do not replace foreach caps. Foreach caps bound local
  scheduling fairness, outstanding frame count, memory, and pending results;
  global node-call limits bound expensive handler execution across the run.
- Platform source/tool/account limits should be enforced at the node-handler
  boundary, before invoking the external call. They layer on top of core global
  node-call admission instead of replacing it.
- Node calls waiting on platform source/tool/account limits still count as
  active node calls. Core global node-call admission should happen before
  platform-specific semaphore acquisition.
- Waiting on a source/tool/account semaphore keeps the frame `RUNNING`; it is
  backpressure inside the admitted node-call boundary, not workflow-level
  `BLOCKED` state that frees foreach active capacity.
- An **Interrupt** pauses the whole **Run**, even if the interrupted frame is a
  child of future concurrent work.
- A **Runtime Failure** is distinct from a node returning an `error` outcome.
  Outcomes are graph control flow; runtime failures are scheduler stops unless
  a policy handles them.
- A node `error` outcome remains normal graph control flow. A runtime-error
  utility node or engine exception is what turns control flow into a
  **Runtime Failure**.
- Missing edges for declared outcomes are validation errors, not normal runtime
  branch policy.
- Unsupported concurrent foreach semantics should be rejected by validation before
  runtime. Runtime may stay defensive, but validation owns the user-facing gate.
- `on_item_error="collect"` and `"skip"` are supported for concurrent foreach.
  Serial foreach still behaves as fail-only until its execution path explicitly
  adopts barrier-buffered item error handling.
- A **Trace** records actual scheduler execution order; grouping or sorting by
  foreach index is a presentation concern.
- Concurrent child frames may write to the same state path only through a
  **Reducer**.
- Future concurrent frames should produce **State Patches** that the scheduler
  commits atomically.
- A frame's **State Visibility** excludes uncommitted sibling writes.
- Future concurrent branches require **Lineage Isolation**: sibling branch writes
  are invisible unless the graph explicitly joins or merges them.
- A **Barrier** is the explicit merge boundary for concurrent lineage patches.
- Foreach may own an implicit **Barrier**; future graph-level convergence may use
  an explicit barrier node.

## Example Dialogue

> **Dev:** "Are we implementing concurrent foreach now?"
> **Domain expert:** "No. First we are implementing the **Scheduler Foundation** so a **Run** can eventually manage multiple runnable **Frames** safely."

## Flagged Ambiguities

- "concurrent foreach" is the future workflow mode. The resolved current scope is
  **Scheduler Foundation**: deterministic internal runtime prep before public
  concurrent foreach support.
- `current_frame_id` / `current_node_id` are compatibility fields for the selected cursor, not the source of truth for all runnable work.
- `current_frame_id` remains persisted for compatibility, but means "the frame
  currently selected by the scheduler", not "the only live frame".
- When the **Ready Queue** is empty, the scheduler must explicitly resolve the
  run as completed, interrupted, failed, or deadlocked. `current_node_id` alone
  is not a terminal-state rule.
- In the first scheduler pass, any **Runtime Failure** fails the whole run and
  stops scheduling.
- `RUNNING` currently means "selected cursor during a deterministic step", not
  "async task already in flight".
- `BLOCKED` should be a first-class frame status for live frames waiting on
  child frame completion or external resume.
- `INTERRUPTED` remains a distinct frame status, not just `BLOCKED` with an
  interrupt reason, because it carries externally visible resume semantics.
- Scheduling order should be explicit through a **Ready Queue**, not inferred
  from frame dictionary iteration.
- `mode="concurrent"` stays unsupported until **Foreach Policy** and parent
  completion semantics are explicit.
- A **Run** has at most one outstanding **Interrupt**. Resume wakes the frame
  referenced by that interrupt and scheduling continues from the **Ready Queue**.
- When a child frame interrupts, only that frame becomes `INTERRUPTED`.
  Ancestors waiting on it remain `BLOCKED`; the **Run** status carries the
  global pause.
- Ready sibling frames are preserved during an **Interrupt**, but the resumed
  frame is placed at the front of the **Ready Queue** before scheduling
  continues.
- Future concurrent execution should not assume in-flight node calls can be
  safely cancelled. When an **Interrupt** occurs, scheduling should stop; already
  started jobs should drain to pending results before resume/commit policy
  decides what becomes visible.
- Future concurrent interrupts should return control to the caller only at a
  quiescent pause point: no new work is scheduled, already-started jobs have
  drained, and their results are captured without unsafe commits.
- Future async execution must protect append-only **Trace** writes, but should
  not change trace semantics. Async runtime is an execution capability for
  simultaneous async node handlers, not a separate foreach workflow mode.
- Scheduler block/wake events should not be added to the public **Trace** in
  the first pass. Future observability, including OpenTelemetry-style spans, is
  a separate concern.
- Frame identifiers remain strings in the first pass, but construction should be
  centralized so a future structural frame id can replace the string format.
- Typed runtime metadata helpers should return `None` for the wrong frame kind,
  but raise for malformed metadata on the right kind. Corrupt runtime metadata
  is a runtime invariant failure.
- First-pass **Block Reason** support only needs child-frame blocking; future
  interrupt, subgraph, and concurrent barrier reasons can extend the same shape.
- Frame creation must reject duplicate frame identifiers. The **Ready Queue**
  must contain only existing pending frames and must never contain duplicate
  frame identifiers.
- Enqueue wakeups may be idempotent: enqueueing an already-ready frame should
  not duplicate it, and priority enqueue may move it to the front.
- Completed frames should remain in the **Frame Set** for the lifetime of an
  in-memory run. Later persistence can add explicit compaction, but scheduler
  correctness should not depend on deleting completed frames.
- Stack-style frame collapse should be demoted in favor of explicit frame
  completion and parent wakeup helpers. Parallel scheduling cannot rely on
  "collapse to parent" semantics.
- The engine/scheduler selects a frame before step preparation. `prepare_step`
  remains a readability helper for resolving the selected frame's current node,
  not for choosing runnable work.
- Sync and async engine loops should migrate to scheduler selection together so
  their runtime semantics do not diverge.
- The **Ready Queue** is part of **Run** state and should be serialized with
  `RunState` so resume/checkpoint behavior preserves scheduler order.
- A new **Run** starts with the root frame pending in the **Ready Queue**.
  Compatibility cursor fields may still point at root initially.
- First-pass serialized `RunState` changes should be additive. `ready_frame_ids`
  may be added, but existing run fields and trace shape should not churn.
- Existing valid serial workflows should keep the same final output/state, node
  execution order, foreach item count, interrupt resume behavior, and meaningful
  trace order after the first scheduler refactor.
- Scheduler foundation is not complete without tests for ready queue selection,
  duplicate protection, block/wake behavior, deadlock detection, serial foreach
  regression, and interrupt resume priority.
- Selecting a **Runnable Frame** removes it from the **Ready Queue** immediately
  and marks it `RUNNING`.
- A normal non-terminal step advance marks the same frame `PENDING` and
  re-enqueues it. Terminal, blocked, interrupted, or failed frames are not
  re-enqueued.
- Ready scheduling is FIFO and one-step-at-a-time. A still-runnable frame goes
  to the back of the **Ready Queue** after each step.
- Serial foreach blocks the parent on one iteration child at a time, so the
  child runs until completion/interruption/failure before the parent wakes.
- Future async execution must protect shared state writes. Last-writer-wins is
  not an acceptable merge policy for concurrent child frames.
- Serial execution may continue mutating state immediately until concurrent
  execution needs scheduler-controlled **State Patch** commits.
- Concurrent sibling frames must not depend on observing each other's writes. Use
  serial foreach or explicit graph structure for ordered dependencies.
- Missing reducers mean replace only within a single serial lineage. At a
  **Barrier**, multiple writes to the same path without a reducer are conflicts,
  not last-writer-wins replacements.
- Current `JoinNode` should not silently become a **Barrier**. It may be
  repurposed later only through an explicit design pass.
- The first **Scheduler Foundation** implementation should create ready/block/wake
  seams only. **Lineage Isolation** and **Barrier** merge behavior are future
  concurrent semantics, not first-pass behavior.
- First-pass scheduler code should add durable seams such as ready queue,
  block/wake helpers, and typed foreach metadata. It should not add public
  concurrent policy, barrier, snapshot, or lineage-patch fields before those
  semantics are enforced.
- Scheduler rules are shared by sync and async runtime paths; only node handler
  execution differs.
- The first scheduler helpers should live in a scheduler module, not a
  concurrency module. Actual async task orchestration can get separate
  concurrency code later.
- Scheduler helpers are internal runtime infrastructure in the first pass and
  should not be exported as public `wf_core` API yet.
