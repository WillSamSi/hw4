import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import * as api from '../api'
import type { User } from '../types'

// The session lives in an HttpOnly cookie set by the backend; the browser keeps
// no password or token in JavaScript-readable storage.
interface AuthValue {
  user: User | null
  /** False until we've asked the server whether a session already exists. */
  ready: boolean
  login: (email: string, password: string) => Promise<void>
  register: (input: api.RegisterInput) => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    api
      .fetchMe()
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setReady(true))
  }, [])

  const value: AuthValue = {
    user,
    ready,
    login: async (email, password) => setUser(await api.login(email, password)),
    register: async (input) => setUser(await api.register(input)),
    logout: async () => {
      await api.logout().catch(() => {})
      setUser(null)
    },
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
