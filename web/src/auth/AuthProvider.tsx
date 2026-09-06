import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react"
import { GoogleLogin, GoogleOAuthProvider, googleLogout } from "@react-oauth/google"
import { useQueryClient } from "@tanstack/react-query"
import { ApiError, getMe, setAuthToken, setViewAsRole as setViewAsRoleHeader } from "@/api/client"
import type { UserContext, ViewableRole } from "@/api/types"

// GIS ID tokens expire ~1h; sessionStorage (not localStorage) matches that -- the
// session ends with the tab, same as the token would anyway (docs/DECISIONS.md #104).
const TOKEN_KEY = "ouroboros_id_token"
// Judge-only (see AuthState.viewAsRole below) -- harmless to restore for a real
// user too, since the backend ignores this header unless the caller is a judge.
const VIEW_AS_KEY = "ouroboros_view_as_role"
const CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID as string

type Status = "loading" | "signed-out" | "signed-in" | "unauthorized"

interface AuthState {
  user: UserContext
  signOut: () => void
  /** Only meaningful when `user.is_judge` -- null means "no override, full access." */
  viewAsRole: ViewableRole | null
  setViewAsRole: (role: ViewableRole | null) => void
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
  const queryClient = useQueryClient()
  const [status, setStatus] = useState<Status>("loading")
  const [user, setUser] = useState<UserContext | null>(null)
  const [deniedReason, setDeniedReason] = useState<string | null>(null)
  const [viewAsRole, setViewAsRoleState] = useState<ViewableRole | null>(null)

  const resolveSession = useCallback(async (token: string, restoredViewAs: string | null) => {
    setAuthToken(token)
    setViewAsRoleHeader(restoredViewAs)
    try {
      const me = await getMe()
      sessionStorage.setItem(TOKEN_KEY, token)
      setUser(me)
      // A real (non-judge) user's view-as header is inert server-side, but don't
      // show a switcher state for them -- drop anything restored for a session
      // that turns out not to be a judge after all.
      setViewAsRoleState(me.is_judge ? (restoredViewAs as ViewableRole | null) : null)
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
      void resolveSession(stored, sessionStorage.getItem(VIEW_AS_KEY))
    } else {
      setStatus("signed-out")
    }
  }, [resolveSession])

  const signOut = useCallback(() => {
    setAuthToken(null)
    setViewAsRoleHeader(null)
    sessionStorage.removeItem(TOKEN_KEY)
    sessionStorage.removeItem(VIEW_AS_KEY)
    googleLogout()
    setUser(null)
    setViewAsRoleState(null)
    setDeniedReason(null)
    setStatus("signed-out")
  }, [])

  // Changing role re-gates both the UI (canRun/canOverride checks read user.role)
  // and every backend call (the header get_current_user reads) -- so every
  // in-flight query result is for the wrong role the instant this changes, and
  // must be thrown away rather than just refetched with stale cached data shown
  // in between.
  const setViewAsRole = useCallback(
    (role: ViewableRole | null) => {
      setViewAsRoleHeader(role)
      if (role) sessionStorage.setItem(VIEW_AS_KEY, role)
      else sessionStorage.removeItem(VIEW_AS_KEY)
      setViewAsRoleState(role)
      queryClient.removeQueries()
      void getMe()
        .then(setUser)
        .catch(() => {
          /* /me itself never varies by view-as role, so a failure here is a real
           * connectivity problem, not something to reflect in the role switcher. */
        })
    },
    [queryClient],
  )

  if (status === "loading") return null
  if (status !== "signed-in" || !user) {
    return (
      <SignInScreen
        reason={deniedReason}
        onCredential={(token) => void resolveSession(token, null)}
      />
    )
  }

  return (
    <AuthContext.Provider value={{ user, signOut, viewAsRole, setViewAsRole }}>
      {children}
    </AuthContext.Provider>
  )
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
