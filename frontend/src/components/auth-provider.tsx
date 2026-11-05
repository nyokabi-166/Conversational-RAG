"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { usePathname } from "next/navigation";
import { apiRequest, type TokenResponse, type UserProfile } from "@/lib/api";

interface AuthContextValue {
  user: UserProfile | null;
  token: string | null;
  ready: boolean;
  signIn: (
    accountType: "passenger" | "staff",
    identifier: string,
    password: string,
  ) => Promise<UserProfile>;
  register: (
    email: string,
    password: string,
    fullName: string,
  ) => Promise<UserProfile>;
  signOut: () => void;
  switchAccount: (returnTo: string) => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);
const TOKEN_KEY = "rag_access_token";

function saveSession(result: TokenResponse) {
  const profile: UserProfile = {
    user_id: result.user_id,
    identifier: result.identifier,
    role: result.role,
    full_name: result.full_name,
  };
  sessionStorage.setItem(TOKEN_KEY, result.access_token);
  return profile;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const isStaffRoute = pathname === "/staff" || pathname.startsWith("/staff/");
  const [user, setUser] = useState<UserProfile | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const restoreSession = async () => {
      const storedToken = sessionStorage.getItem(TOKEN_KEY);
      if (storedToken) {
        try {
          const profile = await apiRequest<UserProfile>("/auth/me", {}, storedToken);
          if (!cancelled) {
            setToken(storedToken);
            setUser(profile);
            setReady(true);
          }
          return;
        } catch {
          sessionStorage.removeItem(TOKEN_KEY);
        }
      }

      // Staff accounts use the application's own credentials. Do not silently
      // exchange a remembered Google passenger session while visiting staff pages.
      if (!isStaffRoute) {
        try {
          const auth0Response = await fetch("/auth/access-token", {
            credentials: "same-origin",
          });
          if (auth0Response.ok) {
            const { token: auth0Token } = (await auth0Response.json()) as {
              token?: string;
            };
            if (auth0Token) {
              const backendSession = await apiRequest<TokenResponse>(
                "/auth/auth0/exchange",
                { method: "POST" },
                auth0Token,
              );
              if (!cancelled) {
                const profile = saveSession(backendSession);
                setToken(backendSession.access_token);
                setUser(profile);
                setReady(true);
              }
              return;
            }
          }
        } catch {
          // Keep the login page available if the Auth0 session cannot be checked.
        }
      }
      if (!cancelled) setReady(true);
    };
    void restoreSession();
    return () => {
      cancelled = true;
    };
  }, [isStaffRoute]);

  const signIn = useCallback(
    async (
      accountType: "passenger" | "staff",
      identifier: string,
      password: string,
    ) => {
      const isPassenger = accountType === "passenger";
      const result = await apiRequest<TokenResponse>(
        isPassenger ? "/auth/passenger/login" : "/auth/staff/login",
        {
          method: "POST",
          body: JSON.stringify(
            isPassenger
              ? { email: identifier, password }
              : { username: identifier, password },
          ),
        },
      );
      const profile = saveSession(result);
      setToken(result.access_token);
      setUser(profile);
      return profile;
    },
    [],
  );

  const register = useCallback(
    async (email: string, password: string, fullName: string) => {
      const result = await apiRequest<TokenResponse>("/auth/register", {
        method: "POST",
        body: JSON.stringify({ email, password, full_name: fullName || null }),
      });
      const profile = saveSession(result);
      setToken(result.access_token);
      setUser(profile);
      return profile;
    },
    [],
  );

  const switchAccount = useCallback((returnTo: string) => {
    sessionStorage.removeItem(TOKEN_KEY);
    sessionStorage.removeItem("rag_guest_conversation_id");
    setToken(null);
    setUser(null);
    const safeReturnTo =
      returnTo.startsWith("/") && !returnTo.startsWith("//") ? returnTo : "/";
    window.location.assign(`/auth/logout?returnTo=${encodeURIComponent(safeReturnTo)}`);
  }, []);

  const signOut = useCallback(() => switchAccount("/"), [switchAccount]);

  const value = useMemo(
    () => ({ user, token, ready, signIn, register, signOut, switchAccount }),
    [user, token, ready, signIn, register, signOut, switchAccount],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used inside AuthProvider.");
  }
  return context;
}
