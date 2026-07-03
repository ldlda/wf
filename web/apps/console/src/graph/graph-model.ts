import dagre from "@dagrejs/dagre";

export type WorkflowGraphNodeKind =
  | "use"
  | "subgraph"
  | "condition"
  | "interrupt"
  | "foreach"
  | "join"
  | "end";

export type WorkflowGraphNodeData = {
  readonly nodeId: string;
  readonly kind: WorkflowGraphNodeKind;
  readonly label: string;
  readonly nodeRef: string | null;
  readonly raw: Readonly<Record<string, unknown>>;
  readonly onSelect?: (nodeId: string) => void;
};

export type WorkflowGraphNode = {
  readonly id: string;
  readonly data: WorkflowGraphNodeData;
  readonly position: { readonly x: number; readonly y: number };
};

export type WorkflowGraphEdge = {
  readonly id: string;
  readonly source: string;
  readonly target: string;
  readonly label: string;
};

export type WorkflowGraphModel = {
  readonly nodes: ReadonlyArray<WorkflowGraphNode>;
  readonly edges: ReadonlyArray<WorkflowGraphEdge>;
};

const NODE_WIDTH = 180;
const NODE_HEIGHT = 60;

const mapNodeKind = (type: string): WorkflowGraphNodeKind => {
  switch (type) {
    case "node":
      return "use";
    case "subgraph":
      return "subgraph";
    case "condition":
      return "condition";
    case "interrupt":
      return "interrupt";
    case "foreach":
      return "foreach";
    case "join":
      return "join";
    case "end":
      return "end";
    default:
      return "use";
  }
};

const buildLabel = (node: Record<string, unknown>): string => {
  const type = node.type as string;
  if (type === "end") return (node.outcome as string) ?? "End";
  if (type === "condition") return "Condition";
  if (type === "interrupt") return (node.kind as string) ?? "Interrupt";
  if (type === "foreach") return "For Each";
  if (type === "join") return "Join";
  if (type === "subgraph") {
    const workflowRef = node.workflow as string | undefined;
    if (workflowRef) {
      const parts = workflowRef.split(".");
      return parts[parts.length - 1] ?? workflowRef;
    }
    return "Subgraph";
  }
  const nodeRef = node.node as string | undefined;
  if (nodeRef) {
    const parts = nodeRef.split(".");
    return parts[parts.length - 1] ?? nodeRef;
  }
  return (node.id as string) ?? "Unknown";
};

export const buildWorkflowGraph = (
  plan: {
    nodes: ReadonlyArray<Record<string, unknown>>;
    edges: ReadonlyArray<Record<string, unknown>>;
  },
): WorkflowGraphModel => {
  const sortedNodes = [...plan.nodes].sort((a, b) =>
    String(a.id).localeCompare(String(b.id)),
  );

  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: "TB", nodesep: 50, ranksep: 80 });

  for (const node of sortedNodes) {
    g.setNode(String(node.id), { width: NODE_WIDTH, height: NODE_HEIGHT });
  }

  for (const edge of plan.edges) {
    g.setEdge(String(edge.from), String(edge.to));
  }

  dagre.layout(g);

  const nodes: WorkflowGraphNode[] = sortedNodes.map((node) => {
    const id = String(node.id);
    const pos = g.node(id);
    return {
      id,
      data: {
        nodeId: id,
        kind: mapNodeKind(node.type as string),
        label: buildLabel(node),
        nodeRef: (node.node as string | null) ?? null,
        raw: node as Record<string, unknown>,
      },
      position: { x: pos.x - NODE_WIDTH / 2, y: pos.y - NODE_HEIGHT / 2 },
    };
  });

  let edgeIndex = 0;
  const edges: WorkflowGraphEdge[] = plan.edges.map((edge) => {
    const source = String(edge.from);
    const target = String(edge.to);
    const label = String(edge.outcome ?? "");
    const id = `e-${source}-${target}-${edgeIndex++}`;
    return { id, source, target, label };
  });

  return { nodes, edges };
};
