import { defineConfig, devices } from "@playwright/test";

/**
 * 브라우저 E2E — **커리어 경기 기록 화면만** 본다(Phase 1 P2).
 *
 * 서버 둘을 띄운다.
 *
 *   API   `fastapi/apps/kayfabe/tests/e2e/career_match_e2e_server.py` — 진짜 라우터 ·
 *         유스케이스 · 세이브 코덱에 메모리 저장소와 테스트 쿠키 인증을 끼운 것.
 *         운영 DB·운영 계정을 모른다.
 *   웹    `next dev` — `NEXT_PUBLIC_*` 를 위 API 로 돌린다. `.env.local` 보다 프로세스
 *         환경이 이긴다(Next 규칙)라 개발자 설정을 건드리지 않는다.
 *
 * **둘 다 127.0.0.1 이다.** 포트만 다르면 같은 사이트라 `SameSite=Lax` 테스트 쿠키가
 * 교차 출처 fetch 에 실린다(localhost 와 섞으면 실리지 않는다).
 *
 * API 서버가 세이브를 메모리에 들고 있고 테스트가 주차를 진행하므로 **직렬로 돈다**
 * (`workers: 1`). 테스트마다 `/__e2e/reset` 으로 처음 상태로 되돌린다.
 *
 * ```bash
 * cd www && pnpm test:e2e
 * ```
 */
const API_PORT = 8765;
const WEB_PORT = 3100;
export const API_ORIGIN = `http://127.0.0.1:${API_PORT}`;
const WEB_ORIGIN = `http://127.0.0.1:${WEB_PORT}`;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 60_000,
  expect: { timeout: 15_000 },
  reporter: [["list"]],
  outputDir: ".next/e2e-results",
  use: {
    baseURL: WEB_ORIGIN,
    trace: "retain-on-failure",
  },
  // `channel: "chromium"` — 헤드리스에서도 **정식 Chromium** 을 쓴다. 기본값은 별도
  // 빌드(`chromium-headless-shell`)를 하나 더 받아야 한다.
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"], channel: "chromium" } }],
  webServer: [
    {
      command: `cd ../fastapi && PYTHONPATH=apps:. uv run python apps/kayfabe/tests/e2e/career_match_e2e_server.py --port ${API_PORT} --origin ${WEB_ORIGIN}`,
      url: `${API_ORIGIN}/docs`,
      timeout: 180_000,
      reuseExistingServer: false,
    },
    {
      command: `pnpm exec next dev -p ${WEB_PORT} -H 127.0.0.1`,
      url: `${WEB_ORIGIN}/sandbox/careers`,
      timeout: 180_000,
      reuseExistingServer: false,
      env: {
        NEXT_PUBLIC_API_BASE_URL: API_ORIGIN,
        NEXT_PUBLIC_AUTH_BASE_URL: API_ORIGIN,
      },
    },
  ],
});
