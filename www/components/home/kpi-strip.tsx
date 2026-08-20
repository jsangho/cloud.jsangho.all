"use client";

import { useEffect, useState } from "react";
import { fetchKayfabeKpi, type KayfabeKpi } from "@/lib/ple-events-api";
import { fetchPleAiStats, type PleAiStats } from "@/lib/ple-ai-stats";
import { cn } from "@/lib/utils";

/**
 * 홈 KPI 스트립 — **실제 수치만 세운다** (KAYFABE 2.0 §7·§12).
 *
 * 값은 이미 있던 두 엔드포인트에서 온다: `/ple_events/events`(대회·경기 수) ·
 * `/ple-matches/competitors`(선수 수) · `/ple_events/ai-stats`(AI 표본·적중).
 *
 * **작아도 그대로 쓴다.** 열한 대회, 예순여덟 경기가 지금 이 서비스가 가진 전부이고,
 * 포트폴리오에서 중요한 것은 숫자의 크기가 아니라 그게 진짜인지다. 못 받은 값은
 * 타일을 아예 안 그린다 — 0이나 임시값으로 채우면 그 순간 거짓이 된다.
 */
type KpiTile = {
  value: string;
  label: string;
  /** 값 아래 한 줄 — 분모나 단서. 없으면 안 그린다. */
  note?: string;
  tone?: "default" | "data";
};

function Tile({ tile }: { tile: KpiTile }) {
  return (
    <div className="flex flex-col justify-center rounded-xl border border-border bg-card px-4 py-3 sm:px-5 sm:py-4">
      <p
        className={cn(
          "text-2xl font-bold tabular-nums sm:text-3xl",
          tile.tone === "data" ? "text-data" : "text-foreground",
        )}
      >
        {tile.value}
      </p>
      <p className="mt-1 text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">
        {tile.label}
      </p>
      {tile.note && <p className="mt-0.5 text-xs text-muted-foreground">{tile.note}</p>}
    </div>
  );
}

export function KpiStrip({ className }: { className?: string }) {
  const [kpi, setKpi] = useState<KayfabeKpi | null>(null);
  const [ai, setAi] = useState<PleAiStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      const [counts, stats] = await Promise.all([fetchKayfabeKpi(), fetchPleAiStats()]);
      if (cancelled) return;
      setKpi(counts);
      setAi(stats);
      setLoading(false);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) {
    return (
      <div
        className={cn("grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6", className)}
        aria-hidden
      >
        {[0, 1, 2, 3, 4, 5].map((i) => (
          <div
            key={i}
            className="h-[5.5rem] animate-pulse rounded-xl border border-border bg-card"
          />
        ))}
      </div>
    );
  }

  const tiles: KpiTile[] = [];
  if (kpi) {
    tiles.push({ value: String(kpi.events), label: "PLE Events" });
    tiles.push({ value: String(kpi.matches), label: "Matches" });
    if (kpi.wrestlers != null) {
      tiles.push({ value: String(kpi.wrestlers), label: "Wrestlers" });
    }
  }
  // **표본이 없으면 AI 타일 자체가 없다** (DESIGN.md §14). 0%로 그리면
  // "틀렸다"로 읽히고, 숨기면 "아직 잴 것이 없다"로 읽힌다 — 후자가 사실이다.
  //
  // **적중률 하나만 크게 세우지 않는다** (2026-08-20 사용자 결정). 12건짜리
  // 100%를 단독으로 걸면 그 숫자가 실제보다 훨씬 단단해 보인다 — 표본 수와
  // 분자/분모를 **같은 크기로 나란히** 세워야 100%가 무엇의 100%인지 읽힌다.
  if (ai && ai.totalGraded > 0) {
    tiles.push({
      value: String(ai.totalGraded),
      label: "Predictions",
      note: "채점된 AI 예측",
      tone: "data",
    });
    tiles.push({
      value: `${ai.correct} / ${ai.totalGraded}`,
      label: "Correct",
      note: `빗나감 ${ai.incorrect}건`,
      tone: "data",
    });
    if (ai.accuracyPercent != null) {
      tiles.push({
        value: `${ai.accuracyPercent}%`,
        label: "Current Hit Rate",
        note: `Sample: ${ai.totalGraded}`,
        tone: "data",
      });
    }
  }

  if (tiles.length === 0) return null;

  return (
    <div className={cn("grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6", className)}>
      {tiles.map((tile) => (
        <Tile key={tile.label} tile={tile} />
      ))}
    </div>
  );
}
