import { useCallback, useMemo } from "react";
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
  readonly onNodeSelect?: (nodeId: string) => void;
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

const CustomNode = ({ data, selected }: { data: WorkflowGraphNodeData; selected: boolean }) => {
  const isActive = (data as WorkflowGraphNodeData & { isActive?: boolean }).isActive;
  return (
    <div
      role="button"
      tabIndex={0}
      data-active={isActive}
      data-node-id={data.nodeId}
      className={`graph-node graph-node--${data.kind} ${selected ? "graph-node--selected" : ""} ${isActive ? "graph-node--active" : ""}`}
      style={{ borderColor: nodeColor(data) }}
    >
      <Handle type="target" position={Position.Top} />
      <div className="graph-node__label">{data.label}</div>
      {data.nodeRef && (
        <div className="graph-node__ref">{data.nodeRef}</div>
      )}
      <Handle type="source" position={Position.Bottom} />
    </div>
  );
};

const nodeTypes: NodeTypes = {
  custom: CustomNode,
};

export const WorkflowGraph = ({ model, activeNodeId = null, onNodeSelect }: WorkflowGraphProps) => {
  const nodes: Node[] = useMemo(
    () =>
      model.nodes.map((n) => ({
        id: n.id,
        type: "custom",
        position: n.position,
        data: { ...n.data, isActive: activeNodeId === n.id },
      })),
    [model.nodes, activeNodeId],
  );

  const edges: Edge[] = useMemo(
    () =>
      model.edges.map((e) => ({
        id: e.id,
        source: e.source,
        target: e.target,
        label: e.label,
        type: "default",
      })),
    [model.edges],
  );

  const handleNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      onNodeSelect?.(node.id);
    },
    [onNodeSelect],
  );

  if (model.nodes.length === 0) {
    return (
      <div className="workflow-graph workflow-graph--empty">
        No nodes in this workflow
      </div>
    );
  }

  return (
    <div className="workflow-graph" data-testid="workflow-graph">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodeClick={handleNodeClick}
        fitView
        proOptions={{ hideAttribution: true }}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
      >
        <Background />
        <Controls />
      </ReactFlow>
    </div>
  );
};
