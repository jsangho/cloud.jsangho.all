/**
 * 경기 기록 화면 규칙 테스트 — `career-match.ts` 의 순수 함수만.
 *
 * 러너는 `career-request-keys.test.ts` 와 같다(의존성 추가 없음 — `tsc` → CommonJS →
 * `node --test`). 이유는 그 파일 머리 주석에 있다.
 *
 * ```bash
 * cd www && pnpm test:match
 * ```
 *
 * 고정 데이터는 **작게 지은 값**이다 — 칸 이름과 모양은 P1 스키마
 * (`MatchDetailSchema`)와 같지만 수치는 규칙을 드러내려고 고른 것이다. 실제 응답
 * 모양은 화면 검증(보고서)이 따로 본다.
 */

import { strict as assert } from "node:assert";
import test from "node:test";

import {
  MATCH_ID_MAX,
  MATCH_PAGE,
  hasNextPage,
  matchParamStatus,
  missingCopy,
  participantRoles,
  participantsBySide,
  readMissingBody,
  recordForWeek,
  signed,
  stateChanges,
  type CareerMatchParticipant,
  type CareerMatchState,
} from "./career-match";

function state(over: Partial<CareerMatchState> = {}): CareerMatchState {
  return {
    popularity: 50,
    condition: 80,
    wins: 3,
    losses: 2,
    winStreak: 1,
    losingStreak: 0,
    ...over,
  };
}

function person(name: string, side: number): CareerMatchParticipant {
  return {
    name,
    side,
    power: { skill: 1, draw: 1, body: 1 },
    before: state(),
    after: state(),
  };
}

// ── URL ─────────────────────────────────────────────────────────

test("match 값이 없으면 닫힘, 정상이면 유효", () => {
  assert.equal(matchParamStatus(null), "none");
  assert.equal(matchParamStatus("s1w52:p"), "valid");
});

test("빈 값·공백·서버 상한 초과는 잘못된 링크", () => {
  assert.equal(matchParamStatus(""), "invalid");
  assert.equal(matchParamStatus("   "), "invalid");
  assert.equal(matchParamStatus(" s1w1:p"), "invalid");
  assert.equal(matchParamStatus("x".repeat(MATCH_ID_MAX)), "valid");
  assert.equal(matchParamStatus("x".repeat(MATCH_ID_MAX + 1)), "invalid");
});

test("형식을 추측해 거르지 않는다 — 서버가 404 로 답할 일이다", () => {
  assert.equal(matchParamStatus("nope"), "valid");
});

// ── 404 본문 ─────────────────────────────────────────────────────

test("missingReason 칸이 있으면 경기 기록 없음, 사유를 그대로 읽는다", () => {
  for (const reason of ["before_records", "trimmed", "unexplained"] as const) {
    assert.deepEqual(readMissingBody({ detail: "…", missingReason: reason }), {
      missing: true,
      reason,
    });
  }
});

test("missingReason 이 null 이어도 칸이 있으면 경기 기록 없음(판정 불가)", () => {
  assert.deepEqual(
    readMissingBody({ detail: "경기 기록을 찾을 수 없습니다", missingReason: null }),
    {
      missing: true,
      reason: null,
    },
  );
});

test("칸이 없는 404 는 커리어 404 — 경기 사유로 읽지 않는다", () => {
  assert.deepEqual(readMissingBody({ detail: "커리어를 찾을 수 없습니다" }), { missing: false });
  assert.deepEqual(readMissingBody(null), { missing: false });
  assert.deepEqual(readMissingBody("text"), { missing: false });
});

test("모르는 사유는 판정 불가로 낮춘다", () => {
  assert.deepEqual(readMissingBody({ missingReason: "something_new" }), {
    missing: true,
    reason: null,
  });
});

test("사유마다 다른 안내, unexplained 만 경고 톤", () => {
  const titles = new Set(
    (["before_records", "trimmed", "unexplained", null] as const).map((r) => missingCopy(r).title),
  );
  assert.equal(titles.size, 4);
  assert.equal(missingCopy("unexplained").tone, "alert");
  assert.match(missingCopy("unexplained").body, /확인이 필요/);
  assert.equal(missingCopy("trimmed").tone, "info");
  assert.equal(missingCopy("before_records").tone, "info");
  assert.equal(missingCopy(null).tone, "info");
});

// ── 전후 ─────────────────────────────────────────────────────────

test("전후 여섯 줄 — 실제 값과 차이를 함께, 순서 고정", () => {
  const rows = stateChanges({
    before: state(),
    after: state({ popularity: 53, condition: 72, wins: 4, winStreak: 2 }),
  });
  assert.deepEqual(
    rows.map((r) => [r.label, r.before, r.after, r.delta]),
    [
      ["인기도", 50, 53, 3],
      ["컨디션", 80, 72, -8],
      ["승리", 3, 4, 1],
      ["패배", 2, 2, 0],
      ["연승", 1, 2, 1],
      ["연패", 0, 0, 0],
    ],
  );
});

test("패배·연패는 늘면 나쁘다, 변화 없음은 판정하지 않는다", () => {
  const rows = stateChanges({
    before: state({ winStreak: 3 }),
    after: state({ losses: 3, losingStreak: 1, winStreak: 0 }),
  });
  const good = Object.fromEntries(rows.map((r) => [r.key, r.good]));
  assert.equal(good.losses, false);
  assert.equal(good.losingStreak, false);
  assert.equal(good.winStreak, false);
  assert.equal(good.popularity, null);
});

test("부호 표기", () => {
  assert.equal(signed(3), "+3");
  assert.equal(signed(-2), "−2");
  assert.equal(signed(0), "±0");
});

// ── 팀 ───────────────────────────────────────────────────────────

test("태그전 네 명 — 팀으로 가르되 저장 순서를 지킨다", () => {
  const ps = [person("Me", 0), person("Ally", 0), person("Foe A", 1), person("Foe B", 1)];
  const [mine, theirs] = participantsBySide(ps);
  assert.deepEqual(
    mine.map((p) => p.name),
    ["Me", "Ally"],
  );
  assert.deepEqual(
    theirs.map((p) => p.name),
    ["Foe A", "Foe B"],
  );
});

test("동명이인도 두 줄로 남는다", () => {
  const ps = [person("Same", 0), person("Same", 0), person("Foe", 1), person("Foe 2", 1)];
  assert.equal(participantsBySide(ps)[0].length, 2);
});

test("핀폴 — 핀 승리·핀 패배가 붙는다", () => {
  const match = { finisher: "Me", scorer: "Me", pinned: "Foe" };
  assert.deepEqual(participantRoles(match, "Me"), ["핀 승리"]);
  assert.deepEqual(participantRoles(match, "Foe"), ["핀 패배"]);
  assert.deepEqual(participantRoles(match, "Ally"), []);
});

test("비핀폴 — scorer·pinned 가 null 이면 핀 역할이 없다", () => {
  const match = { finisher: "Me", scorer: null, pinned: null };
  assert.deepEqual(participantRoles(match, "Me"), ["결정타"]);
  assert.deepEqual(participantRoles(match, "Foe"), []);
});

// ── 페이지 · 보고 링크 ────────────────────────────────────────────

test("total 이 없으니 꽉 찬 페이지일 때만 다음이 있다", () => {
  assert.equal(hasNextPage(MATCH_PAGE), true);
  assert.equal(hasNextPage(MATCH_PAGE - 1), false);
  assert.equal(hasNextPage(0), false);
  assert.equal(hasNextPage(5, 5), true);
});

test("보고 링크는 같은 시즌·주차의 서버 id 만 — 없으면 null", () => {
  const rows = [{ id: "s2w3:p", season: 2, week: 3 }];
  assert.equal(recordForWeek(rows, 2, 3), "s2w3:p");
  assert.equal(recordForWeek(rows, 2, 4), null);
  assert.equal(recordForWeek([], 1, 1), null);
});
