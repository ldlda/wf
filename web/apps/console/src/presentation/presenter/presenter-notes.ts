import {
  findDiscussionBranch,
  mainScenes,
  type DiscussionBranchDefinition,
  type DiscussionBranchId,
  type MainSceneId,
} from "../storyboard.js";

export type PresenterBeatNote = {
  readonly sceneId: MainSceneId;
  readonly beatId: string;
  readonly targetSeconds: number;
  readonly mustSay: string;
  readonly optionalDetail: string | null;
  readonly warning: string | null;
  readonly fallback: string | null;
  readonly evidencePointers: readonly [string, ...string[]];
  readonly qnaBranchIds: readonly DiscussionBranchId[];
};

type PresenterBeatNoteOptions = {
  readonly optionalDetail?: string | null;
  readonly warning?: string | null;
  readonly fallback?: string | null;
  readonly qnaBranchIds?: readonly DiscussionBranchId[];
};

const beatNote = <const EvidencePointers extends readonly [string, ...string[]]>(
  sceneId: MainSceneId,
  beatId: string,
  targetSeconds: number,
  mustSay: string,
  evidencePointers: EvidencePointers,
  options: PresenterBeatNoteOptions = {},
): PresenterBeatNote => ({
  sceneId,
  beatId,
  targetSeconds,
  mustSay,
  optionalDetail: options.optionalDetail ?? null,
  warning: options.warning ?? null,
  fallback: options.fallback ?? null,
  evidencePointers,
  qnaBranchIds: options.qnaBranchIds ?? [],
});

/**
 * Presenter-only speech and evidence source. The audience route remains in
 * storyboard.ts; this catalog is deliberately not rendered by scene content.
 */
export const presenterNotes = [
  beatNote(
    "thesis",
    "title",
    22,
    "This project began with the goal in the title: **an AI agent for creating and automating workspace workflows**. The difficult engineering problem became **the system underneath the chat**.",
    ["Thesis Abstract and Introduction"],
    {
      warning: "Do not present the submitted system as a bundled autonomous planner.",
      qnaBranchIds: ["where-is-ai-agent", "title-ai-agent-wording"],
    },
  ),
  beatNote(
    "thesis",
    "substrate",
    23,
    "The submitted contribution is a **typed workflow substrate**: an external planner can propose work while **the platform owns definitions, validation, bindings, execution records, traces, and explicit resume boundaries**.",
    ["Thesis Abstract and Introduction", "Thesis Contributions"],
    { qnaBranchIds: ["where-is-ai-agent", "not-just-cli"] },
  ),
  beatNote(
    "problem",
    "direct-actions",
    22,
    "A model can call tools and complete one task, but **a tool transcript is not reusable automation**.",
    ["Thesis Problem Statement and Requirements"],
    { qnaBranchIds: ["direct-orchestration", "not-just-scripts"] },
  ),
  beatNote(
    "problem",
    "missing-contracts",
    23,
    "Reuse needs **schemas, source bindings, persistence, traces, and declared recovery boundaries**, with **planning kept separate from execution**.",
    ["Thesis Problem Statement and Requirements"],
    { qnaBranchIds: ["why-schemas", "run-persistence"] },
  ),
  beatNote(
    "positioning",
    "landscape",
    22,
    "Related systems have different centers of gravity: tool loops act now, scripts package code, hosted platforms operate workflows, agent graphs organize planners, and MCP exposes capabilities.",
    ["Thesis Positioning and Related Systems"],
    { qnaBranchIds: ["direct-orchestration", "generated-scripts", "hosted-automation", "durable-agent-graphs", "mcp-agent-scale"] },
  ),
  beatNote(
    "positioning",
    "lda-position",
    23,
    "lda.chat takes a narrower position: a typed, provider-neutral lifecycle for workflows authored or operated by external agents, not a replacement or superiority claim.",
    ["Thesis Positioning and Related Systems", "Thesis Source Model"],
    { warning: "Provider neutrality is demonstrated for the implemented source families, not arbitrary future providers.", qnaBranchIds: ["not-just-scripts"] },
  ),
  beatNote(
    "planner-runtime",
    "planner",
    18,
    "An **external model or human proposes and revises workflow structure**; this keeps planning outside the runtime.",
    ["Thesis Architecture Overview"],
    { qnaBranchIds: ["where-is-ai-agent", "not-just-cli"] },
  ),
  beatNote(
    "planner-runtime",
    "runtime",
    18,
    "For **fixed definitions and handler results**, the runtime validates the graph, resolves sources, executes steps, records state and traces, and **resumes only at declared boundaries**.",
    ["Thesis Workflow Core", "Thesis Architecture Overview"],
    { warning: "Qualify determinism; provider code, resource reads, and external side effects can vary.", qnaBranchIds: ["run-persistence", "typed-interrupts"] },
  ),
  beatNote(
    "planner-runtime",
    "boundary",
    19,
    "**Typed CLI and JSON-RPC operations reach the same Workflow API**, making schemas, diagnostics, and lifecycle state machine-readable without importing runtime internals.",
    ["Thesis Architecture Overview", "docs/source_architecture.md"],
    { qnaBranchIds: ["not-just-cli"] },
  ),
  beatNote(
    "lifecycle",
    "draft",
    11,
    "**Draft** is mutable authoring state.",
    ["Thesis Workflow Lifecycle"],
    { optionalDetail: "Raw plans can also create artifacts without passing through a Draft." },
  ),
  beatNote(
    "lifecycle",
    "artifact",
    11,
    "**Artifact** is an immutable workflow definition.",
    ["Thesis Workflow Lifecycle"],
  ),
  beatNote(
    "lifecycle",
    "deployment",
    11,
    "**Deployment** binds an artifact version to concrete sources and runtime context.",
    ["Thesis Workflow Lifecycle"],
  ),
  beatNote(
    "lifecycle",
    "run",
    12,
    "**Run** records one execution, including status, diagnostics, output, trace, and an explicit stopped or interrupted state.",
    ["Thesis Workflow Lifecycle"],
    { qnaBranchIds: ["lifecycle-states", "run-persistence"] },
  ),
  beatNote(
    "architecture",
    "client",
    13,
    "Human operators and external agents enter through **the same public lifecycle surface**.",
    ["Thesis System Architecture", "docs/project_map.md"],
  ),
  beatNote(
    "architecture",
    "api",
    13,
    "**WorkflowApi owns lifecycle operations**; JSON-RPC adapts requests without owning domain behavior.",
    ["Thesis System Architecture", "docs/source_architecture.md"],
    { qnaBranchIds: ["not-just-cli"] },
  ),
  beatNote(
    "architecture",
    "runtime",
    14,
    "**WorkflowServer composes records, provider-neutral capabilities, WorkflowApi, and the execution kernel**; provider behavior remains outside the core.",
    ["Thesis System Architecture", "docs/source_architecture.md"],
    { qnaBranchIds: ["provider-security"] },
  ),
  beatNote(
    "architecture",
    "node-use",
    15,
    "A NodeUse resolves bindings, **invokes its NodeDef handler**, reduces output into state, appends a trace frame, and routes the outcome.",
    ["Thesis Workflow Core Model"],
  ),
  beatNote(
    "authoring",
    "discover",
    10,
    "Before authoring, a client can discover sources, capabilities, and schemas instead of guessing at hidden interfaces.",
    ["CLI documentation", "Draft authoring API", "Challenge UX findings"],
    { qnaBranchIds: ["why-schemas", "validation-diagnostics"] },
  ),
  beatNote(
    "authoring",
    "author",
    10,
    "Focused operations let an external agent change a mutable Draft while preserving a clear lifecycle boundary.",
    ["CLI documentation", "Draft authoring API"],
    { qnaBranchIds: ["raw-plan-import"] },
  ),
  beatNote(
    "authoring",
    "diagnose",
    10,
    "Validation returns structured diagnostics, affected paths, repair hints, and suggested next actions.",
    ["Validation and diagnostics", "Challenge UX findings"],
    { qnaBranchIds: ["validation-diagnostics"] },
  ),
  beatNote(
    "authoring",
    "repair",
    10,
    "These surfaces make invalid intermediate drafts repairable; they support a loop, but no hint guarantees success.",
    ["Validation and diagnostics", "Challenge UX findings"],
    { warning: "Do not promise that diagnostics automatically repair every workflow.", qnaBranchIds: ["validation-diagnostics"] },
  ),
  beatNote(
    "agent-handoff",
    "request",
    20,
    "I will now show a **prepared demonstration built on this platform**. The chat is a presentation interface, **not the autonomous planner evaluated by the thesis**. The chat translates a report request into the same public lifecycle operations an external agent could call. This prepared path demonstrates product behavior and recorded evidence, not a fresh model-performance result.",
    ["Constrained demo agent and prepared replay recipe"],
    {
      fallback: "This is the reviewed recording, not a live model planning this workflow.",
      qnaBranchIds: ["prepared-replay-boundary", "demo-reliability"],
    },
  ),
  beatNote(
    "prepared-lifecycle",
    "discover",
    9,
    "The later issue-review example first inspects configured local.lda_docs, report, and issue-board capabilities.",
    ["examples/lda_report_workflow", "deployment inspect replay evidence"],
    { qnaBranchIds: ["prepared-replay-boundary"] },
  ),
  beatNote(
    "prepared-lifecycle",
    "draft",
    9,
    "It creates and edits a Draft for report generation, making the proposal visible before execution.",
    ["examples/lda_report_workflow", "deployment inspect replay evidence"],
  ),
  beatNote(
    "prepared-lifecycle",
    "validate",
    9,
    "It validates incomplete state, exposes a missing output binding, and applies a targeted repair.",
    ["examples/lda_report_workflow", "deployment inspect replay evidence"],
    { qnaBranchIds: ["validation-diagnostics"] },
  ),
  beatNote(
    "prepared-lifecycle",
    "artifact",
    9,
    "It saves the validated plan as immutable artifact lda_report_case_study version 1.",
    ["examples/lda_report_workflow", "deployment inspect replay evidence"],
  ),
  beatNote(
    "prepared-lifecycle",
    "deployment",
    9,
    "This later issue-review example is richer than the thesis three-node deterministic report case study: it is an implementation extension built on the same platform. Deployment binds and validates a ready configuration but does not run the workflow.",
    ["examples/lda_report_workflow", "deployment inspect replay evidence", "Thesis deterministic report case study"],
    { warning: "Do not present issue-board output from this later example as the thesis case study.", qnaBranchIds: ["prepared-replay-boundary"] },
  ),
  beatNote(
    "run-from-deployment",
    "input",
    11,
    "The deployment receives selected local documents and an issue-board path.",
    ["workflow.runs.start replay evidence"],
  ),
  beatNote(
    "run-from-deployment",
    "operation",
    12,
    "The public **workflow.runs.start** operation validates the deployment and input, creates a **persisted Run**, and begins the reusable graph.",
    ["workflow.runs.start replay evidence"],
    { qnaBranchIds: ["run-persistence"] },
  ),
  beatNote(
    "run-from-deployment",
    "graph",
    12,
    "The graph reads documents, analyzes them, builds a report, drafts proposed issues, and pauses at a declared review interrupt before issue-board changes.",
    ["workflow.runs.start replay evidence", "examples/lda_report_workflow"],
    { fallback: "The operation view is replay-backed evidence of the prepared path, not a newly completed live run." },
  ),
  beatNote(
    "typed-human-boundary",
    "interrupt",
    15,
    "Execution pauses at a **typed issue_review interrupt** exposing request data, allowed outcomes, request schema, and resume schema.",
    ["Typed interrupt payload and resume contract"],
    { qnaBranchIds: ["typed-interrupts", "why-schemas"] },
  ),
  beatNote(
    "typed-human-boundary",
    "approval",
    15,
    "The operator chooses submitted or revision-requested; this is a typed interrupt and resume contract, not a production approval gate, role system, or policy engine.",
    ["Typed interrupt payload and resume contract"],
    { warning: "Both outcomes resume through declared workflow branches; this is not production approval governance.", qnaBranchIds: ["typed-interrupts", "security-production-boundary"] },
  ),
  beatNote(
    "resume-output-evidence",
    "resume",
    16,
    "On the submitted path, **workflow.runs.resume continues the recorded interrupted Run**.",
    ["workflow.runs.resume replay evidence", "Revision replay identity"],
    { fallback: "The submitted replay demonstrates same-run continuation; the revision branch is recorded separately.", qnaBranchIds: ["replay-provenance", "prepared-replay-boundary"] },
  ),
  beatNote(
    "resume-output-evidence",
    "output",
    16,
    "The workflow creates the report and issue-board changes, then records terminal output.",
    ["workflow.runs.resume replay evidence", "examples/lda_report_workflow"],
    { warning: "Identify these issue-board changes as later example evidence, not output from the thesis three-node case study." },
  ),
  beatNote(
    "resume-output-evidence",
    "trace",
    18,
    "Trace frames and protocol evidence remain inspectable; this is declared-boundary resumability, not arbitrary crash recovery or exactly-once execution. The revision replay is a separate prepared recording.",
    ["workflow.runs.resume replay evidence", "Revision replay identity"],
    { warning: "Never claim run-ID continuity for the prepared revision recording.", qnaBranchIds: ["replay-provenance", "demo-reliability"] },
  ),
  beatNote(
    "evaluation",
    "cohort",
    40,
    "The evaluation combines conformance tests, deterministic case studies, and a **manually audited external-agent campaign**: 36 trials across two challenges, two hosted models, three instruction profiles, and three waves, with three attempts per cell.",
    ["Thesis Evaluation and Appendix C"],
    { qnaBranchIds: ["evaluation-validity"] },
  ),
  beatNote(
    "evaluation",
    "validity",
    40,
    "The author audit classified 27 trials as clean product-path passes, eight as invalid samples, and one as a failure. Invalid samples included contamination such as reading implementation files, prior artifacts, adjacent attempts, or evaluator state.",
    ["Thesis Evaluation and Appendix C", "Author audit"],
    { qnaBranchIds: ["evaluation-validity"] },
  ),
  beatNote(
    "evaluation",
    "findings",
    40,
    "Because prompts, product snapshots, and hosted conditions changed across waves, these results are **longitudinal engineering evidence**. They expose authoring and diagnostic gaps, **not a benchmark** of model success, token reduction, retry reduction, or superiority.",
    ["Thesis Evaluation and Appendix C", "Thesis Threats to Validity"],
    { warning: "Use non-benchmark wording; do not report the counts as general model performance.", qnaBranchIds: ["evaluation-validity"] },
  ),
  beatNote(
    "conclusion",
    "limits",
    18,
    "The prototype uses trusted in-process Python and file-backed stores; it does not provide production authentication, RBAC, sandboxing, scheduling, arbitrary crash recovery, or a bundled autonomous planner.",
    ["Thesis Limitations"],
    { qnaBranchIds: ["security-production-boundary", "production-readiness"] },
  ),
  beatNote(
    "conclusion",
    "future",
    18,
    "A live agent interface, transactional storage, richer debugging, security hardening, scheduling, and controlled comparative evaluation remain future work.",
    ["Thesis Future Work"],
    { qnaBranchIds: ["production-readiness"] },
  ),
  beatNote(
    "conclusion",
    "conclusion",
    20,
    "The contribution is **architectural and implemented**: external planners can propose workflows while a typed platform **validates, binds, executes, persists, interrupts, resumes, and inspects** them through public operations.",
    ["Thesis Contributions", "Thesis Conclusion"],
    { qnaBranchIds: ["where-is-ai-agent", "not-just-cli"] },
  ),
  beatNote(
    "conclusion",
    "questions",
    19,
    "That boundary is the claim I will defend: reusable agent-operated automation is inspectable because planning and execution have explicit contracts. I welcome questions.",
    ["Thesis Conclusion", "Defense Q&A index"],
    { qnaBranchIds: ["where-is-ai-agent", "evaluation-validity", "production-readiness"] },
  ),
] satisfies readonly PresenterBeatNote[];

type PresenterRouteKey = `${MainSceneId}/${string}`;

const presenterNotesByRoute = new Map<PresenterRouteKey, PresenterBeatNote>(
  presenterNotes.map((note) => [`${note.sceneId}/${note.beatId}` as PresenterRouteKey, note]),
);

/** Resolve a presenter note without giving audience components access to the catalog internals. */
export const presenterBeatNoteFor = (sceneId: MainSceneId, beatId: string): PresenterBeatNote | undefined =>
  presenterNotesByRoute.get(`${sceneId}/${beatId}`);

export const presenterSceneNotes = (sceneId: MainSceneId): readonly PresenterBeatNote[] =>
  presenterNotes.filter((note) => note.sceneId === sceneId);

/** Keep the Q&A lookup in one place so note links cannot silently drift from storyboard branches. */
export const discussionBranchForId = (branchId: DiscussionBranchId): DiscussionBranchDefinition | undefined =>
  findDiscussionBranch(branchId);

const NAVIGATION_BUFFER_SECONDS = 75;

export const completeDeckTargetSeconds = (): number =>
  presenterNotes.reduce((total, note) => total + note.targetSeconds, 0) + NAVIGATION_BUFFER_SECONDS;

/**
 * Counts only must-say text. Inline punctuation and identifiers are split into
 * readable word units, while hyphenated terms and contractions stay together.
 */
export const mainSpeechWordCount = (): number => {
  const wordPattern = /\b[\p{L}\p{N}]+(?:['-][\p{L}\p{N}]+)*\b/gu;
  return presenterNotes.reduce((total, note) => total + (note.mustSay.match(wordPattern)?.length ?? 0), 0);
};
