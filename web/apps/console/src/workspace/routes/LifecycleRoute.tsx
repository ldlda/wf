import { useCallback, useEffect, useMemo } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { LifecycleExplorer } from "../../lifecycle/LifecycleExplorer.js";
import { useLifecycleExplorer } from "../../lifecycle/useLifecycleExplorer.js";
import { createLifecycleClients } from "../domain/lifecycle-clients.js";
import { useConsoleWorkspace } from "../context.js";

export type LifecycleRouteKind = "artifact" | "deployment" | "run";

type LifecycleRouteProps = {
  readonly kind: LifecycleRouteKind;
};

const labels: Record<LifecycleRouteKind, string> = {
  artifact: "Artifacts",
  deployment: "Deployments",
  run: "Runs",
};

const artifactPathFor = (artifactKey: string): string => {
  const separator = artifactKey.lastIndexOf("@");
  if (separator <= 0 || separator === artifactKey.length - 1) return "/console/artifacts";
  return `/console/artifacts/${encodeURIComponent(artifactKey.slice(0, separator))}/${encodeURIComponent(artifactKey.slice(separator + 1))}`;
};

const decodeRouteParam = (value: string): string => {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
};

export const LifecycleRoute = ({ kind }: LifecycleRouteProps) => {
  const { readExecutor } = useConsoleWorkspace();
  const navigate = useNavigate();
  const params = useParams<{
    readonly artifactId?: string;
    readonly version?: string;
    readonly deploymentId?: string;
    readonly runId?: string;
  }>();
  const clients = useMemo(
    () => (readExecutor ? createLifecycleClients(readExecutor) : null),
    [readExecutor],
  );
  const controller = useLifecycleExplorer(clients);
  const {
    state,
    selectArtifact,
    selectDeployment,
    selectRun,
  } = controller;

  const artifactIdentity =
    kind === "artifact" && params.artifactId && params.version
      ? `${decodeRouteParam(params.artifactId)}@${decodeRouteParam(params.version)}`
      : null;
  const deploymentIdentity =
    kind === "deployment" && params.deploymentId
      ? decodeRouteParam(params.deploymentId)
      : null;
  const runIdentity =
    kind === "run" && params.runId ? decodeRouteParam(params.runId) : null;

  useEffect(() => {
    if (kind === "artifact") {
      if (artifactIdentity && state.selectedArtifactId !== artifactIdentity) {
        selectArtifact(artifactIdentity);
      } else if (!artifactIdentity && state.selectedArtifactId !== null) {
        selectArtifact(null);
      }
      return;
    }
    if (kind === "deployment") {
      if (deploymentIdentity && state.selectedDeploymentId !== deploymentIdentity) {
        selectDeployment(deploymentIdentity);
      } else if (!deploymentIdentity && state.selectedDeploymentId !== null) {
        selectDeployment(null);
      }
      return;
    }
    if (runIdentity && state.selectedRunId !== runIdentity) {
      selectRun(runIdentity);
    } else if (!runIdentity && state.selectedRunId !== null) {
      selectRun(null);
    }
  }, [
    artifactIdentity,
    deploymentIdentity,
    kind,
    runIdentity,
    selectArtifact,
    selectDeployment,
    selectRun,
    state.selectedArtifactId,
    state.selectedDeploymentId,
    state.selectedRunId,
  ]);

  const onSelectArtifact = useCallback(
    (artifactKey: string | null): void => {
      navigate(artifactKey ? artifactPathFor(artifactKey) : "/console/artifacts");
    },
    [navigate],
  );
  const onSelectDeployment = useCallback(
    (deploymentId: string | null): void => {
      navigate(
        deploymentId
          ? `/console/deployments/${encodeURIComponent(deploymentId)}`
          : "/console/deployments",
      );
    },
    [navigate],
  );
  const onSelectRun = useCallback(
    (runId: string | null): void => {
      navigate(runId ? `/console/runs/${encodeURIComponent(runId)}` : "/console/runs");
    },
    [navigate],
  );

  return (
    <div className="lifecycle-route">
      <header className="lifecycle-route__header">
        <p className="workspace-route-pending__eyebrow">Workflow lifecycle</p>
        <h1>{labels[kind]}</h1>
        <p>Inspect workflow records and their linked lifecycle context.</p>
      </header>
      {!readExecutor && (
        <p role="status">
          Connect a workflow server to view {labels[kind].toLowerCase()}.
        </p>
      )}
      <LifecycleExplorer
        controller={{
          ...controller,
          selectArtifact: onSelectArtifact,
          selectDeployment: onSelectDeployment,
          selectRun: onSelectRun,
        }}
        primaryKind={kind}
      />
    </div>
  );
};
