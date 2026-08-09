import {
  createBrowserRouter,
  createRoutesFromElements,
  RouterProvider,
} from "react-router-dom";
import { createAppRouteElements } from "./app-route-elements.js";

const router = createBrowserRouter(
  createRoutesFromElements(createAppRouteElements({ protectDraftNavigation: true })),
);

export const App = () => (
  <RouterProvider router={router} />
);
