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

/**
 * 저장된 예측 한 건 + 에이전트 리포트.
 *
 * 필드는 기존 `AiPrediction`(`lib/ple-ai-predictions`)과 **같은 이름**이다. 화면이
 * 그대로 `AiReportDialog`에 넘길 수 있어야 해서 맞췄다 — 같은 것을 두 벌 만들지 않는다.
 */
export type PredictionReport = {
  agent: string;
  /** `null`이면 **의견 없음**이다 — 빈 문자열과 다르다. */
  pick: string | null;
  weight: number;
  summary: string;
  /** 에이전트가 인용한 출처 URL. **검색된 청크가 아니다.** */
  sources: string[];
};

export type PredictionItem = {
  eventSlug: string;
  eventLabel: string;
  matchKey: string;
  matchTitle: string;
  pick: string;
  pickName: string;
  winProbability: number;
  confidence: number;
  rationale: string;
  source: string;
  generatedAt: string;
  winnerName: string | null;
  /** 결과가 아직 없으면 `null` (Pending) — 실패(false)와 다르다. */
  correct: boolean | null;
  reports: PredictionReport[];
};

export type PredictionEvent = { slug: string; label: string; count: number };

export type AiLabPredictions = {
  totals: PredictionTotals;
  integrity: Integrity;
  /** 예측이 **실제로 있는** 대회만 온다 — 목록을 화면에 박지 않는다. */
  events: PredictionEvent[];
  items: PredictionItem[];
};

/**
 * `agent`를 주면 그 에이전트가 리포트를 낸 예측만 온다. 모르는 이름이면 **빈 목록**이지
 * 오류가 아니다. 집계·무결성·대회 목록은 필터와 무관하게 전체를 설명한다.
 */
export async function fetchAiLabPredictions(options?: {
  agent?: string;
}): Promise<AiLabPredictions | null> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), requestTimeoutMs);
  try {
    const params = new URLSearchParams();
    if (options?.agent?.trim()) params.set("agent", options.agent.trim());
    const query = params.toString();
    const res = await fetch(`${aiLabBaseUrl}/predictions${query ? `?${query}` : ""}`, {
      signal: controller.signal,
    });
    if (!res.ok) return null;
    return (await res.json()) as AiLabPredictions;
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}

export type AgentAnalysis = {
  /** 코드의 이름 그대로 — storyline · odds · rumor. */
  agent: string;
  reports: number;
  withPick: number;
  noOpinion: number;
  /** 리포트 수 / 전체 예측 수. */
  responseRate: number | null;
  opinionRate: number | null;
  /** 의견을 냈고 결과도 나온 리포트 — **정확도의 분모다.** */
  gradable: number;
  correct: number;
  incorrect: number;
  /** 채점 대상이 없으면 `null` — 0이 아니다. */
  accuracy: number | null;
  accuracyLow: number | null;
  accuracyHigh: number | null;
  avgWeight: number | null;
  avgWeightOpinionated: number | null;
  matchesCovered: number;
  eventsCovered: number;
  /** 그 대회 자체를 다룬 문서를 인용한 리포트 수. */
  selfReferencingReports: number;
  /** 출처를 한 번이라도 낸 적이 있는가. 실측값이다. */
  usesKnowledge: boolean;
};

export type AgentTotals = {
  agentCount: number;
  totalReports: number;
  opinionated: number;
  noOpinion: number;
  overallOpinionRate: number | null;
  gradableReports: number;
  totalPredictions: number;
};

export type AiLabAgents = {
  totals: AgentTotals;
  integrity: Integrity;
  agents: AgentAnalysis[];
};

export async function fetchAiLabAgents(): Promise<AiLabAgents | null> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), requestTimeoutMs);
  try {
    const res = await fetch(`${aiLabBaseUrl}/agents`, { signal: controller.signal });
    if (!res.ok) return null;
    return (await res.json()) as AiLabAgents;
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}

/**
 * 규칙 하나에 대한 판정 (Phase 3-6).
 *
 * `applicable=false`는 **통과가 아니다** — 잴 수 없었다는 뜻이고, 잴 수 없으면
 * 그 예측은 자격을 얻지 못한다.
 */
export type RuleVerdict = {
  code: string;
  failed: boolean;
  applicable: boolean;
  /** 왜 그렇게 판정했는지. 서버가 낸 문장을 그대로 쓴다. */
  detail: string;
};

export type EvaluationStatus = "eligible" | "disqualified" | "held" | "pending" | "not_applicable";

export type EvaluationItem = {
  eventSlug: string;
  eventLabel: string;
  matchKey: string;
  matchTitle: string;
  generatedAt: string;
  /** 결과가 **시스템에 기록된** 시각. 경기가 끝난 시각이 아니다. */
  resultRecordedAt: string | null;
  status: EvaluationStatus;
  eligible: boolean;
  verdicts: RuleVerdict[];
};

export type EvaluationSeverity = "exclude" | "disqualify" | "hold";

export type EvaluationRule = {
  code: string;
  label: string;
  /** **보류를 실격으로 적지 않기 위해** 함께 온다. */
  severity: EvaluationSeverity;
  description: string;
  blocked: number;
};

/** 다섯 칸의 합이 `predictions`와 같다 — 어디로도 새지 않는다. */
export type EvaluationTotals = {
  predictions: number;
  fallback: number;
  pending: number;
  disqualified: number;
  /** 누수를 증명도 반증도 못 한 예측. **실격과 다른 상태다.** */
  held: number;
  eligible: number;
};

/** **자격 있는 표본이 있을 때만 존재한다.** */
export type EligiblePerformance = {
  sample: number;
  correct: number;
  incorrect: number;
  accuracy: number;
  accuracyLow: number;
  accuracyHigh: number;
  eventsCovered: number;
};

export type AiLabEvaluation = {
  totals: EvaluationTotals;
  integrity: Integrity;
  rules: EvaluationRule[];
  items: EvaluationItem[];
  /** 자격 있는 표본이 0건이면 `null`. **0%도 빈 객체도 아니다.** */
  performance: EligiblePerformance | null;
};

export async function fetchAiLabEvaluation(): Promise<AiLabEvaluation | null> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), requestTimeoutMs);
  try {
    const res = await fetch(`${aiLabBaseUrl}/evaluation`, {
      signal: controller.signal,
    });
    if (!res.ok) return null;
    return (await res.json()) as AiLabEvaluation;
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}

/** 예측 하나에 실린 에이전트 한 명의 몫 (Phase 3-5). */
export type ReportContribution = {
  agent: string;
  weight: number;
  /** `pick`이 있었는가. **의견 없음은 오답이 아니다.** */
  opinionated: boolean;
};

/**
 * 예측 하나 + 그것을 만든 리포트 구성 (Phase 3-5).
 *
 * **승률과 근거의 두께는 같지 않다.** 의견이 하나뿐이고 그 weight가 1.0이면 분포가
 * 붕괴해 `winProbability`가 1.0이 되므로 화면은 `coverage`를 반드시 함께 세운다.
 */
export type PerformanceItem = {
  eventSlug: string;
  eventLabel: string;
  matchKey: string;
  matchTitle: string;
  winProbability: number;
  /** 저장된 값. `agreement × coverage`가 이 값을 재현한다. */
  confidence: number;
  /** 최종 pick에 동의한 의견 / 전체 의견. **의견이 없으면 `null`** — 0이 아니다. */
  agreement: number | null;
  coverage: number;
  /** 미채점이면 `null` — 실패(false)와 다르다. */
  correct: boolean | null;
  reports: ReportContribution[];
};

/**
 * `(answered, agreed)` 한 짝. **`confidence`로 묶지 않는다** — 곱이 같으면
 * "2명이 답해 둘 다 동의"와 "3명이 답해 2명 동의"가 한 줄로 접힌다.
 */
export type ConsensusLevel = {
  confidence: number;
  answered: number;
  agreed: number;
  predictions: number;
  /** 결과가 나온 예측 수 — **정답률의 분모다.** */
  graded: number;
  correct: number;
};

/** 그 에이전트의 `weight`가 실제로 변하는가 (Phase 3-5). 3-3의 정확도와 다른 축이다. */
export type AgentContribution = {
  agent: string;
  reports: number;
  opinions: number;
  distinctWeights: number;
  minWeight: number | null;
  maxWeight: number | null;
  /** 값이 하나뿐인가. **의견이 없으면 `null`** — 상수라고 말할 근거가 없다. */
  constant: boolean | null;
};

export type PerformanceTotals = {
  /** 저장된 예측 전체 (폴백 포함). */
  predictions: number;
  graded: number;
  correct: number;
  incorrect: number;
  bookmakerFallback: number;
  /** 아래 둘은 폴백을 뺀 예측을 센다. */
  singles: number;
  multi: number;
};

/** 추론 지표를 낼 수 있는 상태인가. **새 판정이 아니라 `integrity`의 투영이다.** */
export type Inferential = { available: boolean; reasons: string[] };

export type AiLabPerformance = {
  totals: PerformanceTotals;
  integrity: Integrity;
  inferential: Inferential;
  consensus: ConsensusLevel[];
  contributions: AgentContribution[];
  items: PerformanceItem[];
};

export async function fetchAiLabPerformance(): Promise<AiLabPerformance | null> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), requestTimeoutMs);
  try {
    const res = await fetch(`${aiLabBaseUrl}/performance`, {
      signal: controller.signal,
    });
    if (!res.ok) return null;
    return (await res.json()) as AiLabPerformance;
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}

/**
 * 코퍼스 문서 한 건 (Phase 3-4).
 *
 * `usedByReports`는 **인용 주장이 아니라 적재 기록이다** — 저장된 출처가 실제로
 * 프롬프트에 넣은 청크의 URL이라 셀 수 있다. 리포트당 최대 5건만 남으므로 **하한**이다.
 */
export type KnowledgeDocument = {
  sourceUrl: string;
  sourceDomain: string;
  title: string | null;
  chunks: number;
  /** 임베딩이 없는 청크는 검색되지 않는다. */
  chunksEmbedded: number;
  chunksWithPublishedAt: number;
  firstPublishedAt: string | null;
  lastCollectedAt: string | null;
  usedByReports: number;
  usedByAgents: string[];
};

export type KnowledgeDomain = {
  domain: string;
  documents: number;
  chunks: number;
  usedDocuments: number;
};

export type KnowledgeTotals = {
  documents: number;
  chunks: number;
  chunksEmbedded: number;
  chunksWithPublishedAt: number;
  domains: number;
  lastCollectedAt: string | null;
  /** 프롬프트에 한 번이라도 들어간 문서. **하한이다.** */
  usedDocuments: number;
  /** 문서가 0건이면 `null` — 0이 아니다. */
  usedDocumentRate: number | null;
  reportsTotal: number;
  reportsWithSources: number;
  /** 리포트가 든 출처 중 지금 코퍼스에 없는 URL 수. */
  sourcesOutsideCorpus: number;
};

export type AiLabKnowledge = {
  totals: KnowledgeTotals;
  integrity: Integrity;
  documents: KnowledgeDocument[];
  domains: KnowledgeDomain[];
};

export async function fetchAiLabKnowledge(): Promise<AiLabKnowledge | null> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), requestTimeoutMs);
  try {
    const res = await fetch(`${aiLabBaseUrl}/knowledge`, { signal: controller.signal });
    if (!res.ok) return null;
    return (await res.json()) as AiLabKnowledge;
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}

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
