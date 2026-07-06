"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/context/auth-context";
import {
  fetchRankings,
  formatAccuracy,
  type RankingRow,
} from "@/lib/rankings-api";

type MyInfoPageState = {
  statsLoading: boolean;
  stats: RankingRow | null;
  statsUnavailable: boolean;
};

const initialStatsState: MyInfoPageState = {
  statsLoading: true,
  stats: null,
  statsUnavailable: false,
};

export default function MyInfoPage() {
  const router = useRouter();
  const { user, isReady } = useAuth();
  const [statsState, setStatsState] =
    useState<MyInfoPageState>(initialStatsState);

  useEffect(() => {
    if (isReady && !user) {
      router.replace("/login");
    }
  }, [isReady, user, router]);

  useEffect(() => {
    if (!user) return;

    let cancelled = false;
    setStatsState((prev) => ({
      ...prev,
      statsLoading: true,
      statsUnavailable: false,
    }));

    void (async () => {
      try {
        const data = await fetchRankings({ nickname: user.nickname, limit: 1 });
        if (cancelled) return;
        const mine = data?.myRank ?? null;
        setStatsState({
          statsLoading: false,
          stats: mine,
          statsUnavailable: data === null,
        });
      } catch {
        if (cancelled) return;
        setStatsState({
          statsLoading: false,
          stats: null,
          statsUnavailable: true,
        });
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [user?.nickname, user?.id]);

  if (!isReady || !user) {
    return (
      <main className="mx-auto max-w-lg px-4 py-16 text-center text-stone-400">
        불러오는 중...
      </main>
    );
  }

  const { statsLoading, stats, statsUnavailable } = statsState;

  return (
    <main className="mx-auto max-w-lg px-4 py-10">
      <div className="rounded-3xl border border-stone-300/70 dark:border-stone-700/70 bg-stone-50/80 dark:bg-stone-950/58 p-6 shadow-2xl shadow-black/35 backdrop-blur-xl sm:p-8">
        <p className="text-xs font-semibold uppercase tracking-[0.28em] text-stone-500">
          KayFabe
        </p>
        <h1 className="mt-3 text-2xl font-bold tracking-tight text-stone-900 dark:text-stone-50">
          내 정보
        </h1>
        <dl className="mt-8 space-y-4 text-sm">
          <InfoRow label="닉네임" value={user.nickname} />
          <InfoRow label="이메일" value={user.email} />
          <InfoRow label="역할" value={user.role} />
        </dl>

        <section className="mt-6 border-t border-stone-200/70 dark:border-stone-700/70 pt-6">
          <h2 className="text-sm font-bold tracking-tight text-stone-700 dark:text-stone-200">
            PLE 승부예측
          </h2>
          <p className="mt-1 text-xs text-stone-500">
            결과가 확정된 경기만 점수·성공률에 반영됩니다.
          </p>
          {statsLoading ? (
            <p className="mt-4 text-sm text-stone-500">기록 불러오는 중…</p>
          ) : statsUnavailable ? (
            <p className="mt-4 text-sm text-stone-500">
              순위 정보를 불러오지 못했습니다. 잠시 후 다시 확인해 주세요.
            </p>
          ) : stats ? (
            <dl className="mt-4 space-y-3">
              <InfoRow label="순위" value={`${stats.rank}위`} highlight />
              <InfoRow label="점수" value={String(stats.score)} highlight />
              <InfoRow
                label="예측 성공률"
                value={formatAccuracy(stats.accuracy)}
                highlight
              />
            </dl>
          ) : (
            <p className="mt-4 rounded-2xl border border-dashed border-stone-300/60 dark:border-stone-600/60 bg-stone-100/40 dark:bg-stone-900/40 px-4 py-3 text-sm text-stone-500 dark:text-stone-400">
              아직 채점된 예측이 없습니다. PLE 페이지에서 예측하고 결과가 나오면
              점수가 쌓입니다.
            </p>
          )}
        </section>

        <div className="mt-8 flex flex-col gap-2 sm:flex-row">
          <Button
            variant="outline"
            asChild
            className="flex-1 border-stone-600/70"
          >
            <Link href="/rankings">순위표 보기</Link>
          </Button>
          <Button
            variant="outline"
            asChild
            className="flex-1 border-stone-600/70"
          >
            <Link href="/">홈으로 돌아가기</Link>
          </Button>
        </div>
      </div>
    </main>
  );
}

function InfoRow({
  label,
  value,
  highlight,
}: {
  label: string;
  value: string;
  highlight?: boolean;
}) {
  return (
    <div
      className={
        highlight
          ? "rounded-2xl border border-amber-500/25 bg-amber-500/5 px-4 py-3"
          : "rounded-2xl border border-stone-200/80 dark:border-stone-700/80 bg-stone-100/70 dark:bg-stone-900/70 px-4 py-3"
      }
    >
      <dt className="text-stone-500">{label}</dt>
      <dd
        className={
          highlight
            ? "mt-1 text-lg font-bold tabular-nums text-amber-800 dark:text-amber-100"
            : "mt-1 font-medium text-stone-800 dark:text-stone-100"
        }
      >
        {value}
      </dd>
    </div>
  );
}
