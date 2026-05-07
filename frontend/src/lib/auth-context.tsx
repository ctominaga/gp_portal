"use client";

import { useRouter } from "next/navigation";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import { api, getToken, setToken } from "@/lib/api";
import type { TokenResponse, User } from "@/lib/types";

interface AuthState {
  user: User | null;
  loading: boolean;
}

interface AuthContextValue extends AuthState {
  login: (email: string, password: string) => Promise<User>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [state, setState] = useState<AuthState>({ user: null, loading: true });

  const refresh = useCallback(async () => {
    const t = getToken();
    if (!t) {
      setState({ user: null, loading: false });
      return;
    }
    try {
      const r = await api.get<User>("/auth/me");
      setState({ user: r.data, loading: false });
    } catch {
      setToken(null);
      setState({ user: null, loading: false });
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const login = useCallback(
    async (email: string, password: string) => {
      const r = await api.post<TokenResponse>("/auth/login", { email, password });
      setToken(r.data.access_token);
      setState({ user: r.data.user, loading: false });
      return r.data.user;
    },
    [],
  );

  const logout = useCallback(() => {
    setToken(null);
    setState({ user: null, loading: false });
    router.push("/login");
  }, [router]);

  const value = useMemo<AuthContextValue>(
    () => ({ ...state, login, logout }),
    [state, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth fora de AuthProvider");
  return ctx;
}
