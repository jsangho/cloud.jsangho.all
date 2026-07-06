"use client";

import { cn } from "@/lib/utils";
import { BRACKET_LABELS } from "@/lib/bracket-labels";
import {
  normalizedMultiMarket,
  normalizedTwoWayMarket,
} from "@/lib/betting-odds";
import type {
  PleBracketTheme,
  BracketSideStyle,
} from "@/lib/wwe-ple-bracket-theme";
import type {
  PleCompetitor,
  PleMatchCard,
  PleMatchResultHint,
} from "@/lib/wwe-ple-matches";
import { isMultiMatch } from "@/lib/wwe-ple-matches";
import type { PleMatchResult } from "@/lib/ple-api";

type Side = "left" | "right";

type SinglesVotes = { left: number; right: number };
type MultiVotes = number[];

type MatchBracketCardProps = {
  match: PleMatchCard;
  bracketTheme: PleBracketTheme;
  votes: SinglesVotes | MultiVotes;
  selected: Side | number | null;
  locked: boolean;
  onSelect: (pick: Side | number) => void;
  result?: PleMatchResult | PleMatchResultHint | null;
  showResults?: boolean;
  aiPickName?: string | null;
  aiCorrect?: boolean | null;
};

function AiPickBanner({
  aiPickName,
  aiCorrect,
  showResults,
}: {
  aiPickName?: string | null;
  aiCorrect?: boolean | null;
  showResults?: boolean;
}) {
  if (!aiPickName) return null;
  return (
    <p
      className={cn(
        "border-t border-stone-200/50 dark:border-white/8 bg-stone-50/50 dark:bg-white/[0.03] px-3 py-1.5 text-center text-[10px] text-stone-400 sm:text-xs",
        showResults &&
          aiCorrect === true &&
          "bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300",
        showResults &&
          aiCorrect === false &&
          "bg-red-50 dark:bg-red-950/40 text-red-700 dark:text-red-300",
      )}
    >
      <span className="font-semibold text-amber-400/90">AI 예측</span>
      <span className="mx-1 text-stone-600">·</span>
      <span className="font-medium text-stone-700 dark:text-stone-300">
        {aiPickName}
      </span>
      {showResults && aiCorrect != null && (
        <span className="ml-2 font-bold">
          {aiCorrect ? "✓ 적중" : "✗ 실패"}
        </span>
      )}
    </p>
  );
}

function VsDivider() {
  return (
    <div
      className="relative z-10 flex shrink-0 flex-col items-center justify-center px-1 sm:px-2"
      aria-hidden
    >
      <div className="h-full w-px bg-gradient-to-b from-transparent via-red-500/50 to-transparent" />
      <span className="font-sport absolute text-base font-bold tracking-[-0.06em] text-red-500 drop-shadow-[0_0_10px_rgba(239,68,68,0.55)] sm:text-lg">
        VS
      </span>
    </div>
  );
}

function pickOutcome(
  result: PleMatchResult | PleMatchResultHint | null | undefined,
  format: "singles" | "multi",
  index: Side | number,
): "win" | "loss" | null {
  if (!result) return null;
  if (format === "singles" && (index === "left" || index === "right")) {
    if (result.winnerSide === index) return "win";
    if (result.winnerSide) return "loss";
    return null;
  }
  if (
    format === "multi" &&
    typeof index === "number" &&
    result.winnerIndex === index
  ) {
    return "win";
  }
  if (format === "multi" && typeof result.winnerIndex === "number") {
    return "loss";
  }
  return null;
}

function ChampionBelt() {
  return (
    <span
      className="text-base leading-none"
      aria-hidden
      title={BRACKET_LABELS.championTitle}
    >
      {BRACKET_LABELS.trophy}
    </span>
  );
}

function CompetitorPick({
  competitor,
  nameStyle: _nameStyle,
  isSelected,
  isOtherSelected,
  locked,
  onSelect,
  compact,
  outcome,
}: {
  competitor: PleCompetitor;
  nameStyle: BracketSideStyle;
  isSelected: boolean;
  isOtherSelected: boolean;
  locked: boolean;
  onSelect: () => void;
  compact?: boolean;
  outcome?: "win" | "loss" | null;
}) {
  const resultsLocked = outcome !== null && outcome !== undefined;

  return (
    <button
      type="button"
      onClick={onSelect}
      disabled={locked || resultsLocked}
      aria-pressed={isSelected}
      aria-disabled={locked || resultsLocked}
      className={cn(
        "ple-pick-hover relative flex flex-col items-center justify-center gap-1 border-0 bg-transparent transition-all duration-200",
        compact ? "min-h-[56px] px-2 py-2" : "min-h-[80px] flex-1 px-2 py-3",
        "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-amber-400/60",
        outcome === "win" &&
          "bg-emerald-950/50 ring-2 ring-inset ring-emerald-500/70",
        outcome === "loss" && "bg-stone-900/50 opacity-60",
        outcome == null && isSelected && "ple-pick-selected",
        outcome != null && isSelected && "ring-2 ring-inset ring-amber-400/50",
        outcome == null && !isSelected && isOtherSelected && "bg-white/[0.02]",
        outcome == null && !isSelected && locked && "bg-white/[0.02]",
        (locked || resultsLocked) && "cursor-default",
      )}
    >
      <div className="flex items-center gap-1.5">
        {competitor.isChampion && <ChampionBelt />}
        <span
          className={cn(
            "text-center font-semibold text-stone-800 dark:text-stone-100",
            compact ? "text-xs sm:text-sm" : "text-sm sm:text-base",
            outcome === "win" && "text-emerald-300",
            outcome === "loss" && "text-stone-500",
          )}
        >
          {competitor.name}
        </span>
      </div>
      {isSelected && (
        <span
          className={cn(
            "mt-0.5 rounded px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-white",
            outcome == null ? "bg-amber-600" : "bg-amber-700",
          )}
        >
          {BRACKET_LABELS.myPick}
        </span>
      )}
      {outcome === "win" && (
        <span className="mt-0.5 rounded bg-emerald-600 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-white">
          {BRACKET_LABELS.win}
        </span>
      )}
      {outcome === "loss" && (
        <span className="mt-0.5 rounded bg-stone-400 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-white">
          {BRACKET_LABELS.loss}
        </span>
      )}
    </button>
  );
}

function SiteVoteBarTwoWay({
  votes,
  leftBarClass,
  rightBarClass,
}: {
  votes: SinglesVotes;
  leftBarClass: string;
  rightBarClass: string;
}) {
  const total = votes.left + votes.right;

  if (total === 0) {
    return (
      <div className="space-y-1">
        <div className="flex items-center justify-between text-[10px] sm:text-xs">
          <span className="font-medium text-stone-500">
            {BRACKET_LABELS.siteVote}
          </span>
          <span className="text-stone-600">{BRACKET_LABELS.noVotesYet}</span>
        </div>
        <div className="h-2 rounded-full bg-stone-200/60 dark:bg-white/10" />
      </div>
    );
  }

  const leftPercent = Math.round((votes.left / total) * 1000) / 10;
  const rightPercent = Math.round((votes.right / total) * 1000) / 10;

  return (
    <DualStatBar
      label={BRACKET_LABELS.siteVote}
      leftPercent={leftPercent}
      rightPercent={rightPercent}
      leftBarClass={leftBarClass}
      rightBarClass={rightBarClass}
    />
  );
}

function SiteVoteMulti({
  competitors,
  votes,
  barClass,
}: {
  competitors: PleCompetitor[];
  votes: MultiVotes;
  barClass: string;
}) {
  const total = votes.reduce((a, b) => a + b, 0);

  if (total === 0) {
    return (
      <div className="space-y-1">
        <div className="flex items-center justify-between text-[10px] sm:text-xs">
          <span className="font-medium text-stone-500">
            {BRACKET_LABELS.siteVote}
          </span>
          <span className="text-stone-600">{BRACKET_LABELS.noVotesYet}</span>
        </div>
        <div className="h-2 rounded-full bg-stone-200/60 dark:bg-white/10" />
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <span className="text-[10px] font-medium text-stone-500 sm:text-xs">
        {BRACKET_LABELS.siteVote}
      </span>
      <ul className="space-y-1.5">
        {competitors.map((c, i) => {
          const pct = Math.round((votes[i]! / total) * 1000) / 10;
          return (
            <li key={`${c.name}-${i}`} className="space-y-0.5">
              <div className="flex justify-between gap-2 text-[10px] sm:text-xs">
                <span className="truncate font-medium text-stone-400">
                  {c.name}
                </span>
                <span className="shrink-0 tabular-nums font-semibold text-stone-300">
                  {pct}%
                </span>
              </div>
              <div className="h-1.5 overflow-hidden rounded-full bg-stone-200/60 dark:bg-white/10">
                <div
                  className={cn("h-full transition-all", barClass)}
                  style={{ width: `${pct}%` }}
                />
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function DualStatBar({
  label,
  leftPercent,
  rightPercent,
  leftBarClass,
  rightBarClass,
  muted,
}: {
  label: string;
  leftPercent: number;
  rightPercent: number;
  leftBarClass: string;
  rightBarClass: string;
  muted?: boolean;
}) {
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-[10px] sm:text-xs">
        <span
          className={cn(
            "font-medium",
            muted ? "text-stone-400" : "text-stone-500",
          )}
        >
          {label}
        </span>
        <span className="tabular-nums text-stone-400">
          <span className="font-semibold">{leftPercent}%</span>
          <span className="mx-1 text-stone-500 dark:text-stone-300">
            {BRACKET_LABELS.percentSep}
          </span>
          <span className="font-semibold">{rightPercent}%</span>
        </span>
      </div>
      <div className="flex h-2 overflow-hidden rounded-full bg-stone-200/60 dark:bg-white/10">
        <div
          className={cn("h-full transition-all", leftBarClass)}
          style={{ width: `${leftPercent}%` }}
        />
        <div
          className={cn("h-full transition-all", rightBarClass)}
          style={{ width: `${rightPercent}%` }}
        />
      </div>
    </div>
  );
}

function BookmakerMulti({
  competitors,
  decimals,
}: {
  competitors: PleCompetitor[];
  decimals: number[];
}) {
  const percents = normalizedMultiMarket(decimals);

  return (
    <div className="space-y-2">
      <span className="text-[10px] font-medium text-stone-400 sm:text-xs">
        {BRACKET_LABELS.bookmaker}
      </span>
      <ul className="space-y-1">
        {competitors.map((c, i) => (
          <li
            key={`${c.name}-${i}`}
            className="flex justify-between gap-2 text-[10px] tabular-nums text-stone-500 sm:text-xs"
          >
            <span className="truncate">{c.name}</span>
            <span className="shrink-0 font-semibold">{percents[i]}%</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function MatchBracketCard({
  match,
  bracketTheme,
  votes,
  selected,
  locked,
  onSelect,
  result,
  showResults = false,
  aiPickName,
  aiCorrect,
}: MatchBracketCardProps) {
  const leftStyle = bracketTheme.sideA;
  const rightStyle = bracketTheme.sideB;
  const displayResults = showResults && !!result;

  if (isMultiMatch(match)) {
    const multiVotes = votes as MultiVotes;
    const selectedIndex = typeof selected === "number" ? selected : null;
    const barClass = leftStyle.voteBar;

    return (
      <article className="ple-match-card overflow-hidden rounded-xl">
        <div className="min-w-0 flex-1">
          <div className="ple-match-card-header px-3 py-2.5 text-center text-xs font-semibold leading-snug text-stone-900 dark:text-white sm:text-sm">
            {match.title}
          </div>
          <AiPickBanner
            aiPickName={aiPickName}
            aiCorrect={aiCorrect}
            showResults={displayResults}
          />

          <div className="border-t border-stone-200/50 dark:border-white/8 bg-stone-50/50 dark:bg-black/20 p-2">
            <p className="mb-2 text-center text-[10px] font-medium uppercase tracking-wide text-stone-500">
              {BRACKET_LABELS.participants}
            </p>
            <div className="grid grid-cols-2 gap-1.5 sm:grid-cols-3">
              {match.competitors.map((competitor, index) => {
                const style = index % 2 === 0 ? leftStyle : rightStyle;
                return (
                  <CompetitorPick
                    key={`${competitor.name}-${index}`}
                    competitor={competitor}
                    nameStyle={style}
                    isSelected={selectedIndex === index}
                    isOtherSelected={
                      selectedIndex !== null && selectedIndex !== index
                    }
                    locked={locked}
                    onSelect={() => onSelect(index)}
                    compact
                    outcome={
                      displayResults
                        ? pickOutcome(result, "multi", index)
                        : null
                    }
                  />
                );
              })}
            </div>
          </div>

          <div className="space-y-2.5 border-t border-stone-200/50 dark:border-white/8 bg-stone-50/50 dark:bg-white/[0.03] px-3 py-2.5 sm:px-4">
            <SiteVoteMulti
              competitors={match.competitors}
              votes={multiVotes}
              barClass={barClass}
            />
            {match.bookmakerDecimal && (
              <BookmakerMulti
                competitors={match.competitors}
                decimals={match.bookmakerDecimal}
              />
            )}
            <p className="text-center text-[9px] text-stone-600">
              {BRACKET_LABELS.bookNote}
            </p>
          </div>
        </div>
      </article>
    );
  }

  const singlesVotes = votes as SinglesVotes;
  const book = normalizedTwoWayMarket(
    match.bookmakerDecimal.left,
    match.bookmakerDecimal.right,
  );

  return (
    <article className="ple-match-card overflow-hidden rounded-xl">
      <div className="min-w-0 flex-1">
        <div className="ple-match-card-header px-3 py-2.5 text-center text-xs font-semibold leading-snug text-white sm:text-sm">
          {match.title}
        </div>
        <AiPickBanner
          aiPickName={aiPickName}
          aiCorrect={aiCorrect}
          showResults={displayResults}
        />

        <div className="relative flex border-t border-stone-200/50 dark:border-white/8 bg-stone-50/50 dark:bg-black/20">
          <CompetitorPick
            competitor={match.left}
            nameStyle={leftStyle}
            isSelected={selected === "left"}
            isOtherSelected={selected === "right"}
            locked={locked}
            onSelect={() => onSelect("left")}
            outcome={
              displayResults ? pickOutcome(result, "singles", "left") : null
            }
          />
          <VsDivider />
          <CompetitorPick
            competitor={match.right}
            nameStyle={rightStyle}
            isSelected={selected === "right"}
            isOtherSelected={selected === "left"}
            locked={locked}
            onSelect={() => onSelect("right")}
            outcome={
              displayResults ? pickOutcome(result, "singles", "right") : null
            }
          />
        </div>

        <div className="space-y-2.5 border-t border-white/8 bg-white/[0.03] px-3 py-2.5 sm:px-4">
          <SiteVoteBarTwoWay
            votes={singlesVotes}
            leftBarClass={leftStyle.voteBar}
            rightBarClass={rightStyle.voteBar}
          />
          <DualStatBar
            label={BRACKET_LABELS.bookmaker}
            leftPercent={book.left}
            rightPercent={book.right}
            leftBarClass="bg-stone-500"
            rightBarClass="bg-stone-400"
            muted
          />
          <p className="text-center text-[9px] text-stone-600">
            {BRACKET_LABELS.bookNote}
          </p>
        </div>
      </div>
    </article>
  );
}
