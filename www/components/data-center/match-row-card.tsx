"use client";

import Link from "next/link";
import { CheckCircle2, CalendarClock } from "lucide-react";
import type { DataCenterMatch } from "@/lib/data-center-api";
import { cn } from "@/lib/utils";

/**
 * 경기 한 줄 (Phase 2 §7).
 *
 * **모바일에서 표가 아니라 카드다** (§14). 참가자 이름이 길고 열이 여섯이라
 * 좁은 화면에서 표로 두면 글자가 세로로 쪼개진다.
 *
 * 상태는 **아이콘과 글자를 함께** 단다 — 색만으로 말하지 않는다 (§13).
 */
export function MatchRowCard({ match, className }: { match: DataCenterMatch; className?: string }) {
  const finished = match.status === "finished";

  return (
    <article
      className={cn("flex flex-col gap-2 rounded-xl border border-border bg-card p-4", className)}
    >
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <Link
          href={`/data-center/ple?event=${match.eventSlug}`}
          className="text-xs font-semibold text-brand-link underline-offset-4 hover:underline"
        >
          {match.eventLabel}
        </Link>
        <span className="text-xs text-muted-foreground">
          {match.year}
          {match.month ? `.${String(match.month).padStart(2, "0")}` : ""}
        </span>
        {match.isTitleMatch && (
          <span className="rounded-md border border-brand-400/40 px-1.5 py-0.5 text-[11px] font-semibold text-brand-link">
            타이틀전
          </span>
        )}
        <span className="rounded-md border border-border px-1.5 py-0.5 text-[11px] text-muted-foreground">
          {match.format === "multi" ? "다인전" : "싱글"}
        </span>
        <span
          className={cn(
            "ml-auto inline-flex items-center gap-1 text-xs",
            finished ? "text-muted-foreground" : "text-brand-link",
          )}
        >
          {finished ? (
            <CheckCircle2 className="size-3" aria-hidden />
          ) : (
            <CalendarClock className="size-3" aria-hidden />
          )}
          {finished ? "종료" : "예정"}
        </span>
      </div>

      <p className="text-sm text-foreground">{match.title}</p>

      <ul className="flex flex-wrap items-center gap-x-2 gap-y-1">
        {match.participants.map((name) => {
          const won = match.winnerName === name;
          return (
            <li key={name}>
              <Link
                href={`/records/${encodeURIComponent(name)}`}
                className={cn(
                  "inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs transition-colors",
                  won
                    ? "border-chart-win/50 text-chart-win"
                    : "border-border text-muted-foreground hover:text-foreground",
                )}
              >
                {/* 승자는 색만이 아니라 글자로도 표시한다 (§13). */}
                {won && <span className="font-semibold">승</span>}
                {name}
              </Link>
            </li>
          );
        })}
      </ul>

      {finished && !match.winnerName && (
        <p className="text-xs text-muted-foreground">
          승자를 되짚지 못한 경기입니다 — 없는 결과를 채우지 않습니다.
        </p>
      )}
    </article>
  );
}
