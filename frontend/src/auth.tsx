import { useQueryClient } from '@tanstack/react-query'
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'

import { auth, getToken, setToken, SIGNED_OUT_EVENT } from './lib/api'
import type { User } from './lib/types'

type AuthState = {
  user: User | null
  loading: boolean
  signIn: (email: string, password: string) => Promise<void>
  signUp: (email: string, password: string) => Promise<void>
  signOut: () => void
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(Boolean(getToken()))

  const signOut = useCallback(() => {
    setToken(null)
    setUser(null)
    queryClient.clear() // never show the previous user's chats
  }, [queryClient])

  // Restore the session on page load, if a token was saved.
  useEffect(() => {
    if (!getToken()) return
    auth
      .me()
      .then(setUser)
      .catch(() => setToken(null))
      .finally(() => setLoading(false))
  }, [])

  // Any request answered with 401 (token expired) lands back on sign-in.
  useEffect(() => {
    window.addEventListener(SIGNED_OUT_EVENT, signOut)
    return () => window.removeEventListener(SIGNED_OUT_EVENT, signOut)
  }, [signOut])

  const signIn = async (email: string, password: string) => {
    setToken(await auth.login(email, password))
    setUser(await auth.me())
  }

  const signUp = async (email: string, password: string) => {
    await auth.register(email, password)
    await signIn(email, password)
  }

  return <AuthContext.Provider value={{ user, loading, signIn, signUp, signOut }}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthState {
  const value = useContext(AuthContext)
  if (!value) throw new Error('useAuth must be used inside <AuthProvider>')
  return value
}
