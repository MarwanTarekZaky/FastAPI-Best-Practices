import { createContext, useContext } from "react"

import type { Role, Session } from "@/auth/session"

export interface AuthContextValue {
  session: Session | null
  login: (role: Role, email: string, password: string) => Promise<void>
  logout: () => Promise<void>
}

export const AuthContext = createContext<AuthContextValue | null>(null)

// Any component can call useAuth() to read the session or log in and out
export function useAuth() {
  const auth = useContext(AuthContext)
  if (!auth) {
    throw new Error("useAuth must be used inside <AuthProvider>")
  }
  return auth
}

// For pages behind <RequireAuth>, where someone is always logged in
export function useRole(): Role {
  const { session } = useAuth()
  if (!session) {
    throw new Error("useRole must be used on a page behind <RequireAuth>")
  }
  return session.role
}
