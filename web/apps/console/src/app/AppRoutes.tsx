import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { ConsoleWorkspace } from "../workspace/ConsoleWorkspace.js";
import { useConsoleWorkspace } from "../workspace/context.js";
import { DiscoverRoute } from "../workspace/routes/DiscoverRoute.js";
import { PresentationRoute } from "../presentation/PresentationRoute.js";

const PresenterRoute = lazy(() => import("../presentation/presenter/PresenterRoute.js").then((module) => ({
  default: module.PresenterRoute,
})));

const PresenterRouteFallback = () => (
  <main className="presenter-route" aria-label="Presenter notes loading" aria-busy="true">
    <p>Loading presenter notes...</p>
  </main>
);

const WorkspaceRoutePending = ({ label }: { readonly label: string }) => {
  const { connection } = useConsoleWorkspace();
  const connected = connection.phase === "connected";

  return (
    <section className="workspace-route-pending">
      <p className="workspace-route-pending__eyebrow">Workspace route</p>
      <h1>{label}</h1>
      <p>
        {connected
          ? `${label} is ready for its workflow surface.`
          : `${label} is unavailable until a workflow server is connected.`}
      </p>
      {!connected && <p>Connect a workflow server to view {label}.</p>}
    </section>
  );
};

export const AppRoutes = () => (
  <Routes>
    <Route path="/" element={<Navigate to="/console/discover" replace />} />
    <Route path="/console" element={<ConsoleWorkspace />}>
      <Route index element={<Navigate to="discover" replace />} />
      <Route path="discover" element={<DiscoverRoute />} />
      <Route path="drafts" element={<WorkspaceRoutePending label="Drafts" />} />
      <Route path="drafts/:workspaceId" element={<WorkspaceRoutePending label="Draft" />} />
      <Route path="artifacts" element={<WorkspaceRoutePending label="Artifacts" />} />
      <Route path="artifacts/:artifactId/:version" element={<WorkspaceRoutePending label="Artifact" />} />
      <Route path="deployments" element={<WorkspaceRoutePending label="Deployments" />} />
      <Route path="deployments/:deploymentId" element={<WorkspaceRoutePending label="Deployment" />} />
      <Route path="runs" element={<WorkspaceRoutePending label="Runs" />} />
      <Route path="runs/:runId" element={<WorkspaceRoutePending label="Run" />} />
      <Route path="results" element={<WorkspaceRoutePending label="Results" />} />
    </Route>
    <Route path="/present" element={<PresentationRoute />} />
    <Route path="/presenter" element={<Suspense fallback={<PresenterRouteFallback />}><PresenterRoute /></Suspense>} />
    <Route path="*" element={<Navigate to="/console/discover" replace />} />
  </Routes>
);
