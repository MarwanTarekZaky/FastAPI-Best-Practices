import { useQueryClient } from "@tanstack/react-query"
import { useState, type ReactNode } from "react"

import { api } from "@/api/client"
import { AuthContext } from "@/auth/auth-context"
import {
  clearSession,
  getSession,
  saveSession,
  type Role,
  type Session,
} from "@/auth/session"

export function AuthProvider({ children }: { children: ReactNode }) {
  // Starts from localStorage, so a page refresh keeps you logged in
  const [session, setSession] = useState<Session | null>(getSession)
  const queryClient = useQueryClient()

  async function login(role: Role, email: string, password: string) {
    // OAuth2 login forms call the email "username"
    const form = { username: email, password }
    const token =
      role === "seller"
        ? await api.seller.loginSeller(form)
        : await api.partner.loginDeliveryPartner(form)

    const newSession = { token: token.access_token, role }
    saveSession(newSession)
    setSession(newSession)
  }

  async function logout() {
    try {
      // The API puts the token on its Redis blacklist, so it can't be used again
      if (session?.role === "partner") {
        await api.partner.logoutDeliveryPartner()
      } else {
        await api.seller.logoutSeller()
      }
    } finally {
      clearSession()
      setSession(null)
      // Forget the cached data of the user who logged out
      queryClient.clear()
    }
  }

  return <AuthContext value={{ session, login, logout }}>{children}</AuthContext>
}
