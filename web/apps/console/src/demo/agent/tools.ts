export type WorkflowToolName =
  | "inspectDeployment"
  | "startPreparedReportRun"
  | "resumeIssueReview"
  | "readRunTrace";

export type PresentationToolName =
  | "selectWorkflowNode"
  | "focusOperation"
  | "openEvidence"
  | "showTraceFrame"
  | "setBeat";

export type AgentToolName = WorkflowToolName | PresentationToolName;

export type AgentToolDescriptor = {
  readonly name: AgentToolName;
  readonly kind: "workflow" | "presentation";
  readonly description: string;
};

export const AGENT_TOOLS = {
  inspectDeployment: {
    name: "inspectDeployment",
    kind: "workflow",
    description: "Inspect the prepared report deployment.",
  },
  startPreparedReportRun: {
    name: "startPreparedReportRun",
    kind: "workflow",
    description: "Start the prepared report workflow run.",
  },
  resumeIssueReview: {
    name: "resumeIssueReview",
    kind: "workflow",
    description: "Resume the typed issue-review interrupt.",
  },
  readRunTrace: {
    name: "readRunTrace",
    kind: "workflow",
    description: "Read trace frames for the completed report run.",
  },
  selectWorkflowNode: {
    name: "selectWorkflowNode",
    kind: "presentation",
    description: "Focus a workflow graph node in the presentation.",
  },
  focusOperation: {
    name: "focusOperation",
    kind: "presentation",
    description: "Focus an operation event in the presentation.",
  },
  openEvidence: {
    name: "openEvidence",
    kind: "presentation",
    description: "Open evidence for an operation event.",
  },
  showTraceFrame: {
    name: "showTraceFrame",
    kind: "presentation",
    description: "Focus a trace frame in the presentation.",
  },
  setBeat: {
    name: "setBeat",
    kind: "presentation",
    description: "Move the presentation to a named beat.",
  },
} satisfies Record<AgentToolName, AgentToolDescriptor>;

export const isAllowedAgentToolName = (name: string): name is AgentToolName =>
  Object.hasOwn(AGENT_TOOLS, name);
