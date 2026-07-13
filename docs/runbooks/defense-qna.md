# Defense Q&A Runbook

This document is a defense crib sheet. It is not a replacement for the thesis
or slides. Use it to answer predictable examiner questions without overstating
what lda.chat implements.

Each answer has two forms:

- **Short answer:** what to say first under pressure.
- **Expanded answer:** what to say if the examiner pushes.
- **Point to:** where to navigate or what evidence to mention.

## Framing

### Where is the AI agent?

**Short answer:** The autonomous planner is external. The thesis implements the
workflow substrate and tool surface that external agents can operate.

**Expanded answer:** The original product goal was an AI agent that creates and
automates workspace workflows. In building that, I focused on the lower-level
system the agent needs: typed workflow definitions, validation, deployment
binding, execution records, traces, diagnostics, and interrupt/resume
contracts. Existing planners such as Codex, Claude, or another LLM loop can
drive this surface through CLI or JSON-RPC. The thesis contribution is not a
new planning algorithm.

**Point to:** Title framing, Abstract/Introduction boundary, Scene 1, Scene 4
planner/runtime boundary, `wf` CLI / JSON-RPC operations.

### Why does the title say "AI Agent" if the planner is external?

**Short answer:** The title describes the product direction; the implemented
thesis contribution is the agent-operable workflow substrate.

**Expanded answer:** I handle that risk directly in the thesis. The submitted
implementation does not pretend to include a full autonomous agent brain. It
implements the layer that turns planner output into durable workflows: schemas,
artifacts, deployments, runs, traces, and repairable diagnostics. A chat or
LangGraph-style wrapper could be added later as a thin agent interface over
the same operations.

**Point to:** Defense runbook framing, Introduction boundary wording, Future
Work.

### Did you build a product, a library, or a research prototype?

**Short answer:** It is a research prototype with product-facing surfaces.

**Expanded answer:** The system has real CLI, JSON-RPC, web-console, runtime,
and persistence paths, but it is not production-ready software. The thesis
uses it to evaluate an architectural boundary: how external agents or humans
can author, validate, deploy, run, and inspect reusable workflows.

**Point to:** CLI docs, workflow console, verification snapshot, limitations.

### What is the core thesis contribution?

**Short answer:** A typed workflow lifecycle and runtime boundary for
agent-operable workspace automation.

**Expanded answer:** The contribution is the separation between external
planning and deterministic runtime execution. Planners propose workflow
structure, but the platform owns schema validation, source binding, immutable
artifacts, deployments, run records, traces, diagnostics, and controlled
interrupt/resume behavior.

**Point to:** Scenes 4-6, Draft-Artifact-Deployment-Run lifecycle, source
provider boundary, NodeUse model.

## Problem And Positioning

### Why not just let Codex or Claude write scripts?

**Short answer:** Generated scripts are useful, but they do not automatically
provide a managed workflow lifecycle.

**Expanded answer:** Scripts can be simple and debuggable, but the lifecycle is
ad hoc: inputs, versions, deployments, execution state, traces, and recovery
boundaries must be reinvented each time. lda.chat treats workflows as managed
objects with validation and persisted execution records.

**Point to:** Related systems section, generated-scripts discussion branch,
Scene 3.

### Why not just use direct LLM tool orchestration?

**Short answer:** Direct tool use can act, but reusable automation needs
durable contracts.

**Expanded answer:** A direct tool loop is good for one-off work. The thesis
targets reusable workspace automations, where the system needs to remember
what was authored, validate it before execution, bind logical requirements to
sources, and inspect what happened after execution.

**Point to:** Direct orchestration baseline, lifecycle scenes, run traces.

### How is this different from n8n or Zapier?

**Short answer:** Those are mature workflow automation platforms; lda.chat
focuses on typed, agent-operable authoring and source boundaries.

**Expanded answer:** n8n and Zapier center human-authored or hosted automation
flows. lda.chat is a prototype exploring what the workflow substrate should
look like when an external LLM agent is a first-class author/operator. It does
not claim to beat their production features, integrations, scheduling, or
credential systems.

**Point to:** Positioning section, hosted-automation branch, limitations.

### How is this different from Temporal?

**Short answer:** Temporal is a production durable-execution system; this
prototype focuses on agent-operable workflow authoring and inspection.

**Expanded answer:** Temporal solves durable execution at industrial depth.
lda.chat is not trying to replace that. Its emphasis is different: typed
workflow lifecycle surfaces, provider-neutral capability projection, external
agent operation, and explanation/repair surfaces for authoring.

**Point to:** Related systems, future work, non-goals.

### How is this different from LangGraph?

**Short answer:** LangGraph helps build agent graphs; lda.chat focuses on the
workflow substrate and lifecycle records around reusable workspace automation.

**Expanded answer:** LangGraph is closer to the planner/agent-graph side.
lda.chat focuses on artifacts, deployments, source binding, runtime records,
traces, validation, and CLI/API surfaces that external agents can operate.
They are adjacent, not mutually exclusive.

**Point to:** Durable-agent-graphs branch, planner/runtime boundary.

### Is this just MCP with extra steps?

**Short answer:** No. MCP is a capability protocol; lda.chat uses capability
surfaces inside a workflow lifecycle.

**Expanded answer:** MCP helps expose tools and resources to model clients.
The thesis asks what happens after tools are discovered: how to turn them into
validated workflows, persist versions, bind deployments, run them, inspect
trace records, and resume typed interrupts.

**Point to:** MCP branch, source provider boundary, capability projection.

## Architecture

### What are Draft, Artifact, Deployment, and Run?

**Short answer:** Draft is mutable authoring, Artifact is immutable workflow
definition, Deployment binds it to sources, and Run is one execution record.

**Expanded answer:** Drafts support iterative workflow construction and
validation. Artifacts freeze a workflow definition. Deployments connect logical
workflow requirements to concrete runtime sources. Runs store execution status,
outputs, traces, and interruption state.

**Point to:** Scene 5 lifecycle; workflow lifecycle chapter.

### Why separate artifact and deployment?

**Short answer:** The workflow definition and runtime binding change at
different rates.

**Expanded answer:** An artifact should be stable and versioned. A deployment
can bind that artifact to a particular source configuration or environment.
This keeps workflow identity separate from environment-specific wiring.

**Point to:** Deployment validation, lifecycle docs.

### Why have drafts if raw plans can bypass drafts?

**Short answer:** Drafts help iterative authoring; raw plans support direct
imports when the caller already has a full plan.

**Expanded answer:** Agents and humans often need repair loops, schema
projection, route edits, and validation hints. Drafts make that workflow
incremental. Raw plan import remains useful for complete generated plans or
case-study fixtures.

**Point to:** Raw-plan-import branch, lifecycle diagram note, authoring docs.

### What is NodeUse?

**Short answer:** NodeUse is the callable-node path: validate input, invoke a
capability, reduce output into workflow state.

**Expanded answer:** NodeUse is not the entire runtime loop. It is the path for
a step that calls a capability. Separating NodeUse from the broader dispatcher
helps explain why the system can reason about schemas, bindings, local outputs,
state updates, routes, and trace records.

**Point to:** Scene 6 NodeUse deep link, core runtime diagrams.

### Why provider-neutral sources?

**Short answer:** Workflows should depend on capability contracts, not a
specific provider implementation.

**Expanded answer:** A workflow can require a capability shape while the
deployment chooses concrete built-in, Python, MCP, or future providers. This
reduces coupling and makes source drift or missing capability errors explicit.

**Point to:** Architecture chapter, provider-security branch, source package.

### What does validation actually validate?

**Short answer:** It validates workflow shape, schema compatibility, bindings,
routes, destination paths, and deployment/source availability.

**Expanded answer:** Validation is layered. Draft validation catches authoring
issues. Artifact/deployment validation checks compiled workflow structure and
source bindings. Runtime validation checks node inputs and interrupt resumes
before mutation where applicable.

**Point to:** Validation diagnostics branch, `wf explain`, test evidence.

### Why is trace inspection important?

**Short answer:** It makes workflow execution auditable after the planner is
gone.

**Expanded answer:** If an external agent authored or operated a workflow, the
system still needs a durable record of what ran, with which inputs, outputs,
outcomes, and interruptions. Traces make failures debuggable and claims
inspectable.

**Point to:** Run persistence branch, evidence inspector, trace frames.

## Demo Reliability

### Why is the defense demo prepared instead of live model-driven?

**Short answer:** The demo proves the workflow substrate, not arbitrary model
planning ability.

**Expanded answer:** A live model can be slow or unreliable during a defense.
The thesis claim is that the platform can represent, validate, execute,
interrupt, resume, and inspect workflows. The prepared replay demonstrates
that product path deterministically. Live agent trials are evaluated separately
with their own validity limits.

**Point to:** Replay provenance branch, prepared recording, evaluation chapter.

### Is a prepared replay cheating?

**Short answer:** No, as long as it is described as replay and not presented as
live planning.

**Expanded answer:** The replay is a presentation mechanism for a real workflow
case study. It preserves operation evidence and makes the defense robust. It
would be cheating only if I claimed the replay was a live model planning from
scratch.

**Point to:** Replay provenance label, runbook fallback wording.

### What if the live server fails?

**Short answer:** Continue with replay and explain that the thesis evidence is
not dependent on live connectivity.

**Expanded answer:** The live server is useful product proof, but the code,
tests, committed example, replay evidence, and thesis evaluation support the
same architectural claims. A failure is not ideal, but it does not invalidate
the thesis.

**Point to:** Defense presentation runbook, fallback section.

### Why does the demo use local sources instead of Google Drive or email?

**Short answer:** To show the workflow/source boundary without adding external
credential risk.

**Expanded answer:** The architecture supports source boundaries and could be
extended to external services, but production credential handling is explicitly
out of scope. Local sources make the case study deterministic and auditable.

**Point to:** Limitations, source provider design, future work.

### Does the demo prove scheduling or automation?

**Short answer:** No. It proves workflow creation/execution/inspection, not
scheduling.

**Expanded answer:** Scheduling is a natural future layer. The current system
can run workflows and persist execution records, but it does not implement a
hosted scheduler or recurring trigger system.

**Point to:** Future work, hosted-automation branch.

## Evaluation

### Does the 36-trial campaign prove model performance?

**Short answer:** No. It is bounded engineering evidence about agent
operability and UX failure modes.

**Expanded answer:** The campaign uses small `n`, hosted free models, manual
audit, and changed product snapshots across waves. It should not be read as a
controlled model benchmark. Its value is showing whether external agents could
use the surface and where they struggled.

**Point to:** Evaluation validity branch, Appendix C, threat-to-validity text.

### Why is manual audit acceptable?

**Short answer:** Because the key validity questions involve behavior that
automatic success flags cannot fully judge.

**Expanded answer:** Agents can produce a correct output while reading source
code, prior answers, or adjacent stores. The manual audit separates task
completion from valid product-surface use. The thesis treats this as bounded,
author-performed evidence, not as a definitive benchmark.

**Point to:** Trial reports, manual audit fields, read-behavior flags.

### What did the trials actually teach you?

**Short answer:** They exposed product UX gaps: schema discovery, repair hints,
binding commands, output schemas, shell assumptions, and source contamination.

**Expanded answer:** The trials drove concrete improvements in CLI vocabulary,
schema commands, draft focused edits, diagnostics, repair hints, report
projection, resume metadata, and prompt/runbook clarity. That is why the
evaluation is useful even with limited statistical power.

**Point to:** Roadmap entries, challenge reports, UX issue notes.

### Why not compare against n8n, Temporal, or LangGraph quantitatively?

**Short answer:** That would be a different evaluation with different
baselines and more time.

**Expanded answer:** The thesis is a systems implementation thesis. It compares
conceptual boundaries and demonstrates feasibility rather than claiming
superior performance against mature systems. A controlled comparative study is
future work.

**Point to:** Related systems, limitations, future work.

### Are the automated tests enough evidence?

**Short answer:** They prove implementation coverage, not the entire research
claim.

**Expanded answer:** The tests support correctness of schema handling,
lifecycle operations, runtime behavior, transports, and CLI/API contracts.
They are paired with case studies and audited agent trials to support the
broader feasibility claim.

**Point to:** Verification snapshot, test suites, case study chapters.

### What is the biggest evaluation weakness?

**Short answer:** The external-agent evaluation is small and manually audited.

**Expanded answer:** The thesis acknowledges this. The campaign is useful for
observing UX and feasibility, but it cannot establish broad model
generalization, token savings, or superiority over other systems.

**Point to:** Threats to validity, evaluation limitations.

## Security And Production Limits

### Is this production-ready?

**Short answer:** No. It is a prototype with explicit production limitations.

**Expanded answer:** Production credential handling, RBAC, tenant isolation,
untrusted-code sandboxing, scheduling, and hardened deployment are not
implemented. The prototype focuses on architecture and local-first evidence.

**Point to:** Limitations chapter, roadmap boundaries.

### Is reading local files safe?

**Short answer:** Only under the prototype's trusted local assumptions.

**Expanded answer:** Local Python sources and filesystem-backed stores are
useful for auditability and thesis scope. They are not a production security
boundary. A production system needs sandboxing, permissions, and credential
isolation.

**Point to:** Source boundary docs, security limitations.

### What does the web console security model enforce?

**Short answer:** It restricts upstream targets to loopback for the local demo.

**Expanded answer:** The Hono proxy rejects non-loopback targets and keeps the
console local-first. That prevents the demo console from becoming a general
browser-to-network proxy, but it is not a complete production security design.

**Point to:** Web README security section, loopback target policy.

### Could malicious workflow code run?

**Short answer:** In production, that needs sandboxing. The prototype assumes
trusted local sources.

**Expanded answer:** The Python source path is a trusted extension mechanism in
this prototype. It demonstrates capability projection and execution semantics,
not arbitrary untrusted-code isolation.

**Point to:** Python source docs, limitations, future work.

## Implementation Depth

### Is this just a CLI?

**Short answer:** No. The CLI is one front door over a workflow API and runtime.

**Expanded answer:** The system includes core workflow models, runtime
execution, artifact/draft/deployment/run APIs, JSON-RPC transport, server
composition, source providers, CLI, tests, and a web console. The CLI is
important because agents can use it, but it is not the whole system.

**Point to:** Project map, source architecture, web console, JSON-RPC server.

### Why JSON-RPC?

**Short answer:** It is simple, explicit, and easy for local tools and web
clients to call.

**Expanded answer:** The console and CLI can share the same operation surface.
JSON-RPC keeps the transport lightweight while preserving method names,
request/response evidence, and typed schemas in the TypeScript client layer.

**Point to:** Web RPC package, protocol evidence drawer/inspector.

### Why not only use MCP?

**Short answer:** MCP is useful, but the workflow lifecycle needs its own API.

**Expanded answer:** MCP can expose tools to agents. lda.chat needs operations
for drafts, artifacts, deployments, runs, validation, and inspection. Those are
workflow lifecycle operations, not just tool calls.

**Point to:** Legacy MCP notes, JSON-RPC API, CLI.

### Why schemas everywhere?

**Short answer:** Schemas make planner output checkable before runtime actions.

**Expanded answer:** External agents are probabilistic. Schemas let the system
reject invalid bindings, missing fields, wrong interrupt resumes, and source
drift before they become silent runtime corruption.

**Point to:** Schema catalog, validation diagnostics, typed interrupts.

### Why does this need persisted stores?

**Short answer:** Reusable automation needs durable state.

**Expanded answer:** Without persistence, an agent can only perform an action
sequence. With persisted artifacts, deployments, runs, and traces, the system
can inspect, rerun, debug, and audit workflows after the original planning
session.

**Point to:** File-backed stores, run persistence, trace inspection.

## Future Work

### What would the real AI agent layer look like?

**Short answer:** A chat or agent graph wrapper that calls the existing `wf`
CLI/API operations as tools.

**Expanded answer:** The wrapper could be implemented with a chat UI,
LangGraph-style planner loop, or an AI SDK tool-calling layer. It would not
replace the workflow substrate; it would use it to create, validate, deploy,
run, and inspect workflows.

**Point to:** Future work, demo agent boundary, AgentDriver contract.

### What is the next highest-value product work?

**Short answer:** Operational hardening and evaluation: transactional stores,
provider lifecycle management, production auth and secrets, sandboxing, richer
debugging, and controlled comparative evaluation.

**Expanded answer:** The presentation and chat surfaces now demonstrate the
existing substrate. The next product work is to harden the surrounding
operational boundaries and evaluation: transactional persistence, provider
lifecycle management, authentication and secret handling, sandboxing, richer
run debugging, and a controlled comparative study.

**Point to:** Current roadmap wishlist.

### What would make the evaluation stronger?

**Short answer:** Stable product snapshot, larger model set, independent
auditors, and controlled baselines.

**Expanded answer:** A stronger study would freeze prompts and code, run more
trials, compare against direct tool orchestration and generated scripts, track
token/turn metrics consistently, and use independent audit criteria.

**Point to:** Threats to validity, future evaluation work.

### What would make this production-ready?

**Short answer:** Credentials, RBAC, sandboxing, deployment hardening,
scheduling, observability, and integration management.

**Expanded answer:** The thesis deliberately stops before those layers. They
are important, but they would dilute the core implementation question: how to
represent and execute agent-operable reusable workflows.

**Point to:** Limitations and Future Work.

## Trap Questions

### So you did not build an AI agent?

**Short answer:** I built the workflow substrate for one, not the autonomous
planner itself.

**Expanded answer:** That is the honest boundary. The system is agent-operable:
external agents can inspect schemas, create workflows, validate drafts, deploy
artifacts, run workflows, and inspect traces. It does not claim to invent a new
LLM planning algorithm.

**Point to:** Planner/runtime boundary, CLI/API surfaces.

### Is this just prompt engineering?

**Short answer:** No. Prompting helped evaluation, but the contribution is the
typed runtime and lifecycle system.

**Expanded answer:** The system has concrete models, validation, runtime
execution, transports, persisted records, schema projection, and tests. Prompts
are only one way external agents learn to use the surface.

**Point to:** Core/runtime/API packages, tests, schema catalog.

### Could the same thing be done with a few scripts?

**Short answer:** For one workflow, maybe. For reusable, inspectable workflow
lifecycle, scripts alone are not enough.

**Expanded answer:** The thesis is about the managed lifecycle: versioned
artifacts, deployments, validation, source bindings, run records, traces, and
interrupts. Scripts can be one capability behind a workflow, not the whole
platform boundary.

**Point to:** Lifecycle, generated scripts baseline.

### Why should an examiner trust the demo?

**Short answer:** Because the demo is supported by committed code, tests,
replay evidence, and explicit limitations.

**Expanded answer:** The prepared replay is transparent. It is not claimed as
live model planning. The live code path exists separately through JSON-RPC and
the console. The thesis evidence does not rely on pretending the demo is more
general than it is.

**Point to:** Runbook fallback, replay provenance, test suite.

### What is the single most important limitation?

**Short answer:** The work proves a prototype substrate, not broad autonomous
agent success.

**Expanded answer:** The architecture is credible and implemented, but the
agent evidence is bounded. The strongest claim is feasibility and product
surface design, not generalized agent performance or production readiness.

**Point to:** Evaluation limitations, Future Work.
