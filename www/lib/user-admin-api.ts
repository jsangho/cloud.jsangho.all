import { authBaseUrl, requestTimeoutMs } from "@/lib/api";

/**
 * 사용자 관리 — **관리자 전용**.
 *
 * 호스트가 `authBaseUrl`인 것은 사용자가 `auth` 앱의 것이기 때문이다(`/auth/me`와 같은
 * 곳). 토큰은 httpOnly 쿠키라 `credentials: "include"`로 실어 보낸다.
 */

export type AdminUser = {
  userId: number;
  loginId: string;
  nickname: string;
  /** 카카오 이메일 미동의 계정은 없다. */
  email: string | null;
  role: string;
  oauthProvider: string | null;
};

export type AdminUserList = {
  items: AdminUser[];
  /** 관리자 수. 화면이 "마지막 관리자"를 미리 알려 주는 근거다. */
  admins: number;
};

async function parseError(res: Response, fallback: string): Promise<Error> {
  const data = (await res.json().catch(() => null)) as { detail?: string } | null;
  return new Error(data?.detail ?? `${fallback} (${res.status})`);
}

export async function fetchAdminUsers(query?: string): Promise<AdminUserList> {
  const params = new URLSearchParams();
  if (query) params.set("q", query);
  const suffix = params.toString() ? `?${params.toString()}` : "";
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), requestTimeoutMs);
  try {
    const res = await fetch(`${authBaseUrl}/auth/admin/users${suffix}`, {
      credentials: "include",
      signal: controller.signal,
    });
    if (!res.ok) throw await parseError(res, "사용자 목록을 불러오지 못했습니다");
    const data = (await res.json()) as Partial<AdminUserList>;
    return {
      items: Array.isArray(data.items) ? data.items : [],
      admins: data.admins ?? 0,
    };
  } finally {
    clearTimeout(timer);
  }
}

/**
 * 역할 변경. 서버가 거절하는 경우가 둘 있고 **둘 다 409**다 —
 * 자기 자신의 관리자 권한을 뗄 때, 마지막 관리자를 뗄 때. 그 문구를 그대로 보여준다.
 */
export async function changeUserRole(userId: number, role: "user" | "admin"): Promise<AdminUser> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), requestTimeoutMs);
  try {
    const res = await fetch(`${authBaseUrl}/auth/admin/users/${userId}/role`, {
      method: "PATCH",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ role }),
      signal: controller.signal,
    });
    if (!res.ok) throw await parseError(res, "역할을 바꾸지 못했습니다");
    return (await res.json()) as AdminUser;
  } finally {
    clearTimeout(timer);
  }
}
