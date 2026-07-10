export type WorkflowToolName =
  | "inspectDeployment"
  | "startRun"
  | "resumeIssueReview"
  | "readRunTrace";

export type PresentationToolName =
  | "selectWorkflowNode"
  | "focusOperation"
  | "showTraceFrame"
  | "fetchData"
  | "transformPayload"
  | "writeOutput";

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
  startRun: {
    name: "startRun",
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
  showTraceFrame: {
    name: "showTraceFrame",
    kind: "presentation",
    description: "Focus a trace frame in the presentation.",
  },
  fetchData: {
    name: "fetchData",
    kind: "presentation",
    description: "Presentation-only placeholder for fetching data in a one-off tool loop.",
  },
  transformPayload: {
    name: "transformPayload",
    kind: "presentation",
    description: "Presentation-only placeholder for transforming data in a one-off tool loop.",
  },
  writeOutput: {
    name: "writeOutput",
    kind: "presentation",
    description: "Presentation-only placeholder for writing output in a one-off tool loop.",
  },
} satisfies Record<AgentToolName, AgentToolDescriptor>;

export const isAllowedAgentToolName = (name: string): name is AgentToolName =>
  Object.hasOwn(AGENT_TOOLS, name);
