import Link from "next/link";
import { cn } from "@/lib/utils";
import type { PleEventDetail, PleLayoutVariant } from "@/lib/wwe-ple-detail";
import type { PleSlug } from "@/lib/wwe-ple";
import {
  formatPleMonth,
  formatPleSchedule,
  WWE_PLE_MONTHLY_ORDER,
} from "@/lib/wwe-ple";
import { PleMatchBracket } from "@/components/ple/ple-match-bracket";
import { WweArenaShell } from "@/components/wwe-arena-shell";

type PleBase = (typeof WWE_PLE_MONTHLY_ORDER)[number];

const HERO_BANNER_CLASS: Partial<Record<PleLayoutVariant, string>> = {
  rumble: "ple-hero-banner--rumble",
  chamber: "ple-hero-banner--chamber",
  mania: "ple-hero-banner--mania",
};

type PleEventDetailViewProps = {
  ple: PleBase;
  detail: PleEventDetail;
};

export function PleEventDetailView({ ple, detail }: PleEventDetailViewProps) {
  const { theme } = detail;
  const idx = WWE_PLE_MONTHLY_ORDER.findIndex((e) => e.slug === ple.slug);
  const prev = idx > 0 ? WWE_PLE_MONTHLY_ORDER[idx - 1] : undefined;
  const next =
    idx >= 0 && idx < WWE_PLE_MONTHLY_ORDER.length - 1
      ? WWE_PLE_MONTHLY_ORDER[idx + 1]
      : undefined;

  const bannerModifier = HERO_BANNER_CLASS[detail.layout];

  return (
    <WweArenaShell>
      <div className="relative mx-auto max-w-3xl px-4 py-8 sm:py-12">
        <nav className="mb-8 flex flex-wrap items-center justify-between gap-3 text-sm">
          <Link
            href="/ple"
            className="text-stone-500 transition-colors hover:text-stone-800 dark:hover:text-stone-200"
          >
            ← PLE 목록
          </Link>
          <div className="flex gap-2">
            {prev && (
              <Link
                href={`/ple/${prev.slug}`}
                className="rounded-lg border border-stone-300/70 dark:border-white/10 bg-stone-100/50 dark:bg-white/5 px-3 py-1 text-stone-500 dark:text-stone-400 backdrop-blur-sm transition-colors hover:border-stone-400/70 dark:hover:border-white/20 hover:text-stone-800 dark:hover:text-stone-100"
              >
                {formatPleMonth(prev.month)}
              </Link>
            )}
            {next && (
              <Link
                href={`/ple/${next.slug}`}
                className="rounded-lg border border-stone-300/70 dark:border-white/10 bg-stone-100/50 dark:bg-white/5 px-3 py-1 text-stone-500 dark:text-stone-400 backdrop-blur-sm transition-colors hover:border-stone-400/70 dark:hover:border-white/20 hover:text-stone-800 dark:hover:text-stone-100"
              >
                {formatPleMonth(next.month)}
              </Link>
            )}
          </div>
        </nav>

        <header className={cn("ple-hero-banner p-6 sm:p-8", bannerModifier)}>
          <span
            className={cn(
              "inline-flex rounded-full px-3 py-1 text-xs font-bold tracking-wide ring-1 ring-inset",
              theme.badge,
            )}
          >
            {formatPleMonth(ple.month)} · {detail.signatureLabel}
          </span>
          <h1 className="font-sport mt-4 text-4xl font-semibold tracking-[-0.04em] text-stone-900 dark:text-white sm:text-5xl">
            {ple.label}
          </h1>
          <p className="font-kr-hero mt-3 text-lg text-stone-700 dark:text-stone-200 sm:text-xl">
            {detail.tagline}
          </p>
          <p className="mt-4 text-sm leading-relaxed text-stone-500">
            {formatPleSchedule(ple)}
          </p>
          <p className="mt-1 text-xs leading-relaxed text-stone-600">
            {ple.highlight}
          </p>
        </header>

        <PleMatchBracket slug={ple.slug as PleSlug} className="mt-8" />

        <PleHighlightsSection detail={detail} />

        <div className="mt-10 flex flex-wrap justify-center gap-3">
          <Link
            href="/"
            className="rounded-lg border border-stone-300/70 dark:border-white/10 bg-stone-100/50 dark:bg-white/5 px-4 py-2 text-sm font-medium text-stone-600 dark:text-stone-300 backdrop-blur-sm transition-colors hover:bg-stone-200/50 dark:hover:bg-white/10 hover:text-stone-900 dark:hover:text-white"
          >
            홈으로
          </Link>
          <Link
            href="/ple"
            className="rounded-lg border border-stone-300/70 dark:border-white/15 bg-stone-100/50 dark:bg-white/5 px-4 py-2 text-sm font-medium text-stone-600 dark:text-stone-200 backdrop-blur-sm transition-colors hover:border-amber-500/30 hover:text-stone-900 dark:hover:text-white"
          >
            다른 PLE 보기
          </Link>
        </div>
      </div>
    </WweArenaShell>
  );
}

function PleHighlightsSection({ detail }: { detail: PleEventDetail }) {
  const { theme, highlights } = detail;

  return (
    <section className="mt-8">
      <h2 className="font-sport mb-3 text-sm font-semibold tracking-[-0.03em] text-stone-600 dark:text-stone-400">
        PLE INFO
      </h2>
      <HighlightList highlights={highlights} theme={theme} />
    </section>
  );
}

function HighlightList({
  highlights,
  theme,
}: {
  highlights: PleEventDetail["highlights"];
  theme: PleEventDetail["theme"];
}) {
  return (
    <ul className="grid gap-3">
      {highlights.map((h) => (
        <li
          key={h.title}
          className={cn(
            "rounded-xl border border-stone-200/80 dark:border-white/8 bg-stone-100/40 dark:bg-white/[0.04] p-4 backdrop-blur-sm",
            theme.border,
          )}
        >
          <p className="font-semibold text-stone-700 dark:text-stone-200">
            {h.title}
          </p>
          <p className="mt-1 text-sm text-stone-500">{h.detail}</p>
        </li>
      ))}
    </ul>
  );
}
