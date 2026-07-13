import { useCallback, useEffect, useMemo, type MouseEvent } from "react";
import {
  Background,
  Controls,
  Handle,
  Position,
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
  useNodesState,
  type Edge,
  type Node,
  type NodeProps,
  type NodeTypes,
  type ReactFlowInstance,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { CircleCheck, GitBranch, SquareFunction } from "lucide-react";
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
  readonly selectNode: (nodeId: string) => void;
  readonly positionX: number;
  readonly positionY: number;
};

const fullGraphLayout = {
  nodeWidth: 176,
  nodeHeight: 76,
  nodesep: 72,
  ranksep: 56,
} as const;

const compactGraphLayout = {
  nodeWidth: 132,
  nodeHeight: 64,
  nodesep: 42,
  ranksep: 52,
} as const;

const preparedRunPositions: Readonly<Record<string, { readonly x: number; readonly y: number }>> = {
  reset_board: { x: 0, y: 0 },
  read_docs: { x: 205, y: 0 },
  analyze: { x: 410, y: 0 },
  build_report: { x: 615, y: 0 },
  draft_issues: { x: 615, y: 110 },
  review_issues: { x: 820, y: 110 },
  create_issues: { x: 1025, y: 40 },
  finalise: { x: 1025, y: 150 },
  end_completed: { x: 1025, y: 260 },
  revision_requested: { x: 1025, y: 370 },
};

const edgeActive = (edge: { source: string; target: string }, execution: GraphExecutionPresentation): boolean =>
  execution.completedNodeIds.includes(edge.source)
  && (execution.completedNodeIds.includes(edge.target) || execution.currentNodeId === edge.target);

const PresentationFlowNode = ({ data }: NodeProps<Node<PresentationNodeData>>) => {
  const Icon = data.kind === "interrupt"
    ? GitBranch
    : data.kind === "end"
      ? CircleCheck
      : SquareFunction;

  return (
    <>
      <Handle type="target" position={Position.Left} />
      <button
        type="button"
        className="workflow-graph-stage__node"
        data-kind={data.kind}
        data-node-id={data.nodeId}
        data-position-x={data.positionX}
        data-position-y={data.positionY}
        aria-label={`workflow node: ${data.label}${data.detail ? `, ${data.detail}` : ""}`}
        title={data.nodeRef ?? undefined}
        onClick={(event) => {
          event.stopPropagation();
          data.selectNode(data.nodeId);
        }}
      >
        <span className="workflow-graph-stage__node-icon" aria-hidden="true"><Icon size={18} strokeWidth={1.8} /></span>
        <strong>{data.label}</strong>
        <small>{data.detail ?? data.nodeRef ?? "workflow step"}</small>
      </button>
      <Handle type="source" position={Position.Right} />
    </>
  );
};

const nodeTypes: NodeTypes = { presentation: PresentationFlowNode };

const graphFitOptions = { padding: 0.06, minZoom: 0.25, maxZoom: 1.2 } as const;

const WorkflowGraphStageInner = ({
  execution,
  selectNode,
  proof,
  variant = "full",
}: WorkflowGraphStageProps) => {
  const { fitView } = useReactFlow<Node<PresentationNodeData>, Edge>();
  const model = useMemo(() => {
    const generated = buildWorkflowGraph(presentationWorkflowPlan, {
      direction: "LR",
      // Keep Dagre's dimensions in lockstep with the CSS node boxes so React
      // Flow's measured handles stay attached when the graph is fit to view.
      ...(variant === "compact" ? compactGraphLayout : fullGraphLayout),
      label: (node) => {
        if (typeof node.label === "string") return node.label;
        if (node.id === "review_issues") return "Review issues";
        return undefined;
      },
    });

    if (variant === "compact") return generated;

    // This is a layout input, not a second renderer: React Flow still owns
    // handles, edges, pan, zoom, and the user's dragged positions.
    return {
      ...generated,
      nodes: generated.nodes.map((node) => ({
        ...node,
        position: preparedRunPositions[node.id] ?? node.position,
      })),
    };
  }, [variant]);

  const baseNodes: Node<PresentationNodeData>[] = useMemo(
    () => model.nodes.map((node) => ({
      id: node.id,
      type: "presentation",
      position: node.position,
      draggable: true,
      selectable: false,
      data: {
        ...node.data,
        selectNode,
        positionX: node.position.x,
        positionY: node.position.y,
      },
    })),
    [model.nodes, selectNode],
  );

  const [nodes, setNodes, onNodesChange] = useNodesState(baseNodes);

  useEffect(() => {
    setNodes(baseNodes);
  }, [baseNodes, setNodes]);

  useEffect(() => {
    // The presentation canvas can change aspect ratio without remounting the
    // graph. Refit after resize so the outcome branches stay on-screen.
    const refit = () => requestAnimationFrame(() => void fitView(graphFitOptions));
    window.addEventListener("resize", refit);
    return () => window.removeEventListener("resize", refit);
  }, [fitView]);

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

  const handleFlowInit = useCallback((instance: ReactFlowInstance<Node<PresentationNodeData>, Edge>) => {
    // React Flow's initial fit can run before custom node dimensions settle.
    // Refitting from onInit uses the initialized viewport, then one animation
    // frame lets measured node bounds replace the pre-measurement bounds.
    requestAnimationFrame(() => instance.fitView(graphFitOptions));
  }, []);

  return (
    <div
      className="workflow-graph-stage"
      role="group"
      aria-label="workflow graph"
      data-graph-variant={variant}
      data-graph-direction="horizontal"
      data-graph-layout="horizontal"
      data-graph-topology="prepared-run-branches"
      data-pan-zoom="enabled"
      data-node-drag="enabled"
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
        onNodesChange={onNodesChange}
        onInit={handleFlowInit}
        fitView
        fitViewOptions={graphFitOptions}
        minZoom={0.25}
        maxZoom={1.5}
        nodesDraggable
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
