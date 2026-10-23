import { createBrowserRouter } from "react-router-dom";

import { OrdersPage } from "./Orders";
import { ReportsPage } from "./ReportsPage";
import { SettingsDialog } from "./SettingsDialog";

export const routes = [
  { path: "/orders", element: <OrdersPage /> },
  { path: "/orders/:id", element: <OrdersPage /> },
  { path: "/settings", element: <SettingsDialog /> },
];

export const router = createBrowserRouter(routes);
