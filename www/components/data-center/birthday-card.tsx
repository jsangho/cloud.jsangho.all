"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  fetchBirthdays,
  formatDaysAway,
  formatMonthDay,
  type BirthdayBoard,
} from "@/lib/data-center-api";

/**
 * 다가오는 선수 생일.
 *
 * **"오늘의 생일"이 아니라 "다가오는 생일"이다.** 로스터 165명의 생일을 실측하면
 * 1년 중 **239일이 0명**이다(2026-10-12). 오늘만 보여 주면 셋 중 둘은 빈 칸이고,
 * 그 자리는 DESIGN.md §14가 "없는 걸 채우지도, 빈 상자를 세우지도 말라"고 한 자리다.
 * 개수로 끊으면 날짜가 멀어질 뿐 목록이 비지 않는다.
 *
 * **오늘은 서버가 KST로 센다** — 클라이언트 시계를 믿으면 사람마다 다른 날이 된다.
 *
 * 나이는 `wrestlers.birth_date` 하나에서 나온다. 위키처럼 개정본으로 되짚을 계보가
 * 없으므로 화면이 **"현역 로스터 N/M명 기준"**을 함께 적는다.
 */
type BirthdayState =
  | { status: "loading" }
  | { status: "ready"; board: BirthdayBoard }
  | { status: "error" };

export function BirthdayCard({ limit = 5 }: { limit?: number }) {
  const [state, setState] = useState<BirthdayState>({ status: "loading" });

  useEffect(() => {
    let alive = true;
    void (async () => {
      const board = await fetchBirthdays(limit);
      if (!alive) return;
      setState(board ? { status: "ready", board } : { status: "error" });
    })();
    return () => {
      alive = false;
    };
  }, [limit]);

  if (state.status === "loading") {
    return (
      <div className="h-40 animate-pulse rounded-xl border border-border bg-card" aria-hidden />
    );
  }

  // 못 받으면 **아무것도 그리지 않는다.** 곁다리 카드라 에러 문구를 세울 자리가 아니다.
  if (state.status === "error" || state.board.entries.length === 0) return null;

  const { today, entries, dated, total } = state.board;

  return (
    <section aria-labelledby="birthdays" className="rounded-xl border border-border bg-card p-5">
      <div className="mb-1 flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="birthdays" className="font-sport text-lg text-foreground">
          다가오는 생일
        </h2>
        <Link
          href="/data-center/wrestlers"
          className="text-sm font-semibold text-brand-link underline-offset-4 hover:underline"
        >
          선수 전체 보기 →
        </Link>
      </div>
      <p className="mb-4 text-xs text-muted-foreground">
        선수·관계자 {dated}/{total}명 기준 · {today}
      </p>
      <ul className="flex flex-col divide-y divide-border">
        {entries.map((entry) => {
          const isToday = entry.daysAway === 0;
          return (
            <li
              key={`${entry.name}-${entry.monthDay}`}
              className="flex items-baseline gap-3 py-2 first:pt-0 last:pb-0"
            >
              <span className="w-12 shrink-0 text-sm tabular-nums text-muted-foreground">
                {formatMonthDay(entry.monthDay)}
              </span>
              <span className="min-w-0 flex-1 truncate text-sm font-medium text-foreground">
                {entry.name}
                {/* 비선수는 **역할**이 소속보다 중요하다 — 「Commentator」가 「RAW」보다
                    그 사람을 설명한다. 선수는 역할 칸이 비어 있어 브랜드가 남는다. */}
                {(entry.role ?? entry.group) && (
                  <span className="ml-2 text-xs text-muted-foreground">
                    {entry.role ?? entry.group}
                  </span>
                )}
              </span>
              <span className="shrink-0 text-xs tabular-nums text-muted-foreground">
                만 {entry.age}세
              </span>
              <span
                className={
                  isToday
                    ? "shrink-0 rounded-md bg-brand-500/15 px-1.5 py-0.5 text-xs font-bold text-brand-600 dark:text-brand-300/90"
                    : "w-12 shrink-0 text-right text-xs tabular-nums text-muted-foreground"
                }
              >
                {formatDaysAway(entry.daysAway)}
              </span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
