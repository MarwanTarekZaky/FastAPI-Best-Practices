import { Navigate, Outlet, useLocation } from "react-router"

import { useAuth } from "@/auth/auth-context"
import type { Role } from "@/auth/session"

// Wraps the pages of one role. This only improves the experience: the real
// protection is the API, which checks the token on every request
export function RequireAuth({ role }: { role: Role }) {
  const { session } = useAuth()
  const location = useLocation()

  if (!session) {
    // Remember the page, the login form comes back to it
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }
  if (session.role !== role) {
    return <Navigate to={`/${session.role}`} replace />
  }
  // <Outlet /> shows the child route that matched the URL
  return <Outlet />
}
