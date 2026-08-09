import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import type {
  DraftWorkspace,
} from "../domain/draft-workspace-models.js";
import { DraftWorkbench } from "../authoring/DraftWorkbench.js";
import type { WorkbenchSelection } from "../authoring/authoring-graph.js";
import { useDraftWorkspace } from "./useDraftWorkspace.js";
import { useCapabilityDiscovery } from "./useCapabilityDiscovery.js";

const titleFor = (workspace: DraftWorkspace): string =>
  workspace.title?.trim() || workspace.workspaceId;

const formatStatus = (status: DraftWorkspace["status"]): string =>
  status.charAt(0).toUpperCase() + status.slice(1);

export type DraftDetailRouteProps = {
  readonly enableNavigationProtection?: boolean;
};

export const DraftDetailRoute = ({
  enableNavigationProtection = false,
}: DraftDetailRouteProps) => {
  const { workspaceId = null } = useParams<{ workspaceId: string }>();
  const [searchParams] = useSearchParams();
  const capabilityName = searchParams.get("capability");
  const initialSelection: WorkbenchSelection =
    capabilityName !== null && capabilityName.trim() !== ""
      ? { kind: "capability", qualifiedName: capabilityName }
      : { kind: "canvas" };
  const drafts = useDraftWorkspace(workspaceId);
  const capabilities = useCapabilityDiscovery({ loadAllPages: true });
  const draft =
    drafts.selected?.workspaceId === workspaceId ? drafts.selected : null;
  const [authoringDraft, setAuthoringDraft] = useState<DraftWorkspace | null>(null);
  const loaderSourceRef = useRef<{
    readonly draft: DraftWorkspace | null;
    readonly detailPhase: typeof drafts.detailPhase;
    readonly workspaceId: string | null;
  } | null>(null);
  const loaderGenerationRef = useRef(0);
  const loaderSource = {
    draft,
    detailPhase: drafts.detailPhase,
    workspaceId,
  };
  const previousLoaderSource = loaderSourceRef.current;
  if (
    previousLoaderSource === null ||
    previousLoaderSource.draft !== loaderSource.draft ||
    previousLoaderSource.detailPhase !== loaderSource.detailPhase ||
    previousLoaderSource.workspaceId !== loaderSource.workspaceId
  ) {
    loaderSourceRef.current = loaderSource;
    loaderGenerationRef.current += 1;
  }
  const callbackGeneration = loaderGenerationRef.current;

  useEffect(() => {
    setAuthoringDraft(draft);
  }, [draft, drafts.detailPhase, workspaceId]);

  // A successful mutation is displayed immediately; a later loader snapshot
  // replaces it, and the generation prevents an old callback crossing freshness boundaries.
  const displayedDraft =
    draft === null
      ? null
      : authoringDraft?.workspaceId === workspaceId
        ? authoringDraft
        : draft;
  const handleDraftChange = useCallback(
    (nextDraft: DraftWorkspace): void => {
      if (
        callbackGeneration === loaderGenerationRef.current &&
        nextDraft.workspaceId === workspaceId
      ) setAuthoringDraft(nextDraft);
    },
    [callbackGeneration, workspaceId],
  );

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

      {draft && displayedDraft && (
        <>
          <header className="draft-detail__header">
            <p className="workspace-route-pending__eyebrow">Draft authoring workbench</p>
            <h1>{titleFor(displayedDraft)}</h1>
            <p className="draft-detail__workspace-id">{displayedDraft.workspaceId}</p>
            <p className="draft-detail__status-line">
              <span className="draft-workspaces__status" data-status={displayedDraft.status}>
                {formatStatus(displayedDraft.status)}
              </span>
              <span>Revision {displayedDraft.revision}</span>
            </p>
          </header>

          <DraftWorkbench
            capabilities={capabilities.items}
            draft={draft}
            enableNavigationProtection={enableNavigationProtection}
            initialSelection={initialSelection}
            onDraftChange={handleDraftChange}
          />
        </>
      )}
    </div>
  );
};
