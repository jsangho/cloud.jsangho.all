export const apiBaseUrl =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";

/** apps/auth 단독 게이트웨이. 로그인/리프레시/OAuth는 여기로 간다. */
export const authBaseUrl =
  process.env.NEXT_PUBLIC_AUTH_BASE_URL || "http://127.0.0.1:8001";

export const titanicApiBaseUrl = `${apiBaseUrl}/api/titanic`;
export const pleEventsBaseUrl = `${apiBaseUrl}/api/ple_events`;
export const pleMatchPicksBaseUrl = `${apiBaseUrl}/api/ple-match-picks`;
export const pleMatchesBaseUrl = `${apiBaseUrl}/api/ple-matches`;
export const titleAcquisitionsBaseUrl = `${apiBaseUrl}/api/title-acquisitions`;

/**
 * Gemini 채팅 엔드포인트.
 * Vercel 등 프론트만 배포할 때는 같은 출처 `/api/chat`(Next Route Handler)을 씁니다.
 * 로컬에서 FastAPI `/chat`을 쓰려면 `.env.local`에
 * `NEXT_PUBLIC_CHAT_API_URL=http://127.0.0.1:8000/chat` 을 설정하세요.
 */
export function getChatEndpoint(): string {
  const explicit = process.env.NEXT_PUBLIC_CHAT_API_URL?.trim();
  if (explicit) return explicit;
  return "/api/chat";
}

/** Neon cold start·원격 DB를 고려한 요청 타임아웃 */
export const requestTimeoutMs = 20000;

type ApiErrorBody = {
  detail?: string | { msg?: string }[];
  message?: string;
};

export function parseApiError(
  data: ApiErrorBody | null,
  status: number,
): string {
  const detail = data?.detail;
  if (typeof detail === "string") {
    return detail;
  }
  if (Array.isArray(detail)) {
    return detail
      .map((item) => item.msg ?? "")
      .filter(Boolean)
      .join("\n");
  }
  return data?.message ?? `서버 오류: ${status}`;
}

/** REACT_RULES §4: 사용자 UI에는 API 원문·입력 echo를 노출하지 않음 */
export function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

export function getRequestTimeoutMessage(): string {
  return `서버 응답이 ${requestTimeoutMs / 1000}초 이상 걸려 요청을 중단했습니다. 백엔드가 켜져 있는지 확인해 주세요.`;
}
