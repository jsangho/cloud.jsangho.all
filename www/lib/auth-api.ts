import { apiBaseUrl, requestTimeoutMs } from "@/lib/api";
import type { AuthUser } from "@/context/auth-context";

export type AuthProfile = Omit<AuthUser, "token">;

type UserProfileJson = {
  userId?: number;
  id?: number;
  loginId?: string;
  login_id?: string;
  nickname?: string;
  email?: string;
  role?: string;
};

export function parseUserProfile(data: UserProfileJson | null): AuthProfile | null {
  if (!data) return null;
  const id = data.userId ?? data.id;
  const nickname = data.nickname?.trim();
  const email = data.email?.trim();
  const role = data.role?.trim();
  if (id == null || !nickname || !email || !role) return null;
  return {
    id,
    loginId: (data.loginId ?? data.login_id ?? "").trim() || undefined,
    nickname,
    email,
    role,
  };
}

/** JWT payload를 서명 검증 없이 읽어 표시용 값(sub 등)만 꺼낼 때 사용 — 실제 인증은 서버가 검증 */
function decodeJwtPayload(token: string): Record<string, unknown> | null {
  const segment = token.split(".")[1];
  if (!segment) return null;
  try {
    const base64 = segment.replace(/-/g, "+").replace(/_/g, "/");
    const padded = base64.padEnd(base64.length + ((4 - (base64.length % 4)) % 4), "=");
    return JSON.parse(atob(padded)) as Record<string, unknown>;
  } catch {
    return null;
  }
}

export function decodeJwtUserId(token: string): number | null {
  const sub = decodeJwtPayload(token)?.sub;
  if (typeof sub !== "string") return null;
  const id = Number(sub);
  return Number.isFinite(id) ? id : null;
}

export async function fetchUserProfile(userId: number, token: string): Promise<AuthProfile | null> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), requestTimeoutMs);
  try {
    const response = await fetch(`${apiBaseUrl}/api/users/${userId}`, {
      signal: controller.signal,
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!response.ok) return null;
    const data = (await response.json()) as UserProfileJson;
    return parseUserProfile(data);
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}
