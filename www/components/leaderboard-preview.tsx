"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Loader2, Trophy } from "lucide-react";
import { useAuth } from "@/context/auth-context";
import { cn } from "@/lib/utils";
import { fetchRankings, type RankingRow } from "@/lib/rankings-api";
import {
  nicknameColorClass,
  RankingBadgeTag,
} from "@/components/ranking-cosmetics";

type PreviewState = {
  loading: boolean;
  unavailable: boolean;
  rows: RankingRow[];
};

const initialState: PreviewState = {
  loading: true,
  unavailable: false,
  rows: [],
};

function rankNumberClass(rank: number) {
  if (rank === 1) return "font-black text-brand-600 dark:text-brand-300/90";
  if (rank <= 3) return "font-bold text-stone-600 dark:text-stone-300";
  return "font-semibold text-stone-500";
}

export function LeaderboardPreview({ className }: { className?: string }) {
  const { user, isReady } = useAuth();
  const [state, setState] = useState<PreviewState>(initialState);

  useEffect(() => {
    if (!isReady) return;

    let cancelled = false;
    void (async () => {
      const data = await fetchRankings({ limit: 5, nickname: user?.nickname });
      if (cancelled) return;
      setState({
        loading: false,
        unavailable: data === null,
        rows: data?.rows ?? [],
      });
    })();

    return () => {
      cancelled = true;
    };
  }, [isReady, user?.nickname]);

  return (
    <div
      className={cn(
        "rankings-panel ple-section-glow rounded-2xl p-5 sm:rounded-3xl sm:p-6",
        className,
      )}
    >
      <div className="mb-4 flex items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-medium uppercase tracking-[0.2em] text-stone-500">
            순위표
          </p>
          <h3 className="mt-1 flex items-center gap-1.5 text-lg font-bold text-stone-900 dark:text-stone-50">
            <Trophy className="h-4 w-4 shrink-0 text-brand-400" aria-hidden />
            TOP 5
          </h3>
        </div>
        <Link
          href="/rankings"
          className="shrink-0 text-xs font-semibold text-brand-600 dark:text-brand-300 hover:underline"
        >
          전체 보기 →
        </Link>
      </div>

      {!isReady || state.loading ? (
        <div className="flex items-center justify-center gap-2 py-8 text-sm text-stone-400">
          <Loader2 className="h-4 w-4 animate-spin text-brand-400/80" />
          불러오는 중…
        </div>
      ) : state.unavailable ? (
        <p className="py-8 text-center text-sm text-stone-400">
          순위를 불러오지 못했습니다.
        </p>
      ) : state.rows.length === 0 ? (
        <p className="py-8 text-center text-sm text-stone-400">
          아직 순위에 올라온 유저가 없습니다.
        </p>
      ) : (
        <ul className="space-y-1.5">
          {state.rows.map((row) => (
            <li
              key={`${row.rank}-${row.nickname}`}
              className={cn(
                "flex items-center justify-between rounded-lg border border-stone-200/40 dark:border-stone-800/40 px-3 py-2",
                row.nickname === user?.nickname &&
                  "border-brand-500/30 bg-brand-500/[0.04]",
              )}
            >
              <div className="flex min-w-0 items-center gap-2.5">
                <span
                  className={cn(
                    "w-5 shrink-0 text-right text-sm tabular-nums",
                    rankNumberClass(row.rank),
                  )}
                >
                  {row.rank}
                </span>
                <span
                  className={cn(
                    "truncate text-sm font-medium text-stone-800 dark:text-stone-100",
                    nicknameColorClass(row.nicknameColor),
                  )}
                >
                  {row.nickname}
                </span>
                <RankingBadgeTag item={row.badge} />
              </div>
              <span className="shrink-0 text-sm font-semibold tabular-nums text-stone-600 dark:text-stone-300">
                {row.score}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
