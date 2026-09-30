import { NextResponse, type NextRequest } from "next/server";

/**
 * 호스트로 첫 화면을 가른다 (2026-09-30).
 *
 * - `www.jsangho.cloud` · `jsangho.cloud` → 개인 포트폴리오 (`app/page.tsx`)
 * - `kayfabe.jsangho.cloud`               → KAYFABE 제품 (`app/(kayfabe)/…`)
 *
 * **배포는 하나다.** 도메인만 둘이고 코드는 같은 Next.js 앱이라, 갈림은 여기서만
 * 일어난다. 로컬(`localhost`)과 Vercel 프리뷰는 어느 분기에도 안 걸리므로
 * 포트폴리오는 `/`, 제품 홈은 `/kayfabe`, 나머지 제품 경로는 그대로 열린다 —
 * 한 서버에서 양쪽을 다 볼 수 있다.
 */

const PROJECT_HOST = "kayfabe.jsangho.cloud";
const PORTFOLIO_HOSTS = new Set(["www.jsangho.cloud", "jsangho.cloud"]);

/** KAYFABE가 소유한 경로. `app/(kayfabe)/` 아래 디렉터리와 같은 목록이다. */
const PROJECT_PATHS = [
  "/kayfabe",
  "/ple",
  "/rankings",
  "/records",
  "/results",
  "/shop",
  "/data-center",
  "/ai-lab",
  "/chat",
  "/admin",
  "/lesson",
  "/my-info",
  "/login",
];

function isProjectPath(pathname: string): boolean {
  return PROJECT_PATHS.some((p) => pathname === p || pathname.startsWith(`${p}/`));
}

export function middleware(request: NextRequest) {
  const host = request.headers.get("host") ?? "";
  const { pathname, search } = request.nextUrl;

  /* 프로젝트 호스트의 루트는 제품 홈을 그린다. **리다이렉트가 아니라 rewrite**라
     주소창은 `kayfabe.jsangho.cloud/`로 남는다. 레이아웃은 내부 경로(`/kayfabe`)로
     정해지므로 제품 내비게이션이 정상으로 붙는다. */
  if (host === PROJECT_HOST && pathname === "/") {
    return NextResponse.rewrite(new URL("/kayfabe", request.url));
  }

  /* www로 들어온 제품 경로는 제품 호스트로 넘긴다.
     **307(임시)이다.** 301은 브라우저가 영구 캐시해서 되돌리기가 어렵다 —
     주소 구성이 굳은 뒤에 308로 올린다. */
  if (PORTFOLIO_HOSTS.has(host) && isProjectPath(pathname)) {
    return NextResponse.redirect(new URL(`${pathname}${search}`, `https://${PROJECT_HOST}`), 307);
  }

  return NextResponse.next();
}

export const config = {
  /* `/api`와 정적 자산은 건드리지 않는다 — 마지막 `.*\..*`가 확장자 있는 요청
     (이미지·폰트·mp4)을 통째로 뺀다. */
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico|.*\\..*).*)"],
};
