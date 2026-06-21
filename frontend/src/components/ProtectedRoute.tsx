import { Navigate, useLocation } from "react-router-dom";
import { useApp } from "../context/AppContext";
import { isLoggedIn } from "../lib/auth";
import { getActiveGroupId } from "../lib/activeGroup";
import type { ReactNode } from "react";

function LoadingScreen() {
  return (
    <div className="flex h-full items-center justify-center text-gray-600">
      Loading...
    </div>
  );
}

type ProtectedRouteProps = {
  children: ReactNode;
  /** When true, redirect to /groups if no active group is selected. */
  requireActiveGroup?: boolean;
};

export function ProtectedRoute({
  children,
  requireActiveGroup = false,
}: ProtectedRouteProps) {
  const location = useLocation();
  const { isBootstrapping } = useApp();

  if (!isLoggedIn()) {
    const redirect = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`/login?redirect=${redirect}`} replace />;
  }

  if (isBootstrapping) {
    return <LoadingScreen />;
  }

  if (requireActiveGroup && !getActiveGroupId()) {
    return <Navigate to="/groups" replace />;
  }

  return children;
}

type PublicOnlyRouteProps = {
  children: ReactNode;
};

export function PublicOnlyRoute({ children }: PublicOnlyRouteProps) {
  const { isBootstrapping } = useApp();

  if (isLoggedIn()) {
    if (isBootstrapping) {
      return <LoadingScreen />;
    }
    return <Navigate to="/groups" replace />;
  }

  return children;
}
