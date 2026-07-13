import {
  Handle,
  Position,
  ReactFlow,
  ReactFlowProvider,
  type Edge,
  type Node,
  type NodeProps,
  type NodeTypes,
  type ReactFlowInstance,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import Dagre from "@dagrejs/dagre";
import { CircleStop, Database, SquareFunction } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { ReviewedAuthoringEvidence } from "./reviewed-authoring-evidence.js";

type WorkflowEvidence = Extract<
  ReviewedAuthoringEvidence,
  { readonly kind: "draft" | "diagnostic" | "repair" }
>;

type AuthoringWorkflowMode = "draft" | "diagnostic" | "repair";

type AuthoringNodeData = {
  readonly label: string;
  readonly role: "source" | "action" | "outcome";
};

type AuthoringWorkflowDiagramProps = {
  readonly mode: AuthoringWorkflowMode;
  readonly evidence: WorkflowEvidence;
};

const AuthoringFlowNode = ({ id, data }: NodeProps<Node<AuthoringNodeData>>) => {
  const Icon = data.role === "source" ? Database : data.role === "outcome" ? CircleStop : SquareFunction;
  return (
    <>
      {data.role !== "source" && <Handle type="target" position={Position.Left} />}
      <div
        className="authoring-workflow-diagram__node"
        data-authoring-node-id={id}
        data-node-role={data.role}
      >
        <Icon aria-hidden="true" />
        <strong>{data.label}</strong>
      </div>
      {data.role !== "outcome" && <Handle type="source" position={Position.Right} />}
    </>
  );
};

const nodeTypes: NodeTypes = { authoring: AuthoringFlowNode };

const NODE_WIDTH = 224;
const NODE_HEIGHT = 76;
const FIT_VIEW_OPTIONS = { padding: 0.16, minZoom: 0.55, maxZoom: 1.25, duration: 0 } as const;

const workflowNodeDefinitions: Omit<Node<AuthoringNodeData>, "position">[] = [
  {
    id: "read_documents",
    type: "authoring",
    style: { width: NODE_WIDTH },
    data: { label: "read_documents", role: "source" },
  },
  {
    id: "analyze",
    type: "authoring",
    style: { width: NODE_WIDTH },
    data: { label: "analyze", role: "action" },
  },
  {
    id: "__end__",
    type: "authoring",
    style: { width: NODE_WIDTH },
    data: { label: "END", role: "outcome" },
  },
];

const layoutWorkflowNodes = (): Node<AuthoringNodeData>[] => {
  const graph = new Dagre.graphlib.Graph();
  graph.setGraph({ rankdir: "LR", ranksep: 72, nodesep: 48, marginx: 0, marginy: 0 });
  graph.setDefaultEdgeLabel(() => ({}));
  for (const node of workflowNodeDefinitions) {
    graph.setNode(node.id, { width: NODE_WIDTH, height: NODE_HEIGHT });
  }
  graph.setEdge("read_documents", "analyze", { width: 28, height: 22 });
  // Reserve the widest label once so all three beats retain identical node positions.
  graph.setEdge("analyze", "__end__", { width: 154, height: 24 });
  Dagre.layout(graph);
  return workflowNodeDefinitions.map((node) => {
    const position = graph.node(node.id);
    return {
      ...node,
      position: {
        x: position.x - NODE_WIDTH / 2,
        y: position.y - NODE_HEIGHT / 2,
      },
    };
  });
};

const workflowNodes = layoutWorkflowNodes();

const edgesForMode = (mode: AuthoringWorkflowMode): Edge[] => [
  {
    id: "read_documents.ok",
    source: "read_documents",
    target: "analyze",
    label: "ok",
    className: "authoring-workflow-diagram__edge",
  },
  {
    id: "analyze.ok",
    source: "analyze",
    target: "__end__",
    label: mode === "diagnostic" ? "Missing route · ok" : mode === "repair" ? "Route restored · ok" : "ok",
    className: `authoring-workflow-diagram__edge${mode === "diagnostic" ? " authoring-workflow-diagram__edge--missing" : ""}${mode === "repair" ? " authoring-workflow-diagram__edge--restored" : ""}`,
  },
];

const accessibleLabelForMode = (mode: AuthoringWorkflowMode): string => {
  if (mode === "diagnostic") return "Authoring workflow diagram: analyze ok route is missing";
  if (mode === "repair") return "Authoring workflow diagram: analyze ok route restored";
  return "Authoring workflow diagram: valid draft routes";
};

const AuthoringWorkflowDiagramInner = ({ mode }: AuthoringWorkflowDiagramProps) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [flow, setFlow] = useState<ReactFlowInstance<Node<AuthoringNodeData>, Edge>>();

  useEffect(() => {
    if (!flow) return undefined;
    let frame = window.requestAnimationFrame(() => void flow.fitView(FIT_VIEW_OPTIONS));
    // Scene columns resize without remounting React Flow, so fit the settled box again.
    const observer = typeof ResizeObserver === "undefined" || !containerRef.current
      ? undefined
      : new ResizeObserver(() => {
          window.cancelAnimationFrame(frame);
          frame = window.requestAnimationFrame(() => void flow.fitView(FIT_VIEW_OPTIONS));
        });
    if (containerRef.current) observer?.observe(containerRef.current);
    return () => {
      window.cancelAnimationFrame(frame);
      observer?.disconnect();
    };
  }, [flow, mode]);

  return (
    <div
      ref={containerRef}
      className="authoring-workflow-diagram"
      role="img"
      aria-label={accessibleLabelForMode(mode)}
      data-workflow-mode={mode}
    >
    <ReactFlow
      nodes={workflowNodes}
      edges={edgesForMode(mode)}
      nodeTypes={nodeTypes}
      onInit={setFlow}
      fitView
      fitViewOptions={FIT_VIEW_OPTIONS}
      nodesDraggable={false}
      nodesConnectable={false}
      elementsSelectable={false}
      panOnDrag={false}
      zoomOnScroll={false}
      zoomOnPinch={false}
      preventScrolling={false}
      proOptions={{ hideAttribution: true }}
    />
  </div>
  );
};

/** Renders the same authored workflow while its route state changes between beats. */
export const AuthoringWorkflowDiagram = (props: AuthoringWorkflowDiagramProps) => (
  <ReactFlowProvider>
    <AuthoringWorkflowDiagramInner {...props} />
  </ReactFlowProvider>
);
