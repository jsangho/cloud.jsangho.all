"use client";

import { useEffect, useMemo, useState } from "react";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  fetchPleAiStats,
  type PleAiRecord,
  type PleAiStats,
} from "@/lib/ple-ai-stats";
import { WWE_PLE_MONTHLY_ORDER } from "@/lib/wwe-ple";
import { getPleMatches } from "@/lib/wwe-ple-matches";

type PleAiGroup = {
  slug: string;
  label: string;
  rows: PleAiRecord[];
  correct: number;
  total: number;
};

type AiScoreboardUi = {
  sectionOpen: boolean;
  expandedSlug: string | null;
};

const initialUi: AiScoreboardUi = {
  sectionOpen: false,
  expandedSlug: null,
};

function groupRecordsByPle(records: PleAiRecord[]): PleAiGroup[] {
  const map = new Map<string, PleAiGroup>();
  for (const row of records) {
    let group = map.get(row.eventSlug);
    if (!group) {
      group = {
        slug: row.eventSlug,
        label: row.eventLabel,
        rows: [],
        correct: 0,
        total: 0,
      };
      map.set(row.eventSlug, group);
    }
    group.rows.push(row);
    group.total += 1;
    if (row.correct) group.correct += 1;
  }

  const order = new Map(
    WWE_PLE_MONTHLY_ORDER.map((e, i) => [e.slug, i] as const),
  );

  return [...map.values()]
    .map((group) => {
      const cardOrder = new Map(
        getPleMatches(group.slug).map((m, i) => [m.id, i] as const),
      );
      const rows = [...group.rows].sort((a, b) => {
        const ai = cardOrder.get(a.matchKey) ?? 999;
        const bi = cardOrder.get(b.matchKey) ?? 999;
        return ai - bi;
      });
      return { ...group, rows };
    })
    .sort((a, b) => {
      const ai = order.get(a.slug) ?? 999;
      const bi = order.get(b.slug) ?? 999;
      if (ai !== bi) return ai - bi;
      return a.label.localeCompare(b.label);
    });
}

function AiMatchRow({ row }: { row: PleAiRecord }) {
  return (
    <li
      className={cn(
        "flex flex-col gap-1 rounded-lg border px-3 py-2.5 sm:flex-row sm:items-center sm:justify-between",
        row.correct
          ? "border-emerald-500/40 bg-emerald-50/60 dark:bg-emerald-950/25"
          : "border-red-400/35 bg-red-50/60 dark:bg-red-950/20",
      )}
    >
      <p className="min-w-0 truncate text-sm font-semibold text-stone-800 dark:text-stone-100">
        {row.matchTitle}
      </p>
      <div className="flex shrink-0 flex-wrap items-center gap-2 text-xs sm:text-sm">
        <span className="text-stone-400">
          AI:{" "}
          <span className="font-medium text-violet-700 dark:text-violet-200">
            {row.aiPickName}
          </span>
        </span>
        {row.winnerName && (
          <span className="text-stone-500">
            실제:{" "}
            <span className="text-stone-700 dark:text-stone-300">
              {row.winnerName}
            </span>
          </span>
        )}
        <span
          className={cn(
            "rounded-full px-2 py-0.5 text-[11px] font-bold",
            row.correct
              ? "bg-emerald-100 dark:bg-emerald-900/70 text-emerald-700 dark:text-emerald-300"
              : "bg-red-100 dark:bg-red-900/60 text-red-700 dark:text-red-300",
          )}
        >
          {row.correct ? "적중" : "실패"}
        </span>
      </div>
    </li>
  );
}

export function PleAiScoreboard() {
  const [stats, setStats] = useState<PleAiStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [ui, setUi] = useState<AiScoreboardUi>(initialUi);

  const patchUi = (patch: Partial<AiScoreboardUi>) =>
    setUi((prev) => ({ ...prev, ...patch }));

  const pleGroups = useMemo(
    () => (stats?.recent.length ? groupRecordsByPle(stats.recent) : []),
    [stats],
  );

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      setLoading(true);
      const data = await fetchPleAiStats();
      if (!cancelled) {
        setStats(data);
        setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const toggleSection = () => {
    patchUi({
      sectionOpen: !ui.sectionOpen,
      expandedSlug: ui.sectionOpen ? null : ui.expandedSlug,
    });
  };

  const togglePle = (slug: string) => {
    patchUi({
      expandedSlug: ui.expandedSlug === slug ? null : slug,
    });
  };

  return (
    <section className="mx-auto mt-6 w-full max-w-5xl px-4">
      <div className="rounded-2xl border border-stone-300/60 dark:border-stone-600/60 bg-stone-100/40 dark:bg-stone-800/40 shadow-lg shadow-black/20 backdrop-blur-sm">
        <div className="flex flex-col gap-4 p-5 sm:flex-row sm:items-end sm:justify-between sm:p-6">
          <div className="min-w-0">
            <p className="text-xs font-medium uppercase tracking-[0.2em] text-stone-500">
              KayFabe AI
            </p>
            <h3 className="mt-1 text-lg font-bold text-stone-900 dark:text-stone-50 sm:text-xl">
              PLE 승패 예측 기록
            </h3>
            <p className="mt-1 text-sm text-stone-400">
              북메이커 배당 favorite 기준 · 경기 결과 확정 시 자동 채점
            </p>
          </div>
          {stats && stats.totalGraded > 0 && (
            <div className="flex shrink-0 flex-wrap items-center gap-4">
              <div className="flex gap-6 rounded-xl border border-stone-300/50 dark:border-stone-600/50 bg-stone-100/50 dark:bg-stone-900/50 px-5 py-3">
                <div className="text-center">
                  <p className="text-2xl font-bold tabular-nums text-emerald-700 dark:text-emerald-300">
                    {stats.accuracyPercent != null
                      ? `${stats.accuracyPercent}%`
                      : "—"}
                  </p>
                  <p className="text-xs text-stone-500">적중률</p>
                </div>
                <div className="text-center">
                  <p className="text-2xl font-bold tabular-nums text-stone-800 dark:text-stone-100">
                    {stats.correct}
                    <span className="text-base font-medium text-stone-500">
                      /{stats.totalGraded}
                    </span>
                  </p>
                  <p className="text-xs text-stone-500">적중</p>
                </div>
              </div>
              {!loading && pleGroups.length > 0 && (
                <button
                  type="button"
                  onClick={toggleSection}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-stone-300/70 dark:border-stone-600/70 bg-stone-100/60 dark:bg-stone-900/60 px-3 py-2 text-sm font-medium text-stone-700 dark:text-stone-200 transition-colors hover:bg-stone-200 dark:hover:bg-stone-800"
                  aria-expanded={ui.sectionOpen}
                >
                  {ui.sectionOpen ? "접기" : "PLE별 기록 보기"}
                  <ChevronDown
                    className={cn(
                      "size-4 transition-transform",
                      ui.sectionOpen && "rotate-180",
                    )}
                    aria-hidden
                  />
                </button>
              )}
            </div>
          )}
        </div>

        {loading && (
          <p className="border-t border-stone-200/50 dark:border-stone-700/50 px-5 py-6 text-center text-sm text-stone-500 sm:px-6">
            기록 불러오는 중…
          </p>
        )}

        {!loading && (!stats || stats.totalGraded === 0) && (
          <p className="border-t border-stone-200/50 dark:border-stone-700/50 px-5 py-6 text-center text-sm text-stone-500 sm:px-6">
            아직 채점된 AI 예측이 없습니다. PLE 페이지에서 카드를 동기화하고
            결과를 등록하면 기록이 쌓입니다.
          </p>
        )}

        {!loading && ui.sectionOpen && pleGroups.length > 0 && (
          <div className="border-t border-stone-200/50 dark:border-stone-700/50 px-3 pb-4 pt-2 sm:px-4 sm:pb-5">
            <ul className="space-y-1">
              {pleGroups.map((group) => {
                const isOpen = ui.expandedSlug === group.slug;
                const accuracy =
                  group.total > 0
                    ? Math.round((group.correct / group.total) * 100)
                    : 0;
                return (
                  <li
                    key={group.slug}
                    className="overflow-hidden rounded-xl border border-stone-300/60 dark:border-stone-700/60 bg-stone-100/40 dark:bg-stone-900/40"
                  >
                    <button
                      type="button"
                      onClick={() => togglePle(group.slug)}
                      className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left transition-colors hover:bg-stone-100/50 dark:hover:bg-stone-800/50"
                      aria-expanded={isOpen}
                    >
                      <span className="font-semibold text-stone-800 dark:text-stone-100">
                        {group.label}
                      </span>
                      <span className="flex shrink-0 items-center gap-2 text-sm text-stone-400">
                        <span className="tabular-nums">
                          {group.correct}/{group.total}
                          <span className="mx-1 text-stone-600">·</span>
                          {accuracy}%
                        </span>
                        <ChevronDown
                          className={cn(
                            "size-4 text-stone-500 transition-transform",
                            isOpen && "rotate-180",
                          )}
                          aria-hidden
                        />
                      </span>
                    </button>
                    {isOpen && (
                      <ul className="space-y-1.5 border-t border-stone-200/50 dark:border-stone-700/50 px-3 py-3">
                        {group.rows.map((row) => (
                          <AiMatchRow
                            key={`${row.eventSlug}-${row.matchKey}`}
                            row={row}
                          />
                        ))}
                      </ul>
                    )}
                  </li>
                );
              })}
            </ul>
          </div>
        )}
      </div>
    </section>
  );
}
