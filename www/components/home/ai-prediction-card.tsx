"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AiReportDialog } from "@/components/ple/ai-report-dialog";
import { fetchPleEvents } from "@/lib/ple-events-api";
import {
  fetchAiPredictions,
  isBookmakerFallback,
  opponentShare,
  toPercent,
  type AiPrediction,
} from "@/lib/ple-ai-predictions";
import { getPleMatches } from "@/lib/wwe-ple-matches";
import { cn } from "@/lib/utils";

/**
 * 히어로 오른쪽의 AI 예측 카드 (KAYFABE 2.0 §2·§5).
 *
 * **새 데이터를 만들지 않는다.** 이미 있는 `/ple_events/events`로 대회를 고르고
 * `/ple_events/{slug}/ai-predictions`로 그 대회의 예측을 받는다. 근거(에이전트별
 * 판단·출처)는 기존 `AiReportDialog`를 그대로 연다 — 같은 것을 두 벌 만들지 않는다.
 *
 * **예측이 없으면 카드를 지어내지 않는다.** 그 자리에 무엇이 없는지 한 줄로 적고
 * PLE 목록으로 보낸다.
 */
type CardState =
  | { status: "loading" }
  | { status: "empty" }
  | {
      status: "ready";
      slug: string;
      eventLabel: string;
      eventStatus: string;
      matchTitle: string;
      prediction: AiPrediction;
    };

/** 예측을 보여 줄 대회 하나 — 다가오는 대회가 먼저, 없으면 가장 마지막 대회다. */
function pickEventOrder(rows: { slug: string; label: string; status: string }[]) {
  const live = rows.filter((r) => r.status === "live");
  const upcoming = rows.filter((r) => r.status === "upcoming");
  const finished = rows.filter((r) => r.status === "finished").reverse();
  return [...live, ...upcoming, ...finished];
}

/** 한 번에 훑을 대회 수. **순서대로 하나씩 물으면** 예측이 없는 대회마다 왕복이 쌓인다. */
const LOOKUP_LIMIT = 6;

export function AiPredictionCard({ className }: { className?: string }) {
  const [state, setState] = useState<CardState>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      const events = await fetchPleEvents();
      const candidates = pickEventOrder(events).slice(0, LOOKUP_LIMIT);
      const results = await Promise.all(candidates.map((e) => fetchAiPredictions(e.slug)));
      if (cancelled) return;

      for (const [index, event] of candidates.entries()) {
        const result = results[index];
        if (result.status !== "ready") continue;

        // 카드 순서대로 보고 **단일전 예측을 먼저** 고른다 — 두 쪽 승률을
        // 나란히 세울 수 있는 것이 다인전보다 이 카드에 맞는다.
        const cards = getPleMatches(event.slug);
        const singles = cards.find((card) => card.format === "singles" && result.byMatch[card.id]);
        const any = singles ?? cards.find((card) => result.byMatch[card.id]);
        if (!any) continue;

        setState({
          status: "ready",
          slug: event.slug,
          eventLabel: event.label,
          eventStatus: event.status,
          matchTitle: any.title,
          prediction: result.byMatch[any.id],
        });
        return;
      }
      setState({ status: "empty" });
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (state.status === "loading") {
    return (
      <div
        className={cn(
          "h-[19rem] animate-pulse rounded-2xl border border-border bg-card",
          className,
        )}
        aria-hidden
      />
    );
  }

  if (state.status === "empty") {
    return (
      <div
        className={cn(
          "flex min-h-[19rem] flex-col justify-center gap-3 rounded-2xl border border-border bg-card p-6 text-center",
          className,
        )}
      >
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-data">AI Prediction</p>
        <p className="text-sm text-muted-foreground">
          아직 채점할 AI 예측이 없습니다. 대회가 열리면 여기에 승률과 근거가 섭니다.
        </p>
        <Link
          href="/ple"
          className="mx-auto text-sm font-semibold text-brand-link underline-offset-4 hover:underline"
        >
          PLE 목록 보기
        </Link>
      </div>
    );
  }

  const { prediction, slug, eventLabel, eventStatus, matchTitle } = state;
  // **지난 대회의 예측이면 그렇게 적는다.** 결과가 이미 나온 경기를 다가올
  // 경기처럼 세우면 그게 곧 거짓말이다.
  const past = eventStatus === "finished";
  const mine = toPercent(prediction.winProbability);
  const other = opponentShare(slug, prediction);
  const fallback = isBookmakerFallback(prediction);

  return (
    <div
      className={cn(
        "flex min-h-[19rem] flex-col gap-4 rounded-2xl border border-border bg-card p-5 sm:p-6",
        className,
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-data">
            AI Prediction
          </p>
          <p className="mt-1 truncate text-sm text-muted-foreground">
            {past && <span className="mr-1 text-xs">지난 대회 ·</span>}
            {eventLabel} · {matchTitle}
          </p>
        </div>
        <span className="shrink-0 rounded-md border border-data-500/40 bg-data-surface px-2 py-1 text-[11px] font-semibold text-data">
          {fallback ? "배당 기반" : "멀티 에이전트"}
        </span>
      </div>

      <div className="flex flex-col gap-3">
        <div className="flex items-baseline justify-between gap-3 rounded-xl border border-data-500/30 bg-data-surface px-4 py-3">
          <span className="min-w-0 truncate font-sport text-lg text-foreground">
            {prediction.pickName}
          </span>
          <span className="shrink-0 text-2xl font-bold tabular-nums text-data">{mine}%</span>
        </div>

        {other ? (
          <>
            <p className="text-center text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
              vs
            </p>
            <div className="flex items-baseline justify-between gap-3 rounded-xl border border-border bg-card-2 px-4 py-3">
              <span className="min-w-0 truncate font-sport text-lg text-muted-foreground">
                {other.name}
              </span>
              <span className="shrink-0 text-2xl font-bold tabular-nums text-muted-foreground">
                {toPercent(other.probability)}%
              </span>
            </div>
          </>
        ) : (
          <p className="text-xs text-muted-foreground">
            여러 명이 붙는 경기라 나머지 승률은 한 사람 몫으로 나누지 않습니다.
          </p>
        )}
      </div>

      <div className="mt-auto flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs text-muted-foreground">
          확신도 <span className="tabular-nums">{toPercent(prediction.confidence)}%</span>
        </p>
        <AiReportDialog slug={slug} matchTitle={matchTitle} prediction={prediction} />
      </div>
    </div>
  );
}
