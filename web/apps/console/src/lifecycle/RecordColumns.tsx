import type { ArtifactSummary, DeploymentSummary, RunSummary } from "./models.js";

type RecordColumnsProps = {
  readonly artifacts: ReadonlyArray<ArtifactSummary>;
  readonly deployments: ReadonlyArray<DeploymentSummary>;
  readonly runs: ReadonlyArray<RunSummary>;
  readonly selectedArtifactId: string | null;
  readonly selectedDeploymentId: string | null;
  readonly selectedRunId: string | null;
  readonly onSelectArtifact: (artifactId: string | null) => void;
  readonly onSelectDeployment: (deploymentId: string | null) => void;
  readonly onSelectRun: (runId: string | null) => void;
  readonly onLoadMoreArtifacts?: () => void;
  readonly hasMoreArtifacts?: boolean;
  readonly onLoadMoreRuns?: () => void;
  readonly hasMoreRuns?: boolean;
};

export const RecordColumns = ({
  artifacts,
  deployments,
  runs,
  selectedArtifactId,
  selectedDeploymentId,
  selectedRunId,
  onSelectArtifact,
  onSelectDeployment,
  onSelectRun,
  onLoadMoreArtifacts,
  hasMoreArtifacts,
  onLoadMoreRuns,
  hasMoreRuns,
}: RecordColumnsProps) => (
  <div className="lifecycle-columns">
    <div className="lifecycle-column">
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
    </div>
    <div className="lifecycle-column">
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
    </div>
    <div className="lifecycle-column">
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
    </div>
  </div>
);
