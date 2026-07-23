import type { NextRequest } from "next/server";
import { decodeJwtUserId, fetchUserProfile } from "@/lib/auth-api";

type AdminGuardResult = { ok: true } | { ok: false; status: number; detail: string };

/** 어드민 전용 API 라우트 핸들러 맨 앞에서 호출 — 실패 시 그 결과를 그대로 응답으로 반환 */
export async function requireAdmin(req: NextRequest): Promise<AdminGuardResult> {
  const authorization = req.headers.get("authorization");
  const token = authorization?.startsWith("Bearer ")
    ? authorization.slice("Bearer ".length).trim()
    : null;
  if (!token) {
    return { ok: false, status: 401, detail: "인증 토큰이 필요합니다." };
  }

  const userId = decodeJwtUserId(token);
  if (userId == null) {
    return { ok: false, status: 401, detail: "유효하지 않은 토큰입니다." };
  }

  const profile = await fetchUserProfile(userId, token);
  if (!profile) {
    return {
      ok: false,
      status: 401,
      detail: "인증 토큰이 유효하지 않거나 만료됐습니다.",
    };
  }
  if (profile.role !== "admin") {
    return { ok: false, status: 403, detail: "관리자만 접근할 수 있습니다." };
  }

  return { ok: true };
}
