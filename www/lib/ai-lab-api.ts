import { apiBaseUrl, requestTimeoutMs } from "@/lib/api";

/**
 * AI LAB API 클라이언트 (Phase 3-0·3-1).
 *
 * **이 경로는 LLM을 부르지 않는다** — 저장된 예측·리포트·지식 청크를 읽어 집계한
 * 값만 온다. 화면 진입이 비용을 만들지 않는 구조다.
 *
 * 적중률은 점추정(`hitRate`)과 **윌슨 95% 신뢰구간**(`hitRateLow`·`hitRateHigh`)이
 * 함께 온다. 화면은 셋을 같이 적어야 한다 — 표본 12건의 100%를 숫자 하나로 세우면
 * 그 자체가 과장이다.
 *
 * 못 받으면 `null`을 돌려준다. 화면은 그 자리를 비우고, **0으로 채우지 않는다.**
 */
const aiLabBaseUrl = `${apiBaseUrl}/api/ai-lab`;

export type PredictionTotals = {
  total: number;
  /** 실제 결과가 나와 채점된 예측. 북메이커 폴백은 빠진다. */
  graded: number;
  correct: number;
  incorrect: number;
  /** 0~1. 채점된 예측이 없으면 `null` — 0이 아니다. */
  hitRate: number | null;
  hitRateLow: number | null;
  hitRateHigh: number | null;
  avgConfidence: number | null;
  avgWinProbability: number | null;
  bookmakerFallback: number;
};

export type Integrity = {
  sampleSize: number;
  eventsCovered: number;
  eventsTotal: number;
  /** 그 대회 자체를 다룬 문서를 근거로 인용한 예측 수. 0보다 크면 누수 정황이다. */
  selfReferencingPredictions: number;
  predictionsWithSources: number;
  chunksTotal: number;
  chunksWithPublishedAt: number;
  /** 발행일이 하나도 없으면 `false` — 누수가 없다는 것을 증명할 수 없다. */
  temporalVerifiable: boolean;
  generalizable: boolean;
  reasons: string[];
};

export type SystemState = "operational" | "degraded" | "empty" | "unknown";

export type SystemComponent = {
  key: string;
  label: string;
  state: SystemState;
  detail: string;
};

export type AgentActivity = {
  /** 코드의 이름 그대로 — storyline · odds · rumor. */
  agent: string;
  reports: number;
  withPick: number;
  opinionRate: number | null;
  avgWeight: number | null;
};

export type RecentPrediction = {
  eventSlug: string;
  eventLabel: string;
  matchKey: string;
  matchTitle: string;
  pickName: string;
  winProbability: number;
  confidence: number;
  source: string;
  generatedAt: string;
  winnerName: string | null;
  /** 미채점이면 `null` — 실패(false)와 다른 상태다. */
  correct: boolean | null;
};

export type AiLabOverview = {
  predictions: PredictionTotals;
  integrity: Integrity;
  system: SystemComponent[];
  agents: AgentActivity[];
  recent: RecentPrediction[];
};

export async function fetchAiLabOverview(): Promise<AiLabOverview | null> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), requestTimeoutMs);
  try {
    const res = await fetch(`${aiLabBaseUrl}/overview`, { signal: controller.signal });
    if (!res.ok) return null;
    return (await res.json()) as AiLabOverview;
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}

/** 비율 표기 — **`null`이면 대시**다. 0%로 그리면 "다 틀렸다"로 읽힌다. */
export function formatRatio(ratio: number | null): string {
  if (ratio === null) return "—";
  return `${Math.round(ratio * 100)}%`;
}

/** 에이전트 코드 이름 → 화면 라벨. 이름 자체는 코드의 것을 유지한다. */
const AGENT_LABELS: Record<string, string> = {
  storyline: "Storyline",
  odds: "Odds",
  rumor: "Rumor",
};

export function agentLabel(agent: string): string {
  return AGENT_LABELS[agent] ?? agent;
}
