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
 * 리포트의 `pick` 코드를 사람 이름으로 바꾼다.
 *
 * 서버는 채점과 맞추기 위해 코드(`left` · `right` · 다인전 인덱스)를 보낸다.
 * 이름은 정적 카드에 있으므로 화면에서 붙인다 — 못 찾으면 코드를 그대로 보여준다.
 */
export function resolvePickName(
  slug: string,
  matchKey: string,
  pick: string,
): string {
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

export async function fetchAiPredictions(
  slug: string,
): Promise<AiPredictionsResult> {
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
