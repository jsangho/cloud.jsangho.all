"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";
import { AiLabShell } from "@/components/ai-lab/ai-lab-shell";
import { IntegrityBanner } from "@/components/ai-lab/integrity-banner";
import { SynthesisVersion } from "@/components/ai-lab/synthesis-version";
// 대시보드 공통 조각은 데이터 센터(Phase 2)의 것을 그대로 쓴다.
import { DataUnavailable, LoadingBlock } from "@/components/data-center/data-center-shell";
// 근거 모달은 PLE 화면이 쓰던 것을 **그대로** 연다 — 같은 것을 두 벌 만들지 않는다.
import { AiReportDialog } from "@/components/ple/ai-report-dialog";
import {
  agentLabel,
  fetchAiLabPredictions,
  formatRatio,
  scoringExclusionLabel,
  type AiLabPredictions,
  type PredictionItem,
} from "@/lib/ai-lab-api";
import type { AiPrediction } from "@/lib/ple-ai-predictions";
import { getPleBySlug } from "@/lib/wwe-ple";
import { getPleMatches } from "@/lib/wwe-ple-matches";
import { cn } from "@/lib/utils";

type PageState =
  | { status: "loading" }
  | { status: "ready"; data: AiLabPredictions }
  | { status: "error" };

const ALL = "__all__";

/**
 * 한 대회의 예측 묶음.
 *
 * **셋으로 쪼갠 수는 서로 겹치지 않고, 합이 `items.length`다** — `excluded` +
 * `pending` + `graded`. 한 줄이 두 칸에 들어가면 머리말의 산수가 닫히지 않아
 * "예측 7건인데 5+3"처럼 읽힌다.
 *
 * `graded`·`correct`는 **위 무결성 상자와 같은 규칙으로** 센다: 채점에서 빠진 줄
 * (`scoringExclusion`)은 적중했어도 분모에 넣지 않는다. 규칙이 갈리면 섹션 합이
 * 상자의 적중률과 안 맞고, 그러면 둘 중 하나는 거짓말이 된다.
 */
type PleGroup = {
  slug: string;
  label: string;
  dateLabel: string | null;
  items: PredictionItem[];
  graded: number;
  correct: number;
  pending: number;
  excluded: number;
};

/**
 * 예측을 **대회별로 끊는다**.
 *
 * 대회 순서는 서버가 준 순서(최근 생성 순)의 **첫 등장 순**이다 — 화면에서 다시
 * 정렬하지 않으므로 "왜 이 대회가 맨 위인가"가 한 가지 이유로 설명된다.
 *
 * 대회 **안쪽**은 경기 카드 순서를 따른다. 생성 순을 그대로 두면 한 번에 만든
 * 대회에서 마지막 경기가 맨 위에 서서, 대회 페이지의 카드 순서와 어긋난다.
 */
function groupByPle(items: PredictionItem[]): PleGroup[] {
  const groups = new Map<string, PleGroup>();

  for (const item of items) {
    let group = groups.get(item.eventSlug);
    if (!group) {
      group = {
        slug: item.eventSlug,
        label: item.eventLabel,
        dateLabel: getPleBySlug(item.eventSlug)?.dateLabel ?? null,
        items: [],
        graded: 0,
        correct: 0,
        pending: 0,
        excluded: 0,
      };
      groups.set(item.eventSlug, group);
    }
    group.items.push(item);
    if (item.scoringExclusion !== null) {
      group.excluded += 1;
    } else if (item.correct === null) {
      group.pending += 1;
    } else {
      group.graded += 1;
      if (item.correct) group.correct += 1;
    }
  }

  return [...groups.values()].map((group) => {
    const cardOrder = new Map(getPleMatches(group.slug).map((match, i) => [match.id, i] as const));
    const ordered = [...group.items].sort(
      (a, b) => (cardOrder.get(a.matchKey) ?? 999) - (cardOrder.get(b.matchKey) ?? 999),
    );
    return { ...group, items: ordered };
  });
}

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
    <Suspense fallback={<AiLabShell title="이번 예측">{null}</AiLabShell>}>
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
  const groups = useMemo(() => {
    if (!data) return [];
    const items = event === ALL ? data.items : data.items.filter((i) => i.eventSlug === event);
    return groupByPle(items);
  }, [data, event]);

  return (
    <AiLabShell
      title="이번 예측"
      description="AI가 내놓은 예측과, 그렇게 고른 이유입니다. 대회별로 끊어 보여 주고, 분석기 셋의 의견을 각각 볼 수 있습니다."
    >
      {state.status === "loading" && <LoadingBlock rows={4} />}
      {state.status === "error" && <DataUnavailable what="AI 예측 목록" />}
      {data && (
        <div className="flex flex-col gap-6">
          <p className="text-sm text-muted-foreground">
            <span className="tabular-nums text-foreground">{data.totals.total} predictions</span> ·{" "}
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
          ) : groups.length === 0 ? (
            <EmptyState what="이 대회에는 저장된 예측이 없습니다." />
          ) : (
            <div className="flex flex-col gap-2">
              {groups.map((group) => (
                /* 칩으로 한 대회만 남긴 상태라면 펼쳐 둔다 — 좁혀 놓고 또 열게
                   하면 같은 것을 두 번 고르는 셈이다. */
                <PleSection key={group.slug} group={group} open={event !== ALL} />
              ))}
            </div>
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
        <span className="font-medium text-data">{agentLabel(agent)}</span> 분석기가 의견을 낸 예측{" "}
        <span className="tabular-nums">{shown}</span>건
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
 * 대회 한 덩이 — **접힌 채로 선다** (2026-10-06 사용자: "접어둔 상태에서 궁금하면
 * 열 수 있게").
 *
 * 28건을 통으로 펼쳐 두면 대회 경계가 있어도 결국 한 화면을 끝까지 스크롤하게
 * 된다. 접어 두면 **대회 다섯 줄이 먼저 서고**, 그 줄에 건수·적중·대기가 이미
 * 적혀 있어서 열지 않고도 어느 대회에 무엇이 있는지 읽힌다.
 *
 * `<details>`를 쓴 이유는 `AiLabShell`의 개발 노트와 같다 — 펼침 상태 하나 때문에
 * 클라이언트 상태를 만들지 않고, 키보드·스크린리더 동작이 브라우저 기본으로 붙는다.
 *
 * **머리말에 고정폭을 두지 않는다** — 대회명·날짜·집계가 한 줄에 흐르다 좁아지면
 * 줄로 접힌다. 폭을 박으면 긴 대회명이 세로로 쪼개진다.
 *
 * `대회 보기` 링크는 **펼친 안쪽**에 둔다. 머리말에 두면 `<summary>` 안의 링크가
 * 되어, 누를 때 열림까지 함께 토글된다.
 */
function PleSection({ group, open }: { group: PleGroup; open: boolean }) {
  return (
    <details open={open} className="group overflow-hidden rounded-xl border border-border bg-card">
      <summary className="flex cursor-pointer list-none flex-wrap items-baseline gap-x-3 gap-y-1 px-4 py-3 transition-colors hover:bg-card-2 [&::-webkit-details-marker]:hidden">
        <span
          aria-hidden
          className="self-center text-muted-foreground transition-transform group-open:rotate-90"
        >
          ›
        </span>
        <h2 className="font-sport text-lg text-foreground">{group.label}</h2>
        {group.dateLabel && (
          <span className="text-xs tabular-nums text-muted-foreground">{group.dateLabel}</span>
        )}
        <p className="text-xs tabular-nums text-muted-foreground">
          예측 <span className="text-foreground">{group.items.length}</span>건
          {group.graded > 0 && (
            <>
              {" · 적중 "}
              <span className="text-foreground">
                {group.correct}/{group.graded}
              </span>
            </>
          )}
          {group.pending > 0 && ` · 결과 대기 ${group.pending}`}
          {group.excluded > 0 && ` · 채점 제외 ${group.excluded}`}
        </p>
      </summary>

      <div className="border-t border-border px-3 py-3 sm:px-4">
        <div className="mb-2 flex justify-end">
          <Link
            href={`/ple/${group.slug}`}
            className="text-xs text-brand-link underline underline-offset-2 hover:text-brand-hover"
          >
            대회 보기
          </Link>
        </div>
        <ul className="flex flex-col gap-2">
          {group.items.map((item) => (
            <PredictionRow key={`${item.eventSlug}-${item.matchKey}`} item={item} />
          ))}
        </ul>
      </div>
    </details>
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
    /* 대회 카드 **안쪽**이라 반경과 면이 한 단씩 내려간다 — 바깥과 같은 값이면
       안쪽이 바깥 모서리를 뚫고 나온 것처럼 보인다 (DESIGN.md §5·§6). */
    <li className="rounded-lg border border-border bg-card-2 px-4 py-3">
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
        <div className="min-w-0">
          {/* 대회명은 섹션 머리말이 들고 있다 — 줄마다 되풀이하지 않는다. */}
          <p className="text-xs text-muted-foreground">{item.matchTitle}</p>
          <p className="mt-0.5 truncate text-sm font-medium text-foreground">{item.pickName}</p>
        </div>
        <div className="flex shrink-0 flex-wrap items-center gap-2">
          <span className="text-xs tabular-nums text-muted-foreground">
            승률 {formatRatio(item.winProbability)} · 확신 {formatRatio(item.confidence)} ·{" "}
            <SynthesisVersion version={item.synthesisVersion} />
          </span>
          <SourceBadge fallback={fallback} />
          <ResultBadge
            correct={item.correct}
            winnerName={item.winnerName}
            scoringExclusion={item.scoringExclusion}
          />
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
 *
 * 채점에서 빠진 줄은 **Correct/Incorrect를 그대로 두고 사유를 덧붙인다.**
 * 위 적중률이 세지 않는 줄이라는 사실과, 그 예측이 맞았다는 사실은 둘 다 참이다.
 */
function ResultBadge({
  correct,
  winnerName,
  scoringExclusion,
}: {
  correct: boolean | null;
  winnerName: string | null;
  scoringExclusion: string | null;
}) {
  const excluded = scoringExclusion !== null && (
    <span className="rounded border border-border px-1.5 py-0.5 text-xs text-muted-foreground">
      {scoringExclusionLabel(scoringExclusion)}
    </span>
  );

  if (correct === null) {
    return (
      <span className="flex items-center gap-1.5">
        {excluded}
        {/* 개요 화면의 같은 배지와 **같은 낱말을 쓴다** — 한쪽만 `Pending`이면
            같은 상태가 화면마다 다른 것으로 읽힌다. */}
        <span className="rounded border border-border px-1.5 py-0.5 text-xs text-muted-foreground">
          미채점
        </span>
      </span>
    );
  }
  return (
    <span className="flex items-center gap-1.5">
      {excluded}
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
