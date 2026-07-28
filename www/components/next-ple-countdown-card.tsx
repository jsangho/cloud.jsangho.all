"use client";

import Link from "next/link";
import {
  formatPleSchedule,
  getPleCountdownDays,
  getPleThemeClass,
  pickFeaturedPle,
} from "@/lib/wwe-ple";
import { cn } from "@/lib/utils";

export function NextPleCountdownCard({ className }: { className?: string }) {
  const next = pickFeaturedPle();

  if (!next) {
    return (
      <div
        className={cn(
          "ple-section-glow flex min-h-[11rem] flex-col justify-center rounded-2xl border border-stone-300/50 dark:border-stone-700/50 bg-stone-50/60 dark:bg-stone-950/60 p-5 text-center sm:rounded-3xl sm:p-6",
          className,
        )}
      >
        <p className="text-xs font-medium uppercase tracking-[0.2em] text-stone-500">
          다음 PLE
        </p>
        <p className="mt-2 text-sm text-stone-500">
          예정된 다음 PLE 일정이 아직 없습니다.
        </p>
      </div>
    );
  }

  const days = getPleCountdownDays(next);

  return (
    <Link
      href={`/ple/${next.slug}`}
      className={cn(
        "ple-hero-card group relative flex min-h-[11rem] flex-col justify-end rounded-2xl border p-5 text-left sm:rounded-3xl sm:p-6",
        "border-stone-300/60 dark:border-stone-700/60 bg-stone-50/60 dark:bg-stone-900/60",
        getPleThemeClass(next.slug),
        className,
      )}
    >
      <span className="ple-hero-tag absolute left-5 top-5 sm:left-6 sm:top-6">
        다음 PLE
      </span>
      {days != null && (
        <span className="absolute right-5 top-5 rounded-full border border-amber-400/40 bg-amber-500/15 px-2.5 py-1 text-xs font-bold tabular-nums text-amber-700 dark:text-amber-300 sm:right-6 sm:top-6">
          D-{days}
        </span>
      )}
      <span className="font-sport text-3xl font-bold uppercase tracking-[-0.03em] text-stone-800 dark:text-white sm:text-4xl">
        {next.label}
      </span>
      <span className="mt-2 block text-sm text-stone-600 dark:text-stone-300 sm:text-base">
        {formatPleSchedule(next)}
        <span className="ple-chevron" aria-hidden />
        {next.highlight}
      </span>
      <span className="mt-3 inline-flex w-fit items-center gap-1 rounded-lg border border-stone-400/40 dark:border-stone-500/40 bg-stone-900/5 dark:bg-white/5 px-3 py-1.5 text-xs font-semibold text-stone-700 dark:text-stone-200 transition-colors group-hover:bg-stone-900/10 dark:group-hover:bg-white/10">
        지금 예측하러 가기 →
      </span>
    </Link>
  );
}
