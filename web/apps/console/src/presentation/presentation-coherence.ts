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
    return { primarySurface: "trace-evidence", supportSurface: "output-summary" };
  }
  return { primarySurface: "none", supportSurface: "none" };
};
