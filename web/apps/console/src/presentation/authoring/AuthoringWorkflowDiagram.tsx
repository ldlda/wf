import {
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
import { CircleStop, Database, SquareFunction, TriangleAlert } from "lucide-react";
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

// Stable positions make Draft -> Diagnose -> Repair read as one changing object.
const workflowNodes: Node<AuthoringNodeData>[] = [
  {
    id: "read_documents",
    type: "authoring",
    position: { x: 0, y: 60 },
    data: { label: "read_documents", role: "source" },
  },
  {
    id: "analyze",
    type: "authoring",
    position: { x: 310, y: 60 },
    data: { label: "analyze", role: "action" },
  },
  {
    id: "__end__",
    type: "authoring",
    position: { x: 620, y: 60 },
    data: { label: "END", role: "outcome" },
  },
];

const edgesForMode = (mode: AuthoringWorkflowMode): Edge[] => [
  {
    id: "read_documents.ok",
    source: "read_documents",
    target: "analyze",
    label: "ok",
    className: "authoring-workflow-diagram__edge",
  },
  ...(mode === "diagnostic"
    ? []
    : [
        {
          id: "analyze.ok",
          source: "analyze",
          target: "__end__",
          label: mode === "repair" ? "restored · ok" : "ok",
          animated: mode === "repair",
          className: `authoring-workflow-diagram__edge${mode === "repair" ? " authoring-workflow-diagram__edge--restored" : ""}`,
        },
      ]),
];

const accessibleLabelForMode = (mode: AuthoringWorkflowMode): string => {
  if (mode === "diagnostic") return "Authoring workflow diagram: analyze ok route is missing";
  if (mode === "repair") return "Authoring workflow diagram: analyze ok route restored";
  return "Authoring workflow diagram: valid draft routes";
};

const AuthoringWorkflowDiagramInner = ({ mode }: AuthoringWorkflowDiagramProps) => (
  <div
    className="authoring-workflow-diagram"
    role="img"
    aria-label={accessibleLabelForMode(mode)}
    data-workflow-mode={mode}
  >
    <ReactFlow
      nodes={workflowNodes}
      edges={edgesForMode(mode)}
      nodeTypes={nodeTypes}
      fitView
      fitViewOptions={{ padding: 0.16, minZoom: 0.7, maxZoom: 1.25 }}
      nodesDraggable={false}
      nodesConnectable={false}
      elementsSelectable={false}
      panOnDrag={false}
      zoomOnScroll={false}
      zoomOnPinch={false}
      preventScrolling={false}
      proOptions={{ hideAttribution: true }}
    />
    <div className="authoring-workflow-diagram__route-state" aria-hidden="true">
      {mode === "diagnostic" ? (
        <span className="authoring-workflow-diagram__missing-route">
          <TriangleAlert />
          <strong>Missing route</strong>
          <small>analyze · ok</small>
        </span>
      ) : (
        <span
          data-authoring-edge-id="analyze.ok"
          data-route-state={mode === "repair" ? "restored" : "present"}
        >
          {mode === "repair" ? "Route restored" : "Complete route"}
        </span>
      )}
    </div>
  </div>
);

/** Renders the same authored workflow while its route state changes between beats. */
export const AuthoringWorkflowDiagram = (props: AuthoringWorkflowDiagramProps) => (
  <ReactFlowProvider>
    <AuthoringWorkflowDiagramInner {...props} />
  </ReactFlowProvider>
);
