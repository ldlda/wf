import { lazy, Suspense } from "react";
import { Navigate, Route } from "react-router-dom";
import { ConsoleWorkspace } from "../workspace/ConsoleWorkspace.js";
import { DiscoverRoute } from "../workspace/routes/DiscoverRoute.js";
import { DraftDetailRoute } from "../workspace/routes/DraftDetailRoute.js";
import { DraftIndexRoute } from "../workspace/routes/DraftIndexRoute.js";
import { LifecycleRoute } from "../workspace/routes/LifecycleRoute.js";
import { PresentationRoute } from "../presentation/PresentationRoute.js";

const PresenterRoute = lazy(() => import("../presentation/presenter/PresenterRoute.js").then((module) => ({
  default: module.PresenterRoute,
})));

const PresenterRouteFallback = () => (
  <main className="presenter-route" aria-label="Presenter notes loading" aria-busy="true">
    <p>Loading presenter notes...</p>
  </main>
);

export const createAppRouteElements = ({
  protectDraftNavigation = false,
}: {
  readonly protectDraftNavigation?: boolean;
} = {}) => (
  <>
    <Route path="/" element={<Navigate to="/console/discover" replace />} />
    <Route path="/console" element={<ConsoleWorkspace />}>
      <Route index element={<Navigate to="discover" replace />} />
      <Route path="discover" element={<DiscoverRoute />} />
      <Route path="drafts" element={<DraftIndexRoute />} />
      <Route
        path="drafts/:workspaceId"
        element={<DraftDetailRoute enableNavigationProtection={protectDraftNavigation} />}
      />
      <Route path="artifacts" element={<LifecycleRoute kind="artifact" />} />
      <Route path="artifacts/:artifactId/:version" element={<LifecycleRoute kind="artifact" />} />
      <Route path="deployments" element={<LifecycleRoute kind="deployment" />} />
      <Route path="deployments/:deploymentId" element={<LifecycleRoute kind="deployment" />} />
      <Route path="runs" element={<LifecycleRoute kind="run" />} />
      <Route path="runs/:runId" element={<LifecycleRoute kind="run" />} />
    </Route>
    <Route path="/present" element={<PresentationRoute />} />
    <Route path="/presenter" element={<Suspense fallback={<PresenterRouteFallback />}><PresenterRoute /></Suspense>} />
    <Route path="*" element={<Navigate to="/console/discover" replace />} />
  </>
);
