export type BeatId =
  | "intro"
  | "chat-request"
  | "tool-call-start"
  | "graph-reveal"
  | "interrupt-approval"
  | "resume-output"
  | "trace-evidence"
  | "boundary-wrap";

export type PresentationBeat = {
  readonly id: BeatId;
  readonly title: string;
  readonly caption: string;
  readonly lifecycleStep: string;
};

export const presentationBeats: readonly PresentationBeat[] = [
  {
    id: "intro",
    title: "Planner vs runtime",
    caption: "External planners propose actions; the workflow runtime owns deterministic execution.",
    lifecycleStep: "Frame",
  },
  {
    id: "chat-request",
    title: "Operator request",
    caption: "The operator asks for a thesis readiness report through a chat-like product surface.",
    lifecycleStep: "Request",
  },
  {
    id: "tool-call-start",
    title: "Product operation",
    caption: "The assistant invokes a prepared workflow operation instead of inventing ad-hoc script state.",
    lifecycleStep: "Run",
  },
  {
    id: "graph-reveal",
    title: "Workflow graph",
    caption: "The graph shows reusable structure, not a one-off tool-calling transcript.",
    lifecycleStep: "Graph",
  },
  {
    id: "interrupt-approval",
    title: "Typed interrupt",
    caption: "Human approval is a typed workflow boundary with explicit resume outcomes.",
    lifecycleStep: "Interrupt",
  },
  {
    id: "resume-output",
    title: "Resume output",
    caption: "Resuming commits the approved branch and produces report and issue-board output.",
    lifecycleStep: "Resume",
  },
  {
    id: "trace-evidence",
    title: "Trace evidence",
    caption: "Run records and trace frames make the execution inspectable after the fact.",
    lifecycleStep: "Trace",
  },
  {
    id: "boundary-wrap",
    title: "Boundary",
    caption: "lda.chat is the workflow substrate that an external or scripted agent can operate.",
    lifecycleStep: "Boundary",
  },
] as const;

const beatIds = new Set<BeatId>(presentationBeats.map((beat) => beat.id));

export const beatFromHash = (hash: string): BeatId => {
  const id = hash.replace(/^#/, "") as BeatId;
  return beatIds.has(id) ? id : "intro";
};

export const hashForBeat = (beat: BeatId): string => `#${beat}`;
