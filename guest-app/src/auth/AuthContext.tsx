import AsyncStorage from "@react-native-async-storage/async-storage";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { api } from "../api/client";
import type { AuthUser } from "../types";

const KEY = "sd_guest_auth";

interface AuthState {
  user: AuthUser | null;
  ready: boolean;
  login: (email: string) => Promise<AuthUser>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    void (async () => {
      try {
        const raw = await AsyncStorage.getItem(KEY);
        if (raw) {
          const parsed = JSON.parse(raw) as AuthUser;
          if (parsed.role === "guest" && parsed.guest_id) setUser(parsed);
        }
      } finally {
        setReady(true);
      }
    })();
  }, []);

  const login = useCallback(async (email: string) => {
    const u = await api.login(email.trim());
    if (u.role !== "guest" || !u.guest_id) {
      throw new Error("This login is for guests only. Use the Admin Portal for staff/drivers.");
    }
    await AsyncStorage.setItem(KEY, JSON.stringify(u));
    setUser(u);
    return u;
  }, []);

  const logout = useCallback(async () => {
    await AsyncStorage.removeItem(KEY);
    setUser(null);
  }, []);

  const value = useMemo(() => ({ user, ready, login, logout }), [user, ready, login, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth outside provider");
  return ctx;
}
