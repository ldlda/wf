import { findDiscussionBranch, findScene } from "./storyboard.js";

type DiscussionPanelProps = {
  readonly branchId: string;
  readonly onClose: () => void;
};

export const DiscussionPanel = ({ branchId, onClose }: DiscussionPanelProps) => {
  const branch = findDiscussionBranch(branchId);
  if (!branch) return null;

  const parentScene = findScene(branch.parentSceneId);

  return (
    <div className="discussion-panel" role="dialog" aria-label={branch.title}>
      <header>
        <h2>{branch.title}</h2>
        <span className="discussion-panel__badge">{branch.claimClass}</span>
      </header>
      <p className="discussion-panel__evidence">{branch.evidencePointer}</p>
      <p className="discussion-panel__summary">{branch.summary}</p>
      {branchId === "hosted-automation" && (
        <p className="discussion-panel__detail">
          A future scheduler could trigger a workflow that launches a verified headless
          coding-agent command with a stored prompt. lda.chat does not implement that
          trigger or scheduler in the submitted scope.
        </p>
      )}
      {branchId === "mcp-agent-scale" && (
        <p className="discussion-panel__detail">
          <a href="https://modelcontextprotocol.io/" target="_blank" rel="noopener noreferrer">Model Context Protocol</a> ·{" "}
          <a href="https://developers.cloudflare.com/workers-ai/configuration/code-mode/" target="_blank" rel="noopener noreferrer">Cloudflare Code Mode</a>
          {" "}— both are external context.
        </p>
      )}
      <button type="button" onClick={onClose} className="discussion-panel__return">
        Return to {parentScene?.title ?? "scene"}
      </button>
    </div>
  );
};
