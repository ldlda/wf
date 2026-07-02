import { presentationNodes } from "./WorkflowGraphStage.js";

type NodeSpotlightProps = {
  readonly nodeId: string;
  readonly close: () => void;
};

const nodeDescription = (nodeId: string): string => {
  if (nodeId === "review_issues") {
    return "NodeUse of a typed interrupt boundary. It exposes request and resume schemas and waits for a submitted or cancelled outcome.";
  }
  if (nodeId === "create_issues") {
    return "NodeUse that writes selected review items into the local issue-board source.";
  }
  return "NodeUse in the prepared report workflow. The presentation graph is curated, but every node maps back to real workflow/run evidence.";
};

export const NodeSpotlight = ({ nodeId, close }: NodeSpotlightProps) => {
  const node = presentationNodes.find((candidate) => candidate.id === nodeId);
  if (!node) return null;

  return (
    <aside className="node-spotlight" role="dialog" aria-label={node.label}>
      <button type="button" onClick={close}>Close</button>
      <p>NodeUse</p>
      <h2>{node.label}</h2>
      <p>{nodeDescription(node.id)}</p>
    </aside>
  );
};
