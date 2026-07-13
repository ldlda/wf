# Defense speech and claim audit

This runbook gives you the must-say 11:00 defense speech, a 1:15 navigation buffer, and a prioritized 12-minute question period. It also marks claims that require qualification so the presentation stays aligned with the thesis and current implementation. The typed catalog at `web/apps/console/src/presentation/presenter/presenter-notes.ts` is the source for the must-say text.

## Timing and evidence rules

Use these evidence labels while rehearsing. Do not read the labels aloud.

- **Supported**: stated in the thesis and backed by repository evidence
- **Implementation extension**: implemented after or beyond the thesis case study; identify it as a separate demonstration
- **Qualify**: accurate only within an explicit boundary
- **Do not claim**: unsupported, untested, or excluded from scope

Target 11:00 for the must-say speech. Keep 1:15 for navigation or demo delay; the complete deck target is 12:15. The question period then has 12 minutes.

| Segment | Target |
| --- | ---: |
| Scenes 1-2: goal and problem | 1:30 |
| Scenes 3-6: positioning, model, and architecture | 3:06 |
| Scenes 7-11: prepared demonstration | 3:09 |
| Scene 12: evaluation | 2:00 |
| Scene 13: limits and conclusion | 1:15 |
| Must-say speech | 11:00 |
| Navigation buffer | 1:15 |
| Complete deck target | 12:15 |

## Main speech

### Scene 1: State the ambition and the submitted contribution

**Route:** `thesis/title` then `thesis/substrate`  
**Time:** 0:00-0:45  
**Evidence:** Supported

Say:

> This project began with the goal in the title: an AI agent for creating and automating workspace workflows. The difficult engineering problem became the system underneath the chat.
>
> The submitted contribution is a typed workflow substrate: an external planner can propose work while the platform owns definitions, validation, bindings, execution records, traces, and explicit resume boundaries.

Keep the boundary explicit. The thesis states this distinction in the Abstract and Introduction ([thesis lines 109-121](../thesis/system-design-implementation.md#abstract) and [lines 145-181](../thesis/system-design-implementation.md#introduction)).

### Scene 2: Explain why direct tool use is insufficient

**Route:** `problem/direct-actions` then `problem/missing-contracts`  
**Time:** 0:45-1:30  
**Evidence:** Supported

Say:

> A model can call tools and complete one task, but a tool transcript is not reusable automation.
>
> Reuse needs schemas, source bindings, persistence, traces, and declared recovery boundaries, with planning kept separate from execution.

Do not claim that direct tool use or generated scripts are inherently bad. The thesis argues that reusable operation needs additional lifecycle contracts ([lines 214-277](../thesis/system-design-implementation.md#problem-statement-and-requirements)).

### Scene 3: Position the work without claiming superiority

**Route:** `positioning/landscape` then `positioning/lda-position`  
**Time:** 1:30-2:15
**Evidence:** Supported, with qualification

Say:

> Related systems have different centers of gravity: tool loops act now, scripts package code, hosted platforms operate workflows, agent graphs organize planners, and MCP exposes capabilities. lda.chat takes a narrower position: a typed, provider-neutral lifecycle for workflows authored or operated by external agents, not a replacement or superiority claim.

Qualify provider neutrality as demonstrated for the three implemented source families. Do not present compatibility with arbitrary future providers as measured evidence ([lines 460-521](../thesis/system-design-implementation.md#source-model)).

### Scene 4: Draw the planner and runtime boundary

**Route:** `planner-runtime/planner`, `planner-runtime/runtime`, then `planner-runtime/boundary`  
**Time:** 2:15-3:10
**Evidence:** Supported, with qualification

Say:

> An external model or human proposes and revises workflow structure; this keeps planning outside the runtime. For fixed definitions and handler results, the runtime validates the graph, resolves sources, executes steps, records state and traces, and resumes only at declared boundaries. Typed CLI and JSON-RPC operations reach the same Workflow API, making schemas, diagnostics, and lifecycle state machine-readable without importing runtime internals.

Say “deterministic core semantics for fixed definitions and handler results,” not “all execution is deterministic.” Remote calls, provider code, resource reads, and external side effects may be nondeterministic ([lines 808-821](../thesis/system-design-implementation.md#workflow-core)).

### Scene 5: Define the lifecycle vocabulary

**Route:** `lifecycle/draft`, `lifecycle/artifact`, `lifecycle/deployment`, then `lifecycle/run`  
**Time:** 3:10-3:55
**Evidence:** Supported

Say:

> Draft is mutable authoring state. Artifact is an immutable workflow definition. Deployment binds an artifact version to concrete sources and runtime context. Run records one execution, including status, diagnostics, output, trace, and an explicit stopped or interrupted state.

Keep Scene 5 conceptual. Scene 9 applies this vocabulary to the prepared example. Also note that raw plans can create artifacts without passing through Draft ([lines 629-660](../thesis/system-design-implementation.md#workflow-lifecycle)).

### Scene 6: Zoom through the implemented architecture

**Route:** `architecture/overview`, `architecture/client`, `architecture/api`, then `architecture/runtime`<br>
**Time:** 3:55-4:36
**Evidence:** Supported

Say:

> First, the implemented architecture spine and its ownership boundaries. Humans and agents share one public lifecycle surface. WorkflowApi owns lifecycle operations; JSON-RPC only adapts transport. WorkflowServer composes records, capabilities, API, and kernel; providers remain outside the core.

The optional NodeUse deep dive remains available through the architecture focus route and Q&A; it is not part of the timed forward sequence.

### Scene 7: Introduce the prepared demonstration honestly

**Route:** `agent-handoff/request`  
**Time:** 4:36-4:56
**Evidence:** Implementation extension

Say:

> I will now show a prepared demonstration built on this platform. The chat is a presentation interface, not the autonomous planner evaluated by the thesis. The chat translates a report request into the same public lifecycle operations an external agent could call. This prepared path demonstrates product behavior and recorded evidence, not a fresh model-performance result.

If replay is active, say: “This is the reviewed recording, not a live model planning this workflow.”

### Scene 8: Show the prepared lifecycle

**Route:** all six `prepared-lifecycle/*` beats
**Time:** 4:56-5:50
**Evidence:** Implementation extension; supported with qualification

Say:

> It inspects sources, capabilities, and schemas rather than guessing at hidden interfaces. Focused operations modify mutable authoring state before execution. Structured diagnostics identify the missing output projection. One focused output-map edit resolves it; hints do not guarantee automatic repair. It saves the validated plan as immutable artifact lda_report_case_study version 1. Deployment binds and validates three local sources; execution starts in the next scene.

This later issue-review example is richer than the thesis case study; do not present its issue-board output as thesis output. Diagnostics support a repair loop but do not guarantee automatic repair.

### Scene 9: Start the prepared workflow

**Route:** `run-from-deployment/input`, `run-from-deployment/operation`, then `run-from-deployment/graph`  
**Time:** 5:50-6:25
**Evidence:** Implementation extension; live-capable

Say:

> The deployment receives selected local documents and an issue-board path. The public workflow.runs.start operation validates the deployment and input, creates a persisted Run, and begins the reusable graph. The graph reads documents, analyzes them, builds a report, drafts proposed issues, and pauses at a declared review interrupt before issue-board changes.

If live execution has not been completed during rehearsal, say: “The operation view is replay-backed evidence of the prepared path. I am not presenting this as a newly completed live run.”

### Scene 10: Present a typed interrupt, not a production approval system

**Route:** `typed-human-boundary/interrupt` then `typed-human-boundary/approval`  
**Time:** 6:25-6:55
**Evidence:** Implementation extension; qualify

Say:

> Execution pauses at a typed issue_review interrupt exposing request data, allowed outcomes, request schema, and resume schema. The operator chooses submitted or revision-requested; this is a typed interrupt and resume contract, not a production approval gate, role system, or policy engine.

Do not call the negative path “deny without resuming.” Both outcomes resume execution through different workflow branches. Do not imply that the prepared revision recording preserves the submitted branch’s run identity.

### Scene 11: Show output and inspectable evidence

**Route:** `resume-output-evidence/resume`, `resume-output-evidence/output`, then `resume-output-evidence/trace`  
**Time:** 6:55-7:45
**Evidence:** Implementation extension; replay continuity differs by branch

Say:

> On the submitted path, workflow.runs.resume continues the recorded interrupted Run. The workflow creates the report and issue-board changes, then records terminal output. Trace frames and protocol evidence remain inspectable; this is declared-boundary resumability, not arbitrary crash recovery or exactly-once execution. The revision replay is a separate prepared recording.

For the submitted replay, the same run ID is demonstrated. The prepared revision replay currently uses `run_recorded_lda_report_revision`; describe it as a separate prepared branch recording.

### Scene 12: Explain what the evaluation proves

**Route:** `evaluation/cohort`, `evaluation/validity`, then `evaluation/findings`  
**Time:** 7:45-9:45
**Evidence:** Supported, with strict qualification

Say:

> The evaluation combines conformance tests, deterministic case studies, and a manually audited external-agent campaign: 36 trials across two challenges, two hosted models, three instruction profiles, and three waves, with three attempts per cell. The author audit classified 27 trials as clean product-path passes, eight as invalid samples, and one as a failure. Invalid samples included contamination such as reading implementation files, prior artifacts, adjacent attempts, or evaluator state. Because prompts, product snapshots, and hosted conditions changed across waves, these results are longitudinal engineering evidence. They expose authoring and diagnostic gaps, not a benchmark of model success, token reduction, retry reduction, or superiority.

The product and prompts evolved across waves. Call this longitudinal engineering evidence, not a controlled benchmark ([lines 1287-1339](../thesis/system-design-implementation.md#formative-agent-trial-findings)).

### Scene 13: Close on the bounded contribution

**Route:** `conclusion/limits`, `conclusion/future`, `conclusion/conclusion`, then `conclusion/questions`  
**Time:** 9:45-11:00
**Evidence:** Supported

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
