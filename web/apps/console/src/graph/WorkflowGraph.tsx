import { useCallback, useMemo, type KeyboardEvent } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  Handle,
  Position,
  type Node,
  type Edge,
  type NodeTypes,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { WorkflowGraphModel, WorkflowGraphNodeData } from "./graph-model.js";

type WorkflowGraphProps = {
  readonly model: WorkflowGraphModel;
  readonly activeNodeId?: string | null;
  readonly activeEdgeId?: string | null;
  readonly onNodeSelect?: (nodeId: string) => void;
  readonly onEdgeSelect?: (edgeId: string) => void;
  readonly onCanvasSelect?: () => void;
};

const nodeColor = (data: WorkflowGraphNodeData): string => {
  switch (data.kind) {
    case "use":
      return "#3b82f6";
    case "condition":
      return "#f59e0b";
    case "interrupt":
      return "#ef4444";
    case "foreach":
      return "#8b5cf6";
    case "join":
      return "#10b981";
    case "end":
      return "#6b7280";
    default:
      return "#94a3b8";
  }
};

type RenderedNodeData = WorkflowGraphNodeData & {
  readonly direction: "TB" | "LR";
};

const CustomNode = ({ data, selected }: { data: RenderedNodeData; selected: boolean }) => {
  const isActive = data.isActive;
  const targetPosition = data.direction === "LR" ? Position.Left : Position.Top;
  const sourcePosition = data.direction === "LR" ? Position.Right : Position.Bottom;
  const handleKeyDown = (event: KeyboardEvent) => {
    if (event.key !== "Enter" && event.key !== " ") return;
    event.preventDefault();
    data.onSelect?.(data.nodeId);
  };
  return (
    <div
      role="button"
      tabIndex={0}
      onKeyDown={handleKeyDown}
      {...(data.contract
        ? { "aria-label": `${data.label} workflow contract${data.summary ? `, ${data.summary}` : ""}` }
        : {})}
      aria-pressed={selected}
      data-active={isActive}
      {...(data.contract ? { "data-contract": data.contract } : {})}
      data-node-id={data.nodeId}
      className={`graph-node graph-node--${data.kind} ${selected ? "graph-node--selected" : ""} ${isActive ? "graph-node--active" : ""}`}
      style={{ borderColor: nodeColor(data) }}
    >
      <Handle type="target" position={targetPosition} />
      <div className="graph-node__label">{data.label}</div>
      {data.nodeRef && (
        <div className="graph-node__ref">{data.nodeRef}</div>
      )}
      {data.detail && <div className="graph-node__detail">{data.detail}</div>}
      {data.summary && <div className="graph-node__summary">{data.summary}</div>}
      <Handle type="source" position={sourcePosition} />
    </div>
  );
};

const nodeTypes: NodeTypes = {
  custom: CustomNode,
};

export const WorkflowGraph = ({
  model,
  activeNodeId = null,
  activeEdgeId = null,
  onNodeSelect,
  onEdgeSelect,
  onCanvasSelect,
}: WorkflowGraphProps) => {
  const nodes: Node[] = useMemo(
    () =>
      model.nodes.map((n) => ({
        id: n.id,
        type: "custom",
        position: n.position,
        selected: activeNodeId === n.id,
        data: {
          ...n.data,
          direction: model.direction ?? "TB",
          isActive: activeNodeId === n.id,
          onSelect: onNodeSelect,
        },
      })),
    [model.direction, model.nodes, activeNodeId, onNodeSelect],
  );

  const edges: Edge[] = useMemo(
    () =>
      model.edges.map((e) => ({
        id: e.id,
        source: e.source,
        target: e.target,
        label: e.label,
        type: "default",
        className: `graph-edge--${e.kind ?? "route"}`,
        selected: activeEdgeId === e.id,
        selectable: e.kind !== "contract" && Boolean(onEdgeSelect),
      })),
    [activeEdgeId, model.edges, onEdgeSelect],
  );

  const handleNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      onNodeSelect?.(node.id);
    },
    [onNodeSelect],
  );

  const handleEdgeClick = useCallback(
    (_event: React.MouseEvent, edge: Edge) => {
      if (model.edges.find((candidate) => candidate.id === edge.id)?.kind === "contract") return;
      onEdgeSelect?.(edge.id);
    },
    [model.edges, onEdgeSelect],
  );

  if (model.nodes.length === 0) {
    return (
      <div className="workflow-graph workflow-graph--empty">
        No nodes in this workflow
      </div>
    );
  }

  return (
    <div
      className="workflow-graph"
      data-derived-connectors={model.edges.some((edge) => edge.kind === "contract")}
      data-testid="workflow-graph"
    >
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodeClick={handleNodeClick}
        onEdgeClick={handleEdgeClick}
        {...(onCanvasSelect
          ? { onPaneClick: () => onCanvasSelect() }
          : {})}
        fitView
        proOptions={{ hideAttribution: true }}
        nodesDraggable={true}
        nodesConnectable={true}
        elementsSelectable={Boolean(onNodeSelect || onEdgeSelect)}
      >
        <Background />
        <Controls />
      </ReactFlow>
    </div>
  );
};
