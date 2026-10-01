import { pleEventsBaseUrl, requestTimeoutMs } from "@/lib/api";
import { getPleMatches, isMultiMatch } from "@/lib/wwe-ple-matches";

/** 에이전트 한 명의 의견. `pick`이 null이면 **의견 없음**이다 (빈 문자열과 다르다). */
export type AiAgentReport = {
  agent: string;
  pick: string | null;
  weight: number;
  summary: string;
  sources: string[];
};

export type AiPrediction = {
  matchKey: string;
  pick: string;
  pickName: string;
  winProbability: number;
  confidence: number;
  rationale: string;
  /** "agents" | "bookmaker_fallback" — 폴백으로 만들어졌는지 화면이 구분해야 한다. */
  source: string;
  generatedAt: string;
  reports: AiAgentReport[];
};

/** "근거가 없다"와 "못 불러왔다"는 다른 상태다 — 한 값으로 뭉치지 않는다. */
export type AiPredictionsResult =
  | { status: "ready"; byMatch: Record<string, AiPrediction> }
  | { status: "error" };

const AGENT_LABELS: Record<string, string> = {
  storyline: "서사",
  odds: "오즈",
  rumor: "루머",
};

export function agentLabel(agent: string): string {
  return AGENT_LABELS[agent] ?? agent;
}

export function isBookmakerFallback(prediction: AiPrediction): boolean {
  return prediction.source === "bookmaker_fallback";
}

export function toPercent(ratio: number): number {
  return Math.round(ratio * 100);
}

/**
 * 단일전에서 상대가 가진 승률 몫.
 *
 * 서버는 고른 쪽의 승률만 저장하지만, 2파전이면 나머지는 상대의 것이다. 다인전은
 * 나머지를 여러 명이 나눠 가지므로 이 함수가 `null`을 준다 — 6명이 나눈 몫을
 * 한 명 것처럼 보여줄 수는 없다.
 */
export function opponentShare(
  slug: string,
  prediction: AiPrediction,
): { name: string; probability: number } | null {
  const card = getPleMatches(slug).find((match) => match.id === prediction.matchKey);
  if (!card || isMultiMatch(card)) return null;

  const opponent = prediction.pick === "left" ? card.right : card.left;
  return { name: opponent.name, probability: 1 - prediction.winProbability };
}

/**
 * 리포트의 `pick` 코드를 사람 이름으로 바꾼다.
 *
 * 서버는 채점과 맞추기 위해 코드(`left` · `right` · 다인전 인덱스)를 보낸다.
 * 이름은 정적 카드에 있으므로 화면에서 붙인다 — 못 찾으면 코드를 그대로 보여준다.
 */
export function resolvePickName(slug: string, matchKey: string, pick: string): string {
  const card = getPleMatches(slug).find((match) => match.id === matchKey);
  if (!card) return pick;

  if (isMultiMatch(card)) {
    const index = Number.parseInt(pick, 10);
    return card.competitors[index]?.name ?? pick;
  }
  if (pick === "left") return card.left.name;
  if (pick === "right") return card.right.name;
  return pick;
}

/** 생성 결과 — 경기 하나가 실패해도 나머지는 계속되므로 건수로 돌아온다. */
export type AiGenerationSummary = {
  requested: number;
  generated: number;
  skipped: number;
  failed: number;
};

/** 경기 하나를 만드는 데 드는 LLM 호출 수 — 서사·루머 둘. 오즈 축은 LLM을 쓰지 않는다. */
export const LLM_CALLS_PER_MATCH = 2;

/**
 * 생성 요청 타임아웃. 조회(20초)와 따로 두는 이유는 성격이 다르기 때문이다 —
 * 지식 검색 한 번과 Gemini 두 번이 실제로 걸리는 시간이다.
 *
 * **경기를 한 번에 하나씩 보내는 것을 전제로 한 값이다.** 대회 전체를 한 요청으로
 * 묶으면 경기 수에 비례해 길어져 중간 프록시(Cloudflare 100초)에 먼저 끊긴다 —
 * 그러면 백엔드는 계속 만드는데 화면만 실패로 보인다.
 */
const generateTimeoutMs = 90_000;

/**
 * 예측 생성 — **관리자 전용**. 비용(Gemini 호출)이 드는 경로다.
 *
 * 토큰은 httpOnly 쿠키라 `credentials: "include"`로 실어 보낸다 (`lib/ple-api.ts`
 * 의 결과 등록과 같은 방식).
 */
export async function generateAiPredictions(
  slug: string,
  options?: { matchKeys?: string[]; force?: boolean },
): Promise<AiGenerationSummary> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), generateTimeoutMs);
  try {
    const res = await fetch(`${pleEventsBaseUrl}/${slug}/ai-predictions`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        matchKeys: options?.matchKeys ?? [],
        force: options?.force ?? false,
      }),
      signal: controller.signal,
    });
    if (!res.ok) {
      const data = (await res.json().catch(() => null)) as { detail?: string } | null;
      throw new Error(data?.detail ?? `생성 실패 (${res.status})`);
    }
    return (await res.json()) as AiGenerationSummary;
  } finally {
    clearTimeout(timer);
  }
}

export async function fetchAiPredictions(slug: string): Promise<AiPredictionsResult> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), requestTimeoutMs);
  try {
    const res = await fetch(`${pleEventsBaseUrl}/${slug}/ai-predictions`, {
      signal: controller.signal,
    });
    if (!res.ok) return { status: "error" };

    const data: { items?: AiPrediction[] } = await res.json();
    const byMatch: Record<string, AiPrediction> = {};
    for (const item of data.items ?? []) {
      byMatch[item.matchKey] = item;
    }
    return { status: "ready", byMatch };
  } catch {
    return { status: "error" };
  } finally {
    clearTimeout(timer);
  }
}
