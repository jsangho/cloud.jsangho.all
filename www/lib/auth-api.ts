import { apiBaseUrl, requestTimeoutMs } from "@/lib/api";
import type { AuthUser } from "@/context/auth-context";

type UserProfileJson = {
  userId?: number;
  id?: number;
  loginId?: string;
  login_id?: string;
  nickname?: string;
  email?: string;
  role?: string;
};

export function parseUserProfile(
  data: UserProfileJson | null,
): AuthUser | null {
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

export async function fetchUserProfile(
  userId: number,
): Promise<AuthUser | null> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), requestTimeoutMs);
  try {
    const response = await fetch(`${apiBaseUrl}/api/users/${userId}`, {
      signal: controller.signal,
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
