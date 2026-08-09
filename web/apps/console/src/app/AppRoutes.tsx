import { Routes } from "react-router-dom";
import { createAppRouteElements } from "./app-route-elements.js";

export const AppRoutes = () => (
  <Routes>
    {createAppRouteElements()}
  </Routes>
);
