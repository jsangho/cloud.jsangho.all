"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";
import {
  fetchBirthdays,
  formatDaysAway,
  formatMonthDay,
  type BirthdayBoard,
} from "@/lib/data-center-api";

/**
 * 다가오는 선수 생일.
 *
 * **"오늘의 생일"이 아니라 "다가오는 생일"이다.** 선수 165명만 셌을 때 1년 중
 * **239일이 0명**이었다(2026-10-12 실측). 오늘만 보여 주면 셋 중 둘은 빈 칸이고,
 * 그 자리는 DESIGN.md §14가 "없는 걸 채우지도, 빈 상자를 세우지도 말라"고 한 자리다.
 * 개수로 끊으면 날짜가 멀어질 뿐 목록이 비지 않는다.
 *
 * **오늘은 서버가 KST로 센다** — 클라이언트 시계를 믿으면 사람마다 다른 날이 된다.
 *
 * 나이는 `wrestlers`·`wwe_staff`의 `birth_date` 하나에서 나온다. 위키처럼 개정본으로
 * 되짚을 계보가 없으므로 화면이 **"선수·관계자 N/M명 기준"**을 함께 적는다.
 *
 * 두 곳에 선다 — 데이터 센터 1면(기본 5건)과 홈 히어로의 AI 예측 **아래**(3건,
 * 2026-10-12 사용자 요청). 홈에서 수를 줄인 이유는 오른쪽 기둥이 길어지면 왼쪽의
 * 영상·CTA와 높이가 어긋나기 때문이다.
 */
/**
 * 오늘 생일인 사람들의 이름 한 줄.
 *
 * 같은 날이 겹치는 날이 실제로 있다 — 선수만 세도 2명인 날이 34일, 3명 이상이
 * 이틀이다(2026-10-12 실측). 셋 이상이면 이름을 다 늘어놓는 대신 접는다.
 */
function formatTodayNames(entries: { name: string }[]): string {
  const names = entries.map((entry) => entry.name);
  if (names.length <= 2) return names.join(" · ");
  return `${names[0]} 외 ${names.length - 1}명`;
}

type BirthdayState =
  | { status: "loading" }
  | { status: "ready"; board: BirthdayBoard }
  | { status: "error" };

export function BirthdayCard({ limit = 5, className }: { limit?: number; className?: string }) {
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
      <div
        className={cn("h-40 animate-pulse rounded-xl border border-border bg-card", className)}
        aria-hidden
      />
    );
  }

  // 못 받으면 **아무것도 그리지 않는다.** 곁다리 카드라 에러 문구를 세울 자리가 아니다.
  if (state.status === "error" || state.board.entries.length === 0) return null;

  const { today, entries, dated, total } = state.board;
  // D-0은 정렬상 언제나 맨 앞이라 잘릴 일이 없다 (`days_away` 오름차순).
  const todayBirthdays = entries.filter((entry) => entry.daysAway === 0);

  return (
    <section
      aria-labelledby="birthdays"
      className={cn("rounded-xl border border-border bg-card p-5", className)}
    >
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
      <p className="text-xs text-muted-foreground">
        선수·관계자 {dated}/{total}명 기준 · {today}
      </p>
      {/* **있는 날에만 나타나는 줄이다.** 1년의 과반이 빈 날이라 상시 자리를
          비워 두면 빈 상자가 된다 (DESIGN.md §14). 색은 목록의 「오늘」 배지와
          같은 골드 틴트다 — 같은 신호를 두 색으로 말하지 않는다. */}
      {todayBirthdays.length > 0 && (
        <p className="mt-3 rounded-md bg-brand-500/10 px-3 py-2 text-sm text-brand-700 dark:text-brand-200">
          오늘은 <strong className="font-semibold">{formatTodayNames(todayBirthdays)}</strong>의
          생일입니다
        </p>
      )}
      <ul className="mt-4 flex flex-col divide-y divide-border">
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
              {/* 태어난 해를 모르면 이 칸을 **비운다** — 추정 나이를 적지 않는다. */}
              {entry.age !== null && (
                <span className="shrink-0 text-xs tabular-nums text-muted-foreground">
                  만 {entry.age}세
                </span>
              )}
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
