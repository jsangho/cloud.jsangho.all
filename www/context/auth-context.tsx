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
import { fetchMyProfile, logoutSession } from "@/lib/auth-api";

export type AuthUser = {
  /** 로그인 API userId — 예측·순위 집계에 필요 */
  id: number;
  /** 로그인 ID (표시용 아님) */
  loginId?: string;
  /** 내비·순위표에 표시하는 이름 */
  nickname: string;
  /** 카카오 이메일은 선택 동의라 없을 수 있다 — 화면 필수 요소로 만들지 않는다 */
  email?: string;
  role: string;
  /** SNS 로그인 제공자(naver/kakao/google) — 이메일/비밀번호 로그인이면 undefined */
  oauthProvider?: string;
};

type AuthContextValue = {
  user: AuthUser | null;
  isReady: boolean;
  /** 로그인 직후 프로필을 반영한다. 토큰은 서버가 쿠키로 관리하므로 받지 않는다. */
  login: (user: AuthUser) => void;
  logout: () => void;
  /** 서버에 현재 세션을 다시 물어 상태를 맞춘다 (OAuth 팝업 복귀 등). */
  refresh: () => Promise<AuthUser | null>;
};

/**
 * 표시용 프로필 캐시. **토큰은 들어가지 않는다** — 액세스 토큰은 httpOnly
 * 쿠키에만 있고 JS가 읽을 수 없다. 이 값은 첫 화면을 빠르게 그리기 위한
 * 캐시일 뿐이고, 진짜 로그인 여부는 항상 서버(`/auth/me`)가 정한다.
 */
const PROFILE_CACHE_KEY = "kayfabe-profile";

const AuthContext = createContext<AuthContextValue | null>(null);

function isAuthUser(value: unknown): value is AuthUser {
  if (!value || typeof value !== "object") return false;
  const u = value as Partial<AuthUser>;
  return (
    typeof u.id === "number" &&
    typeof u.nickname === "string" &&
    u.nickname.length > 0 &&
    typeof u.role === "string"
  );
}

function cacheProfile(user: AuthUser | null) {
  if (user) {
    localStorage.setItem(PROFILE_CACHE_KEY, JSON.stringify(user));
  } else {
    localStorage.removeItem(PROFILE_CACHE_KEY);
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isReady, setIsReady] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function hydrate() {
      // ① 캐시로 즉시 그린다 (깜빡임 방지). 아직 확정 아님.
      try {
        const raw = localStorage.getItem(PROFILE_CACHE_KEY);
        const parsed: unknown = raw ? JSON.parse(raw) : null;
        if (isAuthUser(parsed)) setUser(parsed);
        else localStorage.removeItem(PROFILE_CACHE_KEY);
      } catch {
        localStorage.removeItem(PROFILE_CACHE_KEY);
      }

      // ② 서버가 최종 판정한다. 쿠키가 없거나 만료면 null.
      const fresh = await fetchMyProfile();
      if (cancelled) return;
      setUser(fresh);
      cacheProfile(fresh);
      setIsReady(true);
    }

    void hydrate();
    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback((nextUser: AuthUser) => {
    cacheProfile(nextUser);
    setUser(nextUser);
  }, []);

  const logout = useCallback(() => {
    // 서버 응답을 기다리지 않고 화면부터 로그아웃 상태로 만든다 —
    // 서버가 느리거나 죽어도 사용자에게는 로그아웃이 되어야 한다.
    cacheProfile(null);
    setUser(null);
    void logoutSession();
  }, []);

  const refresh = useCallback(async () => {
    const fresh = await fetchMyProfile();
    setUser(fresh);
    cacheProfile(fresh);
    return fresh;
  }, []);

  const value = useMemo(
    () => ({ user, isReady, login, logout, refresh }),
    [user, isReady, login, logout, refresh],
  );

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
