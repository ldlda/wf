import type { ReactElement, ReactNode } from "react";
import type { ArtifactSummary, DeploymentSummary, RunSummary } from "./models.js";

type LifecycleKind = "artifact" | "deployment" | "run";

type RecordColumnsProps = {
  readonly artifacts: ReadonlyArray<ArtifactSummary>;
  readonly deployments: ReadonlyArray<DeploymentSummary>;
  readonly runs: ReadonlyArray<RunSummary>;
  readonly selectedArtifactId: string | null;
  readonly selectedDeploymentId: string | null;
  readonly selectedRunId: string | null;
  readonly primaryKind: LifecycleKind;
  readonly onSelectArtifact: (artifactId: string | null) => void;
  readonly onSelectDeployment: (deploymentId: string | null) => void;
  readonly onSelectRun: (runId: string | null) => void;
  readonly onLoadMoreArtifacts?: () => void;
  readonly hasMoreArtifacts?: boolean;
  readonly onLoadMoreRuns?: () => void;
  readonly hasMoreRuns?: boolean;
};

const allKinds: ReadonlyArray<LifecycleKind> = ["artifact", "deployment", "run"];

const LifecycleColumn = ({
  kind,
  primaryKind,
  children,
}: {
  readonly kind: LifecycleKind;
  readonly primaryKind: LifecycleKind;
  readonly children: ReactNode;
}) => (
  <div
    className={`lifecycle-column lifecycle-column--${kind}${primaryKind === kind ? " lifecycle-column--primary" : ""}`}
    data-lifecycle-kind={kind}
  >
    {children}
  </div>
);

export const RecordColumns = ({
  artifacts,
  deployments,
  runs,
  selectedArtifactId,
  selectedDeploymentId,
  selectedRunId,
  primaryKind,
  onSelectArtifact,
  onSelectDeployment,
  onSelectRun,
  onLoadMoreArtifacts,
  hasMoreArtifacts,
  onLoadMoreRuns,
  hasMoreRuns,
}: RecordColumnsProps) => {
  const columns: Record<LifecycleKind, ReactElement> = {
    artifact: (
      <LifecycleColumn key="artifact" kind="artifact" primaryKind={primaryKind}>
        <h3>Artifacts</h3>
        {artifacts.length === 0 ? (
          <p className="empty-state">No artifacts</p>
        ) : (
          <ul role="listbox" aria-label="Artifacts">
            {artifacts.map((artifact) => (
              <li key={artifact.key}>
                <button
                  role="option"
                  aria-selected={selectedArtifactId === artifact.key}
                  onClick={() => onSelectArtifact(artifact.key)}
                  className={selectedArtifactId === artifact.key ? "selected" : ""}
                >
                  {artifact.displayName} version {artifact.version}
                </button>
              </li>
            ))}
          </ul>
        )}
        {hasMoreArtifacts && onLoadMoreArtifacts && (
          <button type="button" onClick={onLoadMoreArtifacts} className="load-more">
            Load more artifacts
          </button>
        )}
      </LifecycleColumn>
    ),
    deployment: (
      <LifecycleColumn key="deployment" kind="deployment" primaryKind={primaryKind}>
        <h3>Deployments</h3>
        {deployments.length === 0 ? (
          <p className="empty-state">No deployments</p>
        ) : (
          <ul role="listbox" aria-label="Deployments">
            {deployments.map((deployment) => (
              <li key={deployment.id}>
                <button
                  role="option"
                  aria-selected={selectedDeploymentId === deployment.id}
                  onClick={() => onSelectDeployment(deployment.id)}
                  className={selectedDeploymentId === deployment.id ? "selected" : ""}
                >
                  {deployment.id}
                </button>
              </li>
            ))}
          </ul>
        )}
      </LifecycleColumn>
    ),
    run: (
      <LifecycleColumn key="run" kind="run" primaryKind={primaryKind}>
        <h3>Runs</h3>
        {runs.length === 0 ? (
          <p className="empty-state">No runs</p>
        ) : (
          <ul role="listbox" aria-label="Runs">
            {runs.map((run) => (
              <li key={run.runId}>
                <button
                  role="option"
                  aria-selected={selectedRunId === run.runId}
                  onClick={() => onSelectRun(run.runId)}
                  className={selectedRunId === run.runId ? "selected" : ""}
                >
                  {run.runId} {run.status}
                </button>
              </li>
            ))}
          </ul>
        )}
        {hasMoreRuns && onLoadMoreRuns && (
          <button type="button" onClick={onLoadMoreRuns} className="load-more">
            Load more runs
          </button>
        )}
      </LifecycleColumn>
    ),
  };
  const orderedKinds = [primaryKind, ...allKinds.filter((kind) => kind !== primaryKind)];

  return (
    <div className="lifecycle-columns">
      {orderedKinds.map((kind) => columns[kind])}
    </div>
  );
};
