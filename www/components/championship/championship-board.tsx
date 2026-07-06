"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Crown, Loader2, Users } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  fetchChampionshipBoard,
  type BrandRoster,
  type ChampionshipTier,
  type TitleReign,
} from "@/lib/championship-api";
import {
  formatChampionshipDate,
  groupTitlesByTier,
} from "@/lib/wwe-current-champions";

const BRAND_ACCENT: Record<
  BrandRoster["accent"],
  { border: string; glow: string; badge: string; label: string }
> = {
  red: {
    border: "border-red-300/60 dark:border-red-700/45",
    glow: "from-red-50/60 via-stone-50/30 to-stone-50/50 dark:from-red-950/50 dark:via-stone-950/40 dark:to-stone-950/70",
    badge:
      "border-red-400/50 bg-red-50 text-red-700 dark:border-red-600/50 dark:bg-red-950/40 dark:text-red-200",
    label: "text-red-600 dark:text-red-300/90",
  },
  blue: {
    border: "border-blue-300/60 dark:border-blue-700/45",
    glow: "from-blue-50/60 via-stone-50/30 to-stone-50/50 dark:from-blue-950/50 dark:via-stone-950/40 dark:to-stone-950/70",
    badge:
      "border-blue-400/50 bg-blue-50 text-blue-700 dark:border-blue-600/50 dark:bg-blue-950/40 dark:text-blue-200",
    label: "text-blue-600 dark:text-blue-300/90",
  },
  gold: {
    border: "border-amber-300/60 dark:border-amber-600/45",
    glow: "from-amber-50/60 via-stone-50/30 to-stone-50/50 dark:from-amber-950/45 dark:via-stone-950/40 dark:to-stone-950/70",
    badge:
      "border-amber-400/50 bg-amber-50 text-amber-700 dark:border-amber-600/50 dark:bg-amber-950/40 dark:text-amber-200",
    label: "text-amber-600 dark:text-amber-300/90",
  },
  purple: {
    border: "border-violet-300/60 dark:border-violet-700/45",
    glow: "from-violet-50/60 via-stone-50/30 to-stone-50/50 dark:from-violet-950/45 dark:via-stone-950/40 dark:to-stone-950/70",
    badge:
      "border-violet-400/50 bg-violet-50 text-violet-700 dark:border-violet-600/50 dark:bg-violet-950/40 dark:text-violet-200",
    label: "text-violet-600 dark:text-violet-300/90",
  },
};

function ChampionNameLink({ name }: { name: string }) {
  return (
    <Link
      href={`/records/${encodeURIComponent(name)}`}
      className="transition-colors hover:text-amber-100 hover:underline hover:underline-offset-2"
    >
      {name}
    </Link>
  );
}

function ChampionNames({
  reign,
  tier,
}: {
  reign: TitleReign;
  tier: ChampionshipTier;
}) {
  const isTag = tier === "tag" && reign.champions.length > 1;

  if (isTag) {
    return (
      <div className="flex flex-wrap items-center gap-x-1.5 gap-y-1">
        {reign.champions.map((name, i) => (
          <span key={name} className="inline-flex items-center">
            {i > 0 ? (
              <span className="mx-1 text-stone-500" aria-hidden>
                &
              </span>
            ) : null}
            <ChampionNameLink name={name} />
          </span>
        ))}
      </div>
    );
  }

  return (
    <span className="block">
      <ChampionNameLink name={reign.champions[0] ?? "—"} />
    </span>
  );
}

function TitleCard({
  reign,
  tier,
  accent,
}: {
  reign: TitleReign;
  tier: ChampionshipTier;
  accent: BrandRoster["accent"];
}) {
  const styles = BRAND_ACCENT[accent];
  const isMain = tier === "main";
  const isTag = tier === "tag";
  const isOther = tier === "other";

  return (
    <article
      className={cn(
        "championship-card group relative overflow-hidden rounded-2xl border bg-gradient-to-br p-4 backdrop-blur-sm transition-all duration-300",
        styles.border,
        styles.glow,
        isMain && "championship-card-main sm:p-6",
        isTag && "championship-card-tag",
        isOther && "championship-card-other",
      )}
    >
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-0 transition-opacity duration-300 group-hover:opacity-100 bg-[radial-gradient(ellipse_80%_60%_at_50%_0%,rgba(251,191,36,0.08),transparent_70%)]"
      />

      <div className="relative z-10 flex h-full flex-col">
        <div className="mb-3 flex items-start justify-between gap-2">
          <p
            className={cn(
              "font-medium leading-snug text-stone-500 dark:text-stone-400",
              isMain ? "text-xs sm:text-sm" : "text-[11px] sm:text-xs",
            )}
          >
            {reign.beltName}
          </p>
          {isMain ? (
            <Crown
              className="h-4 w-4 shrink-0 text-amber-400/80 sm:h-5 sm:w-5"
              aria-hidden
            />
          ) : isTag ? (
            <Users
              className="h-3.5 w-3.5 shrink-0 text-stone-500"
              aria-hidden
            />
          ) : null}
        </div>

        <div className="mt-auto space-y-1">
          {reign.teamName ? (
            <p
              className={cn(
                "font-sport font-bold uppercase tracking-wide text-amber-700 dark:text-amber-200/85",
                isTag ? "text-sm sm:text-base" : "text-xs",
              )}
            >
              {reign.teamName}
            </p>
          ) : null}
          <div
            className={cn(
              "font-bold tracking-tight text-stone-900 dark:text-white",
              isMain && "font-kr-hero text-2xl sm:text-3xl md:text-4xl",
              tier === "secondary" && "text-lg sm:text-xl",
              isTag && "text-base sm:text-lg",
              isOther && "text-sm sm:text-base",
            )}
          >
            <ChampionNames reign={reign} tier={tier} />
          </div>
        </div>

        <p className="mt-2 text-[11px] font-medium text-stone-500 sm:text-xs">
          {formatChampionshipDate(reign.wonAt)}
          {reign.wonEvent ? (
            <span className="text-stone-600"> · {reign.wonEvent}</span>
          ) : null}
        </p>
      </div>
    </article>
  );
}

function TierGrid({
  tier,
  titles,
  accent,
}: {
  tier: ChampionshipTier;
  titles: TitleReign[];
  accent: BrandRoster["accent"];
}) {
  if (titles.length === 0) return null;

  return (
    <div
      className={cn(
        "grid gap-3",
        tier === "main" && "sm:grid-cols-2",
        tier === "secondary" && "sm:grid-cols-2",
        tier === "tag" && "sm:grid-cols-2",
        tier === "other" && "sm:grid-cols-2 lg:grid-cols-3",
      )}
    >
      {titles.map((reign) => (
        <TitleCard
          key={`${reign.beltName}:${reign.champions.join("+")}`}
          reign={reign}
          tier={tier}
          accent={accent}
        />
      ))}
    </div>
  );
}

function BrandSection({ brand }: { brand: BrandRoster }) {
  const styles = BRAND_ACCENT[brand.accent];
  const groups = groupTitlesByTier(brand.titles);

  return (
    <section
      className={cn(
        "ple-section-glow rounded-2xl border bg-stone-50/55 dark:bg-stone-950/55 p-4 backdrop-blur-sm sm:rounded-3xl sm:p-6",
        styles.border,
      )}
      aria-labelledby={`brand-${brand.id}`}
    >
      <header className="mb-6 flex flex-wrap items-end justify-between gap-3 border-b border-stone-200/60 dark:border-stone-800/60 pb-4">
        <div>
          <p
            className={cn(
              "font-sport text-[10px] font-bold uppercase tracking-[0.2em]",
              styles.label,
            )}
          >
            {brand.id === "global" ? "Cross-Brand" : brand.id}
          </p>
          <h2
            id={`brand-${brand.id}`}
            className="mt-1 text-xl font-extrabold text-stone-900 dark:text-white sm:text-2xl"
          >
            {brand.label}
          </h2>
          <p className="mt-1 text-xs font-medium text-stone-500">
            {brand.tagline}
          </p>
        </div>
        <span
          className={cn(
            "rounded-full border px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide",
            styles.badge,
          )}
        >
          {brand.titles.length} titles
        </span>
      </header>

      <div className="space-y-6">
        {groups.map(({ tier, label, titles }) => (
          <div key={tier}>
            <h3 className="mb-3 text-xs font-bold uppercase tracking-wider text-stone-500">
              {label}
            </h3>
            <TierGrid tier={tier} titles={titles} accent={brand.accent} />
          </div>
        ))}
      </div>
    </section>
  );
}

type ChampionshipBoardState = {
  loading: boolean;
  unavailable: boolean;
  asOf: string;
  brands: BrandRoster[];
};

const initialState: ChampionshipBoardState = {
  loading: true,
  unavailable: false,
  asOf: "",
  brands: [],
};

export function ChampionshipBoard() {
  const [state, setState] = useState<ChampionshipBoardState>(initialState);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      setState((prev) => ({ ...prev, loading: true, unavailable: false }));
      const board = await fetchChampionshipBoard();
      if (cancelled) return;
      if (!board) {
        setState({ loading: false, unavailable: true, asOf: "", brands: [] });
        return;
      }
      setState({
        loading: false,
        unavailable: false,
        asOf: board.asOf,
        brands: board.brands,
      });
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (state.loading) {
    return (
      <div className="flex items-center justify-center gap-2 rounded-2xl border border-stone-300/50 dark:border-stone-700/50 bg-stone-100/50 dark:bg-stone-950/50 px-4 py-10 text-sm text-stone-500 dark:text-stone-400">
        <Loader2 className="h-4 w-4 animate-spin text-amber-400/80" />
        불러오는 중…
      </div>
    );
  }

  if (state.unavailable || state.brands.length === 0) {
    return (
      <div className="rounded-2xl border border-dashed border-stone-300/50 dark:border-stone-700/50 bg-stone-100/40 dark:bg-stone-950/40 px-4 py-10 text-center text-sm text-stone-500 dark:text-stone-400">
        챔피언십 정보를 불러오지 못했습니다. 백엔드가 켜져 있는지 확인해 주세요.
      </div>
    );
  }

  const asOfLabel = formatChampionshipDate(state.asOf);

  return (
    <div className="space-y-8 sm:space-y-10">
      {state.brands.map((brand) => (
        <BrandSection key={brand.id} brand={brand} />
      ))}

      <p className="text-center text-[11px] font-medium text-stone-600">
        기준일 {asOfLabel} · WWE 공식 브랜드·타이틀 구분
      </p>
    </div>
  );
}
