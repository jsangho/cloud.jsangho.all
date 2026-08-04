import type { NextRequest } from "next/server";
import { fetchProfileWithToken } from "@/lib/auth-api";

type AdminGuardResult = { ok: true } | { ok: false; status: number; detail: string };

/** 액세스 토큰이 담기는 쿠키 이름 — 서버(`core.security.cookie`)와 같아야 한다. */
const ACCESS_COOKIE = "access_token";

/**
 * 어드민 전용 API 라우트 핸들러 맨 앞에서 호출 — 실패 시 그 결과를 그대로 응답으로 반환.
 *
 * 토큰은 **쿠키**에서 꺼낸다. 액세스 토큰이 httpOnly가 되면서 브라우저 JS가
 * `Authorization` 헤더를 붙일 수 없게 됐고, 대신 같은 사이트인 이 라우트로
 * 쿠키가 자동 전송된다. 예전 방식(헤더)도 한동안 함께 받아 준다.
 *
 * 역할 판정은 서버(`/auth/me`)에 맡긴다. JWT를 프론트에서 직접 뜯어 role을 믿으면
 * 서명 검증 없이 권한을 판단하는 셈이 된다.
 */
export async function requireAdmin(req: NextRequest): Promise<AdminGuardResult> {
  const authorization = req.headers.get("authorization");
  const bearer = authorization?.startsWith("Bearer ")
    ? authorization.slice("Bearer ".length).trim()
    : null;
  const token = req.cookies.get(ACCESS_COOKIE)?.value || bearer;

  if (!token) {
    return { ok: false, status: 401, detail: "인증 토큰이 필요합니다." };
  }

  const profile = await fetchProfileWithToken(token);
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
