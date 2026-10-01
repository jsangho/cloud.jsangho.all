import { pleEventsBaseUrl, requestTimeoutMs } from "@/lib/api";

/**
 * 결과 확정 에이전트 — **관리자 전용**.
 *
 * 끝난 대회의 결과 미기록 경기를 위키에서 찾아 승자를 채운다. 그 값은 채점·적중률·
 * 포인트의 입력이라 한 번 잘못 쓰면 사용자 점수가 조용히 틀어진다. 그래서 문이 둘이다:
 * 목록은 **모델을 부르지 않는 공짜 조회**이고, 실행은 기본이 드라이런이다.
 */

const baseUrl = `${pleEventsBaseUrl}/maintenance/result-verification`;

export type PendingMatch = {
  eventSlug: string;
  eventLabel: string;
  matchKey: string;
  title: string;
  options: string[];
};

export type MatchVerification = {
  eventSlug: string;
  matchKey: string;
  title: string;
  /** 쓸 수 있다고 판정된 값. 보류면 `null`. */
  pick: string | null;
  winnerName: string | null;
  /** 보류 사유. `null`이면 보류가 아니다. */
  hold: string | null;
  /** 실제로 DB에 썼는가. 드라이런에서는 `pick`이 있어도 거짓이다. */
  written: boolean;
  quote: string;
  sourceTitle: string;
  sourceRevisionId: string | null;
  toolCalls: number;
};

export type VerificationRun = {
  matches: MatchVerification[];
  applied: boolean;
  /** 결과 미기록으로 찾아낸 **총수**. 한 건만 돌려도 이 값은 전체다. */
  found: number;
  written: number;
  writable: number;
  held: number;
  toolCalls: number;
};

/**
 * 한 경기 실행의 타임아웃.
 *
 * **중간 프록시가 100초에 먼저 끊을 수 있다.** 에이전트는 경기 하나에 최대 여섯 걸음을
 * 걷고 호출 간격을 15초씩 벌리므로(무료 등급 분당 5회), 긴 경기는 1분을 넘긴다. 그래서
 * 이 값은 프록시보다 **길게** 둔다 — 우리가 먼저 끊으면 "서버는 계속 돌고 있는데 화면만
 * 포기한" 상태가 되고, 그 사실조차 구분되지 않는다. 요청이 실패하면 **쓰기가 됐는지
 * 안 됐는지 알 수 없다**: 그때는 목록을 다시 읽어 확인한다(목록이 곧 사실이다).
 */
const runTimeoutMs = 150_000;

/** 보류 사유 라벨. 서버가 새 사유를 추가하면 그 값을 그대로 보여준다. */
export const HOLD_LABEL: Record<string, string> = {
  no_claim: "주장 없음 (걸음 초과·응답 파손)",
  engine_unavailable: "엔진 장애 — 다시 돌리면 된다",
  no_winner: "승자 없음 (무승부·노컨테스트면 정답)",
  quote_missing: "인용 없음",
  quote_not_found: "인용이 본문에 없음 — 지어낸 것이다",
  name_not_on_card: "카드에 없는 이름",
  ambiguous_name: "두 선택지에 다 걸린다",
  name_not_in_quote: "인용이 그 승자를 말하지 않는다",
};

export async function fetchPendingResults(eventSlug?: string): Promise<PendingMatch[]> {
  const query = eventSlug ? `?event_slug=${encodeURIComponent(eventSlug)}` : "";
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), requestTimeoutMs);
  try {
    const res = await fetch(`${baseUrl}/pending${query}`, {
      credentials: "include",
      signal: controller.signal,
    });
    if (!res.ok) {
      const data = (await res.json().catch(() => null)) as { detail?: string } | null;
      throw new Error(data?.detail ?? `목록을 불러오지 못했습니다 (${res.status})`);
    }
    const data = (await res.json()) as { items?: PendingMatch[] };
    return Array.isArray(data.items) ? data.items : [];
  } finally {
    clearTimeout(timer);
  }
}

/** `apply`를 참으로 주면 **DB에 쓴다.** 기본은 돌려만 보고 쓰지 않는다. */
export async function runResultVerification(options: {
  matchKeys: string[];
  apply: boolean;
  eventSlug?: string;
}): Promise<VerificationRun> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), runTimeoutMs);
  try {
    const res = await fetch(`${baseUrl}/run`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        eventSlug: options.eventSlug ?? null,
        matchKeys: options.matchKeys,
        limit: Math.max(options.matchKeys.length, 1),
        apply: options.apply,
      }),
      signal: controller.signal,
    });
    if (!res.ok) {
      const data = (await res.json().catch(() => null)) as { detail?: string } | null;
      throw new Error(data?.detail ?? `실행이 끝나지 않았습니다 (${res.status})`);
    }
    return (await res.json()) as VerificationRun;
  } finally {
    clearTimeout(timer);
  }
}
