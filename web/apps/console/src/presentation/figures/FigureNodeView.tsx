import type { FigureNodeDefinition, FigureNodeKind } from "./model.js";

type FigureNodeViewProps = {
  readonly node: FigureNodeDefinition;
  readonly isActive: boolean;
  readonly focusedNodeId: string;
  readonly onActivate: (nodeId: string) => void;
  readonly onExpand: (nodeId: string) => void;
  readonly onFocus: (nodeId: string) => void;
};

const kindLabel: Record<FigureNodeKind, string> = {
  actor: "Actor",
  operation: "Operation",
  artifact: "Artifact",
  runtime: "Runtime",
  boundary: "Boundary",
  evidence: "Evidence",
  decision: "Decision",
  terminal: "Terminal",
  provider: "Provider",
  lane: "Lane",
  loop: "Loop",
};

export const FigureNodeView = ({
  node,
  isActive,
  focusedNodeId,
  onActivate,
  onExpand,
  onFocus,
}: FigureNodeViewProps) => {
  const expandable = node.childFigureId !== undefined;
  const accessibleName = expandable
    ? `${node.label}, expand`
    : node.label;

  return (
    <button
      type="button"
      className="figure-node"
      data-figure-node-kind={node.kind}
      data-active={isActive}
      data-expandable={expandable}
      data-testid={`figure-node-${node.id}`}
      aria-label={accessibleName}
      tabIndex={focusedNodeId === node.id ? 0 : -1}
      onClick={() => {
        onActivate(node.id);
        if (expandable) onExpand(node.id);
      }}
      onKeyDown={(event) => {
        if (event.key === "Enter" && expandable) {
          event.preventDefault();
          onExpand(node.id);
        }
      }}
      onFocus={() => onFocus(node.id)}
    >
      <span className="figure-node__kind">{kindLabel[node.kind] ?? node.kind}</span>
      <strong className="figure-node__label">{node.label}</strong>
      <span className="figure-node__summary">{node.summary}</span>
      {expandable && <span className="figure-node__expand-affordance" aria-hidden="true">▸</span>}
      {isActive && <span className="figure-node__current-marker">Current</span>}
    </button>
  );
};
