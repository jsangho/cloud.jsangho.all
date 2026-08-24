"use client";

import { useEffect, useState } from "react";
import { AiLabShell } from "@/components/ai-lab/ai-lab-shell";
import { IntegrityBanner } from "@/components/ai-lab/integrity-banner";
// 대시보드 공통 조각은 데이터 센터(Phase 2)의 것을 그대로 쓴다.
import {
  DataUnavailable,
  LoadingBlock,
  StatTile,
} from "@/components/data-center/data-center-shell";
import {
  agentLabel,
  fetchAiLabEvaluation,
  fetchAiLabPerformance,
  formatRatio,
  type AgentContribution,
  type AiLabEvaluation,
  type AiLabPerformance,
  type ConsensusLevel,
  type EvaluationItem,
  type EvaluationStatus,
  type PerformanceItem,
} from "@/lib/ai-lab-api";
import { cn } from "@/lib/utils";

type PageState =
  | { status: "loading" }
  | { status: "ready"; data: AiLabPerformance }
  | { status: "error" };

type EvaluationState =
  | { status: "loading" }
  | { status: "ready"; data: AiLabEvaluation }
  | { status: "error" };

/**
 * Synthesis (Phase 3-5).
 *
 * **이 화면은 AI가 얼마나 잘 맞히는지를 재지 않는다.** 최종 승률 숫자가 무엇으로
 * 만들어졌는지를 해부한다. 정확도는 이미 두 곳이 답했다 — 전체는 Overview,
 * 에이전트별은 Agents다. 여기서 또 세면 같은 숫자가 세 번 나온다.
 *
 * **차트를 만들지 않았다.** 그릴 후보가 셋인데(캘리브레이션·확신 분포·weight 분포)
 * 전부 표본이 모자라거나 계열이 상수라 점 하나로 찍힌다. 지금은 표가 더 정확하다.
 *
 * 라우트는 `/ai-lab/performance`로 두고 라벨만 Synthesis다 — 엔드포인트·URL·파일명이
 * 서로 다른 이름을 갖지 않게 하기 위해서다. "Performance"라는 이름은 누수 없는 표본이
 * 생긴 뒤의 실제 성능 화면을 위해 남겨 둔다.
 */
export default function AiLabPerformancePage() {
  const [state, setState] = useState<PageState>({ status: "loading" });
  /* 자격 판정은 **따로 받는다** — 한쪽이 실패해도 다른 쪽은 그대로 선다. */
  const [evaluation, setEvaluation] = useState<EvaluationState>({ status: "loading" });

  useEffect(() => {
    let alive = true;
    void (async () => {
      const data = await fetchAiLabPerformance();
      if (!alive) return;
      setState(data ? { status: "ready", data } : { status: "error" });
    })();
    void (async () => {
      const data = await fetchAiLabEvaluation();
      if (!alive) return;
      setEvaluation(data ? { status: "ready", data } : { status: "error" });
    })();
    return () => {
      alive = false;
    };
  }, []);

  return (
    <AiLabShell
      title="Synthesis"
      description="이 화면은 AI가 얼마나 잘 맞히는지를 재지 않습니다. 최종 승률 숫자가 무엇으로 만들어졌는지를 해부합니다."
    >
      {state.status === "loading" && <LoadingBlock rows={4} />}
      {state.status === "error" && <DataUnavailable what="합성 해부" />}
      {state.status === "ready" && <Synthesis data={state.data} />}

      <div className="mt-6">
        {evaluation.status === "loading" && <LoadingBlock rows={2} />}
        {evaluation.status === "error" && <DataUnavailable what="평가 자격" />}
        {evaluation.status === "ready" && <Eligibility data={evaluation.data} />}
      </div>
    </AiLabShell>
  );
}

/**
 * Evaluation eligibility (Phase 3-6).
 *
 * **어떤 예측이 채점 대상이 될 자격이 있는가.** 3-0의 무결성 경고가 표본 수준에서
 * "이 숫자를 믿어도 되는가"를 물었다면, 여기서는 예측 하나하나가 애초에 분모에
 * 들어갈 자격이 있는지를 판정한 결과를 옮긴다.
 *
 * **문구를 화면이 지어내지 않는다** — 규칙 이름·설명·판정 사유가 전부 서버에서 온다.
 * 자격이 0건이면 성능 블록 자체가 없다(`performance === null`).
 */
function Eligibility({ data }: { data: AiLabEvaluation }) {
  const { totals, rules, items, performance } = data;

  return (
    <section
      aria-labelledby="eligibility-heading"
      className="flex flex-col gap-4 border-t border-border pt-6"
    >
      <div>
        <h2 id="eligibility-heading" className="font-sport text-base tracking-wide text-foreground">
          Evaluation eligibility
        </h2>
        <p className="mt-0.5 text-xs text-muted-foreground">
          채점 대상이 될 자격이 있는 예측이 몇 건인가. 자격 없는 예측은 경고를 붙이는 것이 아니라
          분모에서 빼냅니다.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
        <StatTile
          value={totals.eligible}
          label="Eligible"
          note="채점 가능"
          tone={totals.eligible > 0 ? "data" : "default"}
        />
        <StatTile value={totals.disqualified} label="Disqualified" note="누수 확정" />
        <StatTile value={totals.held} label="Held" note="증명도 반증도 불가" />
        <StatTile value={totals.pending} label="Pending" note="결과 없음" />
        <StatTile value={totals.fallback} label="N/A" note="배당 폴백" />
      </div>

      <EligiblePerformanceBlock
        performance={performance}
        eligible={totals.eligible}
        predictions={totals.predictions}
      />

      <ul className="flex flex-col gap-2">
        {rules.map((rule) => (
          <li key={rule.code} className="rounded-xl border border-border bg-card px-4 py-3">
            <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
              <p className="text-sm font-medium text-foreground">
                {rule.label}{" "}
                <span className="font-normal text-muted-foreground">({rule.code})</span>
              </p>
              <span className="flex items-center gap-2">
                <SeverityBadge severity={rule.severity} />
                <span className="text-xs tabular-nums text-muted-foreground">{rule.blocked}건</span>
              </span>
            </div>
            <p className="mt-1 text-xs text-muted-foreground">{rule.description}</p>
          </li>
        ))}
      </ul>

      {items.length > 0 && (
        <ul className="flex flex-col gap-2">
          {items.map((item) => (
            <EligibilityRow key={`${item.eventSlug}-${item.matchKey}`} item={item} />
          ))}
        </ul>
      )}
    </section>
  );
}

/** 자격 있는 표본이 없으면 **숫자를 세우지 않는다.** 0%를 만들지 않기 위해서다. */
function EligiblePerformanceBlock({
  performance,
  eligible,
  predictions,
}: {
  performance: AiLabEvaluation["performance"];
  eligible: number;
  predictions: number;
}) {
  if (performance === null) {
    return (
      <div className="rounded-xl border border-live/40 bg-card px-4 py-4 sm:px-5">
        <p className="text-sm font-medium text-foreground">
          자격 있는 표본이 {eligible}건입니다 — 성능을 계산하지 않았습니다.
        </p>
        <p className="mt-1 text-xs text-muted-foreground">
          저장된 예측 {predictions}건 중 채점 대상 자격을 얻은 것이 없습니다. 0%나 임시 숫자로 이
          자리를 채우지 않습니다.
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-border bg-card px-4 py-4 sm:px-5">
      <p className="text-sm text-foreground">
        자격 표본 {performance.sample}건 ·{" "}
        <span className="tabular-nums">
          {formatRatio(performance.accuracy)} ({performance.correct}/{performance.sample})
        </span>{" "}
        <span className="text-muted-foreground">
          · 95% CI {formatRatio(performance.accuracyLow)}–{formatRatio(performance.accuracyHigh)}
        </span>
      </p>
      <p className="mt-1 text-xs text-muted-foreground">
        대회 {performance.eventsCovered}개 기준. 자격 판정을 통과한 표본이지만 위의 무결성 경고는
        그대로 적용됩니다 — 자격과 일반화 가능성은 다른 층위입니다.
      </p>
    </div>
  );
}

function EligibilityRow({ item }: { item: EvaluationItem }) {
  const blocking = item.verdicts.filter((v) => v.failed || !v.applicable);

  return (
    <li className="rounded-xl border border-border bg-card px-4 py-3">
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
        <div className="min-w-0">
          <p className="text-xs text-muted-foreground">{item.eventLabel}</p>
          <p className="mt-0.5 truncate text-sm font-medium text-foreground">{item.matchTitle}</p>
        </div>
        <StatusBadge status={item.status} />
      </div>
      {blocking.length > 0 && (
        <ul className="mt-2 flex flex-col gap-1">
          {blocking.map((verdict) => (
            <li key={verdict.code} className="flex gap-2 text-xs text-muted-foreground">
              <span aria-hidden className="select-none">
                ·
              </span>
              {/* 사유는 서버가 낸 문장 그대로다. */}
              <span>{verdict.detail}</span>
            </li>
          ))}
        </ul>
      )}
    </li>
  );
}

/** **보류를 실격으로 적지 않는다.** 색만으로 말하지 않고 글자를 함께 단다. */
function SeverityBadge({ severity }: { severity: string }) {
  const label = severity === "disqualify" ? "실격" : severity === "hold" ? "보류" : "제외";
  return (
    <span
      className={cn(
        "rounded border px-1.5 py-0.5 text-xs",
        severity === "disqualify"
          ? "border-live/50 bg-live/10 text-live"
          : "border-border text-muted-foreground",
      )}
    >
      {label}
    </span>
  );
}

function StatusBadge({ status }: { status: EvaluationStatus }) {
  const label: Record<EvaluationStatus, string> = {
    eligible: "자격 있음",
    disqualified: "실격",
    held: "보류",
    pending: "결과 없음",
    not_applicable: "평가 대상 아님",
  };
  return (
    <span
      className={cn(
        "shrink-0 rounded border px-1.5 py-0.5 text-xs",
        status === "eligible"
          ? "border-data-500/50 bg-data-surface text-data"
          : status === "disqualified"
            ? "border-live/50 bg-live/10 text-live"
            : "border-border text-muted-foreground",
      )}
    >
      {label[status]}
    </span>
  );
}

function Synthesis({ data }: { data: AiLabPerformance }) {
  const { totals, integrity, inferential, consensus, contributions, items } = data;

  return (
    <div className="flex flex-col gap-6">
      {/* 적중률 타일이 없다 — 이 화면의 주인공은 비율이 아니라 분모다. */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatTile
          value={totals.predictions}
          label="Predictions"
          note={`2파전 ${totals.singles} · 다파전 ${totals.multi}`}
        />
        <StatTile
          value={totals.graded}
          label="Graded"
          note={`미채점 ${totals.predictions - totals.bookmakerFallback - totals.graded}`}
          tone="data"
        />
        <StatTile
          value={`${integrity.eventsCovered}/${integrity.eventsTotal}`}
          label="Events covered"
          note="예측이 있는 대회 / 전체"
        />
        <StatTile
          value={totals.bookmakerFallback}
          label="Fallback"
          note="배당으로 대체된 예측 — 집계에서 제외"
        />
      </div>

      {/* totals를 넘기지 않는다 — 적중률 줄이 이 화면 제목 옆에 서면 안 된다. */}
      <IntegrityBanner integrity={integrity} />

      <InferentialLock inferential={inferential} />

      <Consensus levels={consensus} />

      <Contributions contributions={contributions} />

      <Items items={items} />

      <p className="text-xs text-muted-foreground">
        <strong className="font-semibold">승률이 높다고 근거가 두꺼운 것은 아닙니다.</strong> 의견을
        낸 에이전트가 하나뿐이고 그 확신이 최대치면 분포가 한쪽으로 붕괴해 승률이 100%로 나옵니다 —
        가장 확신에 찬 예측이 아니라 <strong className="font-semibold">가장 적게 답한 예측</strong>
        입니다. 승률 옆의 Coverage를 함께 보세요.
      </p>
    </div>
  );
}

/**
 * 추론 지표 잠금.
 *
 * **새 문턱을 만들지 않는다** — 서버가 보낸 `integrity.generalizable`과 그 이유를
 * 그대로 옮긴다. 숨기지 않고 "왜 못 그리는지"를 적는 것이 DESIGN.md §14의 규범이다.
 */
function InferentialLock({ inferential }: { inferential: AiLabPerformance["inferential"] }) {
  if (inferential.available) {
    return (
      <section className="rounded-xl border border-border bg-card px-4 py-4 sm:px-5">
        <h2 className="font-sport text-base tracking-wide text-foreground">Inferential metrics</h2>
        <p className="mt-2 text-sm text-muted-foreground">
          무결성 판정이 통과했습니다. 캘리브레이션 같은 추론 지표를 낼 조건이 갖춰졌습니다.
        </p>
      </section>
    );
  }

  return (
    <section
      aria-labelledby="lock-heading"
      className="rounded-xl border border-border bg-card px-4 py-4 sm:px-5"
    >
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <h2 id="lock-heading" className="font-sport text-base tracking-wide text-foreground">
          Inferential metrics
        </h2>
        <span className="rounded border border-border px-1.5 py-0.5 text-xs text-muted-foreground">
          내지 않음
        </span>
      </div>
      <p className="mt-2 text-sm text-muted-foreground">
        캘리브레이션 곡선 · Brier 점수 · ROC 같은 추론 지표를 이 화면에서 내지 않습니다. 아래가
        서버가 밝힌 이유이며, 이 화면이 따로 정한 기준은 없습니다.
      </p>
      {inferential.reasons.length > 0 && (
        <ul className="mt-3 flex flex-col gap-1">
          {inferential.reasons.map((reason) => (
            <li key={reason} className="flex gap-2 text-xs text-muted-foreground">
              <span aria-hidden className="select-none">
                ·
              </span>
              <span>{reason}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

/**
 * 합의 분해.
 *
 * 저장된 확신은 `동의도 × 응답률`인데, 곱해 놓으면 "둘이 답해 둘 다 동의"와
 * "셋이 답해 둘이 동의"가 같은 값으로 보인다. 두 인수를 갈라 놓으면 갈린다.
 */
function Consensus({ levels }: { levels: ConsensusLevel[] }) {
  return (
    <section aria-labelledby="consensus-heading" className="flex flex-col gap-3">
      <div>
        <h2 id="consensus-heading" className="font-sport text-base tracking-wide text-foreground">
          Consensus
        </h2>
        <p className="mt-0.5 text-xs text-muted-foreground">
          확신 = 동의도 × 응답률. 곱이 같아도 답한 수가 다르면 근거의 두께가 다릅니다.
        </p>
      </div>

      {levels.length === 0 ? (
        <EmptyRow>합의를 잴 예측이 없습니다.</EmptyRow>
      ) : (
        <ul className="flex flex-col gap-2">
          {levels.map((level) => (
            <li
              key={`${level.answered}-${level.agreed}`}
              className="rounded-xl border border-border bg-card px-4 py-3"
            >
              <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
                <p className="text-sm text-foreground">
                  <span className="tabular-nums">{level.answered}</span>명이 답해{" "}
                  <span className="tabular-nums">{level.agreed}</span>명이 동의
                </p>
                <p className="text-xs tabular-nums text-muted-foreground">
                  확신 {formatRatio(level.confidence)}
                </p>
              </div>
              <dl className="mt-2 grid grid-cols-2 gap-x-6 gap-y-1 sm:grid-cols-3">
                <Fact label="Predictions" value={`${level.predictions}`} />
                <Fact label="Graded" value={`${level.graded}`} />
                <Fact
                  label="Correct"
                  value={level.graded === 0 ? "—" : `${level.correct}/${level.graded}`}
                />
              </dl>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

/**
 * 기여 변동성.
 *
 * Agents(3-3)가 "그 의견이 맞았나"를 보는 자리라면 여기는 "그 에이전트가 최종 숫자에
 * 정보를 넣었나"를 본다. 한 값만 내는 에이전트는 100% 맞혀도 승률의 변동에는
 * 기여하지 않는다. **판단이 아니라 실측이다** — 서로 다른 값을 세면 나온다.
 */
function Contributions({ contributions }: { contributions: AgentContribution[] }) {
  return (
    <section aria-labelledby="contributions-heading" className="flex flex-col gap-3">
      <div>
        <h2
          id="contributions-heading"
          className="font-sport text-base tracking-wide text-foreground"
        >
          Contributions
        </h2>
        <p className="mt-0.5 text-xs text-muted-foreground">
          그 에이전트가 낸 확신 값이 실제로 움직이는지. 정확도가 아니라 변동성입니다.
        </p>
      </div>

      {contributions.length === 0 ? (
        <EmptyRow>리포트를 낸 에이전트가 없습니다.</EmptyRow>
      ) : (
        <ul className="flex flex-col gap-2">
          {contributions.map((item) => (
            <li key={item.agent} className="rounded-xl border border-border bg-card px-4 py-3">
              <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
                <h3 className="font-sport text-base text-data">{agentLabel(item.agent)}</h3>
                {item.constant === true && (
                  <span className="rounded border border-border px-1.5 py-0.5 text-xs text-muted-foreground">
                    값이 하나뿐 — 변동에 기여하지 않음
                  </span>
                )}
              </div>
              <dl className="mt-2 grid grid-cols-2 gap-x-6 gap-y-1 sm:grid-cols-4">
                <Fact label="Opinions" value={`${item.opinions}/${item.reports}`} />
                <Fact label="Distinct values" value={`${item.distinctWeights}`} />
                <Fact
                  label="Range"
                  value={
                    item.minWeight === null || item.maxWeight === null
                      ? "—"
                      : `${item.minWeight.toFixed(2)} – ${item.maxWeight.toFixed(2)}`
                  }
                />
                <Fact
                  label="Constant"
                  value={item.constant === null ? "—" : item.constant ? "Yes" : "No"}
                />
              </dl>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function Items({ items }: { items: PerformanceItem[] }) {
  return (
    <section aria-labelledby="items-heading" className="flex flex-col gap-3">
      <div>
        <h2 id="items-heading" className="font-sport text-base tracking-wide text-foreground">
          Predictions
        </h2>
        <p className="mt-0.5 text-xs text-muted-foreground">
          최종 승률과 그것을 만든 리포트. 승률이 높은 순입니다.
        </p>
      </div>

      {items.length === 0 ? (
        <EmptyRow>해부할 예측이 없습니다.</EmptyRow>
      ) : (
        <ul className="flex flex-col gap-2">
          {items.map((item) => (
            <ItemRow key={`${item.eventSlug}-${item.matchKey}`} item={item} />
          ))}
        </ul>
      )}
    </section>
  );
}

function ItemRow({ item }: { item: PerformanceItem }) {
  /** 의견 하나로 붕괴한 승률. 숫자만 보면 가장 확신에 차 보이는 자리다. */
  const thinEvidence = item.winProbability >= 1 && item.coverage < 1;

  return (
    <li className="rounded-xl border border-border bg-card px-4 py-3">
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
        <div className="min-w-0">
          <p className="text-xs text-muted-foreground">{item.eventLabel}</p>
          <p className="mt-0.5 truncate text-sm font-medium text-foreground">{item.matchTitle}</p>
        </div>
        <p className="shrink-0 text-sm tabular-nums text-foreground">
          승률 {formatRatio(item.winProbability)}
        </p>
      </div>

      <dl className="mt-3 grid grid-cols-2 gap-x-6 gap-y-2 sm:grid-cols-4">
        <Fact label="Confidence" value={formatRatio(item.confidence)} />
        <Fact label="Agreement" value={formatRatio(item.agreement)} />
        <Fact label="Coverage" value={formatRatio(item.coverage)} />
        <Fact
          label="Result"
          value={item.correct === null ? "Pending" : item.correct ? "적중" : "실패"}
        />
      </dl>

      <ul className="mt-3 flex flex-wrap gap-1.5">
        {item.reports.length === 0 && (
          <li>
            <Note tone="neutral">저장된 리포트가 없습니다</Note>
          </li>
        )}
        {item.reports.map((report) => (
          <li key={report.agent}>
            <Note tone="neutral">
              {agentLabel(report.agent)}{" "}
              {report.opinionated ? report.weight.toFixed(2) : "의견 없음"}
            </Note>
          </li>
        ))}
      </ul>

      {thinEvidence && (
        <p className="mt-2 text-xs text-muted-foreground">
          승률 100%는 확신의 크기가 아니라{" "}
          <strong className="font-semibold">한 명만 답한 결과</strong>입니다 — 의견이 하나면 분포가
          그쪽으로 붕괴합니다.
        </p>
      )}
    </li>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-[0.12em] text-muted-foreground">{label}</dt>
      <dd className="mt-0.5 text-sm font-medium tabular-nums text-foreground">{value}</dd>
    </div>
  );
}

/** 사실만 적는다 — "어느 에이전트가 더 낫다" 같은 해석은 화면이 하지 않는다. */
function Note({ tone, children }: { tone: "neutral" | "warn"; children: React.ReactNode }) {
  return (
    <span
      className={cn(
        "rounded border px-1.5 py-0.5 text-xs",
        tone === "warn"
          ? "border-live/50 bg-live/10 text-live"
          : "border-border text-muted-foreground",
      )}
    >
      {children}
    </span>
  );
}

function EmptyRow({ children }: { children: React.ReactNode }) {
  return (
    <p className="rounded-xl border border-dashed border-border bg-card/50 px-4 py-8 text-center text-sm text-muted-foreground">
      {children}
    </p>
  );
}
