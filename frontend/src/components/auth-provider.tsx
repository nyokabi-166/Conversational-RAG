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
  const [user, setUser] = useState<UserProfile | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [ready, setReady] = useState(false);
  const [auth0Session, setAuth0Session] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const restoreSession = async () => {
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
              setAuth0Session(true);
              setReady(true);
            }
            return;
          }
        }
      } catch {
        // Fall back to the existing email/password session below.
      }

      const storedToken = sessionStorage.getItem(TOKEN_KEY);
      if (storedToken) {
        try {
          const profile = await apiRequest<UserProfile>("/auth/me", {}, storedToken);
          if (!cancelled) {
            setToken(storedToken);
            setUser(profile);
          }
        } catch {
          sessionStorage.removeItem(TOKEN_KEY);
        }
      }
      if (!cancelled) setReady(true);
    };
    void restoreSession();
    return () => {
      cancelled = true;
    };
  }, []);

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
      setAuth0Session(false);
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
      setAuth0Session(false);
      return profile;
    },
    [],
  );

  const signOut = useCallback(() => {
    sessionStorage.removeItem(TOKEN_KEY);
    sessionStorage.removeItem("rag_guest_conversation_id");
    setToken(null);
    setUser(null);
    if (auth0Session) {
      window.location.assign("/auth/logout?returnTo=%2F");
    }
  }, [auth0Session]);

  const value = useMemo(
    () => ({ user, token, ready, signIn, register, signOut }),
    [user, token, ready, signIn, register, signOut],
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
