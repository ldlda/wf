import { BrowserRouter } from "react-router-dom";
import { AppRoutes } from "./AppRoutes.js";

export const App = () => (
  <BrowserRouter>
    <AppRoutes />
  </BrowserRouter>
);
