import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react"
import { GoogleLogin, GoogleOAuthProvider, googleLogout } from "@react-oauth/google"
import { ApiError, getMe, setAuthToken } from "@/api/client"
import type { UserContext } from "@/api/types"

// GIS ID tokens expire ~1h; sessionStorage (not localStorage) matches that -- the
// session ends with the tab, same as the token would anyway (docs/DECISIONS.md #104).
const TOKEN_KEY = "ouroboros_id_token"
const CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID as string

type Status = "loading" | "signed-out" | "signed-in" | "unauthorized"

interface AuthState {
  user: UserContext
  signOut: () => void
}

const AuthContext = createContext<AuthState | null>(null)

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error("useAuth must be used within AuthProvider")
  return ctx
}

function SignInScreen({
  reason,
  onCredential,
}: {
  reason: string | null
  onCredential: (token: string) => void
}) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-6 bg-background px-6">
      <img src="/logo.svg" alt="" className="h-14 w-14" />
      <h1 className="font-display text-3xl text-foreground">Ouroboros</h1>
      {reason && (
        <p className="max-w-sm text-center text-sm text-muted-foreground">{reason}</p>
      )}
      <GoogleLogin
        onSuccess={(credentialResponse) => {
          if (credentialResponse.credential) onCredential(credentialResponse.credential)
        }}
      />
    </div>
  )
}

function AuthGate({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<Status>("loading")
  const [user, setUser] = useState<UserContext | null>(null)
  const [deniedReason, setDeniedReason] = useState<string | null>(null)

  const resolveSession = useCallback(async (token: string) => {
    setAuthToken(token)
    try {
      const me = await getMe()
      sessionStorage.setItem(TOKEN_KEY, token)
      setUser(me)
      setStatus("signed-in")
    } catch (err) {
      setAuthToken(null)
      sessionStorage.removeItem(TOKEN_KEY)
      setDeniedReason(err instanceof ApiError ? err.message : "Sign-in failed. Try again.")
      setStatus(err instanceof ApiError && err.status === 403 ? "unauthorized" : "signed-out")
    }
  }, [])

  useEffect(() => {
    const stored = sessionStorage.getItem(TOKEN_KEY)
    if (stored) {
      void resolveSession(stored)
    } else {
      setStatus("signed-out")
    }
  }, [resolveSession])

  const signOut = useCallback(() => {
    setAuthToken(null)
    sessionStorage.removeItem(TOKEN_KEY)
    googleLogout()
    setUser(null)
    setDeniedReason(null)
    setStatus("signed-out")
  }, [])

  if (status === "loading") return null
  if (status !== "signed-in" || !user) {
    return (
      <SignInScreen reason={deniedReason} onCredential={(token) => void resolveSession(token)} />
    )
  }

  return <AuthContext.Provider value={{ user, signOut }}>{children}</AuthContext.Provider>
}

// 401 from any authenticated call (expired token mid-session) routes here: clearing
// the stored token and reloading drops back to AuthGate's "signed-out" branch, which
// re-prompts sign-in -- simpler than plumbing a global interceptor through every
// React Query call site for what's a rare, session-ending event.
export function forceReauth(): void {
  setAuthToken(null)
  sessionStorage.removeItem(TOKEN_KEY)
  window.location.reload()
}

export function AuthProvider({ children }: { children: ReactNode }) {
  return (
    <GoogleOAuthProvider clientId={CLIENT_ID}>
      <AuthGate>{children}</AuthGate>
    </GoogleOAuthProvider>
  )
}
