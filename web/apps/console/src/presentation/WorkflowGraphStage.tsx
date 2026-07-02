export type PresentationNode = {
  readonly id: string;
  readonly label: string;
  readonly kind: "node" | "interrupt" | "end";
  readonly x: number;
  readonly y: number;
};

export const presentationNodes: readonly PresentationNode[] = [
  { id: "read_docs", label: "Read docs", kind: "node", x: 8, y: 45 },
  { id: "build_report", label: "Build report", kind: "node", x: 30, y: 30 },
  { id: "review_issues", label: "Issue review", kind: "interrupt", x: 52, y: 45 },
  { id: "create_issues", label: "Create issues", kind: "node", x: 74, y: 30 },
  { id: "end_completed", label: "Completed", kind: "end", x: 92, y: 45 },
];

type WorkflowGraphStageProps = {
  readonly selectedNodeId: string | null;
  readonly selectNode: (nodeId: string) => void;
};

export const WorkflowGraphStage = ({ selectedNodeId, selectNode }: WorkflowGraphStageProps) => (
  <section className="workflow-graph-stage" aria-label="workflow graph">
    {presentationNodes.map((node) => (
      <button
        key={node.id}
        type="button"
        className="workflow-graph-stage__node"
        data-kind={node.kind}
        data-selected={selectedNodeId === node.id}
        style={{ left: `${node.x}%`, top: `${node.y}%` }}
        onClick={() => selectNode(node.id)}
      >
        {node.label}
      </button>
    ))}
  </section>
);
