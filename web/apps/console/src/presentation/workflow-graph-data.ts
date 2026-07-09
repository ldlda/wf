export type PresentationNode = {
  readonly id: string;
  readonly label: string;
  readonly detail: string;
  readonly kind: "node" | "interrupt" | "end";
  readonly x: number;
  readonly y: number;
};

export const presentationNodes: ReadonlyArray<PresentationNode> = [
  { id: "read_docs", label: "Read docs", detail: "document source", kind: "node", x: 0, y: 120 },
  { id: "reset_board", label: "Reset board", detail: "issue board", kind: "node", x: 190, y: 120 },
  { id: "analyze", label: "Analyze", detail: "report source", kind: "node", x: 380, y: 120 },
  { id: "build_report", label: "Build report", detail: "markdown", kind: "node", x: 570, y: 120 },
  { id: "draft_issues", label: "Draft issues", detail: "proposals", kind: "node", x: 760, y: 120 },
  { id: "review_issues", label: "Issue review", detail: "typed interrupt", kind: "interrupt", x: 950, y: 120 },
  { id: "create_issues", label: "Create issues", detail: "selected only", kind: "node", x: 1140, y: 120 },
  { id: "finalise", label: "Finalise", detail: "state output", kind: "node", x: 1330, y: 120 },
  { id: "end_completed", label: "Completed", detail: "persisted run", kind: "end", x: 1520, y: 120 },
  { id: "revision_requested", label: "Revision requested", detail: "operator branch", kind: "end", x: 950, y: 300 },
];

export type PresentationHandle = "left" | "right" | "top" | "bottom";

export type PresentationEdge = {
  readonly from: string;
  readonly to: string;
  readonly fromHandle?: PresentationHandle;
  readonly toHandle?: PresentationHandle;
};

const mainEdge = (from: string, to: string): PresentationEdge => ({
  from,
  to,
  fromHandle: "right",
  toHandle: "left",
});

export const presentationEdges: ReadonlyArray<PresentationEdge> = [
  mainEdge("read_docs", "reset_board"),
  mainEdge("reset_board", "analyze"),
  mainEdge("analyze", "build_report"),
  mainEdge("build_report", "draft_issues"),
  mainEdge("draft_issues", "review_issues"),
  mainEdge("review_issues", "create_issues"),
  mainEdge("create_issues", "finalise"),
  mainEdge("finalise", "end_completed"),
  { from: "review_issues", to: "revision_requested", fromHandle: "bottom", toHandle: "top" },
];
