export type Role = "seller" | "partner"

export interface Session {
  token: string
  role: Role
}

const STORAGE_KEY = "fastship.session"

// localStorage keeps the session after a page refresh or closing the tab
export function getSession(): Session | null {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    return saved ? (JSON.parse(saved) as Session) : null
  } catch {
    // Broken or blocked storage: treat it as logged out
    return null
  }
}

export function saveSession(session: Session) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(session))
}

export function clearSession() {
  localStorage.removeItem(STORAGE_KEY)
}
