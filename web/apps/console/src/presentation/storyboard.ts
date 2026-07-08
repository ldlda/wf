export type ClaimClass = "motivation" | "implemented" | "evaluated" | "external-context" | "future-work";
export type StageTheme = "paper" | "night";
export type ChatTheme = "light" | "dark";
export type ChatMode = "hidden" | "full" | "rail" | "dock";
export type EvidencePresentation = "hidden" | "receipt" | "inspector";
export type BeatEvidencePresentation = Exclude<EvidencePresentation, "inspector">;
export type SceneView =
  | "narrative"
  | "positioning"
  | "boundary"
  | "lifecycle"
  | "architecture"
  | "authoring"
  | "agent"
  | "demo"
  | "evaluation"
  | "conclusion";

export type FigureBeatDefinition = {
  readonly catalogId: string;
  readonly focusPath: readonly string[];
  readonly activeNodeId: string | null;
};

export type SceneBeatDefinition = {
  readonly id: string;
  readonly title: string;
  readonly caption: string;
  readonly chatMode: ChatMode;
  readonly chatTheme: ChatTheme;
  readonly evidencePresentation: BeatEvidencePresentation;
  readonly figure: FigureBeatDefinition | null;
};

export type SceneDefinition = {
  readonly id: string;
  readonly number: number;
  readonly title: string;
  readonly claimClass: ClaimClass;
  readonly evidencePointer: string;
  readonly stageTheme: StageTheme;
  readonly view: SceneView;
  readonly beats: readonly SceneBeatDefinition[];
};

const defineScenes = <const Scenes extends readonly SceneDefinition[]>(scenes: Scenes): Scenes => scenes;

const sceneBeat = (
  id: string,
  title: string,
  caption: string,
  options: Partial<Pick<SceneBeatDefinition, "chatMode" | "chatTheme" | "evidencePresentation" | "figure">> = {},
): SceneBeatDefinition => ({
  id,
  title,
  caption,
  chatMode: options.chatMode ?? "hidden",
  chatTheme: options.chatTheme ?? "dark",
  evidencePresentation: options.evidencePresentation ?? "hidden",
  figure: options.figure ?? null,
});

export const mainScenes = defineScenes([
  {
    id: "thesis",
    number: 1,
    title: "Thesis",
    claimClass: "implemented",
    evidencePointer: "Thesis Abstract and Introduction",
    stageTheme: "paper",
    view: "narrative",
    beats: [
      sceneBeat("title", "Design and Implementation of lda.chat", "The project began as a pursuit of an AI agent for workspace automation."),
      sceneBeat("substrate", "The substrate an agent needs", "The submitted contribution creates, validates, runs, and inspects reusable workflows."),
    ],
  },
  {
    id: "problem",
    number: 2,
    title: "The Problem",
    claimClass: "motivation",
    evidencePointer: "Thesis Problem Statement and Requirements",
    stageTheme: "paper",
    view: "narrative",
    beats: [
      sceneBeat("direct-actions", "Direct actions are not reusable automation", "A tool loop can act without owning durable lifecycle records."),
      sceneBeat("missing-contracts", "The missing contracts", "Reusable automation needs schemas, bindings, persistence, traces, and recovery boundaries."),
    ],
  },
  {
    id: "positioning",
    number: 3,
    title: "Positioning and Related Systems",
    claimClass: "motivation",
    evidencePointer: "Thesis Positioning and Related Systems",
    stageTheme: "paper",
    view: "positioning",
    beats: [
      sceneBeat("landscape", "Different centers of gravity", "Tool loops, scripts, hosted automation, agent graphs, and MCP solve different parts of the problem."),
      sceneBeat("lda-position", "lda.chat's position", "Typed lifecycle contracts and provider-neutral sources are exposed for external-agent operation."),
    ],
  },
  {
    id: "planner-runtime",
    number: 4,
    title: "Planner and Runtime",
    claimClass: "implemented",
    evidencePointer: "Thesis Architecture Overview",
    stageTheme: "night",
    view: "boundary",
    beats: [
      sceneBeat("planner", "External planner", "The planner proposes and revises workflow structure."),
      sceneBeat("runtime", "Deterministic runtime", "The runtime validates, executes, records, and resumes."),
      sceneBeat("boundary", "Explicit operations", "Typed CLI and JSON-RPC operations cross the boundary."),
    ],
  },
  {
    id: "lifecycle",
    number: 5,
    title: "Workflow Lifecycle",
    claimClass: "implemented",
    evidencePointer: "Thesis Workflow Lifecycle",
    stageTheme: "night",
    view: "lifecycle",
    beats: [
      sceneBeat("draft", "Draft", "Mutable iterative authoring state."),
      sceneBeat("artifact", "Artifact", "Immutable saved workflow definition."),
      sceneBeat("deployment", "Deployment", "Logical requirements bound to concrete sources."),
      sceneBeat("run", "Run", "Persisted execution, output, status, and trace."),
    ],
  },
  {
    id: "architecture",
    number: 6,
    title: "Architecture Zoom",
    claimClass: "implemented",
    evidencePointer: "Thesis System Architecture; docs/project_map.md; docs/source_architecture.md",
    stageTheme: "night",
    view: "architecture",
    beats: [
      sceneBeat("client", "Client operations", "Human and agent clients use the same public lifecycle surface.", { figure: { catalogId: "system-architecture", focusPath: [], activeNodeId: "client-operations" } }),
      sceneBeat("api", "Transport and API", "JSON-RPC reaches WorkflowApi without owning domain behavior.", { figure: { catalogId: "system-architecture", focusPath: [], activeNodeId: "application-lifecycle" } }),
      sceneBeat("runtime", "Runtime and providers", "The runtime resolves provider-neutral capabilities and stores lifecycle records.", { figure: { catalogId: "system-architecture", focusPath: ["runtime-providers"], activeNodeId: "configured-providers" } }),
      sceneBeat("node-use", "NodeUse", "One callable node validates input, invokes a capability, and reduces output into state.", { evidencePresentation: "receipt", figure: { catalogId: "system-architecture", focusPath: ["node-use"], activeNodeId: "invoke-handler" } }),
    ],
  },
  {
    id: "authoring",
    number: 7,
    title: "Author, Validate, Repair",
    claimClass: "implemented",
    evidencePointer: "CLI documentation; draft authoring API; challenge UX findings",
    stageTheme: "night",
    view: "authoring",
    beats: [
      sceneBeat("discover", "Discover", "Inspect capabilities and schemas before authoring."),
      sceneBeat("author", "Author", "Focused operations build and connect the draft."),
      sceneBeat("diagnose", "Diagnose", "Structured diagnostics identify invalid state.", { evidencePresentation: "receipt" }),
      sceneBeat("repair", "Repair", "Repair hints lead to a valid compiled workflow."),
    ],
  },
  {
    id: "agent-handoff",
    number: 8,
    title: "Agent Handoff",
    claimClass: "implemented",
    evidencePointer: "Constrained demo agent and prepared replay recipe",
    stageTheme: "night",
    view: "agent",
    beats: [
      sceneBeat("request", "Operator request", "A thin agent interface receives the report request.", { chatMode: "full", chatTheme: "light" }),
      sceneBeat("handoff", "Prepared operation", "The interface delegates durable work to lda.chat.", { chatMode: "full", chatTheme: "light" }),
    ],
  },
  {
    id: "workflow-demo",
    number: 9,
    title: "Workflow Takes the Stage",
    claimClass: "implemented",
    evidencePointer: "Prepared replay and examples/lda_report_workflow",
    stageTheme: "night",
    view: "demo",
    beats: [
      sceneBeat("operation", "Start operation", "Raw and interpreted operation evidence enters from chat.", { chatMode: "full", chatTheme: "light" }),
      sceneBeat("graph", "Reusable graph", "The graph becomes primary while chat moves out of the way.", { chatMode: "hidden", chatTheme: "light" }),
      sceneBeat("interrupt", "Typed interrupt", "Execution reaches the issue-review boundary.", { chatMode: "hidden", chatTheme: "light" }),
    ],
  },
  {
    id: "interrupt-evidence",
    number: 10,
    title: "Interrupt, Resume, Evidence",
    claimClass: "implemented",
    evidencePointer: "Typed interrupt schemas, run inspection, and trace events",
    stageTheme: "night",
    view: "demo",
    beats: [
      sceneBeat("approval", "Approval", "The operator reviews a schema-backed resume request.", { chatMode: "hidden", chatTheme: "light" }),
      sceneBeat("resume", "Resume", "The submitted payload resumes the same persisted run.", { chatMode: "hidden", chatTheme: "light" }),
      sceneBeat("output", "Output", "The workflow produces the report and issue-board changes.", { chatMode: "hidden", chatTheme: "light" }),
      sceneBeat("trace", "Evidence", "Trace frames and protocol evidence remain inspectable.", { chatMode: "dock", chatTheme: "light", evidencePresentation: "receipt" }),
    ],
  },
  {
    id: "evaluation",
    number: 11,
    title: "Evaluation",
    claimClass: "evaluated",
    evidencePointer: "Thesis Evaluation and Appendix C",
    stageTheme: "paper",
    view: "evaluation",
    beats: [
      sceneBeat("cohort", "36-trial cohort", "Two challenges, two hosted models, three profiles, and three waves."),
      sceneBeat("validity", "Bounded validity", "Manual audit separates task completion from valid product-surface evidence."),
      sceneBeat("findings", "Longitudinal findings", "Trials exposed concrete authoring and diagnostic UX gaps."),
    ],
  },
  {
    id: "conclusion",
    number: 12,
    title: "Limits and Conclusion",
    claimClass: "future-work",
    evidencePointer: "Thesis Limitations, Future Work, and Conclusion",
    stageTheme: "paper",
    view: "conclusion",
    beats: [
      sceneBeat("limits", "Implemented boundary", "The prototype is not a production sandbox, scheduler, or broad agent benchmark."),
      sceneBeat("future", "Surrounding layers", "A live LLM interface, scheduling, and broader evaluation remain future work."),
      sceneBeat("conclusion", "Planner proposes; runtime executes", "The typed substrate makes reusable agent-operated automation inspectable.", { chatMode: "dock", chatTheme: "light" }),
    ],
  },
]);

export type MainSceneId = (typeof mainScenes)[number]["id"];

export type MainLocation = {
  readonly kind: "main";
  readonly sceneId: MainSceneId;
  readonly beatId: string;
  readonly focusPath: readonly string[];
};

type DiscussionLink = {
  readonly label: string;
  readonly href: string;
};

type DiscussionBranchDetail = {
  readonly text: string;
  readonly links?: readonly DiscussionLink[];
};

type QuestionAnswerBranchFields = {
  readonly question?: string;
  readonly shortAnswer?: string;
  readonly expandedAnswer?: string;
  readonly speakerHint?: string;
};

export type DiscussionBranchDefinition = QuestionAnswerBranchFields & {
  readonly id: string;
  readonly parentSceneId: MainSceneId;
  readonly title: string;
  readonly claimClass: ClaimClass;
  readonly evidencePointer: string;
  readonly summary: string;
  readonly detail?: DiscussionBranchDetail;
};

const defineDiscussionBranches = <const Branches extends readonly DiscussionBranchDefinition[]>(
  branches: Branches,
): Branches => branches;

export const discussionBranches = defineDiscussionBranches([
  {
    id: "where-is-ai-agent",
    parentSceneId: "thesis",
    title: "Where is the AI agent?",
    claimClass: "implemented",
    evidencePointer: "Abstract; Chapter 1 framing; presentation Scene 1",
    summary: "The implementation is the agent-operable workflow substrate, not a bundled autonomous planner.",
    question: "Where is the AI agent in this thesis?",
    shortAnswer: "The submitted implementation is the lower-level workflow substrate that external agents operate. It exposes typed lifecycle, validation, execution, trace, and inspection surfaces; the autonomous planner layer is intentionally outside the core contribution.",
    expandedAnswer: "The forced product framing uses AI-agent language, but the engineering contribution is not a new planning algorithm. The system gives external LLM operators and human users a reliable workflow lifecycle: drafts, artifacts, deployments, runs, source bindings, diagnostics, traces, and bounded resume. A thin chat or agent graph interface could sit above it, but this thesis evaluates the substrate that makes such an interface useful.",
    speakerHint: "Answer directly first; do not sound defensive. Say substrate, then lifecycle evidence.",
  },
  {
    id: "title-ai-agent-wording",
    parentSceneId: "thesis",
    title: "Title wording boundary",
    claimClass: "implemented",
    evidencePointer: "Abstract; Introduction; Future Work",
    summary: "The title is defended as product direction while the body narrows the implemented contribution.",
    question: "Does the title overclaim by saying AI Agent?",
    shortAnswer: "It is a risky title if read as a claim that the thesis implements a complete autonomous agent brain. The body narrows that claim: this work implements the workflow substrate for agent-operated automation.",
    expandedAnswer: "The safest defense is to distinguish product ambition from the submitted technical artifact. The artifact owns schemas, validation, source projection, lifecycle state, deployment binding, run records, traces, and typed interrupts. A future agent wrapper can use those operations as tools, but that wrapper is not the thesis contribution.",
    speakerHint: "Do not argue that the platform is secretly a full agent. Reframe to agent-operable substrate.",
  },
  {
    id: "direct-orchestration",
    parentSceneId: "positioning",
    title: "Direct orchestration",
    claimClass: "motivation",
    evidencePointer: "Thesis: Direct LLM Tool Orchestration",
    summary: "Dynamic adaptation versus durable reusable procedure.",
  },
  {
    id: "generated-scripts",
    parentSceneId: "positioning",
    title: "Generated scripts",
    claimClass: "motivation",
    evidencePointer: "Thesis: Generated Scripts",
    summary: "Simplicity and debuggability versus managed lifecycle records.",
  },
  {
    id: "hosted-automation",
    parentSceneId: "positioning",
    title: "Hosted automation",
    claimClass: "future-work",
    evidencePointer: "Thesis: Workflow Automation Platforms and Future Work",
    summary: "Hosted triggers and scheduling are mature elsewhere and remain future work here.",
    detail: {
      text: "A future scheduler could trigger a workflow that launches a verified headless coding-agent command with a stored prompt. lda.chat does not implement that trigger or scheduler in the submitted scope.",
    },
  },
  {
    id: "durable-agent-graphs",
    parentSceneId: "positioning",
    title: "Durable agent graphs",
    claimClass: "motivation",
    evidencePointer: "Thesis: Agent Graph Frameworks",
    summary: "Shared durability concerns, with a different lifecycle and source-binding emphasis.",
  },
  {
    id: "mcp-agent-scale",
    parentSceneId: "positioning",
    title: "MCP and agent-facing scale",
    claimClass: "external-context",
    evidencePointer: "Thesis: Model Context Protocol; Anthropic MCP; Cloudflare Code Mode",
    summary: "MCP is a capability protocol; progressive discovery addresses large agent-facing surfaces.",
    detail: {
      text: "Both are external context.",
      links: [
        {
          label: "Anthropic MCP",
          href: "https://www.anthropic.com/engineering/code-execution-with-mcp",
        },
        {
          label: "Cloudflare Code Mode",
          href: "https://blog.cloudflare.com/code-mode-mcp/",
        },
      ],
    },
  },
  {
    id: "not-just-scripts",
    parentSceneId: "positioning",
    title: "Why not scripts?",
    claimClass: "motivation",
    evidencePointer: "Chapter 3 positioning; Draft-Artifact-Deployment-Run model",
    summary: "Scripts are simple, but they do not naturally provide lifecycle state, deployment binding, validation, traces, or reusable inspection records.",
    question: "Why not generate Python scripts instead?",
    shortAnswer: "Generated scripts can solve one task, but reusable workspace automation needs lifecycle state, validation, deployment binding, traces, and recovery boundaries that should not be left inside generated code.",
    expandedAnswer: "The thesis does not claim scripts are bad. It claims that as soon as external agents are expected to author reusable automations, the platform should own the durable parts: schema contracts, source inventory, validation, immutable artifacts, deployment bindings, run records, and inspection. Generated scripts can still be one capability source behind that boundary.",
  },
  {
    id: "not-just-cli",
    parentSceneId: "planner-runtime",
    title: "Not just a CLI",
    claimClass: "implemented",
    evidencePointer: "wf_api surface; JSON-RPC transport; web console",
    summary: "The CLI is one front door over the same workflow API and runtime lifecycle.",
    question: "Is this just a CLI wrapper?",
    shortAnswer: "No. The CLI is only one client. The same operations are exposed through the workflow API and JSON-RPC server, and the web console uses that protocol boundary to inspect lifecycle records and execute the prepared demo.",
    expandedAnswer: "A CLI-only project would stop at command parsing. This system has typed workflow models, source providers, transport-neutral API surfaces, persisted artifacts/deployments/runs, trace inspection, validation diagnostics, and a React console that consumes JSON-RPC. The CLI remains useful because agents and humans can operate it, but it is not the architecture boundary.",
  },
  {
    id: "lifecycle-states",
    parentSceneId: "lifecycle",
    title: "Lifecycle state machine",
    claimClass: "implemented",
    evidencePointer: "Thesis Workflow Lifecycle; lifecycle state transitions",
    summary: "Draft, artifact, deployment, and run form a typed lifecycle; raw plans can bypass the draft stage.",
  },
  {
    id: "raw-plan-import",
    parentSceneId: "authoring",
    title: "Raw plan import",
    claimClass: "implemented",
    evidencePointer: "Thesis Authoring; raw plan import and compilation",
    summary: "Raw plans are compiled into validated workflow definitions with typed operations.",
  },
  {
    id: "validation-diagnostics",
    parentSceneId: "authoring",
    title: "Validation and diagnostics",
    claimClass: "implemented",
    evidencePointer: "Thesis Validation; diagnostic repair hints",
    summary: "Structured diagnostics identify invalid state and suggest repair hints.",
  },
  {
    id: "why-schemas",
    parentSceneId: "authoring",
    title: "Why schemas matter",
    claimClass: "implemented",
    evidencePointer: "wf schema command; draft validation diagnostics; typed interrupt contracts",
    summary: "Schemas move correctness checks out of agent guesses and into the platform.",
    question: "Why put so much emphasis on schemas?",
    shortAnswer: "Schemas are how the platform turns agent-authored workflow guesses into checkable contracts. They let the system validate bindings, project capability inputs/outputs, describe interrupts, and explain repair paths before runtime execution.",
    expandedAnswer: "Without schemas, the planner must infer every shape and failure appears late. With schemas, the runtime can detect invalid source paths, undeclared destinations, missing outcomes, incompatible resume payloads, and source drift. That does not make agents perfect, but it gives them a public surface to discover and repair against.",
  },
  {
    id: "typed-interrupts",
    parentSceneId: "interrupt-evidence",
    title: "Typed interrupt contracts",
    claimClass: "implemented",
    evidencePointer: "Thesis Typed Interrupts; interrupt schemas",
    summary: "Interrupts are typed resume-request payloads with schema-backed review boundaries.",
  },
  {
    id: "run-persistence",
    parentSceneId: "architecture",
    title: "Run persistence and inspection",
    claimClass: "implemented",
    evidencePointer: "Thesis Runtime; run persistence and trace events",
    summary: "Persisted runs store output, status, and trace for post-hoc inspection.",
  },
  {
    id: "provider-security",
    parentSceneId: "architecture",
    title: "Provider-neutral security",
    claimClass: "implemented",
    evidencePointer: "Thesis Architecture; provider-neutral capability resolution",
    summary: "Provider-neutral capabilities reduce vendor lock-in; runtime enforces boundary contracts.",
    question: "Do source providers solve security?",
    shortAnswer: "No. Source providers create a clearer boundary for capability projection and deployment binding, but they are not a complete security model.",
    expandedAnswer: "The provider boundary helps separate source inventory, schemas, and runtime calls from the workflow graph. It gives the platform a place to inspect and validate capabilities. Production security still needs credentials, sandboxing, RBAC, policy enforcement, and operational audit beyond this prototype.",
  },
  {
    id: "security-production-boundary",
    parentSceneId: "architecture",
    title: "Security and production boundary",
    claimClass: "implemented",
    evidencePointer: "Limitations; source-provider boundary; loopback console policy",
    summary: "The prototype defines boundaries but does not claim production hardening.",
    question: "Is this secure enough for production?",
    shortAnswer: "No. The thesis is explicit that this is a prototype. It demonstrates source/provider boundaries, local-first transport, and typed validation, but not production-grade authentication, authorization, sandboxing, secret handling, or tenant isolation.",
    expandedAnswer: "The implemented boundary is still useful: sources are projected through a provider-neutral surface, deployments bind requirements explicitly, and runs are inspectable. But production security would require a separate hardening track: credentials, RBAC, audit policy, sandboxed tool execution, untrusted workflow review, network policy, and operational monitoring.",
  },
  {
    id: "evaluation-validity",
    parentSceneId: "evaluation",
    title: "Evaluation validity bounds",
    claimClass: "evaluated",
    evidencePointer: "Thesis Evaluation; bounded validity",
    summary: "Manual audit separates task completion from valid product-surface evidence.",
    question: "How valid is the 36-trial external-agent evaluation?",
    shortAnswer: "It is useful engineering evidence, but not a controlled model comparison. The thesis treats it as bounded longitudinal evidence about agent-operability and UX failure modes.",
    expandedAnswer: "The cohort has N=3 per cell, two challenges, two hosted models, and three instruction profiles, but it spans product and prompt evolution. Manual audit is authoritative for validity. That supports feasibility and failure analysis, not broad claims about model generalization, token savings, or superiority over other workflow systems.",
    speakerHint: "Emphasize honesty: useful evidence, deliberately bounded claim.",
  },
  {
    id: "replay-provenance",
    parentSceneId: "workflow-demo",
    title: "Replay provenance",
    claimClass: "implemented",
    evidencePointer: "Thesis Prepared Replay; replay evidence chain",
    summary: "Replay evidence is projected from the canonical recording for deterministic demonstration.",
  },
  {
    id: "demo-reliability",
    parentSceneId: "workflow-demo",
    title: "Live demo reliability",
    claimClass: "implemented",
    evidencePointer: "Prepared lda_report_workflow; replay recording; defense presentation runbook",
    summary: "The demo is designed with live and replay paths so the defense can explain the system even if local services fail.",
    question: "What if the live demo fails?",
    shortAnswer: "The defense has a replay path with the same recorded operation sequence and evidence. If live RPC fails, the point is still demonstrable: the workflow lifecycle, typed interrupt, resume result, trace, and output records are shown from the prepared recording.",
    expandedAnswer: "The replay is not presented as fresh empirical evidence. It is a presentation fallback for an already-tested deterministic example. The live path demonstrates current server behavior when available; the replay path preserves the explanation if Wi-Fi, local ports, or process state fail during the defense.",
  },
  {
    id: "prepared-replay-boundary",
    parentSceneId: "workflow-demo",
    title: "Prepared replay boundary",
    claimClass: "evaluated",
    evidencePointer: "Demo recording fixture; replay provenance branch; runbook fallback wording",
    summary: "Prepared replay is a communication artifact, not a benchmark result.",
    question: "Is the replay cheating?",
    shortAnswer: "It would be cheating if presented as a new live result. Here it is a controlled presentation artifact that shows a previously verified operation path, with provenance separated from the external-agent evaluation.",
    expandedAnswer: "The thesis separates implementation evidence, automated tests, external-agent trials, and presentation replay. Replay exists so the audience can see the lifecycle without relying on a fragile live environment. It should be described as recorded evidence of a deterministic path, not as a live autonomous-agent success.",
  },
  {
    id: "production-readiness",
    parentSceneId: "conclusion",
    title: "Production readiness",
    claimClass: "future-work",
    evidencePointer: "Limitations; Future Work; roadmap",
    summary: "The system is submission-ready as a prototype, not production-ready as a hosted automation service.",
    question: "What is missing before this becomes a production product?",
    shortAnswer: "The major missing pieces are security hardening, real credential management, better hosted operations, stronger UI flows, controlled evaluation, scheduler semantics, and a real external-agent interface.",
    expandedAnswer: "The thesis contribution is the substrate: typed lifecycle, validation, source binding, artifacts, deployments, runs, traces, and interrupt contracts. A production product would need authentication, RBAC, secret stores, sandboxing, migration policy, operational dashboards, scaling, billing or tenant boundaries, and a validated planner/chat layer on top.",
  },
]);

export type DiscussionBranchId = (typeof discussionBranches)[number]["id"];

export type DiscussionLocation = {
  readonly kind: "discussion";
  readonly branchId: DiscussionBranchId;
};

export type PresentationLocation = MainLocation | DiscussionLocation;

export const findScene = (sceneId: string): SceneDefinition | undefined =>
  mainScenes.find((scene) => scene.id === sceneId);

export const findBeat = (sceneId: string, beatId: string): SceneBeatDefinition | undefined =>
  findScene(sceneId)?.beats.find((beat) => beat.id === beatId);

export const findDiscussionBranch = (branchId: string): DiscussionBranchDefinition | undefined =>
  discussionBranches.find((branch) => branch.id === branchId);

export const defaultMainLocation: MainLocation = { kind: "main", sceneId: "thesis", beatId: "title", focusPath: [] };

export const mainLocation = (sceneId: string, beatId: string): MainLocation | null => {
  const scene = findScene(sceneId);
  if (!scene) return null;
  const beat = scene.beats.find((b) => b.id === beatId);
  if (!beat) return null;
  return { kind: "main", sceneId: scene.id as MainSceneId, beatId: beat.id, focusPath: beat.figure?.focusPath ?? [] };
};
