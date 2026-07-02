import type { ArtifactDetail, DeploymentDetail, RunDetail } from "./models.js";

type RecordDetailsProps = {
  readonly artifactDetail: ArtifactDetail | null;
  readonly deploymentDetail: DeploymentDetail | null;
  readonly runDetail: RunDetail | null;
};

export const RecordDetails = ({
  artifactDetail,
  deploymentDetail,
  runDetail,
}: RecordDetailsProps) => (
  <div className="record-details">
    {artifactDetail && (
      <section aria-label="Artifact details">
        <h3>Artifact</h3>
        <dl>
          <dt>Name</dt>
          <dd>{artifactDetail.title}</dd>
          <dt>ID</dt>
          <dd>{artifactDetail.artifactId}</dd>
          <dt>Version</dt>
          <dd>{artifactDetail.version}</dd>
          <dt>Kind</dt>
          <dd>{artifactDetail.kind}</dd>
          <dt>Outcomes</dt>
          <dd>{artifactDetail.outcomes.join(", ")}</dd>
        </dl>
      </section>
    )}
    {deploymentDetail && (
      <section aria-label="Deployment details">
        <h3>Deployment</h3>
        <dl>
          <dt>ID</dt>
          <dd>{deploymentDetail.id}</dd>
          <dt>Artifact ID</dt>
          <dd>{deploymentDetail.artifactId}</dd>
          <dt>Artifact Version</dt>
          <dd>{deploymentDetail.artifactVersion}</dd>
          <dt>Drift Policy</dt>
          <dd>{deploymentDetail.driftPolicy}</dd>
          <dt>Bindings</dt>
          <dd>{deploymentDetail.bindings.length}</dd>
        </dl>
      </section>
    )}
    {runDetail && (
      <section aria-label="Run details">
        <h3>Run</h3>
        <dl>
          <dt>ID</dt>
          <dd>{runDetail.runId}</dd>
          <dt>Deployment</dt>
          <dd>{runDetail.deploymentId}</dd>
          <dt>Status</dt>
          <dd>{runDetail.status}</dd>
          <dt>Resume Readiness</dt>
          <dd>{runDetail.resumeReadiness}</dd>
        </dl>
        {runDetail.interrupt && (
          <div className="interrupt-details">
            <h4>Interrupt</h4>
            <dl>
              <dt>Kind</dt>
              <dd>{runDetail.interrupt.kind}</dd>
              <dt>Outcomes</dt>
              <dd>{runDetail.interrupt.outcomes.join(", ")}</dd>
            </dl>
          </div>
        )}
      </section>
    )}
    {!artifactDetail && !deploymentDetail && !runDetail && (
      <p className="empty-state">Select a record to view details</p>
    )}
  </div>
);
