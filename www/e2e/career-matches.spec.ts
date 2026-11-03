import { expect, test, type APIRequestContext, type Page, type Route } from "@playwright/test";

/**
 * 커리어 경기 기록 — 목록 · 상세 Dialog · URL 딥링크 · 뒤로/앞으로 · 주간 보고 링크 ·
 * 늦은 응답과 오류. **실제 P1 API 응답**(테스트 API 서버 — `playwright.config.ts`)을
 * 브라우저가 받는다.
 *
 * 기대값은 화면이 아니라 **API 가 준 값**에서 뽑는다(`api()`). 화면 문구를 기대값으로
 * 박으면 화면이 틀려도 테스트가 그 틀린 값을 따라간다.
 *
 * 인증은 테스트 쿠키다(`kayfabe_e2e_user`). 비밀번호·토큰이 없다.
 */

const API = "http://127.0.0.1:8765";
const BASE = "/sandbox/careers";

type Summary = {
  id: string;
  season: number;
  week: number;
  kind: string;
  teams: string[][];
  winnerSide: number;
  finish: string;
};
type Detail = Summary & {
  scorer: string | null;
  pinned: string | null;
  finisher: string | null;
  participants: {
    name: string;
    side: number;
    before: Record<string, number>;
    after: Record<string, number>;
  }[];
  heat: { a: string; b: string; before: number | null; after: number }[];
  injury: { kind: string; weeksOut: number } | null;
};

async function login(page: Page, userId = 1) {
  await page
    .context()
    .addCookies([
      { name: "kayfabe_e2e_user", value: String(userId), domain: "127.0.0.1", path: "/" },
    ]);
}

async function api<T>(request: APIRequestContext, path: string): Promise<T> {
  const res = await request.get(`${API}/api/sandbox/careers${path}`, {
    headers: { Cookie: "kayfabe_e2e_user=1" },
  });
  expect(res.ok(), `${path} → ${res.status()}`).toBeTruthy();
  return (await res.json()) as T;
}

async function allRecords(request: APIRequestContext, career = 1): Promise<Summary[]> {
  return api<Summary[]>(request, `/${career}/matches?limit=200&offset=0`);
}

const records = (page: Page) => page.getByRole("region", { name: "경기 기록" });
const recordRows = (page: Page) => records(page).getByRole("button", { name: /경기 상세 보기$/ });
const dialog = (page: Page) => page.getByRole("dialog");
const matchParam = (page: Page) => new URL(page.url()).searchParams.get("match");

/** 그 경기의 행 — `S2 W26 경기 상세 보기`. */
const rowOf = (page: Page, m: Pick<Summary, "season" | "week">) =>
  records(page).getByRole("button", { name: `S${m.season} W${m.week} 경기 상세 보기` });

/** 그 URL 로 끝나는 요청을 `ms` 만큼 늦춘다. */
async function delay(page: Page, match: (url: URL) => boolean, ms: number) {
  await page.route(
    (url) => url.origin === API && match(url),
    async (route: Route) => {
      await new Promise((r) => setTimeout(r, ms));
      await route.continue();
    },
  );
}

const pageErrors: string[] = [];

test.beforeEach(async ({ page, request }) => {
  pageErrors.length = 0;
  page.on("pageerror", (e) => pageErrors.push(e.message));
  const reset = await request.post(`${API}/__e2e/reset`);
  expect(reset.ok()).toBeTruthy();
  await login(page);
});

test.afterEach(() => {
  // 어느 시나리오에서도 렌더 오류가 나면 안 된다(요청 중 닫기 포함).
  expect(pageErrors).toEqual([]);
});

// ── A. 경기 목록 ─────────────────────────────────────────────────

test.describe("A. 경기 목록", () => {
  test("최신 경기부터 20건, 싱글·태그, 승리 팀·참가자 순서", async ({ page, request }) => {
    const all = await allRecords(request);
    await page.goto(`${BASE}?career=1&tab=matches`);

    await expect(recordRows(page)).toHaveCount(20);
    // 첫 줄은 API 의 첫 기록(최신)이다.
    await expect(recordRows(page).first()).toHaveAccessibleName(
      `S${all[0].season} W${all[0].week} 경기 상세 보기`,
    );

    const firstPage = all.slice(0, 20);
    const tag = firstPage.find((m) => m.kind === "tag");
    const single = firstPage.find((m) => m.kind !== "tag");
    expect(tag, "첫 쪽에 태그 경기가 있어야 시나리오가 성립한다").toBeTruthy();
    expect(single).toBeTruthy();

    for (const m of [tag!, single!]) {
      const row = rowOf(page, m);
      // 참가자 순서 — 저장 순서 그대로 `A & B vs C & D`.
      await expect(row).toContainText(`${m.teams[0].join(" & ")}vs${m.teams[1].join(" & ")}`);
      await expect(row).toContainText(m.winnerSide === 0 ? "승" : "패");
      await expect(row).toContainText(m.finish);
    }
  });

  test("시즌 필터", async ({ page, request }) => {
    const all = await allRecords(request);
    const s1 = all.filter((m) => m.season === 1);
    await page.goto(`${BASE}?career=1&tab=matches`);
    await expect(recordRows(page)).toHaveCount(20);

    await records(page)
      .getByRole("group", { name: "시즌" })
      .getByRole("button", { name: "시즌 1" })
      .click();

    await expect(recordRows(page).first()).toHaveAccessibleName(`S1 W${s1[0].week} 경기 상세 보기`);
    for (const name of await recordRows(page).evaluateAll((els) =>
      els.map((e) => e.getAttribute("aria-label") ?? ""),
    )) {
      expect(name).toMatch(/^S1 /);
    }
  });

  test("다음 쪽 · 이전 쪽", async ({ page, request }) => {
    const all = await allRecords(request);
    await page.goto(`${BASE}?career=1&tab=matches`);
    await expect(recordRows(page)).toHaveCount(20);

    await page.getByRole("button", { name: "지난 경기 →" }).click();
    await expect(recordRows(page).first()).toHaveAccessibleName(
      `S${all[20].season} W${all[20].week} 경기 상세 보기`,
    );
    await expect(page.getByText("2쪽")).toBeVisible();

    await page.getByRole("button", { name: "← 최근 경기" }).click();
    await expect(recordRows(page).first()).toHaveAccessibleName(
      `S${all[0].season} W${all[0].week} 경기 상세 보기`,
    );
  });

  test("마지막 쪽이 꽉 차 있으면 다음 쪽은 빈 결과로 그린다", async ({ page, request }) => {
    const s2 = (await allRecords(request)).filter((m) => m.season === 2);
    expect(s2).toHaveLength(20); // 데이터가 이 경계를 만들도록 지어졌다(서버 독스트링)
    await page.goto(`${BASE}?career=1&tab=matches`);
    await records(page)
      .getByRole("group", { name: "시즌" })
      .getByRole("button", { name: "시즌 2" })
      .click();
    await expect(recordRows(page)).toHaveCount(20);

    await page.getByRole("button", { name: "지난 경기 →" }).click();

    await expect(records(page).getByText("더 이상 경기가 없습니다.")).toBeVisible();
    await expect(page.getByRole("button", { name: "지난 경기 →" })).toBeDisabled();
    await expect(page.getByRole("button", { name: "← 최근 경기" })).toBeEnabled();
  });

  test("기록이 없는 커리어는 빈 상태", async ({ page }) => {
    await page.goto(`${BASE}?career=2&tab=matches`);
    await expect(records(page).getByText(/아직 상세 기록이 남은 경기가 없습니다/)).toBeVisible();
    await expect(recordRows(page)).toHaveCount(0);
  });

  test("API 오류는 빈 상태와 다르게 그린다", async ({ page }) => {
    await page.route(
      (url) => url.origin === API && /\/matches$/.test(url.pathname),
      (route) => route.fulfill({ status: 500, json: { detail: "세이브를 읽을 수 없습니다" } }),
    );
    await page.goto(`${BASE}?career=1&tab=matches`);
    await expect(records(page).getByRole("alert")).toContainText("세이브를 읽을 수 없습니다");
    await expect(records(page).getByText(/아직 상세 기록/)).toHaveCount(0);
  });
});

// ── B. 경기 상세 Dialog ──────────────────────────────────────────

test.describe("B. 상세 Dialog", () => {
  test("목록에서 태그 경기 — 개요 · 4명 · 전후 표 · 닫기", async ({ page, request }) => {
    const tag = (await allRecords(request)).slice(0, 20).find((m) => m.kind === "tag")!;
    const detail = await api<Detail>(request, `/1/matches/${encodeURIComponent(tag.id)}`);
    await page.goto(`${BASE}?career=1&tab=matches`);

    await rowOf(page, tag).click();

    await expect(dialog(page)).toBeVisible();
    await expect(dialog(page)).toContainText(`S${tag.season} · W${tag.week} — 태그 경기`);
    expect(matchParam(page)).toBe(tag.id);
    const teams = dialog(page).getByRole("region", { name: "참가자" });
    for (const p of detail.participants) await expect(teams).toContainText(p.name);
    // 팀 카드 안 순서 — 저장 순서.
    const names = await teams.locator("li span.font-semibold").allTextContents();
    expect(names).toEqual(detail.participants.map((p) => p.name));
    // 참가자마다 전후 표 하나.
    await expect(dialog(page).getByRole("table")).toHaveCount(4);
    await expect(dialog(page)).toContainText("태그 경기의 개인 전적은 엔진이 실제로 반영한 값");

    await dialog(page).getByRole("button", { name: "Close" }).click();
    await expect(dialog(page)).toBeHidden();
    expect(matchParam(page)).toBeNull();
  });

  test("싱글 경기 · 핀폴 — 핀 승리/핀 패배, 전후 값", async ({ page, request }) => {
    const all = await allRecords(request);
    let pin: Detail | null = null;
    for (const m of all.filter((r) => r.kind !== "tag" && r.finish === "핀폴")) {
      pin = await api<Detail>(request, `/1/matches/${encodeURIComponent(m.id)}`);
      break;
    }
    expect(pin, "데이터에 싱글 핀폴 경기가 있어야 한다").toBeTruthy();
    await page.goto(`${BASE}?career=1&tab=matches&match=${encodeURIComponent(pin!.id)}`);

    await expect(dialog(page)).toBeVisible();
    const teams = dialog(page).getByRole("region", { name: "참가자" });
    await expect(teams.locator("li")).toHaveCount(2);
    await expect(teams.getByText(pin!.scorer!).locator("..")).toContainText("핀 승리");
    await expect(teams.getByText(pin!.pinned!).locator("..")).toContainText("핀 패배");

    // 전후 — 첫 참가자의 인기도 행이 API 값 그대로 (경기 전 / 경기 후).
    const p0 = pin!.participants[0];
    const row = dialog(page)
      .getByRole("table", { name: `${p0.name} 경기 전후 상태` })
      .getByRole("row", { name: /^인기도/ });
    const cells = await row.getByRole("cell").allTextContents();
    expect(cells[0]).toBe(String(p0.before.popularity));
    expect(cells[1]).toBe(String(p0.after.popularity));
    const delta = p0.after.popularity - p0.before.popularity;
    expect(cells[2]).toContain(delta > 0 ? "▲" : delta < 0 ? "▼" : "±0");
  });

  test("비핀폴 — scorer/pinned 표시 없음", async ({ page, request }) => {
    const m = (await allRecords(request)).find((r) => r.finish !== "핀폴")!;
    const detail = await api<Detail>(request, `/1/matches/${encodeURIComponent(m.id)}`);
    expect(detail.scorer).toBeNull();
    await page.goto(`${BASE}?career=1&tab=matches&match=${encodeURIComponent(m.id)}`);

    await expect(dialog(page)).toContainText(detail.finish);
    await expect(dialog(page).getByText("핀 승리")).toHaveCount(0);
    await expect(dialog(page).getByText("핀 패배")).toHaveCount(0);
  });

  test("부상 · 관계 변화", async ({ page, request }) => {
    const all = await allRecords(request);
    let hurt: Detail | null = null;
    for (const m of all) {
      const d = await api<Detail>(request, `/1/matches/${encodeURIComponent(m.id)}`);
      if (d.injury && d.heat.length > 0) {
        hurt = d;
        break;
      }
    }
    expect(hurt, "부상과 관계 변화가 함께 있는 경기").toBeTruthy();
    await page.goto(`${BASE}?career=1&tab=matches&match=${encodeURIComponent(hurt!.id)}`);

    await expect(dialog(page)).toContainText(`부상 — ${hurt!.injury!.kind}`);
    await expect(dialog(page)).toContainText(`결장 ${hurt!.injury!.weeksOut}주`);
    await expect(dialog(page)).toContainText("관계 변화");
    const h = hurt!.heat[0];
    await expect(dialog(page)).toContainText(`${h.a} → ${h.b}`);
  });

  test("기록 없음 사유 — trimmed 와 판정 불가", async ({ page, request }) => {
    const first = (await allRecords(request)).at(-1)!; // 가장 오래된 기록 — 커리어 3 에선 잘렸다
    await page.goto(`${BASE}?career=3&tab=matches&match=${encodeURIComponent(first.id)}`);
    await expect(dialog(page)).toContainText("보존 기간이 지난 경기");

    await page.goto(`${BASE}?career=1&tab=matches&match=nope`);
    await expect(dialog(page)).toContainText("경기 기록을 찾을 수 없습니다");
  });
});

// ── C. URL · 히스토리 ────────────────────────────────────────────

test.describe("C. URL 딥링크 · 히스토리", () => {
  test("딥링크 → 탭 선택 + 자동 열림, 새로고침 유지, 닫으면 match 제거·페이지 유지", async ({
    page,
  }) => {
    await page.goto(`${BASE}?career=1&tab=matches&match=s1w52:p`);

    // 모달이 열려 있으면 Radix 가 바깥을 aria-hidden 으로 감춘다 — 숨은 요소까지 찾는다.
    await expect(
      page.getByRole("button", { name: "경기 · 대진", includeHidden: true }),
    ).toHaveAttribute("aria-current", "page");
    await expect(dialog(page)).toContainText("S1 · W52");

    await page.reload();
    await expect(dialog(page)).toContainText("S1 · W52");

    await dialog(page).getByRole("button", { name: "Close" }).click();
    await expect(dialog(page)).toBeHidden();
    // 딥링크 닫기는 `replace` — 히스토리를 뒤로 옮기지 않는다(앞 페이지로 튕기지 않는다).
    expect(new URL(page.url()).pathname).toBe(BASE);
    expect(matchParam(page)).toBeNull();
    await expect(recordRows(page).first()).toBeVisible();
  });

  test("목록에서 열기 → 뒤로 닫힘 → 앞으로 다시 열림 → 닫기 → 뒤로 가도 재등장 없음", async ({
    page,
    request,
  }) => {
    const m = (await allRecords(request))[3];
    await page.goto(`${BASE}?career=1&tab=matches`);
    await rowOf(page, m).click();
    await expect(dialog(page)).toContainText(`S${m.season} · W${m.week}`);

    await page.goBack();
    await expect(dialog(page)).toBeHidden();
    expect(matchParam(page)).toBeNull();
    expect(new URL(page.url()).pathname).toBe(BASE);

    await page.goForward();
    await expect(dialog(page)).toContainText(`S${m.season} · W${m.week}`);
    expect(matchParam(page)).toBe(m.id);

    await dialog(page).getByRole("button", { name: "Close" }).click();
    await expect(dialog(page)).toBeHidden();
    expect(matchParam(page)).toBeNull();
    expect(new URL(page.url()).pathname).toBe(BASE);

    // 닫은 뒤 뒤로 — 같은 Dialog 가 다시 뜨면 안 된다.
    await page.goBack();
    await page.waitForLoadState();
    expect(new URL(page.url()).searchParams.get("match")).toBeNull();
    await expect(dialog(page)).toHaveCount(0);
  });

  test("다른 탭으로 가면 match 가 정리된다", async ({ page }) => {
    await page.goto(`${BASE}?career=1&tab=matches&match=s1w52:p`);
    await expect(dialog(page)).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(dialog(page)).toBeHidden();

    // 손으로 만든 URL 처럼 다른 탭에 match 가 남아 있어도 열리지 않고, 탭 이동이 지운다.
    await page.goto(`${BASE}?career=1&tab=dashboard&match=s1w52:p`);
    await expect(page.getByRole("button", { name: "대시보드" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    await expect(dialog(page)).toHaveCount(0);
    await page.getByRole("button", { name: "경기 · 대진" }).click();
    await expect(page).toHaveURL(/tab=matches/);
    expect(matchParam(page)).toBeNull();
    await expect(dialog(page)).toHaveCount(0);
  });

  test("커리어 목록으로 돌아가면 목록이 보인다 (match 없이)", async ({ page }) => {
    await page.goto(`${BASE}?career=1&tab=dashboard`);
    await expect(page.getByRole("button", { name: "← 커리어 목록" })).toBeVisible();
    await page.getByRole("button", { name: "← 커리어 목록" }).click();
    await expect(page).not.toHaveURL(/career=/);
    await expect(page.getByRole("heading", { name: "내 커리어" })).toBeVisible();
    await page.waitForTimeout(1000); // 늦게 도는 복구가 앞 커리어를 되살리지 않는지
    await expect(page.getByRole("heading", { name: "내 커리어" })).toBeVisible();
    await expect(page.getByRole("navigation", { name: "커리어 메뉴" })).toHaveCount(0);
  });

  test("다른 커리어로 옮기면 이전 match 가 남지 않는다", async ({ page }) => {
    await page.goto(`${BASE}?career=1&tab=matches&match=s1w52:p`);
    await expect(dialog(page)).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(dialog(page)).toBeHidden();
    // 열린 상태의 match 를 URL 에 다시 얹고(손으로 만든 URL) 목록으로 나간다.
    await page.goto(`${BASE}?career=1&tab=log&match=s1w52:p`);
    await page.getByRole("button", { name: "← 커리어 목록" }).click();
    await expect(page).not.toHaveURL(/career=/);
    expect(matchParam(page)).toBeNull();

    await page.getByRole("button", { name: /Rookie Ho/ }).click();
    await expect(page).toHaveURL(/career=2/);
    expect(matchParam(page)).toBeNull();
    await expect(dialog(page)).toHaveCount(0);
  });
});

// ── D. 주간 보고 ─────────────────────────────────────────────────

test.describe("D. 주간 보고 링크", () => {
  test("경기 주 — 「경기 상세 →」 를 누르면 경기 탭에서 그 경기가 열린다", async ({ page }) => {
    await page.goto(`${BASE}?career=5&tab=week`);
    await page.getByRole("button", { name: "주차 진행" }).first().click();

    const title = await page
      .getByText(/^지난 주 — S2 W\d+/)
      .first()
      .textContent();
    const week = Number(/W(\d+)/.exec(title ?? "")?.[1]);
    expect(week).toBeGreaterThan(0);
    const link = page.getByRole("button", { name: "경기 상세 →" });
    await expect(link).toBeVisible();

    await link.click();
    await expect(page).toHaveURL(/tab=matches/);
    expect(matchParam(page)).toBe(`s2w${week}:p`);
    await expect(dialog(page)).toContainText(`S2 · W${week}`);
  });

  test("결장 주 — 보고는 보이고 링크는 없다", async ({ page }) => {
    await page.goto(`${BASE}?career=4&tab=week`);
    await page.getByRole("button", { name: "주차 진행" }).first().click();
    await expect(page.getByText(/^지난 주 — S2 W\d+/).first()).toBeVisible();
    await expect(page.getByRole("button", { name: "경기 상세 →" })).toHaveCount(0);
  });

  test("기록 조회 실패 — 보고는 그대로, 링크만 없다", async ({ page }) => {
    await page.route(
      (url) =>
        url.origin === API &&
        url.pathname.endsWith("/matches") &&
        url.searchParams.get("limit") === "1",
      (route) => route.abort("failed"),
    );
    await page.goto(`${BASE}?career=5&tab=week`);
    await page.getByRole("button", { name: "주차 진행" }).first().click();
    await expect(page.getByText(/^지난 주 — S2 W\d+/).first()).toBeVisible();
    await page.waitForTimeout(500);
    await expect(page.getByRole("button", { name: "경기 상세 →" })).toHaveCount(0);
  });
});

// ── E. 늦은 응답 · 오류 · 중복 ────────────────────────────────────

test.describe("E. 비동기", () => {
  test("시즌 필터를 빠르게 바꿔도 늦게 온 앞 응답이 덮지 않는다", async ({ page }) => {
    await page.goto(`${BASE}?career=1&tab=matches`);
    await expect(recordRows(page)).toHaveCount(20);
    await delay(page, (u) => u.searchParams.get("season") === "1", 1500);
    const seasons = records(page).getByRole("group", { name: "시즌" });

    await seasons.getByRole("button", { name: "시즌 1" }).click();
    await seasons.getByRole("button", { name: "시즌 2" }).click();
    await expect(recordRows(page).first()).toHaveAccessibleName(/^S2 /);
    await page.waitForTimeout(2000); // 시즌 1 응답이 도착할 시간
    const names = await recordRows(page).evaluateAll((els) =>
      els.map((e) => e.getAttribute("aria-label") ?? ""),
    );
    expect(names.every((n) => n.startsWith("S2 "))).toBe(true);
  });

  test("다음 쪽 로딩 중 필터를 바꿔도 앞 쪽 응답이 덮지 않는다", async ({ page }) => {
    await page.goto(`${BASE}?career=1&tab=matches`);
    await expect(recordRows(page)).toHaveCount(20);
    await delay(
      page,
      (u) => u.searchParams.get("offset") === "20" && !u.searchParams.has("season"),
      1500,
    );

    await page.getByRole("button", { name: "지난 경기 →" }).click();
    await records(page)
      .getByRole("group", { name: "시즌" })
      .getByRole("button", { name: "시즌 2" })
      .click();
    await page.waitForTimeout(2000);
    await expect(recordRows(page)).toHaveCount(20);
    const names = await recordRows(page).evaluateAll((els) =>
      els.map((e) => e.getAttribute("aria-label") ?? ""),
    );
    expect(names.every((n) => n.startsWith("S2 "))).toBe(true);
    await expect(page.getByText("1쪽")).toBeVisible();
  });

  test("상세 로딩 중 닫고 다른 경기를 열면 앞 경기 응답이 나타나지 않는다", async ({
    page,
    request,
  }) => {
    const [a, b] = await allRecords(request);
    await page.goto(`${BASE}?career=1&tab=matches`);
    await delay(page, (u) => u.pathname.endsWith(`/matches/${encodeURIComponent(a.id)}`), 2000);

    await rowOf(page, a).click();
    await expect(dialog(page)).toContainText("경기 기록을 읽는 중");
    await page.keyboard.press("Escape"); // 요청 중 닫기
    await expect(dialog(page)).toBeHidden();
    await rowOf(page, b).click();
    await expect(dialog(page)).toContainText(`S${b.season} · W${b.week}`);

    await page.waitForTimeout(2500); // a 의 늦은 응답
    await expect(dialog(page)).toContainText(`S${b.season} · W${b.week}`);
    await expect(dialog(page)).not.toContainText(`S${a.season} · W${a.week} —`);
    expect(matchParam(page)).toBe(b.id);
  });

  test("네트워크 오류 → 다시 시도", async ({ page, request }) => {
    const m = (await allRecords(request))[0];
    const detailUrl = (u: URL) =>
      u.origin === API && u.pathname.endsWith(`/matches/${encodeURIComponent(m.id)}`);
    await page.route(detailUrl, (route) => route.abort("failed"));
    await page.goto(`${BASE}?career=1&tab=matches&match=${encodeURIComponent(m.id)}`);

    await expect(dialog(page).getByRole("alert")).toContainText("불러오지 못했습니다");
    await page.unroute(detailUrl);
    await dialog(page).getByRole("button", { name: "다시 시도" }).click();
    await expect(dialog(page)).toContainText(`S${m.season} · W${m.week}`);
  });

  test("같은 경기는 한 번만 요청한다 — 진행 중 재열기도, 다 받은 뒤 재열기도", async ({
    page,
    request,
  }) => {
    const m = (await allRecords(request))[1];
    const path = `/api/sandbox/careers/1/matches/${encodeURIComponent(m.id)}`;
    let hits = 0;
    page.on("request", (r) => {
      if (new URL(r.url()).pathname === path) hits += 1;
    });
    await page.goto(`${BASE}?career=1&tab=matches`);
    await delay(page, (u) => u.pathname === path, 1500);

    await rowOf(page, m).click(); // 1) 요청 시작
    await expect(dialog(page)).toContainText("경기 기록을 읽는 중");
    await page.keyboard.press("Escape");
    await expect(dialog(page)).toBeHidden();
    await rowOf(page, m).click(); // 2) 진행 중 재열기 — 같은 약속
    await expect(dialog(page)).toContainText(`S${m.season} · W${m.week}`);
    await page.keyboard.press("Escape");
    await expect(dialog(page)).toBeHidden();
    await rowOf(page, m).click(); // 3) 받은 뒤 재열기 — 기억한 기록
    await expect(dialog(page)).toContainText(`S${m.season} · W${m.week}`);

    expect(hits).toBe(1);
  });
});
