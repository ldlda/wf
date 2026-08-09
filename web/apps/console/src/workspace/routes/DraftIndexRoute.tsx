import { useState } from "react";
import { Link } from "react-router-dom";
import type { DraftWorkspace } from "../domain/draft-workspace-models.js";
import { CreateDraftDialog } from "../authoring/CreateDraftDialog.js";
import { useDraftWorkspace } from "./useDraftWorkspace.js";

const titleFor = (workspace: DraftWorkspace): string =>
  workspace.title?.trim() || workspace.workspaceId;

const formatStatus = (status: DraftWorkspace["status"]): string =>
  status.charAt(0).toUpperCase() + status.slice(1);

const DraftRow = ({ workspace }: { readonly workspace: DraftWorkspace }) => (
  <tr>
    <th scope="row">
      <Link to={`/console/drafts/${encodeURIComponent(workspace.workspaceId)}`}>
        {titleFor(workspace)}
      </Link>
      <span className="draft-workspaces__row-id">{workspace.workspaceId}</span>
    </th>
    <td>
      <span className="draft-workspaces__status" data-status={workspace.status}>
        {formatStatus(workspace.status)}
      </span>
    </td>
    <td>Revision {workspace.revision}</td>
    <td>{workspace.summary.stepCount} steps</td>
    <td>{workspace.summary.routeCount} routes</td>
  </tr>
);

export const DraftIndexRoute = () => {
  const drafts = useDraftWorkspace(null);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);

  return (
    <div className="draft-workspaces">
      <header className="draft-workspaces__header">
        <p className="workspace-route-pending__eyebrow">Authoring inventory</p>
        <h1>Draft workspaces</h1>
        <p>Inspect saved workflow drafts without changing their definitions.</p>
        <div className="draft-workspaces__actions">
          <button onClick={() => setCreateDialogOpen(true)} type="button">
            New draft
          </button>
          <button onClick={drafts.refresh} type="button">
            Refresh drafts
          </button>
        </div>
      </header>

      <section aria-labelledby="draft-workspaces-list-heading" className="draft-workspaces__panel">
        <div className="draft-workspaces__section-heading">
          <div>
            <p className="workspace-route-pending__eyebrow">Read-only index</p>
            <h2 id="draft-workspaces-list-heading">Available drafts</h2>
          </div>
          {drafts.items.length > 0 && (
            <span className="draft-workspaces__count">{drafts.items.length} shown</span>
          )}
        </div>

        {drafts.listPhase === "disconnected" && (
          <p role="status">Connect a workflow server to list draft workspaces.</p>
        )}
        {drafts.listPhase === "loading" && <p role="status">Loading draft workspaces...</p>}
        {drafts.listPhase === "error" && (
          <p role="alert">{drafts.listMessage ?? "Draft workspace list failed."}</p>
        )}
        {drafts.listPhase === "ready" && drafts.items.length === 0 && (
          <p role="status">No draft workspaces are available.</p>
        )}

        {drafts.items.length > 0 && (
          <div className="draft-workspaces__table-wrap">
            <table>
              <caption className="visually-hidden">Draft workspace inventory</caption>
              <thead>
                <tr>
                  <th scope="col">Workspace</th>
                  <th scope="col">Status</th>
                  <th scope="col">Revision</th>
                  <th scope="col">Steps</th>
                  <th scope="col">Routes</th>
                </tr>
              </thead>
              <tbody>
                {drafts.items.map((workspace) => (
                  <DraftRow key={workspace.workspaceId} workspace={workspace} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
      {createDialogOpen && (
        <CreateDraftDialog capability={null} onClose={() => setCreateDialogOpen(false)} />
      )}
    </div>
  );
};
