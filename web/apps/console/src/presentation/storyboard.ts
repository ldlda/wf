export type ClaimClass = "motivation" | "implemented" | "evaluated" | "external-context" | "future-work";
export type StageTheme = "paper" | "night";
export type ChatTheme = "light" | "dark";
export type ChatMode = "hidden" | "full" | "rail" | "dock";
export type EvidenceMode = "hidden" | "peek" | "open";
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
  readonly evidenceMode: EvidenceMode;
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
  options: Partial<Pick<SceneBeatDefinition, "chatMode" | "chatTheme" | "evidenceMode" | "figure">> = {},
): SceneBeatDefinition => ({
  id,
  title,
  caption,
  chatMode: options.chatMode ?? "hidden",
  chatTheme: options.chatTheme ?? "dark",
  evidenceMode: options.evidenceMode ?? "hidden",
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
      sceneBeat("client", "Client operations", "Human and agent clients use the same public lifecycle surface."),
      sceneBeat("api", "Transport and API", "JSON-RPC reaches WorkflowApi without owning domain behavior."),
      sceneBeat("runtime", "Runtime and providers", "The runtime resolves provider-neutral capabilities and stores lifecycle records."),
      sceneBeat("node-use", "NodeUse", "One callable node validates input, invokes a capability, and reduces output into state.", { evidenceMode: "peek" }),
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
      sceneBeat("diagnose", "Diagnose", "Structured diagnostics identify invalid state.", { evidenceMode: "peek" }),
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
      sceneBeat("graph", "Reusable graph", "The graph becomes primary while chat moves to a rail.", { chatMode: "rail", chatTheme: "light" }),
      sceneBeat("interrupt", "Typed interrupt", "Execution reaches the issue-review boundary.", { chatMode: "rail", chatTheme: "light" }),
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
      sceneBeat("approval", "Approval", "The operator reviews a schema-backed resume request.", { chatMode: "rail", chatTheme: "light" }),
      sceneBeat("resume", "Resume", "The approved payload resumes the same persisted run.", { chatMode: "rail", chatTheme: "light" }),
      sceneBeat("output", "Output", "The workflow produces the report and issue-board changes.", { chatMode: "dock", chatTheme: "light" }),
      sceneBeat("trace", "Evidence", "Trace frames and protocol evidence remain inspectable.", { chatMode: "dock", chatTheme: "light", evidenceMode: "open" }),
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

export type DiscussionBranchDefinition = {
  readonly id: string;
  readonly parentSceneId: MainSceneId;
  readonly title: string;
  readonly claimClass: ClaimClass;
  readonly evidencePointer: string;
  readonly summary: string;
};

const defineDiscussionBranches = <const Branches extends readonly DiscussionBranchDefinition[]>(
  branches: Branches,
): Branches => branches;

export const discussionBranches = defineDiscussionBranches([
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
  },
  {
    id: "evaluation-validity",
    parentSceneId: "evaluation",
    title: "Evaluation validity bounds",
    claimClass: "evaluated",
    evidencePointer: "Thesis Evaluation; bounded validity",
    summary: "Manual audit separates task completion from valid product-surface evidence.",
  },
  {
    id: "replay-provenance",
    parentSceneId: "workflow-demo",
    title: "Replay provenance",
    claimClass: "implemented",
    evidencePointer: "Thesis Prepared Replay; replay evidence chain",
    summary: "Replay evidence is projected from the canonical recording for deterministic demonstration.",
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
