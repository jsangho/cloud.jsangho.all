/**
 * 요청 키 생명주기 테스트.
 *
 * ## 러너를 새로 들이지 않았다
 *
 * 이 저장소의 `www` 에는 테스트 러너가 없고 `pnpm lint` · `pnpm type-check` 가 그
 * 자리를 대신한다(루트 `CLAUDE.md`). 키 생명주기는 조건 분기가 있는 로직이라 타입
 * 검사로는 고정되지 않으므로 테스트를 붙였지만, **의존성은 하나도 더하지 않았다** —
 * 이미 있는 `typescript` 로 CommonJS 로 떨어뜨리고 Node 내장 러너로 돌린다.
 *
 * ```bash
 * cd www && pnpm test:keys
 * ```
 *
 * `--module commonjs` 로 떨어뜨리는 것은 의도다. 이 Node(22.22.1)는 **Amaro 없이
 * 빌드돼 있어** `.ts` 를 직접 못 읽고(`ERR_NO_TYPESCRIPT`), ESM 으로 떨어뜨리면
 * 확장자 없는 상대 import 를 못 찾는다. CJS 는 둘 다 피한다.
 *
 * 화면(`page.tsx`)의 React 훅은 이 러너로 돌리지 않는다 — 그러려면 렌더러가 필요하고
 * 그건 새 의존성이다. 그래서 **키 생명주기를 순수 모듈로 빼고 그것만** 고정한다.
 * 훅이 이 모듈을 올바르게 부르는지는 타입 검사와 수동 확인이 본다(§보고서).
 */

import { strict as assert } from "node:assert";
import test from "node:test";

import {
  actionScope,
  beginAttempt,
  endAttempt,
  eventScope,
  type PendingRequestKey,
} from "./career-request-keys";

/** 부를 때마다 다른 키. 진짜 `crypto.randomUUID()` 자리다. */
function minter(): () => string {
  let n = 0;
  return () => `key-${++n}`;
}

// ── 1. 다른 훈련 대상은 새 키를 쓴다 ────────────────────────────────

test("훈련 대상이 다르면 요청 범위가 갈린다", () => {
  assert.notEqual(actionScope("훈련", "in_ring"), actionScope("훈련", "mic"));
  // 화면의 busy 식별자(`action:훈련`)는 둘이 같다 — 그래서 범위를 따로 둔다.
  assert.equal(actionScope("훈련", "in_ring"), "action:훈련:in_ring");
});

test("불확실한 실패 뒤 대상을 바꾸면 새 키를 쓴다", () => {
  const mint = minter();
  // in_ring 으로 보냈고 타임아웃됐다.
  const first = beginAttempt(null, actionScope("훈련", "in_ring"), mint);
  const retained = endAttempt(first, "unresolved");
  assert.notEqual(retained, null);

  // 사용자가 mic 로 바꿔 누른다 — **같은 키를 재사용하면 서버가 409 를 준다.**
  const second = beginAttempt(retained, actionScope("훈련", "mic"), mint);
  assert.notEqual(second.requestId, first.requestId);
});

test("대상이 없는 행동끼리도 범위가 갈린다", () => {
  const mint = minter();
  const promo = beginAttempt(null, actionScope("프로모", null), mint);
  const rest = beginAttempt(endAttempt(promo, "unresolved"), actionScope("휴식", null), mint);
  assert.notEqual(rest.requestId, promo.requestId);
});

// ── 2. 같은 요청의 불확실한 실패 뒤 재시도는 같은 키·같은 payload ──

test("같은 범위의 재시도는 키를 재사용한다", () => {
  const mint = minter();
  const scope = actionScope("훈련", "in_ring");

  const first = beginAttempt(null, scope, mint);
  const retry = beginAttempt(endAttempt(first, "unresolved"), scope, mint);

  assert.equal(retry.requestId, first.requestId);
  assert.equal(retry.scope, scope);
});

test("불확실한 실패가 이어지면 계속 같은 키다", () => {
  const mint = minter();
  const scope = "advance";

  let slot: PendingRequestKey = null;
  const ids: string[] = [];
  for (let i = 0; i < 3; i += 1) {
    const attempt = beginAttempt(slot, scope, mint);
    ids.push(attempt.requestId);
    slot = endAttempt(attempt, "unresolved");
  }

  assert.deepEqual(ids, ["key-1", "key-1", "key-1"]);
});

// ── 3. 이전 요청의 상태가 새 요청에 재사용되지 않는다 ──────────────

test("성공한 뒤에는 슬롯이 비고 다음 요청이 새 키를 받는다", () => {
  const mint = minter();
  const scope = "advance";

  const first = beginAttempt(null, scope, mint);
  const cleared = endAttempt(first, "applied");
  assert.equal(cleared, null);

  const next = beginAttempt(cleared, scope, mint);
  assert.notEqual(next.requestId, first.requestId);
});

test("4xx 로 거부된 뒤에도 슬롯이 빈다", () => {
  const mint = minter();
  const scope = actionScope("훈련", "mic");

  const rejected = endAttempt(beginAttempt(null, scope, mint), "rejected");
  assert.equal(rejected, null);
});

test("다른 요청을 시작하면 앞의 미해결 시도는 버려진다", () => {
  const mint = minter();
  // 주차 진행이 타임아웃된 채로 남았다.
  const stale = endAttempt(beginAttempt(null, "advance", mint), "unresolved");

  // 사용자가 결산을 누른다 — 앞 키가 실리면 서버가 다른 payload 로 보고 409 를 준다.
  const settle = beginAttempt(stale, "settle", mint);
  assert.notEqual(settle.requestId, (stale as NonNullable<PendingRequestKey>).requestId);

  // 그리고 버려진 `advance` 키는 **되살아나지 않는다** — 맵이던 시절의 결함이다.
  const advanceAgain = beginAttempt(endAttempt(settle, "applied"), "advance", mint);
  assert.notEqual(advanceAgain.requestId, (stale as NonNullable<PendingRequestKey>).requestId);
});

// ── 4. 이벤트·진행·정산·다음 시즌의 계약이 그대로다 ────────────────

test("사건 범위는 사건 id 와 선택을 함께 담는다", () => {
  assert.equal(eventScope("evt:injury:1", "rest"), "event:evt:injury:1:rest");
  assert.notEqual(eventScope("evt:x", "a"), eventScope("evt:x", "b"));
  assert.notEqual(eventScope("evt:x", "a"), eventScope("evt:y", "a"));
});

test("본문 없는 쓰기 셋은 서로 다른 범위다", () => {
  const mint = minter();
  const scopes = ["advance", "settle", "next-season"];
  const ids = new Set<string>();

  let slot: PendingRequestKey = null;
  for (const scope of scopes) {
    const attempt = beginAttempt(slot, scope, mint);
    ids.add(attempt.requestId);
    slot = endAttempt(attempt, "unresolved");
  }

  assert.equal(ids.size, scopes.length);
});

test("같은 사건·같은 선택의 재시도는 같은 키다", () => {
  const mint = minter();
  const scope = eventScope("evt:promo:3", "accept");

  const first = beginAttempt(null, scope, mint);
  const retry = beginAttempt(endAttempt(first, "unresolved"), scope, mint);

  assert.equal(retry.requestId, first.requestId);
});
