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
import { fetchUserProfile } from "@/lib/auth-api";

export type AuthUser = {
  /** 로그인 API userId — 예측·순위 집계에 필요 */
  id: number;
  /** 로그인 ID (표시용 아님) */
  loginId?: string;
  /** 내비·순위표에 표시하는 이름 */
  nickname: string;
  email: string;
  role: string;
  /** 서버가 검증하는 JWT 액세스 토큰 — 보호된 API 호출 시 Authorization 헤더로 전달 */
  token: string;
};

type AuthContextValue = {
  user: AuthUser | null;
  isReady: boolean;
  login: (user: AuthUser) => void;
  logout: () => void;
};

const AUTH_STORAGE_KEY = "kayfabe-auth";

const AuthContext = createContext<AuthContextValue | null>(null);

function isAuthUser(value: unknown): value is AuthUser {
  if (!value || typeof value !== "object") return false;
  const u = value as Partial<AuthUser>;
  return (
    typeof u.id === "number" &&
    typeof u.nickname === "string" &&
    u.nickname.length > 0 &&
    typeof u.email === "string" &&
    typeof u.role === "string" &&
    typeof u.token === "string" &&
    u.token.length > 0
  );
}

function persistUser(user: AuthUser) {
  localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(user));
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isReady, setIsReady] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function hydrate() {
      try {
        const raw = localStorage.getItem(AUTH_STORAGE_KEY);
        if (!raw) return;
        const parsed: unknown = JSON.parse(raw);
        if (!isAuthUser(parsed)) {
          localStorage.removeItem(AUTH_STORAGE_KEY);
          return;
        }
        setUser(parsed);

        const fresh = await fetchUserProfile(parsed.id, parsed.token);
        if (cancelled) return;
        if (!fresh) {
          // 토큰이 만료·무효 — 세션 종료
          localStorage.removeItem(AUTH_STORAGE_KEY);
          setUser(null);
          return;
        }
        const nextUser: AuthUser = { ...fresh, token: parsed.token };
        setUser(nextUser);
        persistUser(nextUser);
      } catch {
        localStorage.removeItem(AUTH_STORAGE_KEY);
      } finally {
        if (!cancelled) setIsReady(true);
      }
    }

    void hydrate();
    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback((nextUser: AuthUser) => {
    persistUser(nextUser);
    setUser(nextUser);
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem(AUTH_STORAGE_KEY);
    setUser(null);
  }, []);

  const value = useMemo(() => ({ user, isReady, login, logout }), [user, isReady, login, logout]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}

/** 내비·UI에 쓸 표시 이름 — 로그인 ID가 아닌 닉네임만 */
export function authDisplayName(user: AuthUser): string {
  return user.nickname.trim();
}
