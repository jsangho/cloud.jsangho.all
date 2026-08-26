"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";
import { AiLabShell } from "@/components/ai-lab/ai-lab-shell";
import { IntegrityBanner } from "@/components/ai-lab/integrity-banner";
// 대시보드 공통 조각은 데이터 센터(Phase 2)의 것을 그대로 쓴다.
import {
  DataUnavailable,
  LoadingBlock,
} from "@/components/data-center/data-center-shell";
// 근거 모달은 PLE 화면이 쓰던 것을 **그대로** 연다 — 같은 것을 두 벌 만들지 않는다.
import { AiReportDialog } from "@/components/ple/ai-report-dialog";
import {
  agentLabel,
  fetchAiLabPredictions,
  formatRatio,
  type AiLabPredictions,
  type PredictionItem,
} from "@/lib/ai-lab-api";
import type { AiPrediction } from "@/lib/ple-ai-predictions";
import { cn } from "@/lib/utils";

type PageState =
  | { status: "loading" }
  | { status: "ready"; data: AiLabPredictions }
  | { status: "error" };

const ALL = "__all__";

/**
 * AI LAB Predictions (Phase 3-2).
 *
 * **저장된 예측만 보여 준다** — 이 화면은 LLM을 부르지도, 예측을 만들지도 않는다.
 *
 * 적중률은 목록 위 무결성 상자 안에서만 말한다(§7). 목록을 스크롤하다 "적중"만 열두 번
 * 보게 되므로, 그 위에 표본과 자기 참조 출처가 함께 서 있어야 100%가 무슨 뜻인지 읽힌다.
 */
export default function AiLabPredictionsPage() {
  /* `useSearchParams`는 Suspense 경계 안에서만 정적 프리렌더가 된다(Next 15). */
  return (
    <Suspense fallback={<AiLabShell title="Predictions">{null}</AiLabShell>}>
      <PredictionsView />
    </Suspense>
  );
}

function PredictionsView() {
  const searchParams = useSearchParams();
  /* Agents 화면에서 넘어오는 `?agent=odds`. 모르는 이름이면 서버가 빈 목록을 준다. */
  const agent = searchParams.get("agent");
  const [state, setState] = useState<PageState>({ status: "loading" });
  const [event, setEvent] = useState<string>(ALL);

  useEffect(() => {
    let alive = true;
    setState({ status: "loading" });
    void (async () => {
      const data = await fetchAiLabPredictions(agent ? { agent } : undefined);
      if (!alive) return;
      setState(data ? { status: "ready", data } : { status: "error" });
    })();
    return () => {
      alive = false;
    };
  }, [agent]);

  const data = state.status === "ready" ? state.data : null;
  const items = useMemo(() => {
    if (!data) return [];
    return event === ALL
      ? data.items
      : data.items.filter((item) => item.eventSlug === event);
  }, [data, event]);

  return (
    <AiLabShell
      title="Predictions"
      description="저장된 AI 예측과 각 예측을 만든 세 에이전트의 판단 근거."
    >
      {state.status === "loading" && <LoadingBlock rows={4} />}
      {state.status === "error" && <DataUnavailable what="AI 예측 목록" />}
      {data && (
        <div className="flex flex-col gap-6">
          <p className="text-sm text-muted-foreground">
            <span className="tabular-nums text-foreground">
              {data.totals.total} predictions
            </span>{" "}
            ·{" "}
            <span className="tabular-nums text-foreground">
              {data.integrity.eventsCovered} / {data.integrity.eventsTotal} PLE
            </span>
          </p>

          {agent && <AgentFilterNotice agent={agent} shown={data.items.length} />}

          <IntegrityBanner integrity={data.integrity} totals={data.totals} />

          {data.events.length > 1 && (
            <EventFilter
              events={data.events}
              total={data.items.length}
              value={event}
              onChange={setEvent}
            />
          )}

          {data.items.length === 0 ? (
            <EmptyState what="저장된 예측이 없습니다." />
          ) : items.length === 0 ? (
            <EmptyState what="이 대회에는 저장된 예측이 없습니다." />
          ) : (
            <ul className="flex flex-col gap-2">
              {items.map((item) => (
                <PredictionRow key={`${item.eventSlug}-${item.matchKey}`} item={item} />
              ))}
            </ul>
          )}
        </div>
      )}
    </AiLabShell>
  );
}

/**
 * `?agent=` 로 걸러진 상태임을 밝힌다.
 *
 * 위의 집계·무결성은 **필터와 무관하게 전체**를 설명한다. 그 사실을 안 적으면
 * "odds 예측 12건인데 표본 12건"으로 읽혀 두 숫자가 같은 것을 센다고 오해하게 된다.
 */
function AgentFilterNotice({ agent, shown }: { agent: string; shown: number }) {
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-xl border border-data-500/40 bg-data-surface px-4 py-2.5">
      <span className="text-sm text-foreground">
        <span className="font-medium text-data">{agentLabel(agent)}</span> 에이전트가
        리포트를 낸 예측 <span className="tabular-nums">{shown}</span>건
      </span>
      <Link
        href="/ai-lab/predictions"
        className="text-xs text-brand-link underline underline-offset-2 hover:text-brand-hover"
      >
        필터 해제
      </Link>
      <span className="basis-full text-xs text-muted-foreground">
        아래 집계와 무결성은 필터와 무관하게 저장된 예측 전체를 설명합니다.
      </span>
    </div>
  );
}

function EventFilter({
  events,
  total,
  value,
  onChange,
}: {
  events: AiLabPredictions["events"];
  total: number;
  value: string;
  onChange: (next: string) => void;
}) {
  return (
    <nav aria-label="대회 필터" className="-mx-4 overflow-x-auto px-4 pb-1">
      <ul className="flex min-w-max items-center gap-1.5">
        <li>
          <FilterChip
            active={value === ALL}
            onClick={() => onChange(ALL)}
            label={`전체 ${total}`}
          />
        </li>
        {events.map((option) => (
          <li key={option.slug}>
            <FilterChip
              active={value === option.slug}
              onClick={() => onChange(option.slug)}
              label={`${option.label} ${option.count}`}
            />
          </li>
        ))}
      </ul>
    </nav>
  );
}

function FilterChip({
  active,
  onClick,
  label,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        "inline-flex h-8 items-center rounded-lg border px-3 text-sm font-medium transition-colors",
        active
          ? "border-data-500/50 bg-data-surface text-data"
          : "border-border bg-card text-muted-foreground hover:bg-card-2 hover:text-foreground",
      )}
    >
      {label}
    </button>
  );
}

/**
 * 예측 한 줄.
 *
 * "AI가 맞혔다"를 크게 세우지 않는다 — 결과 배지는 다른 메타데이터와 같은 크기다.
 * 지금 데이터에는 평가 무결성 문제가 있어서, 목록이 성능 홍보처럼 읽히면 안 된다.
 */
function PredictionRow({ item }: { item: PredictionItem }) {
  const fallback = item.source === "bookmaker_fallback";

  return (
    <li className="rounded-xl border border-border bg-card px-4 py-3">
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
        <div className="min-w-0">
          <p className="text-xs text-muted-foreground">
            {item.eventLabel} · {item.matchTitle}
          </p>
          <p className="mt-0.5 truncate text-sm font-medium text-foreground">
            {item.pickName}
          </p>
        </div>
        <div className="flex shrink-0 flex-wrap items-center gap-2">
          <span className="text-xs tabular-nums text-muted-foreground">
            승률 {formatRatio(item.winProbability)} · 확신 {formatRatio(item.confidence)}
          </span>
          <SourceBadge fallback={fallback} />
          <ResultBadge correct={item.correct} winnerName={item.winnerName} />
          {/* 기존 PLE 근거 모달을 그대로 연다. */}
          <AiReportDialog
            slug={item.eventSlug}
            matchTitle={item.matchTitle}
            prediction={toAiPrediction(item)}
          />
        </div>
      </div>
      {item.reports.length === 0 && (
        <p className="mt-2 text-xs text-muted-foreground">
          이 예측에는 저장된 분석 리포트가 없습니다.
        </p>
      )}
    </li>
  );
}

/** `AiReportDialog`가 받는 모양으로 옮긴다. 필드 이름이 같아 값만 추린다. */
function toAiPrediction(item: PredictionItem): AiPrediction {
  return {
    matchKey: item.matchKey,
    pick: item.pick,
    pickName: item.pickName,
    winProbability: item.winProbability,
    confidence: item.confidence,
    rationale: item.rationale,
    source: item.source,
    generatedAt: item.generatedAt,
    reports: item.reports.map((report) => ({
      agent: report.agent,
      pick: report.pick,
      weight: report.weight,
      summary: report.summary,
      sources: report.sources,
    })),
  };
}

/** 폴백으로 만들어진 예측은 화면에서 구분된다 — 에이전트 판단이 아니었다. */
function SourceBadge({ fallback }: { fallback: boolean }) {
  if (!fallback) return null;
  return (
    <span className="rounded border border-border px-1.5 py-0.5 text-xs text-muted-foreground">
      배당 폴백
    </span>
  );
}

/**
 * 결과 배지. **미채점은 빈칸이 아니라 Pending이다** — 실패와 다른 상태다.
 * 색만으로 말하지 않고 글자를 함께 적는다(DESIGN.md §2).
 */
function ResultBadge({
  correct,
  winnerName,
}: {
  correct: boolean | null;
  winnerName: string | null;
}) {
  if (correct === null) {
    return (
      <span className="rounded border border-border px-1.5 py-0.5 text-xs text-muted-foreground">
        Pending
      </span>
    );
  }
  return (
    <span
      title={winnerName ? `실제 승자 ${winnerName}` : undefined}
      className={cn(
        "rounded px-1.5 py-0.5 text-xs font-medium",
        correct
          ? "border border-chart-win/50 bg-chart-win/10 text-chart-win"
          : "border border-live/50 bg-live/10 text-live",
      )}
    >
      {correct ? "Correct" : "Incorrect"}
    </span>
  );
}

function EmptyState({ what }: { what: string }) {
  return (
    <p className="rounded-xl border border-dashed border-border bg-card/50 px-4 py-8 text-center text-sm text-muted-foreground">
      {what}
    </p>
  );
}
