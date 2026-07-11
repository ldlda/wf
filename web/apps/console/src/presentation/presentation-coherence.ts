export type PrimaryArtifact =
  | "opening-decomposition"
  | "tool-loop-transcript"
  | "positioning-map"
  | "boundary-diagram"
  | "lifecycle-rail"
  | "interactive-architecture"
  | "authoring-loop"
  | "agent-handoff"
  | "prepared-lifecycle"
  | "workflow-graph"
  | "interrupt-approval"
  | "trace-evidence"
  | "evaluation-board"
  | "future-work-map";

export type SupportSurface =
  | "none"
  | "discussion-rail"
  | "current-state-panel"
  | "run-receipt"
  | "facts-only"
  | "output-summary";

export type ChatRole = "hidden" | "narration" | "approval" | "trace";

export type BeatVisualMode = "focal" | "split" | "zoom" | "conversation" | "evidence";

export type SceneBeatVisualContract = {
  readonly sceneId: string;
  readonly beatId: string;
  readonly mode: BeatVisualMode;
  readonly primarySurface: string;
  readonly supportSurface: string;
};

export type SceneCoherenceEntry = {
  readonly sceneId: string;
  readonly primaryArtifact: PrimaryArtifact;
  readonly supportSurface: SupportSurface;
  readonly chatRole: ChatRole;
  readonly presenterFocus: string;
};

export const sceneCoherenceMatrix = [
  {
    sceneId: "thesis",
    primaryArtifact: "opening-decomposition",
    supportSurface: "discussion-rail",
    chatRole: "hidden",
    presenterFocus: "Move from AI-agent ambition to the submitted workflow substrate.",
  },
  {
    sceneId: "problem",
    primaryArtifact: "tool-loop-transcript",
    supportSurface: "none",
    chatRole: "hidden",
    presenterFocus: "Contrast a one-off agent/tool loop with reusable automation requirements.",
  },
  {
    sceneId: "positioning",
    primaryArtifact: "positioning-map",
    supportSurface: "discussion-rail",
    chatRole: "hidden",
    presenterFocus: "Place the system among scripts, tool loops, hosted automation, MCP, and agent graphs.",
  },
  {
    sceneId: "planner-runtime",
    primaryArtifact: "boundary-diagram",
    supportSurface: "discussion-rail",
    chatRole: "hidden",
    presenterFocus: "Show that external planners propose while the runtime validates and records.",
  },
  {
    sceneId: "lifecycle",
    primaryArtifact: "lifecycle-rail",
    supportSurface: "current-state-panel",
    chatRole: "hidden",
    presenterFocus: "Explain Draft -> Artifact -> Deployment -> Run as the durable lifecycle.",
  },
  {
    sceneId: "architecture",
    primaryArtifact: "interactive-architecture",
    supportSurface: "discussion-rail",
    chatRole: "hidden",
    presenterFocus: "Use the recursive architecture figure as the only primary artifact.",
  },
  {
    sceneId: "authoring",
    primaryArtifact: "authoring-loop",
    supportSurface: "discussion-rail",
    chatRole: "hidden",
    presenterFocus: "Show the authoring loop without turning it into generic process cards.",
  },
  {
    sceneId: "agent-handoff",
    primaryArtifact: "agent-handoff",
    supportSurface: "none",
    chatRole: "narration",
    presenterFocus: "Introduce the prepared operator flow only as a bridge into product proof.",
  },
  {
    sceneId: "prepared-lifecycle",
    primaryArtifact: "prepared-lifecycle",
    supportSurface: "none",
    chatRole: "hidden",
    presenterFocus: "Show the prepared workflow before execution starts.",
  },
  {
    sceneId: "run-from-deployment",
    primaryArtifact: "workflow-graph",
    supportSurface: "run-receipt",
    chatRole: "hidden",
    presenterFocus: "Start a persisted run from a deployment and keep the graph dominant.",
  },
  {
    sceneId: "typed-human-boundary",
    primaryArtifact: "interrupt-approval",
    supportSurface: "facts-only",
    chatRole: "approval",
    presenterFocus: "Show the typed interrupt, selected issues, and operator decision.",
  },
  {
    sceneId: "resume-output-evidence",
    primaryArtifact: "trace-evidence",
    supportSurface: "output-summary",
    chatRole: "trace",
    presenterFocus: "Show resume, output, and trace as evidence from the same run.",
  },
  {
    sceneId: "evaluation",
    primaryArtifact: "evaluation-board",
    supportSurface: "discussion-rail",
    chatRole: "hidden",
    presenterFocus: "Summarize evaluation as bounded evidence, not a model leaderboard.",
  },
  {
    sceneId: "conclusion",
    primaryArtifact: "future-work-map",
    supportSurface: "discussion-rail",
    chatRole: "narration",
    presenterFocus: "End on boundary and future layers without overclaiming an autonomous agent.",
  },
] as const satisfies readonly SceneCoherenceEntry[];

const beatContracts = {
  "thesis/title": { mode: "focal", primarySurface: "title-boundary", supportSurface: "none" },
  "thesis/substrate": { mode: "split", primarySurface: "opening-decomposition", supportSurface: "none" },
  "problem/direct-actions": { mode: "split", primarySurface: "tool-loop-transcript", supportSurface: "workflow-blueprint" },
  "problem/missing-contracts": { mode: "split", primarySurface: "workflow-blueprint", supportSurface: "tool-loop-transcript" },
  "architecture/client": { mode: "zoom", primarySurface: "interactive-architecture", supportSurface: "none" },
  "architecture/api": { mode: "zoom", primarySurface: "interactive-architecture", supportSurface: "none" },
  "architecture/runtime": { mode: "zoom", primarySurface: "interactive-architecture", supportSurface: "none" },
  "architecture/node-use": { mode: "zoom", primarySurface: "interactive-architecture", supportSurface: "evidence-receipt" },
  "authoring/discover": { mode: "evidence", primarySurface: "authoring-discovery", supportSurface: "authoring-loop" },
  "authoring/author": { mode: "evidence", primarySurface: "authoring-draft", supportSurface: "authoring-loop" },
  "authoring/diagnose": { mode: "evidence", primarySurface: "authoring-diagnostic", supportSurface: "authoring-loop" },
  "authoring/repair": { mode: "evidence", primarySurface: "authoring-repair", supportSurface: "authoring-loop" },
  "agent-handoff/request": { mode: "conversation", primarySurface: "prepared-conversation", supportSurface: "none" },
  "evaluation/cohort": { mode: "evidence", primarySurface: "evaluation-cohort", supportSurface: "none" },
  "evaluation/validity": { mode: "evidence", primarySurface: "evaluation-validity", supportSurface: "audit-reconciliation" },
  "evaluation/findings": { mode: "evidence", primarySurface: "evaluation-findings", supportSurface: "validity-boundary" },
  "conclusion/limits": { mode: "evidence", primarySurface: "contribution-boundary", supportSurface: "non-claims" },
  "conclusion/future": { mode: "evidence", primarySurface: "future-layers", supportSurface: "contribution-boundary" },
  "conclusion/conclusion": { mode: "focal", primarySurface: "contribution-statement", supportSurface: "evidence-attachment" },
  "conclusion/questions": { mode: "focal", primarySurface: "discussion-index", supportSurface: "none" },
} as const satisfies Record<string, Omit<SceneBeatVisualContract, "sceneId" | "beatId">>;

export const beatVisualContractFor = (
  sceneId: string,
  beatId: string,
): SceneBeatVisualContract => {
  const key = `${sceneId}/${beatId}`;
  const contract = beatContracts[key as keyof typeof beatContracts];
  if (!contract) throw new Error(`No visual contract for ${key}`);
  return { sceneId, beatId, ...contract };
};

export const coherenceForScene = (sceneId: string): SceneCoherenceEntry => {
  const entry = sceneCoherenceMatrix.find((candidate) => candidate.sceneId === sceneId);
  if (!entry) {
    throw new Error(`No presentation coherence entry for scene ${sceneId}`);
  }
  return entry;
};

export const demoSurfaceForBeat = (
  sceneId: string,
  beatId: string,
): { readonly primarySurface: string; readonly supportSurface: string } => {
  if (sceneId === "prepared-lifecycle") {
    return { primarySurface: "prepared-lifecycle", supportSurface: "none" };
  }
  if (sceneId === "run-from-deployment") {
    return {
      primarySurface: beatId === "operation" ? "run-operation" : "workflow-graph",
      supportSurface: beatId === "operation" ? "none" : "run-receipt",
    };
  }
  if (sceneId === "typed-human-boundary") {
    return {
      primarySurface: beatId === "interrupt" ? "interrupt-payload" : "interrupt-approval",
      supportSurface: "facts-only",
    };
  }
  if (sceneId === "resume-output-evidence") {
    if (beatId === "resume") return { primarySurface: "resume-decision", supportSurface: "output-summary" };
    if (beatId === "output") return { primarySurface: "workflow-output", supportSurface: "none" };
    if (beatId === "trace") return { primarySurface: "trace-evidence", supportSurface: "output-summary" };
    throw new Error(`Unknown beat ${beatId} for scene resume-output-evidence`);
  }
  return { primarySurface: "none", supportSurface: "none" };
};
