"use client";

import { useEffect, useState } from "react";
import { AiLabShell } from "@/components/ai-lab/ai-lab-shell";
import { IntegrityBanner } from "@/components/ai-lab/integrity-banner";
// 대시보드 공통 조각은 데이터 센터(Phase 2)의 것을 그대로 쓴다 — 같은 것을 두 벌 만들지 않는다.
import {
  DataUnavailable,
  LoadingBlock,
  StatTile,
} from "@/components/data-center/data-center-shell";
import {
  agentLabel,
  fetchAiLabOverview,
  formatRatio,
  type AiLabOverview,
  type SystemComponent,
  type SystemState,
} from "@/lib/ai-lab-api";
import { cn } from "@/lib/utils";

type PageState =
  | { status: "loading" }
  | { status: "ready"; data: AiLabOverview }
  | { status: "error" };

/**
 * AI Overview (Phase 3-1) — 그리고 그 위에 얹힌 Evaluation Integrity (Phase 3-0).
 *
 * **이 화면의 첫 블록은 성과가 아니라 경고다.** 현재 적중률은 12전 12승 100%인데,
 * 그 숫자를 그대로 세우면 거짓말이 된다 — 표본이 12건이고, 한 대회뿐이고, 예측의
 * 대부분이 그 대회 결과가 적힌 문서를 근거로 인용했다. 세 사실 모두 서버가 실제로
 * 센 값이고, 화면은 그것을 숨기지 않는다.
 *
 * 모든 숫자는 `/api/ai-lab/overview`가 준 값이다. 화면에서 만들어 내는 수치는 없다.
 */
export default function AiLabPage() {
  const [state, setState] = useState<PageState>({ status: "loading" });

  useEffect(() => {
    let alive = true;
    void (async () => {
      const data = await fetchAiLabOverview();
      if (!alive) return;
      setState(data ? { status: "ready", data } : { status: "error" });
    })();
    return () => {
      alive = false;
    };
  }, []);

  return (
    <AiLabShell
      title="AI Overview"
      description="예측이 어떻게 만들어지고 무엇으로 평가되는지, 그리고 그 평가를 어디까지 믿을 수 있는지."
    >
      {state.status === "loading" && <LoadingBlock rows={4} />}
      {state.status === "error" && <DataUnavailable what="AI LAB 개요" />}
      {state.status === "ready" && <Overview data={state.data} />}
    </AiLabShell>
  );
}

function Overview({ data }: { data: AiLabOverview }) {
  const { predictions: p, integrity, system, agents, recent } = data;

  return (
    <div className="flex flex-col gap-8">
      <IntegrityBanner integrity={integrity} totals={p} />

      <section>
        <SectionTitle>Prediction Record</SectionTitle>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
          <StatTile value={p.total} label="AI Predictions" note="저장된 예측" />
          <StatTile
            value={p.graded}
            label="Graded"
            note="결과가 나온 경기"
            tone="data"
          />
          <StatTile value={p.correct} label="Correct" note={`실패 ${p.incorrect}`} />
          <StatTile
            value={p.hitRate === null ? null : `${formatRatio(p.hitRate)}`}
            label="Hit Rate"
            note={
              p.hitRate === null
                ? "채점된 예측 없음"
                : `${p.correct}/${p.graded} · 95% CI ${formatRatio(p.hitRateLow)}–${formatRatio(p.hitRateHigh)}`
            }
          />
          <StatTile
            value={formatRatio(p.avgConfidence)}
            label="Avg Confidence"
            note={`평균 승률 ${formatRatio(p.avgWinProbability)}`}
          />
        </div>
        <p className="mt-3 text-xs text-muted-foreground">
          적중률은 점추정과 <strong className="font-semibold">윌슨 95% 신뢰구간</strong>을
          함께 적습니다. 표본이 작을 때 점추정만 세우면 그 자체가 과장입니다
          {p.bookmakerFallback > 0 && ` · 북메이커 폴백 ${p.bookmakerFallback}건은 채점에서 제외`}
          .
        </p>
      </section>

      <section>
        <SectionTitle>AI System Status</SectionTitle>
        <ul className="flex flex-col gap-2">
          {system.map((item) => (
            <SystemRow key={item.key} item={item} />
          ))}
        </ul>
        <p className="mt-3 text-xs text-muted-foreground">
          이 화면은 LLM을 호출하지 않습니다 — 확인하지 않은 것은{" "}
          <span className="text-foreground">unknown</span>으로 둡니다. 초록불을 채우려고
          헬스체크를 부르면 화면 진입이 곧 비용이 됩니다.
        </p>
      </section>

      <section>
        <SectionTitle>Agent Activity</SectionTitle>
        {agents.length === 0 ? (
          <p className="rounded-xl border border-dashed border-border bg-card/50 px-4 py-6 text-center text-sm text-muted-foreground">
            리포트를 낸 에이전트가 없습니다.
          </p>
        ) : (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            {agents.map((agent) => (
              <div
                key={agent.agent}
                className="rounded-xl border border-border bg-card px-4 py-3"
              >
                <p className="font-sport text-base text-data">{agentLabel(agent.agent)}</p>
                <p className="mt-1 text-2xl font-bold tabular-nums text-foreground">
                  {agent.withPick}
                  <span className="text-base text-muted-foreground">/{agent.reports}</span>
                </p>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  의견을 낸 리포트 / 전체 · 평균 가중치 {formatRatio(agent.avgWeight)}
                </p>
              </div>
            ))}
          </div>
        )}
        <p className="mt-3 text-xs text-muted-foreground">
          에이전트 이름은 코드의 이름 그대로입니다. 근거가 없으면 모델을 부르지 않고
          &ldquo;의견 없음&rdquo;을 내며, 그것은 고장이 아니라 설계된 동작입니다.
        </p>
      </section>

      <section>
        <SectionTitle>Recent Predictions</SectionTitle>
        {recent.length === 0 ? (
          <p className="rounded-xl border border-dashed border-border bg-card/50 px-4 py-6 text-center text-sm text-muted-foreground">
            저장된 예측이 없습니다.
          </p>
        ) : (
          <ul className="flex flex-col gap-2">
            {recent.map((row) => (
              <li
                key={`${row.eventSlug}-${row.matchKey}`}
                className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 rounded-xl border border-border bg-card px-4 py-3"
              >
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-foreground">
                    {row.pickName}
                  </p>
                  <p className="truncate text-xs text-muted-foreground">
                    {row.eventLabel} · {row.matchTitle}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-3">
                  <span className="text-xs tabular-nums text-muted-foreground">
                    승률 {formatRatio(row.winProbability)} · 확신{" "}
                    {formatRatio(row.confidence)}
                  </span>
                  <ResultBadge correct={row.correct} />
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}


const STATE_STYLE: Record<SystemState, { dot: string; text: string; label: string }> = {
  operational: { dot: "bg-chart-win", text: "text-chart-win", label: "operational" },
  degraded: { dot: "bg-live", text: "text-live", label: "degraded" },
  empty: { dot: "bg-chart-pending", text: "text-muted-foreground", label: "empty" },
  unknown: { dot: "bg-chart-pending", text: "text-muted-foreground", label: "unknown" },
};

/** 상태는 **색만으로 말하지 않는다** — 점 옆에 상태 문자열을 항상 적는다(DESIGN.md §2). */
function SystemRow({ item }: { item: SystemComponent }) {
  const style = STATE_STYLE[item.state] ?? STATE_STYLE.unknown;
  return (
    <li className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-xl border border-border bg-card px-4 py-3">
      <span className="flex shrink-0 items-center gap-2">
        <span aria-hidden className={cn("h-2 w-2 rounded-full", style.dot)} />
        <span className="text-sm font-medium text-foreground">{item.label}</span>
      </span>
      <span className={cn("shrink-0 text-xs uppercase tracking-[0.12em]", style.text)}>
        {style.label}
      </span>
      <span className="min-w-0 basis-full text-xs text-muted-foreground sm:basis-auto">
        {item.detail}
      </span>
    </li>
  );
}

/** 미채점은 빈칸이 아니라 **미채점**이라고 적는다 — 실패와 다른 상태다. */
function ResultBadge({ correct }: { correct: boolean | null }) {
  if (correct === null) {
    return (
      <span className="rounded border border-border px-1.5 py-0.5 text-xs text-muted-foreground">
        미채점
      </span>
    );
  }
  return (
    <span
      className={cn(
        "rounded px-1.5 py-0.5 text-xs font-medium",
        correct
          ? "border border-chart-win/50 bg-chart-win/10 text-chart-win"
          : "border border-live/50 bg-live/10 text-live",
      )}
    >
      {correct ? "적중" : "실패"}
    </span>
  );
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="mb-3 font-sport text-base tracking-wide text-foreground">{children}</h2>
  );
}
