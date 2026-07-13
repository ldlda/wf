# Defense speech and claim audit

This runbook gives you the must-say 9:27 defense speech, a 1:15 navigation buffer, and a prioritized 12-minute question period. It also marks claims that require qualification so the presentation stays aligned with the thesis and current implementation. The typed catalog at `web/apps/console/src/presentation/presenter/presenter-notes.ts` is the source for the must-say text.

## Timing and evidence rules

Use these evidence labels while rehearsing. Do not read the labels aloud.

- **Supported**: stated in the thesis and backed by repository evidence
- **Implementation extension**: implemented after or beyond the thesis case study; identify it as a separate demonstration
- **Qualify**: accurate only within an explicit boundary
- **Do not claim**: unsupported, untested, or excluded from scope

Target 9:27 for the must-say speech. Keep 1:15 for navigation or demo delay; the complete deck target is 10:42. The question period then has 12 minutes.

| Segment | Target |
| --- | ---: |
| Scenes 1-2: goal and problem | 1:00 |
| Scenes 3-6: positioning, model, and architecture | 2:23 |
| Scenes 7-11: prepared demonstration | 2:49 |
| Scene 12: evaluation | 2:00 |
| Scene 13: limits and conclusion | 1:15 |
| Must-say speech | 9:27 |
| Navigation buffer | 1:15 |
| Complete deck target | 10:42 |

## Main speech

### Scene 1: State the ambition and the submitted contribution

**Route:** `thesis/title` then `thesis/substrate`  
**Time:** 0:00-0:30
**Evidence:** Supported

**Beat:** `thesis/title`
**Goal:** Separate the AI-agent ambition from the implemented contribution.
**Anchor terms:** AI-agent goal; platform underneath

**Beat:** `thesis/substrate`
**Goal:** State what the platform lets its users do.
**Anchor terms:** agents and humans; build, run, inspect

Say:

> The title describes the original goal: an AI agent for workspace automation. My contribution is the platform underneath that agent.
>
> It lets agents and humans build workflows, run them, and inspect what happened.

Keep the boundary explicit. The thesis states this distinction in the Abstract and Introduction ([thesis lines 109-121](../thesis/system-design-implementation.md#abstract) and [lines 145-181](../thesis/system-design-implementation.md#introduction)).

### Scene 2: Explain why direct tool use is insufficient

**Route:** `problem/direct-actions` then `problem/missing-contracts`  
**Time:** 0:30-1:00
**Evidence:** Supported

**Beat:** `problem/direct-actions`
**Goal:** Show why one successful chat is not yet automation.
**Anchor terms:** tool calls; not reusable

**Beat:** `problem/missing-contracts`
**Goal:** Name the minimum durable properties reusable automation needs.
**Anchor terms:** saved definition; validation; execution records

Say:

> Like the chat example, an agent can call tools and finish one task. But that conversation is not yet a reusable workflow.
>
> Reusable automation needs a saved definition, validation, execution records, and a clear way to pause and continue.

Do not claim that direct tool use or generated scripts are inherently bad. The thesis argues that reusable operation needs additional lifecycle contracts ([lines 214-277](../thesis/system-design-implementation.md#problem-statement-and-requirements)).

### Scene 3: Position the work without claiming superiority

**Route:** `positioning/landscape` then `positioning/lda-position`  
**Time:** 1:00-1:35
**Evidence:** Supported, with qualification

**Beat:** `positioning/landscape`
**Goal:** Place the work beside familiar adjacent systems.
**Anchor terms:** Python / n8n / Zapier; LangGraph; MCP

**Beat:** `positioning/lda-position`
**Goal:** State the platform's narrow position without a superiority claim.
**Anchor terms:** provider-neutral; workflow layer; not a replacement

Say:

> Existing systems solve different parts of this problem: Python scripts, n8n, Zapier, LangGraph, and MCP.
>
> My platform does not replace them. It provides a provider-neutral workflow layer that agents and humans can operate.

Qualify provider neutrality as demonstrated for the three implemented source families. Do not present compatibility with arbitrary future providers as measured evidence ([lines 460-521](../thesis/system-design-implementation.md#source-model)).

### Scene 4: Draw the planner and runtime boundary

**Route:** `planner-runtime/planner`, `planner-runtime/runtime`, then `planner-runtime/boundary`  
**Time:** 1:35-2:15
**Evidence:** Supported, with qualification

**Beat:** `planner-runtime/planner`
**Goal:** Assign workflow decisions to an external planner.
**Anchor terms:** human or AI planner

**Beat:** `planner-runtime/runtime`
**Goal:** Assign execution and recording to the runtime.
**Anchor terms:** validation; step-by-step execution; state and traces

**Beat:** `planner-runtime/boundary`
**Goal:** Introduce the public seam between clients and runtime.
**Anchor terms:** Workflow API; CLI; JSON-RPC

Say:

> A human or AI planner decides what workflow to build.
>
> The runtime validates the graph, executes it step by step, records state and traces, and pauses at declared boundaries.
>
> Both sides communicate through the Workflow API. Today, clients reach it through the CLI or JSON-RPC without accessing runtime internals directly.

Say “deterministic core semantics for fixed definitions and handler results,” not “all execution is deterministic.” Remote calls, provider code, resource reads, and external side effects may be nondeterministic ([lines 808-821](../thesis/system-design-implementation.md#workflow-core)).

### Scene 5: Define the lifecycle vocabulary

**Route:** `lifecycle/draft`, `lifecycle/artifact`, `lifecycle/deployment`, then `lifecycle/run`  
**Time:** 2:15-2:51
**Evidence:** Supported

**Beat:** `lifecycle/draft`
**Goal:** Introduce the editable lifecycle state.
**Anchor terms:** Draft; being built

**Beat:** `lifecycle/artifact`
**Goal:** Introduce the immutable saved definition.
**Anchor terms:** Artifact; immutable version

**Beat:** `lifecycle/deployment`
**Goal:** Connect a saved definition to a runnable environment.
**Anchor terms:** Deployment; sources; ready

**Beat:** `lifecycle/run`
**Goal:** Introduce one persisted execution record.
**Anchor terms:** Run; status; output and trace

Say:

> A workflow moves through four lifecycle stages. Draft means the workflow is still being built.
>
> Artifact is a saved, immutable version.
>
> Deployment connects that version to the sources it needs and checks whether it is ready.
>
> Run is one recorded execution, including its status, output, and trace.

Keep Scene 5 conceptual. Scene 9 applies this vocabulary to the prepared example. Also note that raw plans can create artifacts without passing through Draft ([lines 629-660](../thesis/system-design-implementation.md#workflow-lifecycle)).

### Scene 6: Zoom through the implemented architecture

**Route:** `architecture/overview`, `architecture/client`, `architecture/api`, then `architecture/runtime`<br>
**Time:** 2:51-3:23
**Evidence:** Supported

**Beat:** `architecture/overview`
**Goal:** Show how the implementation realizes the earlier concepts.
**Anchor terms:** architecture spine

**Beat:** `architecture/client`
**Goal:** Show that humans and agents share one public surface.
**Anchor terms:** shared operations

**Beat:** `architecture/api`
**Goal:** Identify the system's public front door.
**Anchor terms:** Workflow API; public boundary

**Beat:** `architecture/runtime`
**Goal:** Explain what the server composes behind the API.
**Anchor terms:** WorkflowServer; records and capabilities; execution core

Say:

> This is how those concepts are organized in the implementation.
>
> Humans and agents use the same public workflow operations.
>
> The Workflow API is the front door. It exposes lifecycle operations without exposing runtime internals.
>
> Behind it, the workflow server brings together stored records, available capabilities, and the execution core.

The optional NodeUse deep dive remains available through the architecture focus route and Q&A; it is not part of the timed forward sequence.

### Scene 7: Introduce the prepared demonstration honestly

**Route:** `agent-handoff/request`  
**Time:** 3:23-3:35
**Evidence:** Implementation extension

**Beat:** `agent-handoff/request`
**Goal:** Disclose the prepared demonstration before it begins.
**Anchor terms:** prepared example; not an autonomous planner

Say:

> This is a prepared example, not a live autonomous AI agent. It shows how an agent could use the platform to build and run a workflow.

If replay is active, say: “This is the reviewed recording, not a live model planning this workflow.”

### Scene 8: Show the prepared lifecycle

**Route:** all six `prepared-lifecycle/*` beats
**Time:** 3:35-4:17
**Evidence:** Implementation extension; supported with qualification

**Beat:** `prepared-lifecycle/discover`
**Goal:** Show that authoring starts with interface discovery.
**Anchor terms:** sources; capabilities

**Beat:** `prepared-lifecycle/draft`
**Goal:** Show mutable workflow authoring.
**Anchor terms:** Draft; editable workflow

**Beat:** `prepared-lifecycle/diagnose`
**Goal:** Show a concrete structured validation failure.
**Anchor terms:** validation; missing_outcome_edge

**Beat:** `prepared-lifecycle/repair`
**Goal:** Show the exact focused correction and revalidation.
**Anchor terms:** set-route; validation passes

**Beat:** `prepared-lifecycle/artifact`
**Goal:** Show the transition to an immutable saved version.
**Anchor terms:** Artifact; immutable

**Beat:** `prepared-lifecycle/deployment`
**Goal:** Show source binding and readiness before execution.
**Anchor terms:** Deployment; three local sources

Say:

> First, the agent checks which sources and operations are available.
>
> Then it builds an editable workflow draft.
>
> Validation finds that the analyze step has no route for its ok outcome.
>
> The agent adds that route, and validation passes.
>
> The valid workflow is saved as an immutable artifact.
>
> Finally, a deployment connects it to the three local sources it needs.

This later issue-review example is richer than the thesis case study; do not present its issue-board output as thesis output. Diagnostics support a repair loop but do not guarantee automatic repair.

### Scene 9: Start the prepared workflow

**Route:** `run-from-deployment/input`, `run-from-deployment/operation`, then `run-from-deployment/graph`  
**Time:** 4:17-4:52
**Evidence:** Implementation extension; live-capable

**Beat:** `run-from-deployment/input`
**Goal:** Show the concrete inputs supplied before execution.
**Anchor terms:** run input; selected documents

**Beat:** `run-from-deployment/operation`
**Goal:** Show that one public operation creates a persisted execution.
**Anchor terms:** workflow.runs.start; persisted Run

**Beat:** `run-from-deployment/graph`
**Goal:** Show the reusable workflow executing beyond the chat conversation.
**Anchor terms:** workflow graph; declared interrupt

Say:

> The deployment receives selected local documents and an issue-board path. The public workflow.runs.start operation validates the deployment and input, creates a persisted Run, and begins the reusable graph. The graph reads documents, analyzes them, builds a report, drafts proposed issues, and pauses at a declared review interrupt before issue-board changes.

If live execution has not been completed during rehearsal, say: “The operation view is replay-backed evidence of the prepared path. I am not presenting this as a newly completed live run.”

### Scene 10: Present a typed interrupt, not a production approval system

**Route:** `typed-human-boundary/interrupt` then `typed-human-boundary/approval`  
**Time:** 4:52-5:22
**Evidence:** Implementation extension; qualify

**Beat:** `typed-human-boundary/interrupt`
**Goal:** Show what the paused workflow asks from the operator.
**Anchor terms:** issue_review; interrupt payload; resume schema

**Beat:** `typed-human-boundary/approval`
**Goal:** Show that the operator chooses a declared continuation.
**Anchor terms:** submitted; revision-requested; typed resume

Say:

> Execution pauses at a typed issue_review interrupt exposing request data, allowed outcomes, request schema, and resume schema. The operator chooses submitted or revision-requested; this is a typed interrupt and resume contract, not a production approval gate, role system, or policy engine.

Do not call the negative path “deny without resuming.” Both outcomes resume execution through different workflow branches. Do not imply that the prepared revision recording preserves the submitted branch’s run identity.

### Scene 11: Show output and inspectable evidence

**Route:** `resume-output-evidence/resume`, `resume-output-evidence/output`, then `resume-output-evidence/trace`  
**Time:** 5:22-6:12
**Evidence:** Implementation extension; replay continuity differs by branch

**Beat:** `resume-output-evidence/resume`
**Goal:** Show continuation of the same recorded run.
**Anchor terms:** workflow.runs.resume; same Run

**Beat:** `resume-output-evidence/output`
**Goal:** Show the persisted terminal results of the submitted path.
**Anchor terms:** report output; issue-board changes

**Beat:** `resume-output-evidence/trace`
**Goal:** Show that execution evidence remains inspectable after completion.
**Anchor terms:** trace frames; protocol evidence

Say:

> On the submitted path, workflow.runs.resume continues the recorded interrupted Run. The workflow creates the report and issue-board changes, then records terminal output. Trace frames and protocol evidence remain inspectable; this is declared-boundary resumability, not arbitrary crash recovery or exactly-once execution. The revision replay is a separate prepared recording.

For the submitted replay, the same run ID is demonstrated. The prepared revision replay currently uses `run_recorded_lda_report_revision`; describe it as a separate prepared branch recording.

### Scene 12: Explain what the evaluation proves

**Route:** `evaluation/cohort`, `evaluation/validity`, then `evaluation/findings`  
**Time:** 6:12-8:12
**Evidence:** Supported, with strict qualification

**Beat:** `evaluation/cohort`
**Goal:** Describe the external-agent evaluation design.
**Anchor terms:** 36 trials; two challenges; three profiles

**Beat:** `evaluation/validity`
**Goal:** Separate audited valid evidence from contaminated samples.
**Anchor terms:** 27 pass; 8 invalid; 1 fail

**Beat:** `evaluation/findings`
**Goal:** State what the evaluation supports and what it cannot prove.
**Anchor terms:** longitudinal evidence; not a benchmark

Say:

> The evaluation combines conformance tests, deterministic case studies, and a manually audited external-agent campaign: 36 trials across two challenges, two hosted models, three instruction profiles, and three waves, with three attempts per cell. The author audit classified 27 trials as clean product-path passes, eight as invalid samples, and one as a failure. Invalid samples included contamination such as reading implementation files, prior artifacts, adjacent attempts, or evaluator state. Because prompts, product snapshots, and hosted conditions changed across waves, these results are longitudinal engineering evidence. They expose authoring and diagnostic gaps, not a benchmark of model success, token reduction, retry reduction, or superiority.

The product and prompts evolved across waves. Call this longitudinal engineering evidence, not a controlled benchmark ([lines 1287-1339](../thesis/system-design-implementation.md#formative-agent-trial-findings)).

### Scene 13: Close on the bounded contribution

**Route:** `conclusion/limits`, `conclusion/future`, `conclusion/conclusion`, then `conclusion/questions`  
**Time:** 8:12-9:27
**Evidence:** Supported

**Beat:** `conclusion/limits`
**Goal:** Bound the prototype claims before the final contribution statement.
**Anchor terms:** prototype; not production security

**Beat:** `conclusion/future`
**Goal:** Name the surrounding layers left as future work.
**Anchor terms:** live agent; scheduling; controlled evaluation

**Beat:** `conclusion/conclusion`
**Goal:** Restate the implemented contribution and planner-runtime boundary.
**Anchor terms:** planner proposes; platform executes

**Beat:** `conclusion/questions`
**Goal:** Open structured examiner discussion without introducing new claims.
**Anchor terms:** defense questions; evidence

Say:

> The prototype uses trusted in-process Python and file-backed stores; it does not provide production authentication, RBAC, sandboxing, scheduling, arbitrary crash recovery, or a bundled autonomous planner. A live agent interface, transactional storage, richer debugging, security hardening, scheduling, and controlled comparative evaluation remain future work. The contribution is architectural and implemented: external planners can propose workflows while a typed platform validates, binds, executes, persists, interrupts, resumes, and inspects them through public operations. That boundary is the claim I will defend: reusable agent-operated automation is inspectable because planning and execution have explicit contracts. I welcome questions.

## Live and replay fallback wording

Use one sentence and continue. Do not apologize or debug during the timed defense.

- **Replay selected:** “This is the reviewed recording of the deterministic path, not a fresh model or live-server result.”
- **Live target unavailable:** “The live target is unavailable, so I am switching to the recorded operation evidence used for rehearsal.”
- **Run state is unexpected:** “I will use the recorded branch so the lifecycle and evidence remain inspectable.”
- **Trace is unavailable:** “The live trace did not load. The prepared trace route shows the reviewed frames; automated tests separately verify trace retrieval.”
- **Revision branch shown:** “This is a separate prepared branch recording, so I am not claiming run-ID continuity with the submitted recording.”

## Prioritized 12-minute Q&A

Start with the short answer. Expand only when the examiner continues.

### 1. Where is the AI agent, and does the title overclaim?

**Short answer:** The autonomous planner is external. The submitted contribution is the typed workflow substrate that an agent operates.

**Expanded answer:** The original product ambition was an AI agent for workspace automation. The thesis narrowed the technical contribution to the infrastructure beneath that agent: schemas, lifecycle records, source bindings, validation, execution, traces, and explicit resume contracts. A chat or planner graph can use the `wf` operations as tools, but the thesis does not claim a new planning algorithm.

### 2. What is novel about the work?

**Short answer:** The contribution is the combination of an agent-operable lifecycle, provider-neutral capabilities, structured repair surfaces, and persisted execution boundaries.

**Expanded answer:** Individual concepts exist elsewhere. The thesis contribution is their integration around external agents as workflow authors and operators: Draft, Artifact, Deployment, and Run records; provider projection outside the core; diagnostics and next actions; and CLI/JSON-RPC access without runtime imports. The thesis claims architectural feasibility, not invention of workflow graphs.

### 3. Why not use scripts, LangGraph, n8n, Zapier, Temporal, or MCP?

**Short answer:** They solve adjacent problems. The thesis does not claim global superiority.

**Expanded answer:** Scripts package code but leave lifecycle and inspection to custom conventions. LangGraph focuses on agent graphs. Temporal emphasizes durable distributed execution. n8n and Zapier provide mature hosted automation. MCP exposes capabilities. `lda.chat` focuses on typed workflow lifecycle and repair surfaces designed for external-agent operation, with MCP and Python behind one provider boundary.

### 4. What do the 36 trials prove?

**Short answer:** They provide bounded engineering evidence about operability and failure modes, not a model benchmark.

**Expanded answer:** The campaign used two challenges, two hosted models, three profiles, three waves, and three attempts per cell. The author manually audited product-path validity. Because prompts, product snapshots, and hosted conditions changed, the results support feasibility and longitudinal product learning, not stable model comparison or general success rates.

### 5. Is the prepared replay honest?

**Short answer:** Yes, if it is labeled as recorded presentation evidence rather than fresh live planning.

**Expanded answer:** Replay demonstrates the same prepared operation sequence without depending on network or model latency. Automated tests and repository examples verify underlying behavior separately. It would be misleading only if presented as a new autonomous-agent result or as proof that the full live path was rehearsed.

### 6. Is the system production-ready or secure?

**Short answer:** No. It is a systems prototype with explicit non-goals.

**Expanded answer:** Python sources are trusted and unsandboxed. Stores are file-backed. Production credentials, role-based authorization, tenant isolation, secret management, policy enforcement, and operational monitoring remain future work. Provider and deployment boundaries create places for those controls, but they do not implement them.

### 7. Why separate Artifact and Deployment?

**Short answer:** An Artifact preserves what the workflow is; a Deployment records where and with which sources it can run.

**Expanded answer:** The separation keeps a workflow definition immutable while allowing environment-specific bindings and validation. Deployment validation can detect missing capabilities or source drift without rewriting the artifact.

### 8. What does resumability mean here?

**Short answer:** The runtime persists and resumes explicit stopped or interrupted boundaries.

**Expanded answer:** Resume validates a declared payload and outcome, restores persisted state, and follows the selected route. The thesis does not claim arbitrary mid-node checkpointing, exactly-once side effects, or general crash recovery.

### 9. Does the typed decision implement human approval?

**Short answer:** It implements a typed interrupt and decision contract, not a production approval system.

**Expanded answer:** The workflow declares request and resume schemas plus allowed outcomes. The demo renders an operator decision from that contract. Roles, authorization, policy, multi-user review, and approval governance are not implemented.

### 10. Why use JSON-RPC?

**Short answer:** It exposes the same workflow API to long-lived external clients without moving domain behavior into transport code.

**Expanded answer:** The CLI can target the JSON-RPC server, and the web console uses the same protocol boundary. JSON-RPC is an implementation choice, not the thesis contribution; the protocol-neutral workflow API is the architectural seam.

### 11. What is the strongest evidence in the thesis?

**Short answer:** The strongest evidence is the combination of conformance tests, deterministic case studies, and bounded audited agent trials.

**Expanded answer:** Tests verify lifecycle operations, deployment validation, source providers, interrupt/resume, and transport behavior. Case studies demonstrate controlled end-to-end paths. The agent campaign then exposes whether external clients can use the public surface without bypassing it.

### 12. What would you do next?

**Short answer:** First harden operations and evaluation, then add the surrounding live agent interface.

**Expanded answer:** Priorities are transactional storage, provider lifecycle management, production auth and secret handling, sandboxing, richer run debugging, and stable controlled evaluation. A live chat or planner loop can then call the existing operations without changing the core runtime boundary.

## Claim audit summary

| Presentation claim | Status | Safe wording |
| --- | --- | --- |
| `lda.chat` is an autonomous AI agent | Do not claim | It is the workflow substrate operated by an external planner |
| Runtime execution is deterministic | Qualify | Core routing and state transitions are deterministic for fixed handler results |
| Draft, Artifact, Deployment, and Run are distinct records | Supported | State the four responsibilities directly |
| Built-in, MCP, and Python prove provider neutrality | Qualify | Demonstrated across these three controlled source families |
| Repair hints make workflows valid | Qualify | Diagnostics and hints support repair; they do not guarantee success |
| The demo is the thesis case study | Do not claim | It is a later issue-review demonstration built on the same platform |
| Issue-board changes are thesis case-study output | Do not claim | They belong to the later prepared example implementation |
| The decision surface is a production approval gate | Do not claim | It is a typed interrupt and resume contract |
| Submitted replay resumes the same run | Supported | Valid for the submitted recording |
| Revision replay uses the same run | Do not claim | It is a separate prepared branch recording |
| Resume provides arbitrary crash recovery | Do not claim | Resume works at explicit stopped or interrupted boundaries |
| The 36 trials estimate model success | Do not claim | They are bounded longitudinal engineering evidence |
| The campaign measured token or retry reduction | Do not claim | These remain unmeasured design hypotheses |
| The system is production-secure or scheduled | Do not claim | Security hardening and scheduling remain future work |

## Evidence anchors

- Thesis framing and contributions: [Abstract](../thesis/system-design-implementation.md#abstract), [Introduction](../thesis/system-design-implementation.md#introduction), and [Contributions](../thesis/system-design-implementation.md#contributions)
- Lifecycle definitions: [Lifecycle objects](../thesis/system-design-implementation.md#lifecycle-objects)
- Architecture and NodeUse: [System architecture](../thesis/system-design-implementation.md#system-architecture) and [Workflow core model](../thesis/system-design-implementation.md#workflow-core-model)
- Validation and repair: [Validation and diagnostics](../thesis/system-design-implementation.md#validation-and-diagnostics)
- Evaluation scope: [Evaluation](../thesis/system-design-implementation.md#evaluation) and [Agent challenge harness](../thesis/system-design-implementation.md#agent-challenge-harness)
- Limitations and future work: [Limitations](../thesis/system-design-implementation.md#limitations) and [Future work](../thesis/system-design-implementation.md#future-work)
- Prepared example implementation: `examples/lda_report_workflow/`
- Presentation replay evidence: `web/apps/console/src/demo/recordings/lda-report-success.v1.json`
- Revision replay identity: `web/apps/console/src/demo/timeline/replay.ts`

## Presentation defects to resolve or avoid

- The thesis’s deterministic report case study has three workflow nodes. The later presentation example has eleven plan nodes, while its simplified graph intentionally omits the terminal `end_cancelled` marker. Avoid quoting a graph-node count unless the distinction is relevant.
- The live health probe does not establish a completed live Scene 9-11 rehearsal. Label replay-backed output and trace evidence as recorded.
- The revision replay has a separate run ID. Never use the submitted branch’s “same persisted run” wording for that branch.
