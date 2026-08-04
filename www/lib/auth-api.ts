import { authBaseUrl, requestTimeoutMs } from "@/lib/api";
import type { AuthUser } from "@/context/auth-context";

export type AuthProfile = AuthUser;

type UserProfileJson = {
  userId?: number;
  id?: number;
  loginId?: string;
  login_id?: string;
  nickname?: string;
  email?: string | null;
  role?: string;
  oauthProvider?: string | null;
};

export function parseUserProfile(data: UserProfileJson | null): AuthProfile | null {
  if (!data) return null;
  const id = data.userId ?? data.id;
  const nickname = data.nickname?.trim();
  const role = data.role?.trim();
  // 이메일은 필수가 아니다 — 카카오 이메일은 선택 동의 항목이라 없는 계정이
  // 정상적으로 존재한다. 예전에는 `!email`이면 프로필을 통째로 버려서
  // 그런 계정의 웹 로그인이 실패했다.
  if (id == null || !nickname || !role) return null;
  return {
    id,
    loginId: (data.loginId ?? data.login_id ?? "").trim() || undefined,
    nickname,
    email: data.email?.trim() || undefined,
    role,
    oauthProvider: data.oauthProvider?.trim() || undefined,
  };
}

/**
 * 인증 게이트웨이 호출 옵션 — 쿠키를 반드시 함께 보낸다.
 *
 * httpOnly 쿠키는 `credentials: "include"` 없이는 교차 출처 요청에 실리지 않는다.
 * (프론트는 `jsangho.cloud`, 게이트웨이는 `auth.jsangho.cloud`)
 */
function credentialed(signal: AbortSignal, init: RequestInit = {}): RequestInit {
  return { ...init, credentials: "include", signal };
}

async function withTimeout<T>(run: (signal: AbortSignal) => Promise<T>, fallback: T): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), requestTimeoutMs);
  try {
    return await run(controller.signal);
  } catch {
    return fallback;
  } finally {
    clearTimeout(timer);
  }
}

/**
 * 현재 로그인한 사용자. 로그인하지 않았으면 `null`.
 *
 * 액세스 토큰이 httpOnly 쿠키에 있어 JS가 읽을 수 없으므로, "나는 누구인가"는
 * 서버에 물어야 한다.
 */
export function fetchMyProfile(): Promise<AuthProfile | null> {
  return withTimeout(async (signal) => {
    const response = await fetch(`${authBaseUrl}/auth/me`, credentialed(signal));
    if (!response.ok) return null;
    return parseUserProfile((await response.json()) as UserProfileJson);
  }, null);
}

/**
 * 주어진 토큰으로 프로필을 조회한다 — **서버사이드(Route Handler) 전용**.
 *
 * 브라우저에서는 쿠키가 자동으로 실려 `fetchMyProfile`을 쓰면 되지만, Next.js
 * 라우트 핸들러는 받은 쿠키 값을 직접 꺼내 게이트웨이로 넘겨야 한다.
 */
export function fetchProfileWithToken(token: string): Promise<AuthProfile | null> {
  return withTimeout(async (signal) => {
    const response = await fetch(`${authBaseUrl}/auth/me`, {
      signal,
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!response.ok) return null;
    return parseUserProfile((await response.json()) as UserProfileJson);
  }, null);
}

/**
 * 서버 세션을 끊고 쿠키를 지운다.
 *
 * 예전에는 localStorage만 비워서 **서버 세션과 쿠키가 그대로 살아 있었다.**
 * 쿠키 방식에서는 그러면 새로고침 한 번에 다시 로그인 상태가 된다.
 */
export function logoutSession(): Promise<boolean> {
  return withTimeout(async (signal) => {
    const response = await fetch(
      `${authBaseUrl}/auth/logout`,
      credentialed(signal, { method: "POST" }),
    );
    return response.ok;
  }, false);
}
