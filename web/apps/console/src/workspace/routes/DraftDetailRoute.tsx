import { Link, useParams } from "react-router-dom";
import type {
  DraftWorkspace,
} from "../domain/draft-workspace-models.js";
import { DraftWorkbench } from "../authoring/DraftWorkbench.js";
import { useDraftWorkspace } from "./useDraftWorkspace.js";

const titleFor = (workspace: DraftWorkspace): string =>
  workspace.title?.trim() || workspace.workspaceId;

const formatStatus = (status: DraftWorkspace["status"]): string =>
  status.charAt(0).toUpperCase() + status.slice(1);

export const DraftDetailRoute = () => {
  const { workspaceId = null } = useParams<{ workspaceId: string }>();
  const drafts = useDraftWorkspace(workspaceId);
  const draft =
    drafts.selected?.workspaceId === workspaceId ? drafts.selected : null;

  return (
    <div className="draft-detail">
      <nav aria-label="Draft breadcrumbs" className="draft-detail__breadcrumbs">
        <Link to="/console/drafts">Drafts</Link>
        <span aria-hidden="true">/</span>
        <span>{workspaceId ?? "Unknown workspace"}</span>
      </nav>

      {drafts.detailPhase === "disconnected" && (
        <p role="status">Connect a workflow server to view this draft.</p>
      )}
      {drafts.detailPhase === "loading" && <p role="status">Loading draft workspace...</p>}
      {drafts.detailPhase === "error" && (
        <p role="alert">{drafts.detailMessage ?? "Draft workspace detail failed."}</p>
      )}
      {drafts.detailPhase === "idle" && <p role="status">Select a draft workspace to inspect.</p>}

      {draft && (
        <>
          <header className="draft-detail__header">
            <p className="workspace-route-pending__eyebrow">Draft authoring workbench</p>
            <h1>{titleFor(draft)}</h1>
            <p className="draft-detail__workspace-id">{draft.workspaceId}</p>
            <p className="draft-detail__status-line">
              <span className="draft-workspaces__status" data-status={draft.status}>
                {formatStatus(draft.status)}
              </span>
              <span>Revision {draft.revision}</span>
            </p>
          </header>

          <DraftWorkbench draft={draft} />
        </>
      )}
    </div>
  );
};
