import { NextResponse, type NextRequest } from "next/server";

/**
 * 호스트로 첫 화면을 가른다 (2026-09-30).
 *
 * - `www.jsangho.cloud` · `jsangho.cloud` → 개인 포트폴리오 (`app/page.tsx`)
 * - `kayfabe.jsangho.cloud`               → KAYFABE 제품 (`app/(kayfabe)/…`)
 * - `supersub.jsangho.cloud`              → Super-Sub 목업 데모 (`app/(supersub)/s/…`)
 *
 * **배포는 하나다.** 도메인만 셋이고 코드는 같은 Next.js 앱이라, 갈림은 여기서만
 * 일어난다. 로컬(`localhost`)과 Vercel 프리뷰는 어느 분기에도 안 걸리므로
 * 포트폴리오는 `/`, 제품 홈은 `/kayfabe`, 나머지 제품 경로는 그대로 열린다 —
 * 한 서버에서 양쪽을 다 볼 수 있다.
 */

const PROJECT_HOST = "kayfabe.jsangho.cloud";
const PORTFOLIO_HOSTS = new Set(["www.jsangho.cloud", "jsangho.cloud"]);

/**
 * Super-Sub 는 **통째로 한 칸 아래**(`/s`)에 산다 — 2026-10-06.
 *
 * 그 제품은 원래 최상위에 살았는데(`/`·`/home`·`/login`·`/admin`), 이 앱에서는
 * 🔴 **`/login` 과 `/admin` 을 KAYFABE 가 이미 쓰고 있고**, API 쪽은 더 나빠서
 * `/api/auth/*`(NextAuth) 와 `/api/chat` 이 **정면으로 겹친다.** 그래서 파일은
 * `app/(supersub)/s/…` · `app/api/supersub/…` 에 두고, 이 호스트로 들어온 요청만
 * 여기서 그 아래로 **rewrite** 한다.
 *
 * ✅ **리다이렉트가 아니라 rewrite 라** 주소창은 `supersub.jsangho.cloud/home` 으로
 * 남는다. 그래서 옮겨 온 제품 코드의 `href="/home"` 을 **한 줄도 안 고쳤다.**
 * 대신 `usePathname()` 이 `/s/home` 을 돌려줄 수 있으므로 그쪽은
 * `supersub/lib/ssPathname.ts` 가 접두사를 떼어 맞춘다.
 */
const SUPERSUB_HOST = "supersub.jsangho.cloud";
const SUPERSUB_PREFIX = "/s";
const SUPERSUB_API_PREFIX = "/api/supersub";

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

  /* Super-Sub 호스트는 **들어온 것을 전부** 한 칸 아래로 보낸다. API 가 먼저다 —
     `/api/…` 도 `/s/api/…` 가 아니라 `/api/supersub/…` 로 가야 Route Handler 가
     잡는다(라우트 그룹은 주소에 안 나타나지만 `api` 는 실제 폴더다). */
  if (host === SUPERSUB_HOST) {
    if (pathname.startsWith("/api/")) {
      return NextResponse.rewrite(
        new URL(`${SUPERSUB_API_PREFIX}${pathname.slice(4)}${search}`, request.url),
      );
    }
    return NextResponse.rewrite(
      new URL(`${SUPERSUB_PREFIX}${pathname === "/" ? "" : pathname}${search}`, request.url),
    );
  }

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
  /* 정적 자산은 건드리지 않는다 — 마지막 `.*\..*`가 확장자 있는 요청
     (이미지·폰트·mp4)을 통째로 뺀다. Super-Sub 의 `public/` 자산이 `/demo.mp4`
     처럼 최상위 이름이라, 이 제외가 그대로 그 파일들을 지켜 준다. */
  matcher: [
    "/((?!api|_next/static|_next/image|favicon.ico|.*\\..*).*)",
    /* 🔴 `/api` 를 **다시 들여놓는다** (2026-10-06). Super-Sub 의 BFF 경로를
       호스트별로 갈라 주려면 미들웨어가 그 요청을 봐야 한다. 다른 호스트에서는
       위 분기 어디에도 안 걸려 `next()` 로 그냥 지나가므로, NextAuth(`/api/auth/*`)
       와 포트폴리오의 `/api/chat` 은 **동작이 바뀌지 않는다.** */
    "/api/:path*",
  ],
};
