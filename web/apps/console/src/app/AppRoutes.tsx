import { Navigate, Route, Routes } from "react-router-dom";
import { ConsoleHome } from "./ConsoleHome.js";
import { PresentationRoute } from "../presentation/PresentationRoute.js";
import { PresenterRoute } from "../presentation/presenter/PresenterRoute.js";

export const AppRoutes = () => (
  <Routes>
    <Route path="/" element={<ConsoleHome />} />
    <Route path="/console" element={<ConsoleHome />} />
    <Route path="/present" element={<PresentationRoute />} />
    <Route path="/presenter" element={<PresenterRoute />} />
    <Route path="*" element={<Navigate to="/" replace />} />
  </Routes>
);
