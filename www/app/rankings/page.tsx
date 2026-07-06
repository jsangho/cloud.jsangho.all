"use client";

import { useEffect, useMemo, useState } from "react";
import { Loader2 } from "lucide-react";
import { useAuth } from "@/context/auth-context";
import { cn } from "@/lib/utils";
import { WweArenaShell } from "@/components/wwe-arena-shell";
import {
  fetchRankings,
  formatAccuracy,
  type RankingRow,
} from "@/lib/rankings-api";

type RankingsPageState = {
  loading: boolean;
  unavailable: boolean;
  rows: RankingRow[];
  myRank: RankingRow | null;
};

const initialState: RankingsPageState = {
  loading: true,
  unavailable: false,
  rows: [],
  myRank: null,
};

function rankRowClass(rank: number, isMe: boolean) {
  const base = "border-b border-stone-200/35 dark:border-stone-800/35";

  if (rank === 1) {
    return cn(
      base,
      "rankings-row-first",
      isMe && "ring-1 ring-inset ring-amber-400/20",
    );
  }
  if (rank === 2 || rank === 3) {
    return cn(
      base,
      "bg-stone-900/15",
      isMe && "bg-amber-500/[0.04] ring-1 ring-inset ring-amber-500/15",
    );
  }
  return cn(
    base,
    isMe && "bg-amber-500/[0.04] ring-1 ring-inset ring-amber-500/15",
  );
}

function rankNumberClass(rank: number) {
  const base = "text-sm tabular-nums";
  if (rank === 1)
    return cn(base, "font-black text-amber-600 dark:text-amber-300/90");
  if (rank <= 3)
    return cn(base, "font-bold text-stone-600 dark:text-stone-300");
  return cn(base, "font-semibold text-stone-500");
}

function rankTextClass(rank: number) {
  if (rank === 1) return "text-stone-900 dark:text-white";
  if (rank <= 3) return "text-stone-700 dark:text-stone-200";
  return "text-stone-600 dark:text-stone-300";
}

function TableRow({ row, isMe }: { row: RankingRow; isMe: boolean }) {
  const text = rankTextClass(row.rank);

  return (
    <tr className={rankRowClass(row.rank, isMe)}>
      <td className={cn("py-3.5 pr-3 text-right", rankNumberClass(row.rank))}>
        {row.rank}
      </td>
      <td className={cn("py-3.5 pr-3", text)}>
        <span
          className={cn(
            "text-sm",
            row.rank === 1 ? "font-bold text-head-of-table" : "font-medium",
          )}
        >
          {row.nickname}
        </span>
        {isMe && (
          <span className="ml-2 rounded-md border border-amber-500/25 bg-amber-100 dark:bg-amber-950/30 px-1.5 py-0.5 text-[10px] font-bold tracking-wide text-amber-700 dark:text-amber-200/90">
            나
          </span>
        )}
      </td>
      <td
        className={cn(
          "py-3.5 pr-3 text-right text-sm font-medium tabular-nums",
          text,
        )}
      >
        {row.score}
      </td>
      <td
        className={cn(
          "py-3.5 text-right text-sm font-medium tabular-nums",
          text,
        )}
      >
        {formatAccuracy(row.accuracy)}
      </td>
    </tr>
  );
}

function RankingsTable({
  rows,
  userNickname,
}: {
  rows: RankingRow[];
  userNickname?: string;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[520px]">
        <thead>
          <tr className="border-b border-stone-200/50 dark:border-stone-700/50">
            <th className="py-3 pr-3 text-right text-[11px] font-bold uppercase tracking-wider text-stone-500">
              순위
            </th>
            <th className="py-3 pr-3 text-left text-[11px] font-bold uppercase tracking-wider text-stone-500">
              닉네임
            </th>
            <th className="py-3 pr-3 text-right text-[11px] font-bold uppercase tracking-wider text-stone-500">
              점수
            </th>
            <th className="py-3 text-right text-[11px] font-bold uppercase tracking-wider text-stone-500">
              성공 확률
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <TableRow
              key={`${row.rank}-${row.nickname}`}
              row={row}
              isMe={!!userNickname && row.nickname === userNickname}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function RankingsPage() {
  const { user, isReady } = useAuth();
  const [state, setState] = useState<RankingsPageState>(initialState);

  useEffect(() => {
    if (!isReady) return;

    let cancelled = false;
    setState((prev) => ({ ...prev, loading: true, unavailable: false }));

    void (async () => {
      const data = await fetchRankings({
        limit: 20,
        nickname: user?.nickname,
      });
      if (cancelled) return;
      setState({
        loading: false,
        unavailable: data === null,
        rows: data?.rows ?? [],
        myRank: data?.myRank ?? null,
      });
    })();

    return () => {
      cancelled = true;
    };
  }, [isReady, user?.nickname, user?.id]);

  const myRow = useMemo(() => {
    if (!user) return null;
    const inTop = state.rows.find((r) => r.nickname === user.nickname);
    return inTop ?? state.myRank;
  }, [state.rows, state.myRank, user]);

  const showMySection =
    !!user &&
    myRow != null &&
    !state.rows.some((r) => r.nickname === user.nickname);

  return (
    <WweArenaShell>
      <div className="mx-auto w-full max-w-5xl px-4 py-8 sm:py-10">
        <header className="relative mb-8 text-center sm:mb-10">
          <div
            aria-hidden
            className="hero-title-backdrop mx-auto"
            style={{ height: "8rem", width: "min(100%, 22rem)" }}
          />
          <h1 className="font-kr-hero relative z-10 text-2xl text-stone-900 dark:text-white sm:text-3xl md:text-4xl">
            순위표
          </h1>
          <p className="relative z-10 mx-auto mt-3 max-w-2xl text-sm font-medium leading-relaxed tracking-tight text-stone-600 dark:text-stone-400 sm:text-base">
            닉네임 · 점수 · 예측 성공 확률(%) 기준으로 표시합니다.
            <br className="hidden sm:inline" /> 로그인 후 예측한 회원만
            집계됩니다.
          </p>
        </header>

        {!isReady || state.loading ? (
          <div className="flex items-center justify-center gap-2 py-16 text-sm text-stone-400">
            <Loader2 className="h-4 w-4 animate-spin text-amber-400/80" />
            불러오는 중…
          </div>
        ) : state.unavailable ? (
          <div className="rankings-panel rounded-2xl px-4 py-8 text-center text-sm text-stone-400 sm:rounded-3xl">
            순위를 불러오지 못했습니다. 백엔드가 실행 중인지 확인해 주세요.
          </div>
        ) : (
          <>
            <section className="rankings-panel ple-section-glow rounded-2xl p-4 sm:rounded-3xl sm:p-6">
              <div className="mb-4 text-center sm:mb-5">
                <p className="font-sport text-sm font-semibold tracking-[-0.04em] text-stone-500 dark:text-stone-400">
                  <span className="text-stone-900 dark:text-white">TOP</span> 20
                </p>
              </div>

              {state.rows.length === 0 ? (
                <p className="rounded-xl border border-dashed border-stone-300/45 dark:border-stone-700/45 bg-stone-100/30 dark:bg-stone-950/30 px-4 py-8 text-center text-sm text-stone-500 dark:text-stone-400">
                  아직 순위에 올라온 유저가 없습니다. PLE에서 예측하고 결과가
                  확정되면 표시됩니다.
                </p>
              ) : (
                <RankingsTable
                  rows={state.rows}
                  userNickname={user?.nickname}
                />
              )}
            </section>

            <section className="rankings-panel mt-5 rounded-2xl p-4 sm:mt-6 sm:rounded-3xl sm:p-6">
              <div className="mb-4">
                <h2 className="font-sport text-sm font-semibold tracking-[-0.04em] text-stone-600 dark:text-stone-300">
                  내 순위
                </h2>
                {!user && (
                  <p className="mt-1 text-xs font-medium text-stone-500">
                    로그인하면 내 순위가 표시됩니다.
                  </p>
                )}
              </div>

              {!user ? (
                <div className="ple-login-callout rounded-xl px-5 py-6 text-center">
                  <p className="text-sm font-medium text-stone-400">
                    로그인이 필요합니다.
                  </p>
                </div>
              ) : myRow == null ? (
                <div className="ple-login-callout rounded-xl px-5 py-6 text-center">
                  <p className="text-sm font-medium leading-relaxed text-stone-400">
                    아직 채점된 예측이 없습니다.
                    <br />
                    PLE 페이지에서 예측하고 결과가 나오면 순위에 반영됩니다.
                  </p>
                </div>
              ) : showMySection ? (
                <RankingsTable rows={[myRow]} userNickname={user.nickname} />
              ) : (
                <p className="text-sm font-medium text-stone-500">
                  TOP 20 표에 내 순위가 포함되어 있습니다.
                </p>
              )}
            </section>
          </>
        )}
      </div>
    </WweArenaShell>
  );
}
