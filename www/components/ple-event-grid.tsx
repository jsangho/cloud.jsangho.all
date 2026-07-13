"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  formatPleMonth,
  formatPleSchedule,
  getPleStatusBadge,
  getPleThemeClass,
  isPleTbd,
  pickFeaturedPle,
  type PleStatusBadge,
  WWE_PLE_MONTHLY_ORDER,
} from "@/lib/wwe-ple";
import { cn } from "@/lib/utils";

type PleEventGridProps = {
  variant?: "compact" | "large";
  className?: string;
  onNavigate?: () => void;
  /** 링크 접두사 (기본 `/ple`, 결과 페이지는 `/results`) */
  hrefPrefix?: string;
  /** 가장 임박한 이벤트를 상단에 큰 피처드 카드로 분리 표시 */
  featured?: boolean;
};

const STATUS_CLASS: Record<PleStatusBadge["variant"], string> = {
  deadline: "ple-status-badge--deadline",
  done: "ple-status-badge--done",
  ended: "ple-status-badge--ended",
  open: "ple-status-badge--open",
  tbd: "ple-status-badge--tbd",
};

function resolveBadge(slug: string, base: PleStatusBadge): PleStatusBadge {
  if (typeof window === "undefined") return base;
  if (base.variant === "ended" || base.variant === "tbd") return base;
  try {
    if (localStorage.getItem(`ple-predicted-${slug}`) === "1") {
      return { label: "예측 참여 완료", variant: "done" };
    }
  } catch {
    /* ignore */
  }
  return base;
}

export function PleEventGrid({
  variant = "large",
  className,
  onNavigate,
  hrefPrefix = "/ple",
  featured = false,
}: PleEventGridProps) {
  const isLarge = variant === "large";
  const [badges, setBadges] = useState<Record<string, PleStatusBadge>>({});

  useEffect(() => {
    const next: Record<string, PleStatusBadge> = {};
    for (const ple of WWE_PLE_MONTHLY_ORDER) {
      next[ple.slug] = resolveBadge(ple.slug, getPleStatusBadge(ple));
    }
    setBadges(next);
  }, []);

  const featuredPle = featured ? pickFeaturedPle() : null;
  const gridEvents = featuredPle
    ? WWE_PLE_MONTHLY_ORDER.filter((ple) => ple.slug !== featuredPle.slug)
    : WWE_PLE_MONTHLY_ORDER;

  return (
    <>
      {featuredPle && (
        <Link
          href={`${hrefPrefix}/${featuredPle.slug}`}
          onClick={onNavigate}
          className={cn(
            "ple-hero-card group relative mb-4 flex min-h-[10rem] w-full flex-col justify-end rounded-2xl border p-5 text-left sm:min-h-[12rem] sm:p-7",
            "border-stone-300/60 dark:border-stone-700/60 bg-stone-50/60 dark:bg-stone-900/60",
            getPleThemeClass(featuredPle.slug),
          )}
        >
          <span className="ple-hero-tag absolute left-5 top-5 sm:left-7 sm:top-7">
            {(badges[featuredPle.slug] ?? getPleStatusBadge(featuredPle))
              .variant === "deadline"
              ? "마감임박"
              : "다음 예측 이벤트"}
          </span>
          <span
            className={cn(
              "ple-status-badge absolute right-5 top-5 sm:right-7 sm:top-7",
              STATUS_CLASS[
                (badges[featuredPle.slug] ?? getPleStatusBadge(featuredPle))
                  .variant
              ],
            )}
          >
            {(badges[featuredPle.slug] ?? getPleStatusBadge(featuredPle))
              .label}
          </span>
          <span className="font-sport text-4xl font-bold uppercase tracking-[-0.03em] text-stone-800 dark:text-white sm:text-5xl">
            {featuredPle.label}
          </span>
          <span className="mt-2 block text-sm text-stone-600 dark:text-stone-300 sm:text-base">
            {formatPleSchedule(featuredPle)}
            <span className="ple-chevron" aria-hidden />
            {featuredPle.highlight}
          </span>
        </Link>
      )}
      <ul
        className={cn(
          "m-0 w-full list-none p-0",
          isLarge
            ? "grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3"
            : "mx-auto flex max-w-5xl flex-wrap justify-center gap-2 sm:gap-2.5",
          className,
        )}
      >
        {gridEvents.map((ple) => {
          const tbd = isPleTbd(ple);
          const themeClass = getPleThemeClass(ple.slug);
          const badge = badges[ple.slug] ?? getPleStatusBadge(ple);

          return (
            <li
              key={ple.slug}
              className={cn(
                "min-w-0",
                !isLarge && "w-[calc(50%-0.25rem)] sm:w-[9.5rem]",
              )}
            >
              <Link
                href={`${hrefPrefix}/${ple.slug}`}
                onClick={onNavigate}
                className={cn(
                  "ple-card group relative flex h-full w-full min-w-0 flex-col rounded-xl border text-left",
                  tbd
                    ? "ple-card--tbd border-stone-300/80 dark:border-stone-800/80 bg-stone-100/40 dark:bg-stone-950/40"
                    : "border-stone-300/60 dark:border-stone-700/60 bg-stone-50/55 dark:bg-stone-900/55",
                  !tbd && themeClass,
                  isLarge
                    ? "px-4 pb-3.5 pt-10 sm:px-4 sm:pb-4 sm:pt-11"
                    : "px-2.5 py-2 text-xs sm:px-3 sm:text-sm",
                )}
              >
                <span
                  className={cn(
                    "ple-status-badge absolute right-3 top-3 z-10",
                    STATUS_CLASS[badge.variant],
                  )}
                >
                  {badge.label}
                </span>

                <span
                  className={cn(
                    "ple-month-badge absolute left-3 top-3",
                    tbd && "opacity-60",
                  )}
                >
                  {formatPleMonth(ple.month)}
                </span>

                <span
                  className={cn(
                    "block font-bold leading-tight tracking-tight",
                    tbd
                      ? "text-stone-400 dark:text-stone-600"
                      : "text-stone-800 dark:text-stone-50",
                    isLarge
                      ? "font-sport text-xl sm:text-2xl"
                      : "font-semibold",
                  )}
                >
                  {ple.label}
                </span>

                <span
                  className={cn(
                    "mt-1.5 block leading-snug",
                    tbd
                      ? "text-[11px] text-stone-700 sm:text-xs"
                      : "text-xs text-stone-500 sm:text-sm",
                  )}
                >
                  {formatPleSchedule(ple)}
                </span>

                {isLarge && (
                  <span
                    className={cn(
                      "mt-2.5 block text-[11px] leading-snug sm:text-xs",
                      tbd ? "text-stone-800" : "text-stone-500",
                    )}
                  >
                    {ple.highlight}
                  </span>
                )}
              </Link>
            </li>
          );
        })}
      </ul>
    </>
  );
}
