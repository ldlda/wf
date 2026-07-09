import { m } from "motion/react";
import { useId } from "react";
import type { GraphExecutionPresentation } from "./demo-workflow-model.js";

export type PresentationNode = {
  readonly id: string;
  readonly label: string;
  readonly detail: string;
  readonly kind: "node" | "interrupt" | "end";
  readonly x: number;
  readonly y: number;
};

export const presentationNodes: ReadonlyArray<PresentationNode> = [
  { id: "read_docs", label: "Read docs", detail: "document source", kind: "node", x: 8, y: 54 },
  { id: "reset_board", label: "Reset board", detail: "issue board", kind: "node", x: 20, y: 34 },
  { id: "analyze", label: "Analyze", detail: "report source", kind: "node", x: 32, y: 54 },
  { id: "build_report", label: "Build report", detail: "markdown", kind: "node", x: 44, y: 34 },
  { id: "draft_issues", label: "Draft issues", detail: "proposals", kind: "node", x: 56, y: 54 },
  { id: "review_issues", label: "Issue review", detail: "typed interrupt", kind: "interrupt", x: 68, y: 34 },
  { id: "create_issues", label: "Create issues", detail: "selected only", kind: "node", x: 80, y: 54 },
  { id: "finalise", label: "Finalise", detail: "state output", kind: "node", x: 92, y: 34 },
  { id: "revision_requested", label: "Revision requested", detail: "operator branch", kind: "end", x: 68, y: 78 },
  { id: "end_completed", label: "Completed", detail: "persisted run", kind: "end", x: 92, y: 72 },
  { id: "end_cancelled", label: "Cancelled", detail: "no submitted output", kind: "end", x: 80, y: 78 },
];

type PresentationEdge = readonly [from: string, to: string];

const presentationEdges: ReadonlyArray<PresentationEdge> = [
  ["read_docs", "reset_board"],
  ["reset_board", "analyze"],
  ["analyze", "build_report"],
  ["build_report", "draft_issues"],
  ["draft_issues", "review_issues"],
  ["review_issues", "create_issues"],
  ["review_issues", "revision_requested"],
  ["review_issues", "end_cancelled"],
  ["create_issues", "finalise"],
  ["finalise", "end_completed"],
];

type NodeExecutionState = "completed" | "current" | "future";

export type WorkflowGraphProof = {
  readonly runId: string | null;
  readonly planLabel: string;
  readonly traceLabel: string;
  readonly evidenceLabel: string;
};

type WorkflowGraphStageProps = {
  readonly execution: GraphExecutionPresentation;
  readonly selectedNodeId: string | null;
  readonly selectNode: (nodeId: string) => void;
  readonly proof?: WorkflowGraphProof;
  readonly variant?: "full" | "compact";
};

const executionStateForNode = (
  nodeId: string,
  execution: GraphExecutionPresentation,
): NodeExecutionState => {
  if (execution.currentNodeId === nodeId) return "current";
  if (execution.completedNodeIds.includes(nodeId)) return "completed";
  return "future";
};

const requireNode = (nodeId: string): PresentationNode => {
  const node = presentationNodes.find((candidate) => candidate.id === nodeId);
  if (!node) throw new Error(`presentation edge references unknown node ${nodeId}`);
  return node;
};

export const WorkflowGraphStage = ({
  execution,
  selectedNodeId,
  selectNode,
  proof,
  variant = "full",
}: WorkflowGraphStageProps) => {
  const markerPrefix = useId().replaceAll(":", "");
  const arrowMarkerId = `${markerPrefix}-workflow-arrow`;
  const activeArrowMarkerId = `${markerPrefix}-workflow-arrow-active`;

  return (
    <div className="workflow-graph-stage" role="group" aria-label="workflow graph" data-graph-variant={variant}>
    <div className="workflow-graph-stage__legend" aria-hidden="true">
      <span><i data-state="completed" />Completed</span>
      <span><i data-state="current" />Current</span>
      <span><i data-state="interrupt" />Human boundary</span>
    </div>

    {/* Compact mode is used beside interrupt contracts; proof chips would
        compete with the contract and outcome panel in that narrow layout. */}
    {variant === "full" && proof && (
      <div className="workflow-graph-stage__proof" aria-label="workflow graph proof">
        <span><b>Run</b><code>{proof.runId ?? "run unavailable"}</code></span>
        <span><b>Plan</b>{proof.planLabel}</span>
        <span><b>Trace</b>{proof.traceLabel}</span>
        <span><b>Evidence</b>{proof.evidenceLabel}</span>
      </div>
    )}

    <svg className="workflow-graph-stage__connectors" aria-hidden="true">
      <defs>
        <marker className="workflow-graph-stage__arrow-marker" id={arrowMarkerId} markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
          <polygon points="0 0, 8 3, 0 6" />
        </marker>
        <marker className="workflow-graph-stage__arrow-marker--active" id={activeArrowMarkerId} markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
          <polygon points="0 0, 8 3, 0 6" />
        </marker>
      </defs>
      {presentationEdges.map(([fromId, toId]) => {
        const from = requireNode(fromId);
        const to = requireNode(toId);
        const active = execution.completedNodeIds.includes(from.id);
        return (
          <line
            key={`${fromId}-${toId}`}
            data-testid="workflow-connector"
            data-active={active}
            x1={`${from.x}%`}
            y1={`${from.y}%`}
            x2={`${to.x}%`}
            y2={`${to.y}%`}
            markerEnd={active ? `url(#${activeArrowMarkerId})` : `url(#${arrowMarkerId})`}
          />
        );
      })}
    </svg>

    {presentationNodes.map((node, index) => {
      const executionState = executionStateForNode(node.id, execution);
      const currentInterrupt = executionState === "current" && node.kind === "interrupt";
      const stateLabel = currentInterrupt
        ? "Current interrupt"
        : executionState === "current"
          ? "Current"
          : executionState === "completed"
            ? "Completed"
            : "Queued";
      return (
        <m.div
          key={node.id}
          className="workflow-graph-stage__node-slot"
          style={{ left: `${node.x}%`, top: `${node.y}%` }}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.2, delay: index * 0.025 }}
        >
          <button
            type="button"
            className="workflow-graph-stage__node"
            data-kind={node.kind}
            data-execution-state={executionState}
            data-current-interrupt={currentInterrupt}
            data-selected={selectedNodeId === node.id}
            aria-pressed={selectedNodeId === node.id}
            aria-label={`${node.label}, ${stateLabel}`}
            onClick={() => selectNode(node.id)}
          >
            <span className="workflow-graph-stage__node-state">{stateLabel}</span>
            <strong>{node.label}</strong>
            <small>{node.detail}</small>
          </button>
        </m.div>
      );
    })}
    </div>
  );
};
