import { Link, useParams, useSearchParams } from "react-router-dom";
import { DraftWorkbench } from "../authoring/DraftWorkbench.js";
import type { WorkbenchSelection } from "../authoring/authoring-graph.js";
import { useDraftWorkspace } from "./useDraftWorkspace.js";
import { useCapabilityDiscovery } from "./useCapabilityDiscovery.js";

export type DraftDetailRouteProps = {
  readonly enableNavigationProtection?: boolean;
};

export const DraftDetailRoute = ({
  enableNavigationProtection = false,
}: DraftDetailRouteProps) => {
  const { workspaceId = null } = useParams<{ workspaceId: string }>();
  const [searchParams] = useSearchParams();
  const capabilityName = searchParams.get("capability")?.trim() ?? "";
  const initialSelection: WorkbenchSelection =
    capabilityName !== ""
      ? { kind: "capability", qualifiedName: capabilityName }
      : { kind: "canvas" };
  const drafts = useDraftWorkspace(workspaceId);
  const capabilities = useCapabilityDiscovery({ loadAllPages: true });
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
        <DraftWorkbench
          capabilities={capabilities.items}
          draft={draft}
          enableNavigationProtection={enableNavigationProtection}
          initialSelection={initialSelection}
        />
      )}
    </div>
  );
};
