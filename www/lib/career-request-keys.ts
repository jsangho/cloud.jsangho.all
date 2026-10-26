/**
 * 쓰기 요청 키의 생명주기. **UI 의 busy 표시와 다른 개념이다.**
 *
 * 둘을 한 문자열로 쓰다가 생긴 결함을 가르는 자리다(2026-10-22). 전에는 `run` 의
 * `label` 하나가 두 일을 했다 — 패널이 `busy === \`action:${action}\`` 로 비교하는
 * **화면 식별자**이면서, 멱등 키를 담아 두는 **요청 식별자**였다. 그래서 키의
 * 범위가 화면 버튼의 범위를 따라갔고, 서버가 지문을 내는 범위와 어긋났다:
 * 서버는 payload(`{action, target}`)를 해시하는데 키는 `target` 을 몰랐다.
 *
 * 결과는 불필요한 409 였다. 훈련이 타임아웃된 뒤 대상을 `in_ring` → `mic` 로
 * 바꿔 다시 누르면 같은 키에 다른 payload 가 실려 서버가 거부했다. 데이터가
 * 중복 적용되는 문제는 아니었지만, 사용자가 하지 않은 잘못을 통보받았다.
 *
 * ## 슬롯이 하나다 — 맵이 아니다
 *
 * 전에는 라벨 → 키 **맵**이었다. 맵은 두 가지가 샌다.
 *
 *   1. **옛 키가 남는다.** `in_ring` 이 타임아웃된 뒤 `mic` 로 성공하면 `in_ring`
 *      항목이 그대로 남고, 나중에 사용자가 다시 `in_ring` 을 누르면 **그 옛 키**가
 *      실린다. 그 사이 원래 요청이 실제로 적용돼 영수증이 남아 있었다면 서버가
 *      재시도로 보고 **옛 응답을 재생한다** — 사용자는 눌렀는데 아무 일도 일어나지
 *      않는다.
 *   2. 커리어를 옮길 때마다 맵을 통째로 비우는 손질이 필요했다.
 *
 * 미해결 시도는 **언제나 최대 하나**다. 화면이 `busy != null` 인 동안 모든 버튼을
 * 막으므로 요청이 둘 날아가지 못한다. 그래서 슬롯 하나로 충분하고, 슬롯 하나면
 * 위 둘이 구조적으로 사라진다 — 다른 요청을 시작하는 순간 앞의 미해결 시도는
 * **버려진다.**
 *
 * 버리는 것이 맞는 이유: 사용자가 다른 입력을 골랐다는 것은 **다른 의도**라는
 * 뜻이다. 앞 요청이 실제로 적용됐다면 그것도 사용자의 의도였고(포인트 둘이 각각
 * 쓰인다), 적용되지 않았다면 잃을 것이 없다. 어느 쪽이든 409 는 나지 않는다.
 *
 * ## `scope` 는 서버가 지문을 내는 범위와 같아야 한다
 *
 * 서버는 `[연산, payload]` 를 정규화해 sha256 을 낸다
 * (`career_sandbox_interactor._fingerprint`). 그래서 `scope` 도 **payload 를 포함**
 * 해야 한다 — 그것이 "같은 요청" 의 정의다. 어긋나면 다시 409 가 돌아온다.
 */

/** 아직 결론이 나지 않은 시도 하나. 없으면 `null`. */
export type PendingRequestKey = {
  /** 서버가 지문을 내는 범위와 같은 문자열. 같으면 같은 요청이다. */
  readonly scope: string;
  /** 그 요청에 실린 `Idempotency-Key`. */
  readonly requestId: string;
} | null;

/**
 * 시도의 결말. **`unresolved` 만 키를 남긴다.**
 *
 * `applied` 와 `rejected` 는 결론이 났다 — 서버가 답했고 상태가 정해졌으므로 그
 * 키는 다시 쓸 일이 없다. `unresolved`(타임아웃 · 네트워크 오류 · 5xx)만 "서버가
 * 처리했는지 모른다" 로 남고, 그때만 재전송이 같은 키를 써야 한다.
 */
export type AttemptResult = "applied" | "rejected" | "unresolved";

/**
 * 이 시도에 쓸 키를 정한다.
 *
 * 같은 `scope` 의 미해결 시도가 있으면 **그 키를 재사용한다**(재전송). 아니면 새
 * 키를 만든다 — 그리고 앞의 미해결 시도는 버려진다(위 모듈 주석).
 *
 * `mint` 를 주입받는 것은 테스트 때문만이 아니다. 키 생성은
 * `crypto.randomUUID()` 에 의존하므로 순수 함수로 둘 수 없고, 그 의존을 호출
 * 경계로 밀어내면 이 파일이 **브라우저 API 없이** 돌아간다.
 */
export function beginAttempt(
  pending: PendingRequestKey,
  scope: string,
  mint: () => string,
): NonNullable<PendingRequestKey> {
  if (pending != null && pending.scope === scope) return pending;
  return { scope, requestId: mint() };
}

/**
 * 시도가 끝난 뒤의 보관 상태.
 *
 * `unresolved` 면 그 슬롯을 그대로 남겨 다음 클릭이 재전송이 되게 하고, 결론이
 * 났으면 비운다.
 */
export function endAttempt(
  attempt: NonNullable<PendingRequestKey>,
  result: AttemptResult,
): PendingRequestKey {
  return result === "unresolved" ? attempt : null;
}

/**
 * 주간 행동의 요청 범위. **대상까지 넣는다** — 서버 payload 가 `{action, target}`
 * 이므로 대상이 다르면 다른 요청이다.
 *
 * 화면의 busy 식별자(`action:${action}`)와 **일부러 다른 문자열**이다. busy 는
 * 버튼 하나를 가리키고(대상 선택과 무관하게 그 버튼이 돌고 있다), 이쪽은 요청
 * 하나를 가리킨다.
 */
export function actionScope(action: string, target: string | null | undefined): string {
  return `action:${action}:${target ?? ""}`;
}

/** 사건 해결의 요청 범위. 서버 payload 가 `{event_id, choice}` 다. */
export function eventScope(eventId: string, choice: string): string {
  return `event:${eventId}:${choice}`;
}
