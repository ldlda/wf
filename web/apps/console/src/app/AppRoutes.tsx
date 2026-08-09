import { Routes } from "react-router-dom";
import { createAppRouteElements } from "./app-route-elements.js";

export type AppRoutesProps = {
  readonly protectDraftNavigation?: boolean;
};

export const AppRoutes = ({
  protectDraftNavigation = false,
}: AppRoutesProps = {}) => (
  <Routes>
    {createAppRouteElements({ protectDraftNavigation })}
  </Routes>
);
