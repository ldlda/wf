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
import { buildWorkflowGraph, type WorkflowGraphNodeData } from "../graph/graph-model.js";
import type { GraphExecutionPresentation } from "./demo-workflow-model.js";
import { presentationWorkflowPlan } from "./workflow-graph-data.js";

export type WorkflowGraphProof = {
  readonly runId: string | null;
  readonly evidenceLabel: string;
};

type WorkflowGraphStageProps = {
  readonly execution: GraphExecutionPresentation;
  readonly selectedNodeId: string | null;
  readonly selectNode: (nodeId: string) => void;
  readonly proof?: WorkflowGraphProof;
  readonly variant?: "full" | "compact";
};

type PresentationNodeData = WorkflowGraphNodeData & {
  readonly selected: boolean;
  readonly selectNode: (nodeId: string) => void;
};

const edgeActive = (edge: { source: string; target: string }, execution: GraphExecutionPresentation): boolean =>
  execution.completedNodeIds.includes(edge.source)
  && (execution.completedNodeIds.includes(edge.target) || execution.currentNodeId === edge.target);

const PresentationFlowNode = ({ data }: NodeProps<Node<PresentationNodeData>>) => (
  <>
    <Handle type="target" position={Position.Left} />
    <button
      type="button"
      className="workflow-graph-stage__node"
      data-kind={data.kind}
      data-selected={data.selected}
      aria-pressed={data.selected}
      aria-label={`${data.label}${data.detail ? `, ${data.detail}` : ""}`}
      title={data.nodeRef ?? undefined}
      onClick={(event) => {
        event.stopPropagation();
        data.selectNode(data.nodeId);
      }}
    >
      <strong>{data.label}</strong>
      <small>{data.detail ?? data.nodeRef ?? "workflow step"}</small>
    </button>
    <Handle type="source" position={Position.Right} />
  </>
);

const nodeTypes: NodeTypes = { presentation: PresentationFlowNode };

const WorkflowGraphStageInner = ({
  execution,
  selectedNodeId,
  selectNode,
  proof,
  variant = "full",
}: WorkflowGraphStageProps) => {
  const model = useMemo(
    () => buildWorkflowGraph(presentationWorkflowPlan, {
      direction: "LR",
      nodeWidth: 150,
      nodeHeight: 64,
      nodesep: 35,
      ranksep: 80,
      label: (node) => {
        if (typeof node.label === "string") return node.label;
        if (node.id === "review_issues") return "Review issues";
        return undefined;
      },
    }),
    [],
  );

  const nodes: Node<PresentationNodeData>[] = useMemo(
    () => model.nodes.map((node) => ({
      id: node.id,
      type: "presentation",
      position: node.position,
      draggable: false,
      selectable: false,
      data: {
        ...node.data,
        selected: selectedNodeId === node.id,
        selectNode,
      },
    })),
    [model.nodes, selectedNodeId, selectNode],
  );

  const edges: Edge[] = useMemo(
    () => model.edges.map((edge) => {
      const active = edgeActive(edge, execution);
      return {
        id: edge.id,
        source: edge.source,
        target: edge.target,
        label: edge.label,
        type: "default",
        animated: active,
        focusable: false,
        selectable: false,
        className: active
          ? "workflow-graph-stage__edge workflow-graph-stage__edge--active"
          : "workflow-graph-stage__edge",
      };
    }),
    [model.edges, execution],
  );

  const handleNodeClick = useCallback((_: MouseEvent, node: Node) => selectNode(node.id), [selectNode]);

  return (
    <div
      className="workflow-graph-stage"
      role="group"
      aria-label="workflow graph"
      data-graph-variant={variant}
      data-graph-direction="horizontal"
    >
      <div className="workflow-graph-stage__legend" aria-label="workflow graph node types">
        <span data-kind="use"><i aria-hidden="true" />Action</span>
        <span data-kind="interrupt"><i aria-hidden="true" />Human boundary</span>
        <span data-kind="end"><i aria-hidden="true" />Outcome</span>
      </div>
      {variant === "full" && proof && (
        <div className="workflow-graph-stage__proof" aria-label="workflow graph proof">
          <span><b>Run</b><code>{proof.runId ?? "run unavailable"}</code></span>
          <span><b>Evidence</b>{proof.evidenceLabel}</span>
        </div>
      )}
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodeClick={handleNodeClick}
        fitView
        fitViewOptions={{ padding: 0.02, minZoom: 0.5, maxZoom: 1 }}
        minZoom={0.25}
        maxZoom={1.5}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
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
