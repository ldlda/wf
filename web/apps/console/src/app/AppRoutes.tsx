import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { ConsoleHome } from "./ConsoleHome.js";
import { PresentationRoute } from "../presentation/PresentationRoute.js";

const PresenterRoute = lazy(() => import("../presentation/presenter/PresenterRoute.js").then((module) => ({
  default: module.PresenterRoute,
})));

const PresenterRouteFallback = () => (
  <main className="presenter-route" aria-label="Presenter notes loading" aria-busy="true">
    <p>Loading presenter notes...</p>
  </main>
);

export const AppRoutes = () => (
  <Routes>
    <Route path="/" element={<ConsoleHome />} />
    <Route path="/console" element={<ConsoleHome />} />
    <Route path="/present" element={<PresentationRoute />} />
    <Route path="/presenter" element={<Suspense fallback={<PresenterRouteFallback />}><PresenterRoute /></Suspense>} />
    <Route path="*" element={<Navigate to="/" replace />} />
  </Routes>
);
