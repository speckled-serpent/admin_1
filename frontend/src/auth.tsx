import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import { api } from "./api";
import type { LoginResult } from "./types";

const TOKEN_KEY = "admin1.token";

type AuthContextValue = {
  token: string | null;
  username: string | null;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  setUsername: (username: string | null) => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() => sessionStorage.getItem(TOKEN_KEY));
  const [username, setUsername] = useState<string | null>(null);

  const value = useMemo<AuthContextValue>(
    () => ({
      token,
      username,
      setUsername,
      async login(nextUsername: string, password: string) {
        const result = await api<LoginResult>("/api/auth/login", {
          method: "POST",
          body: JSON.stringify({ username: nextUsername, password }),
        });
        sessionStorage.setItem(TOKEN_KEY, result.token);
        setToken(result.token);
        setUsername(result.username);
      },
      async logout() {
        const current = sessionStorage.getItem(TOKEN_KEY);
        sessionStorage.removeItem(TOKEN_KEY);
        setToken(null);
        setUsername(null);
        if (current) {
          try {
            await api<void>("/api/auth/logout", { method: "POST" }, current);
          } catch {
            // The local session is already cleared.
          }
        }
      },
    }),
    [token, username],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (!value) {
    throw new Error("useAuth must be used inside AuthProvider");
  }
  return value;
}
