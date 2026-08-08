import dagre from "@dagrejs/dagre";

export type WorkflowGraphNodeKind =
  | "use"
  | "subgraph"
  | "condition"
  | "interrupt"
  | "foreach"
  | "join"
  | "end"
  | "unsupported";

export type WorkflowGraphNodeData = {
  readonly nodeId: string;
  readonly kind: WorkflowGraphNodeKind;
  readonly label: string;
  readonly detail?: string | null;
  readonly nodeRef: string | null;
  readonly raw: Readonly<Record<string, unknown>>;
  readonly onSelect?: (nodeId: string) => void;
  readonly isActive?: boolean;
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

export type WorkflowGraphLayoutOptions = {
  readonly direction?: "TB" | "LR";
  readonly nodeWidth?: number;
  readonly nodeHeight?: number;
  readonly nodesep?: number;
  readonly ranksep?: number;
  readonly label?: (node: Readonly<Record<string, unknown>>) => string | undefined;
};

const DEFAULT_LAYOUT: Required<Omit<WorkflowGraphLayoutOptions, "label">> = {
  direction: "TB",
  nodeWidth: 180,
  nodeHeight: 60,
  nodesep: 50,
  ranksep: 80,
};

const mapNodeKind = (type: unknown): WorkflowGraphNodeKind => {
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
      return "unsupported";
  }
};

const buildLabel = (
  node: Record<string, unknown>,
  labelOverride?: WorkflowGraphLayoutOptions["label"],
): string => {
  const overriddenLabel = labelOverride?.(node);
  if (overriddenLabel) return overriddenLabel;
  const type = typeof node.type === "string" ? node.type : "";
  if (type === "end") {
    return typeof node.outcome === "string" ? node.outcome : "End";
  }
  if (type === "condition") return "Condition";
  if (type === "interrupt") {
    return typeof node.kind === "string" ? node.kind : "Interrupt";
  }
  if (type === "foreach") return "For Each";
  if (type === "join") return "Join";
  if (type === "subgraph") {
    const workflowRef = typeof node.workflow === "string" ? node.workflow : undefined;
    if (workflowRef) {
      const parts = workflowRef.split(".");
      return parts[parts.length - 1] ?? workflowRef;
    }
    return "Subgraph";
  }
  const nodeRef = typeof node.node === "string" ? node.node : undefined;
  if (nodeRef) {
    const parts = nodeRef.split(".");
    return parts[parts.length - 1] ?? nodeRef;
  }
  return typeof node.id === "string" ? node.id : "Unknown";
};

export const buildWorkflowGraph = (
  plan: {
    nodes: ReadonlyArray<Record<string, unknown>>;
    edges: ReadonlyArray<Record<string, unknown>>;
  },
  options: WorkflowGraphLayoutOptions = {},
): WorkflowGraphModel => {
  const layout = { ...DEFAULT_LAYOUT, ...options };
  const sortedNodes = plan.nodes.toSorted((a, b) =>
    String(a.id).localeCompare(String(b.id)),
  );

  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({
    rankdir: layout.direction,
    nodesep: layout.nodesep,
    ranksep: layout.ranksep,
  });

  for (const node of sortedNodes) {
    g.setNode(String(node.id), {
      width: layout.nodeWidth,
      height: layout.nodeHeight,
    });
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
        kind: mapNodeKind(node.type),
        label: buildLabel(node, layout.label),
        detail: typeof node.detail === "string" ? node.detail : null,
        nodeRef: typeof node.node === "string" ? node.node : null,
        raw: node,
      },
      position: {
        x: pos.x - layout.nodeWidth / 2,
        y: pos.y - layout.nodeHeight / 2,
      },
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
