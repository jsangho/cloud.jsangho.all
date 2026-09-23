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
  /** 위키는 발행일 메타태그를 안 내보낸다 — 이 값은 구조적으로 0이고 판정 근거가 아니다. */
  chunksWithPublishedAt: number;
  /** 개정본 계보를 아는 청크 수. `temporalVerifiable`이 보는 값이 이쪽이다. */
  chunksWithRevision: number;
  /** **계보가 한 건이라도 빠지면 `false`** — 그 청크를 인용한 예측은 검증할 수 없다. */
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
  /**
   * 채점에서 빠진 이유, 아니면 `null`.
   *
   * 이 목록은 **재고**라 폴백까지 싣는다. 그래서 `correct`가 `true`인데 위
   * `predictions` 적중률에 안 세어지는 줄이 있고, 화면은 그 이유를 적어야 한다.
   */
  scoringExclusion: string | null;
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
  /**
   * 채점에서 빠진 이유, 아니면 `null`.
   *
   * **`source`로는 못 가린다** — 사후 재현 표본의 `source`도 `agents`다.
   */
  scoringExclusion: string | null;
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

export type EvaluationStatus =
  | "eligible"
  | "disqualified"
  | "held"
  | "pending"
  | "withdrawn_match"
  | "ex_post"
  | "not_applicable";

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

/** 일곱 칸의 합이 `predictions`와 같다 — 어디로도 새지 않는다. */
export type EvaluationTotals = {
  predictions: number;
  fallback: number;
  /** 생성 전에 결과가 시스템 밖에서 알려져 있던 표본. **실격과 다른 상태다.** */
  exPost: number;
  /** 가리키는 경기가 카드에서 사라진 표본. **실격과 다른 상태다.** */
  withdrawn: number;
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

/**
 * 규칙 하나의 **정의**. 건수가 없다 (Phase 9).
 *
 * `EvaluationRule`의 `blocked`는 **전체 집계**라 한 건짜리 감사 화면에서 뜻이 없다.
 * 0으로 받으면 화면은 그것을 "이 규칙이 아무것도 막지 않았다"로 읽게 된다.
 */
export type RuleDefinition = {
  code: string;
  label: string;
  severity: EvaluationSeverity;
  description: string;
};

/**
 * 증거 한 조각이 **시간 규칙에서 차지하는 자리** (Phase 6·9).
 *
 * 한국어 문장이 아니라 값으로 온다 — 화면이 색과 문구를 고르려고 서버 문장을
 * 파싱하는 일이 없어야 한다.
 */
export type EvidenceTemporal =
  | "before_event"
  | "not_before_event"
  | "unknown_revision"
  | "unknown_event_date";

/**
 * 증거 한 조각이 **예측 시각 기준으로** 차지하는 자리 (Phase 2).
 *
 * `EvidenceTemporal`과 갈라 둔 이유는 두 축이 서로 독립이기 때문이다 — 경기보다
 * 앞선 글이면서 동시에 예측보다 나중일 수 있다. 한 값으로 접으면 그 조합을
 * 말할 방법이 없어진다.
 */
export type EvidenceRevisionPosition =
  | "before_prediction"
  | "after_prediction"
  | "unknown_revision";

/**
 * 예측이 **그때 실제로 읽은** 청크 하나 + 판정에서 한 역할 (Phase 6·9).
 *
 * `temporal`과 `selfReference`는 **결정적 규칙 엔진이 낸 값이다.** LLM에게 왜
 * 실격인지 설명시킨 것이 아니라, 판정이 쓴 것과 같은 함수를 지난 결과다.
 */
export type Evidence = {
  /** 프롬프트에 들어간 순서. 검색 순위가 아니라 **읽은 순서**다. */
  rank: number;
  sourceUrl: string | null;
  /** 그때 읽은 개정본. **URL이 같아도 개정본이 다르면 다른 글이다.** */
  sourceRevisionId: string | null;
  sourceRevisedAt: string | null;
  /** 위키는 이 값을 안 내보내므로 대개 `null`이다 — 판정은 이것을 보지 않는다. */
  publishedAt: string | null;
  /** 코사인 거리. 작을수록 가깝다. 못 구했으면 `null`. */
  distance: number | null;
  temporal: EvidenceTemporal;
  /**
   * 그 글이 **예측 시점에 이미 있던 글인가** (Phase 2).
   *
   * `temporal`과 기준이 다르다 — 저쪽은 경기 시작일, 이쪽은 예측 생성 시각이다.
   * `after_prediction`은 그때 존재하지도 않던 글이 증거 목록에 있다는 뜻이고,
   * 그러면 기록 자체가 성립하지 않는다.
   */
  revisionVsPrediction: EvidenceRevisionPosition;
  selfReference: boolean;
};

/** 감사 화면이 보는 리포트 한 건 (Phase 9). **모델 이름은 오지 않는다**(§11-6). */
export type AuditReport = {
  agent: string;
  pick: string | null;
  weight: number;
  summary: string;
  sources: string[];
  /** 에이전트 로직의 판. `null`이면 **기록이 없는 옛 리포트**다 — 백필하지 않았다. */
  agentVersion: string | null;
  /** 지시문 해시 앞 16자리. 모델을 부르지 않은 리포트는 `null`. */
  promptVersion: string | null;
};

/** 재현에서 어긋난 칸 하나 (Phase 5). **두 값을 다 싣는다.** */
export type ReplayMismatch = {
  field: string;
  stored: string;
  replayed: string;
};

/**
 * 생성 파이프라인 한 단계와 그것을 다시 돌릴 수 있는지 (Phase 5).
 *
 * **못 돌리는 단계도 목록에 온다.** 빠지면 화면이 "전부 재현됐다"로 읽힌다.
 */
export type ReplayStage = {
  stage: string;
  label: string;
  replayable: boolean;
  note: string;
};

/** "reproduced" | "diverged" | "unreplayable". */
export type ReplayStatus = "reproduced" | "diverged" | "unreplayable";

/**
 * 저장된 재료로 합성을 다시 돌린 결과 (Phase 5).
 *
 * **채점이 아니다.** 예측이 맞았는지가 아니라 "저장된 재료로 저장된 결론이 다시
 * 나오는가"를 묻는다.
 */
export type PredictionReplay = {
  status: ReplayStatus;
  /** `unreplayable`의 사유. 돌아갔으면 `null`. */
  reason: string | null;
  mismatches: ReplayMismatch[];
  /**
   * 저장된 질의와 **지금 카드로 다시 만든 질의**가 같은가.
   *
   * **`null`은 "같다"가 아니라 "판단할 수 없다"는 뜻이다** — 질의 기록이 없거나
   * 경기 행이 사라져 견줄 상대가 없는 경우다.
   */
  cardUnchanged: boolean | null;
  stages: ReplayStage[];
};

/**
 * 예측 한 건의 전체 계보 (Phase 9 · Phase 5).
 *
 * `evaluation`은 목록 화면이 받는 것과 **같은 판정**이다 — 두 화면이 같은 예측을
 * 두고 다른 말을 할 수 없다.
 *
 * `replay`는 **재현된 것만 말한다.** 다섯 단계 중 둘만 다시 돌아가고, 나머지 셋은
 * 왜 못 돌리는지를 `stages`가 문장으로 싣는다.
 */
export type PredictionAudit = {
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
  /** 결과가 **시스템에 기록된** 시각. 경기가 끝난 시각이 아니다. */
  resultRecordedAt: string | null;
  /** 대회가 열린 날. 증거의 개정본 시각을 이 날과 견준다. */
  eventStartDate: string | null;
  winnerName: string | null;
  /** 결과가 없으면 `null` — 오답(false)과 다른 상태다. */
  correct: boolean | null;
  evaluation: EvaluationItem;
  rules: RuleDefinition[];
  reports: AuditReport[];
  /** **비어 있는 것은 정상이다** — Stage 4 이전 예측에는 검색 기록이 없다. */
  evidence: Evidence[];
  /** 저장된 재료로 합성을 다시 돌린 결과 (Phase 5). 채점과 무관하다. */
  replay: PredictionReplay;
  /**
   * 그 청크들을 찾을 때 던진 질의 (Phase 3). 증거 **앞**의 한 단계다.
   *
   * `null`은 기록 전이라는 뜻이다. 질의는 경기 제목과 선택지 이름에서 만들어지므로,
   * 경기가 카드에서 사라진 예측은 기록해 두지 않았으면 영영 복원되지 않는다.
   */
  knowledgeQuery: string | null;
};

/**
 * 예측 한 건의 계보를 받는다 (Phase 9).
 *
 * 없는 예측이면 서버가 404를 내고 여기서는 `null`이 된다 — 화면은 그것을 오류가
 * 아니라 "그런 예측이 없다"로 세운다.
 */
export async function fetchPredictionAudit(
  eventSlug: string,
  matchKey: string,
): Promise<PredictionAudit | null> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), requestTimeoutMs);
  try {
    const path = `${encodeURIComponent(eventSlug)}/${encodeURIComponent(matchKey)}`;
    const res = await fetch(`${aiLabBaseUrl}/audit/${path}`, {
      signal: controller.signal,
    });
    if (!res.ok) return null;
    return (await res.json()) as PredictionAudit;
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
  /**
   * 채점에서 빠진 이유, 아니면 `null`. 이 목록은 폴백을 이미 뺀 뒤라
   * 실제로 오는 값은 `ex_post` 하나다.
   */
  scoringExclusion: string | null;
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
  /** 계보를 아는 청크 수. 이 문서의 작성 시점을 아는지는 발행일이 아니라 이쪽이 말한다. */
  chunksWithRevision: number;
  /** 이 문서에서 **가장 늦은** 개정본 시각 — 판정은 최악을 기준으로 한다. */
  latestRevisedAt: string | null;
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
  /** `chunks`보다 작으면 코퍼스가 `temporalVerifiable=false`다 — 판정과 같은 값이다. */
  chunksWithRevision: number;
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

/** 문서 하나가 예측 하나를 막은 간선 (Phase 10). */
export type LeakageEdge = {
  eventSlug: string;
  eventLabel: string;
  matchKey: string;
  matchTitle: string;
  /** 판정이 낸 그 예측의 상태. **그래프가 다시 정하지 않는다.** */
  status: EvaluationStatus;
  /** 이 문서가 실패시킨 규칙 코드. 비어 있지 않다. */
  codes: string[];
  /** 이 문서만 없었다면 자격을 얻었는가 (반사실). */
  soleCause: boolean;
  /**
   * 이 문서가 그 예측의 **유일한 근거**였는가.
   *
   * 유일했다면 빼는 순간 근거가 0건이 되어 코퍼스 규칙이 통과시킨다. 그 통과는
   * `soleCause`로 세지 않는다 — "근거가 사라져서 통과"이지 "혼자 막았다"가 아니다.
   */
  soleEvidence: boolean;
};

export type LeakageDocument = {
  sourceUrl: string;
  sourceDomain: string;
  blocked: number;
  soleCause: number;
  codes: string[];
  predictions: LeakageEdge[];
};

/** **합이 맞아야 한다**: `blockedPredictions === attributed + unattributed`. */
export type LeakageTotals = {
  blockedPredictions: number;
  attributed: number;
  /** 문서로 돌릴 수 없는 수 — 시간 역전처럼 근거의 성질이 아닌 이유로 막힌 예측. */
  unattributed: number;
  documents: number;
  soleCausePredictions: number;
};

/**
 * 어느 문서가 어느 예측을 막았는가 (Phase 10).
 *
 * **새 판정이 아니다.** 예측의 상태는 평가 화면이 내는 것과 같은 계산에서 나온다.
 */
export type AiLabLeakage = {
  totals: LeakageTotals;
  integrity: Integrity;
  documents: LeakageDocument[];
  /** **문서로 돌릴 수 있는 셋만.** 건수는 오지 않는다 — 전체 집계는 평가 화면 몫이다. */
  rules: RuleDefinition[];
};

/**
 * 대회 하나의 위험도 (Phase 8).
 *
 * **판정이 아니라 위험이다.** 자격은 예측이 생긴 뒤에 평가 화면이 정한다.
 */
export type ReadinessRisk = "clear" | "hold_risk" | "disqualify_risk";

/** 그 대회를 막을 문서 하나. **자기참조 지뢰만 온다.** */
export type ReadinessMine = {
  sourceUrl: string;
  sourceDomain: string;
  title: string | null;
  chunks: number;
  /** 계보를 아는 청크 수. `chunks`보다 작으면 시간 확인도 함께 막힌다. */
  chunksWithRevision: number;
};

export type ReadinessEvent = {
  slug: string;
  label: string;
  startDate: string;
  /** 대회 행에 적힌 상태. **위험도와 무관하다** — 사람이 닫으므로 드리프트한다. */
  status: string;
  daysUntil: number;
  matches: number;
  /** 이미 예측이 만들어진 경기 수. **자격은 보지 않는다.** */
  predicted: number;
  mines: ReadinessMine[];
  /**
   * 이 대회 날짜 기준으로 시간을 확인할 수 없는 문서 수.
   *
   * 목록이 아닌 이유는 그것이 대회가 아니라 **문서의 성질**이라 대회마다 같은
   * 목록이 반복되기 때문이다 — 그 목록은 코퍼스 칸에 한 번 선다.
   */
  unverifiableDocuments: number;
  risk: ReadinessRisk;
};

export type ReadinessCorpus = {
  documents: number;
  /** 계보가 불완전한 문서 수. **어느 대회를 예측하든** 인용되면 보류를 만든다. */
  incompleteLineage: number;
  /** 임베딩이 하나도 없는 문서 수. 지뢰가 아니라 **없는 것**이다. */
  unembeddedDocuments: number;
};

/** **합이 맞아야 한다**: `events === clear + holdRisk + disqualifyRisk`. */
export type ReadinessTotals = {
  events: number;
  clear: number;
  holdRisk: number;
  disqualifyRisk: number;
  /** 날짜가 없어 앞에 있는지조차 모르는 대회 수. 0이 아니면 그만큼 못 보고 있다. */
  undatedEvents: number;
  matches: number;
  predictedMatches: number;
  mineDocuments: number;
};

/**
 * 지금 코퍼스로 다음 대회를 예측하면 무엇이 막히는가 (Phase 8).
 *
 * **다른 화면과 보는 방향이 반대다.** 나머지는 이미 만들어진 예측을 놓고 무엇이
 * 막혔는지 묻고, 이 화면은 아직 없는 예측을 놓고 무엇이 막을지 묻는다.
 */
export type AiLabReadiness = {
  totals: ReadinessTotals;
  corpus: ReadinessCorpus;
  integrity: Integrity;
  events: ReadinessEvent[];
  /** **앞서 볼 수 있는 둘만.** `revision_after_prediction`은 견줄 예측 시각이 없다. */
  rules: RuleDefinition[];
};

export async function fetchAiLabReadiness(): Promise<AiLabReadiness | null> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), requestTimeoutMs);
  try {
    const res = await fetch(`${aiLabBaseUrl}/readiness`, { signal: controller.signal });
    if (!res.ok) return null;
    return (await res.json()) as AiLabReadiness;
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}

export async function fetchAiLabLeakage(): Promise<AiLabLeakage | null> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), requestTimeoutMs);
  try {
    const res = await fetch(`${aiLabBaseUrl}/leakage`, { signal: controller.signal });
    if (!res.ok) return null;
    return (await res.json()) as AiLabLeakage;
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}

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

/**
 * 채점에서 빠진 이유를 화면 문구로 (Phase 3-8 잔여).
 *
 * **세 화면이 같은 문구를 써야 한다.** 예측 목록·개요 최근·Synthesis 항목이
 * 각자 다르게 적으면, 같은 예측이 화면마다 다른 이유로 빠진 것처럼 읽힌다.
 *
 * 모르는 코드는 그대로 내보낸다 — 서버가 사유를 늘렸는데 화면이 조용히 "채점됨"인
 * 척하는 것이 더 나쁘다.
 */
const SCORING_EXCLUSION_LABELS: Record<string, string> = {
  ex_post: "사후 재현 — 채점 제외",
  bookmaker_fallback: "배당 대체 — 채점 제외",
};

export function scoringExclusionLabel(reason: string): string {
  return SCORING_EXCLUSION_LABELS[reason] ?? `채점 제외 (${reason})`;
}
