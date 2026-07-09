import { useCallback, useMemo, type MouseEvent } from "react";
import {
  Background,
  Controls,
  Handle,
  Position,
  ReactFlow,
  ReactFlowProvider,
  type Edge,
  type Node,
  type NodeProps,
  type NodeTypes,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { GraphExecutionPresentation } from "./demo-workflow-model.js";
import { presentationEdges, presentationNodes, type PresentationHandle, type PresentationNode } from "./workflow-graph-data.js";

type NodeExecutionState = "completed" | "current" | "future";

type PresentationNodeData = {
  readonly node: PresentationNode;
  readonly executionState: NodeExecutionState;
  readonly currentInterrupt: boolean;
  readonly selected: boolean;
  readonly selectNode: (nodeId: string) => void;
};

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

const stateLabelFor = (
  executionState: NodeExecutionState,
  currentInterrupt: boolean,
): string => {
  if (currentInterrupt) return "Current interrupt";
  if (executionState === "current") return "Current";
  if (executionState === "completed") return "Completed";
  return "Queued";
};

const edgeActive = (
  fromId: string,
  toId: string,
  execution: GraphExecutionPresentation,
): boolean =>
  execution.completedNodeIds.includes(fromId)
  && (execution.completedNodeIds.includes(toId) || execution.currentNodeId === toId);

const handlePositionFor = (handle: PresentationHandle): Position => {
  if (handle === "left") return Position.Left;
  if (handle === "right") return Position.Right;
  if (handle === "top") return Position.Top;
  return Position.Bottom;
};

const PresentationFlowNode = ({ data }: NodeProps<Node<PresentationNodeData>>) => {
  const { node, executionState, currentInterrupt, selected, selectNode } = data;
  const stateLabel = stateLabelFor(executionState, currentInterrupt);
  return (
    <>
      {(["left", "top"] as const).map((handle) => (
        <Handle key={`target-${handle}`} id={handle} type="target" position={handlePositionFor(handle)} />
      ))}
      <button
        type="button"
        className="workflow-graph-stage__node"
        data-kind={node.kind}
        data-execution-state={executionState}
        data-current-interrupt={currentInterrupt}
        data-selected={selected}
        aria-pressed={selected}
        aria-label={`${node.label}, ${stateLabel}`}
        onClick={(event) => {
          event.stopPropagation();
          selectNode(node.id);
        }}
      >
        <span className="workflow-graph-stage__node-state">{stateLabel}</span>
        <strong>{node.label}</strong>
        <small>{node.detail}</small>
      </button>
      {(["right", "bottom"] as const).map((handle) => (
        <Handle key={`source-${handle}`} id={handle} type="source" position={handlePositionFor(handle)} />
      ))}
    </>
  );
};

const nodeTypes: NodeTypes = {
  presentation: PresentationFlowNode,
};

const WorkflowGraphStageInner = ({
  execution,
  selectedNodeId,
  selectNode,
  proof,
  variant = "full",
}: WorkflowGraphStageProps) => {
  const nodes: Node<PresentationNodeData>[] = useMemo(
    () =>
      presentationNodes.map((node) => {
        const executionState = executionStateForNode(node.id, execution);
        const currentInterrupt = executionState === "current" && node.kind === "interrupt";
        return {
          id: node.id,
          type: "presentation",
          position: { x: node.x, y: node.y },
          draggable: false,
          selectable: false,
          data: {
            node,
            executionState,
            currentInterrupt,
            selected: selectedNodeId === node.id,
            selectNode,
          },
        };
      }),
    [execution, selectedNodeId, selectNode],
  );

  const edges: Edge[] = useMemo(
    () =>
      presentationEdges.map((transition, index) => {
        requireNode(transition.from);
        requireNode(transition.to);
        const active = edgeActive(transition.from, transition.to, execution);
        return {
          id: `presentation-edge-${index}-${transition.from}-${transition.to}`,
          source: transition.from,
          target: transition.to,
          sourceHandle: transition.fromHandle ?? "right",
          targetHandle: transition.toHandle ?? "left",
          type: "smoothstep",
          animated: active,
          focusable: false,
          selectable: false,
          data: { active },
          className: active
            ? "workflow-graph-stage__edge workflow-graph-stage__edge--active"
            : "workflow-graph-stage__edge",
        };
      }),
    [execution],
  );

  const handleNodeClick = useCallback((_: MouseEvent, node: Node) => selectNode(node.id), [selectNode]);

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
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodeClick={handleNodeClick}
        fitView
        fitViewOptions={{ padding: variant === "compact" ? 0.04 : 0.08 }}
        minZoom={0.25}
        maxZoom={1.5}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
        edgesFocusable={false}
        panOnDrag
        zoomOnScroll
        zoomOnPinch
        proOptions={{ hideAttribution: true }}
      >
        <Background gap={28} color="oklch(0.35 0.03 250 / 0.22)" />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
};

export const WorkflowGraphStage = (props: WorkflowGraphStageProps) => (
  <ReactFlowProvider>
    <WorkflowGraphStageInner {...props} />
  </ReactFlowProvider>
);
