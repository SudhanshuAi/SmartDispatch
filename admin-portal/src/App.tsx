import type { ReactNode } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth/AuthContext";
import { AdminShell } from "./layouts/AdminShell";
import { DriverShell } from "./layouts/DriverShell";
import { LoginPage } from "./pages/LoginPage";
import { DashboardPage } from "./pages/admin/DashboardPage";
import { DriversPage } from "./pages/admin/DriversPage";
import { FleetMapPage } from "./pages/admin/FleetMapPage";
import { GuestsPage } from "./pages/admin/GuestsPage";
import { OverridePage } from "./pages/admin/OverridePage";
import { RideRequestsPage } from "./pages/admin/RideRequestsPage";
import { DriverTripPage } from "./pages/driver/DriverTripPage";

function RequireRole({ role, children }: { role: "admin" | "driver"; children: ReactNode }) {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  if (user.role !== role) {
    return <Navigate to={user.role === "admin" ? "/admin" : "/driver"} replace />;
  }
  return children;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/admin"
        element={
          <RequireRole role="admin">
            <AdminShell />
          </RequireRole>
        }
      >
        <Route index element={<DashboardPage />} />
        <Route path="map" element={<FleetMapPage />} />
        <Route path="requests" element={<RideRequestsPage />} />
        <Route path="drivers" element={<DriversPage />} />
        <Route path="guests" element={<GuestsPage />} />
        <Route path="override" element={<OverridePage />} />
      </Route>
      <Route
        path="/driver"
        element={
          <RequireRole role="driver">
            <DriverShell />
          </RequireRole>
        }
      >
        <Route index element={<DriverTripPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  );
}
