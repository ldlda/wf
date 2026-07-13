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
  readonly goal: string;
  readonly keywords: readonly [string, ...string[]];
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
  goal: string,
  keywords: readonly [string, ...string[]],
  mustSay: string,
  evidencePointers: EvidencePointers,
  options: PresenterBeatNoteOptions = {},
): PresenterBeatNote => ({
  sceneId,
  beatId,
  targetSeconds,
  goal,
  keywords,
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
    15,
    "Separate the AI-agent ambition from the implemented contribution.",
    ["AI-agent goal", "platform underneath"],
    "The title describes the original goal: an AI agent for workspace automation. My contribution is the platform underneath that agent.",
    ["Thesis Abstract and Introduction"],
    {
      warning: "Do not present the submitted system as a bundled autonomous planner.",
      qnaBranchIds: ["where-is-ai-agent", "title-ai-agent-wording"],
    },
  ),
  beatNote(
    "thesis",
    "substrate",
    15,
    "State what the platform lets its users do.",
    ["agents and humans", "build, run, inspect"],
    "It lets agents and humans build workflows, run them, and inspect what happened.",
    ["Thesis Abstract and Introduction", "Thesis Contributions"],
    { qnaBranchIds: ["where-is-ai-agent", "not-just-cli"] },
  ),
  beatNote(
    "problem",
    "direct-actions",
    15,
    "Show why one successful chat is not yet automation.",
    ["tool calls", "not reusable"],
    "Like the chat example, an agent can call tools and finish one task. But that conversation is not yet a reusable workflow.",
    ["Thesis Problem Statement and Requirements"],
    { qnaBranchIds: ["direct-orchestration", "not-just-scripts"] },
  ),
  beatNote(
    "problem",
    "missing-contracts",
    15,
    "Name the minimum durable properties reusable automation needs.",
    ["saved definition", "validation", "execution records"],
    "Reusable automation needs a saved definition, validation, execution records, and a clear way to pause and continue.",
    ["Thesis Problem Statement and Requirements"],
    { qnaBranchIds: ["why-schemas", "run-persistence"] },
  ),
  beatNote(
    "positioning",
    "landscape",
    18,
    "Place the work beside familiar adjacent systems.",
    ["Python / n8n / Zapier", "LangGraph", "MCP"],
    "Existing systems solve different parts of this problem: Python scripts, n8n, Zapier, LangGraph, and MCP.",
    ["Thesis Positioning and Related Systems"],
    { qnaBranchIds: ["direct-orchestration", "generated-scripts", "hosted-automation", "durable-agent-graphs", "mcp-agent-scale"] },
  ),
  beatNote(
    "positioning",
    "lda-position",
    17,
    "State the platform's narrow position without a superiority claim.",
    ["provider-neutral", "workflow layer", "not a replacement"],
    "My platform does not replace them. It provides a provider-neutral workflow layer that agents and humans can operate.",
    ["Thesis Positioning and Related Systems", "Thesis Source Model"],
    { warning: "Provider neutrality is demonstrated for the implemented source families, not arbitrary future providers.", qnaBranchIds: ["not-just-scripts"] },
  ),
  beatNote(
    "planner-runtime",
    "planner",
    12,
    "Assign workflow decisions to an external planner.",
    ["human or AI planner"],
    "A human or AI planner decides what workflow to build.",
    ["Thesis Architecture Overview"],
    { qnaBranchIds: ["where-is-ai-agent", "not-just-cli"] },
  ),
  beatNote(
    "planner-runtime",
    "runtime",
    16,
    "Assign execution and recording to the runtime.",
    ["validation", "step-by-step execution", "state and traces"],
    "The runtime validates the graph, executes it step by step, records state and traces, and pauses at declared boundaries.",
    ["Thesis Workflow Core", "Thesis Architecture Overview"],
    {
      optionalDetail: "This explanation assumes fixed workflow definitions and handler results.",
      warning: "Qualify determinism; provider code, resource reads, and external side effects can vary.",
      qnaBranchIds: ["run-persistence", "typed-interrupts"],
    },
  ),
  beatNote(
    "planner-runtime",
    "boundary",
    12,
    "Introduce the public seam between clients and runtime.",
    ["Workflow API", "CLI", "JSON-RPC"],
    "Both sides communicate through the Workflow API. Today, clients reach it through the CLI or JSON-RPC without accessing runtime internals directly.",
    ["Thesis Architecture Overview", "docs/source_architecture.md"],
    { qnaBranchIds: ["not-just-cli"] },
  ),
  beatNote(
    "lifecycle",
    "draft",
    9,
    "Introduce the editable lifecycle state.",
    ["Draft", "being built"],
    "A workflow moves through four lifecycle stages. Draft means the workflow is still being built.",
    ["Thesis Workflow Lifecycle"],
    { optionalDetail: "Raw plans can also create artifacts without passing through a Draft." },
  ),
  beatNote(
    "lifecycle",
    "artifact",
    9,
    "Introduce the immutable saved definition.",
    ["Artifact", "immutable version"],
    "Artifact is a saved, immutable version.",
    ["Thesis Workflow Lifecycle"],
  ),
  beatNote(
    "lifecycle",
    "deployment",
    9,
    "Connect a saved definition to a runnable environment.",
    ["Deployment", "sources", "ready"],
    "Deployment connects that version to the sources it needs and checks whether it is ready.",
    ["Thesis Workflow Lifecycle"],
  ),
  beatNote(
    "lifecycle",
    "run",
    9,
    "Introduce one persisted execution record.",
    ["Run", "status", "output and trace"],
    "Run is one recorded execution, including its status, output, and trace.",
    ["Thesis Workflow Lifecycle"],
    { qnaBranchIds: ["lifecycle-states", "run-persistence"] },
  ),
  beatNote(
    "architecture",
    "overview",
    6,
    "Show how the implementation realizes the earlier concepts.",
    ["architecture spine"],
    "This is how those concepts are organized in the implementation.",
    ["Thesis System Architecture", "docs/project_map.md"],
  ),
  beatNote(
    "architecture",
    "client",
    8,
    "Show that humans and agents share one public surface.",
    ["shared operations"],
    "Humans and agents use the same public workflow operations.",
    ["Thesis System Architecture", "docs/project_map.md"],
  ),
  beatNote(
    "architecture",
    "api",
    9,
    "Identify the system's public front door.",
    ["Workflow API", "public boundary"],
    "The Workflow API is the front door. It exposes lifecycle operations without exposing runtime internals.",
    ["Thesis System Architecture", "docs/source_architecture.md"],
    { qnaBranchIds: ["not-just-cli"] },
  ),
  beatNote(
    "architecture",
    "runtime",
    9,
    "Explain what the server composes behind the API.",
    ["WorkflowServer", "records and capabilities", "execution core"],
    "Behind it, the workflow server brings together stored records, available capabilities, and the execution core.",
    ["Thesis System Architecture", "docs/source_architecture.md"],
    { qnaBranchIds: ["provider-security"] },
  ),
  beatNote(
    "agent-handoff",
    "request",
    12,
    "Disclose the prepared demonstration before it begins.",
    ["prepared example", "not an autonomous planner"],
    "This is a prepared example, not a live autonomous AI agent. It shows how an agent could use the platform to build and run a workflow.",
    ["Constrained demo agent and prepared replay recipe"],
    {
      fallback: "This is the reviewed recording, not a live model planning this workflow.",
      qnaBranchIds: ["prepared-replay-boundary", "demo-reliability"],
    },
  ),
  beatNote(
    "prepared-lifecycle",
    "discover",
    7,
    "Show that authoring starts with interface discovery.",
    ["sources", "capabilities"],
    "First, the agent checks which sources and operations are available.",
    ["examples/lda_report_workflow", "deployment inspect replay evidence"],
    { qnaBranchIds: ["prepared-replay-boundary", "why-schemas", "validation-diagnostics"] },
  ),
  beatNote(
    "prepared-lifecycle",
    "draft",
    7,
    "Show mutable workflow authoring.",
    ["Draft", "editable workflow"],
    "Then it builds an editable workflow draft.",
    ["examples/lda_report_workflow", "deployment inspect replay evidence", "CLI documentation", "Draft authoring API"],
    { qnaBranchIds: ["raw-plan-import"] },
  ),
  beatNote(
    "prepared-lifecycle",
    "diagnose",
    7,
    "Show a concrete structured validation failure.",
    ["validation", "missing_outcome_edge"],
    "Validation finds that the analyze step has no route for its ok outcome.",
    ["examples/lda_report_workflow", "deployment inspect replay evidence"],
    { qnaBranchIds: ["validation-diagnostics"] },
  ),
  beatNote(
    "prepared-lifecycle",
    "repair",
    7,
    "Show the exact focused correction and revalidation.",
    ["set-route", "validation passes"],
    "The agent adds that route, and validation passes.",
    ["Validation and diagnostics", "Challenge UX findings"],
    { warning: "Do not promise that diagnostics automatically repair every workflow.", qnaBranchIds: ["validation-diagnostics"] },
  ),
  beatNote(
    "prepared-lifecycle",
    "artifact",
    7,
    "Show the transition to an immutable saved version.",
    ["Artifact", "immutable"],
    "The valid workflow is saved as an immutable artifact.",
    ["examples/lda_report_workflow", "deployment inspect replay evidence"],
  ),
  beatNote(
    "prepared-lifecycle",
    "deployment",
    7,
    "Show source binding and readiness before execution.",
    ["Deployment", "three local sources"],
    "Finally, a deployment connects it to the three local sources it needs.",
    ["examples/lda_report_workflow", "deployment inspect replay evidence", "Thesis deterministic report case study"],
    { warning: "This later issue-review example is richer than the thesis case study; do not present its issue-board output as thesis output.", qnaBranchIds: ["prepared-replay-boundary"] },
  ),
  beatNote(
    "run-from-deployment",
    "input",
    11,
    "Show the concrete inputs supplied before execution.",
    ["run input", "selected documents"],
    "The deployment receives selected local documents and an issue-board path.",
    ["workflow.runs.start replay evidence"],
  ),
  beatNote(
    "run-from-deployment",
    "operation",
    12,
    "Show that one public operation creates a persisted execution.",
    ["workflow.runs.start", "persisted Run"],
    "The public **workflow.runs.start** operation validates the deployment and input, creates a **persisted Run**, and begins the reusable graph.",
    ["workflow.runs.start replay evidence"],
    { qnaBranchIds: ["run-persistence"] },
  ),
  beatNote(
    "run-from-deployment",
    "graph",
    12,
    "Show the reusable workflow executing beyond the chat conversation.",
    ["workflow graph", "declared interrupt"],
    "The graph reads documents, analyzes them, builds a report, drafts proposed issues, and pauses at a declared review interrupt before issue-board changes.",
    ["workflow.runs.start replay evidence", "examples/lda_report_workflow"],
    { fallback: "The operation view is replay-backed evidence of the prepared path, not a newly completed live run." },
  ),
  beatNote(
    "typed-human-boundary",
    "interrupt",
    15,
    "Show what the paused workflow asks from the operator.",
    ["issue_review", "interrupt payload", "resume schema"],
    "Execution pauses at a **typed issue_review interrupt** exposing request data, allowed outcomes, request schema, and resume schema.",
    ["Typed interrupt payload and resume contract"],
    { qnaBranchIds: ["typed-interrupts", "why-schemas"] },
  ),
  beatNote(
    "typed-human-boundary",
    "approval",
    15,
    "Show that the operator chooses a declared continuation.",
    ["submitted", "revision-requested", "typed resume"],
    "The operator chooses submitted or revision-requested; this is a typed interrupt and resume contract, not a production approval gate, role system, or policy engine.",
    ["Typed interrupt payload and resume contract"],
    { warning: "Both outcomes resume through declared workflow branches; this is not production approval governance.", qnaBranchIds: ["typed-interrupts", "security-production-boundary"] },
  ),
  beatNote(
    "resume-output-evidence",
    "resume",
    16,
    "Show continuation of the same recorded run.",
    ["workflow.runs.resume", "same Run"],
    "On the submitted path, **workflow.runs.resume continues the recorded interrupted Run**.",
    ["workflow.runs.resume replay evidence", "Revision replay identity"],
    { fallback: "The submitted replay demonstrates same-run continuation; the revision branch is recorded separately.", qnaBranchIds: ["replay-provenance", "prepared-replay-boundary"] },
  ),
  beatNote(
    "resume-output-evidence",
    "output",
    16,
    "Show the persisted terminal results of the submitted path.",
    ["report output", "issue-board changes"],
    "The workflow creates the report and issue-board changes, then records terminal output.",
    ["workflow.runs.resume replay evidence", "examples/lda_report_workflow"],
    { warning: "Identify these issue-board changes as later example evidence, not output from the thesis three-node case study." },
  ),
  beatNote(
    "resume-output-evidence",
    "trace",
    18,
    "Show that execution evidence remains inspectable after completion.",
    ["trace frames", "protocol evidence"],
    "Trace frames and protocol evidence remain inspectable; this is declared-boundary resumability, not arbitrary crash recovery or exactly-once execution. The revision replay is a separate prepared recording.",
    ["workflow.runs.resume replay evidence", "Revision replay identity"],
    { warning: "Never claim run-ID continuity for the prepared revision recording.", qnaBranchIds: ["replay-provenance", "demo-reliability"] },
  ),
  beatNote(
    "evaluation",
    "cohort",
    40,
    "Describe the external-agent evaluation design.",
    ["36 trials", "two challenges", "three profiles"],
    "The evaluation combines conformance tests, deterministic case studies, and a **manually audited external-agent campaign**: 36 trials across two challenges, two hosted models, three instruction profiles, and three waves, with three attempts per cell.",
    ["Thesis Evaluation and Appendix C"],
    { qnaBranchIds: ["evaluation-validity"] },
  ),
  beatNote(
    "evaluation",
    "validity",
    40,
    "Separate audited valid evidence from contaminated samples.",
    ["27 pass", "8 invalid", "1 fail"],
    "The author audit classified 27 trials as clean product-path passes, eight as invalid samples, and one as a failure. Invalid samples included contamination such as reading implementation files, prior artifacts, adjacent attempts, or evaluator state.",
    ["Thesis Evaluation and Appendix C", "Author audit"],
    { qnaBranchIds: ["evaluation-validity"] },
  ),
  beatNote(
    "evaluation",
    "findings",
    40,
    "State what the evaluation supports and what it cannot prove.",
    ["longitudinal evidence", "not a benchmark"],
    "Because prompts, product snapshots, and hosted conditions changed across waves, these results are **longitudinal engineering evidence**. They expose authoring and diagnostic gaps, **not a benchmark** of model success, token reduction, retry reduction, or superiority.",
    ["Thesis Evaluation and Appendix C", "Thesis Threats to Validity"],
    { warning: "Use non-benchmark wording; do not report the counts as general model performance.", qnaBranchIds: ["evaluation-validity"] },
  ),
  beatNote(
    "conclusion",
    "limits",
    18,
    "Bound the prototype claims before the final contribution statement.",
    ["prototype", "not production security"],
    "The prototype uses trusted in-process Python and file-backed stores; it does not provide production authentication, RBAC, sandboxing, scheduling, arbitrary crash recovery, or a bundled autonomous planner.",
    ["Thesis Limitations"],
    { qnaBranchIds: ["security-production-boundary", "production-readiness"] },
  ),
  beatNote(
    "conclusion",
    "future",
    18,
    "Name the surrounding layers left as future work.",
    ["live agent", "scheduling", "controlled evaluation"],
    "A live agent interface, transactional storage, richer debugging, security hardening, scheduling, and controlled comparative evaluation remain future work.",
    ["Thesis Future Work"],
    { qnaBranchIds: ["production-readiness"] },
  ),
  beatNote(
    "conclusion",
    "conclusion",
    20,
    "Restate the implemented contribution and planner-runtime boundary.",
    ["planner proposes", "platform executes"],
    "The contribution is **architectural and implemented**: external planners can propose workflows while a typed platform **validates, binds, executes, persists, interrupts, resumes, and inspects** them through public operations.",
    ["Thesis Contributions", "Thesis Conclusion"],
    { qnaBranchIds: ["where-is-ai-agent", "not-just-cli"] },
  ),
  beatNote(
    "conclusion",
    "questions",
    19,
    "Open structured examiner discussion without introducing new claims.",
    ["defense questions", "evidence"],
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
