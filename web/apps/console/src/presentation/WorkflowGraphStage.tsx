import { m } from "motion/react";
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
  { id: "read_docs", label: "Read documents", detail: "5 selected", kind: "node", x: 9, y: 57 },
  { id: "build_report", label: "Build report", detail: "Markdown", kind: "node", x: 30, y: 35 },
  { id: "review_issues", label: "Issue review", detail: "Typed interrupt", kind: "interrupt", x: 52, y: 57 },
  { id: "create_issues", label: "Create issues", detail: "Selected only", kind: "node", x: 74, y: 35 },
  { id: "end_completed", label: "Completed", detail: "Persisted run", kind: "end", x: 92, y: 57 },
];

type PresentationEdge = readonly [from: string, to: string];

const presentationEdges: ReadonlyArray<PresentationEdge> = [
  ["read_docs", "build_report"],
  ["build_report", "review_issues"],
  ["review_issues", "create_issues"],
  ["create_issues", "end_completed"],
];

type NodeExecutionState = "completed" | "current" | "future";

type WorkflowGraphStageProps = {
  readonly execution: GraphExecutionPresentation;
  readonly selectedNodeId: string | null;
  readonly selectNode: (nodeId: string) => void;
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
}: WorkflowGraphStageProps) => (
  <div className="workflow-graph-stage" role="group" aria-label="workflow graph">
    <div className="workflow-graph-stage__legend" aria-hidden="true">
      <span><i data-state="completed" />Completed</span>
      <span><i data-state="current" />Current</span>
      <span><i data-state="interrupt" />Human boundary</span>
    </div>

    <svg className="workflow-graph-stage__connectors" aria-hidden="true">
      <defs>
        <marker id="workflow-arrow" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
          <polygon points="0 0, 8 3, 0 6" />
        </marker>
        <marker id="workflow-arrow-active" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
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
            markerEnd={active ? "url(#workflow-arrow-active)" : "url(#workflow-arrow)"}
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
