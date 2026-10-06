"use client";

import { cn } from "@/lib/utils";
import { BRACKET_LABELS } from "@/lib/bracket-labels";
import {
  consensusFromQuotes,
  normalizedMultiMarket,
  normalizedTwoWayMarket,
} from "@/lib/betting-odds";
import type { PleBracketTheme, BracketSideStyle } from "@/lib/wwe-ple-bracket-theme";
import type {
  BookmakerQuote,
  PleCompetitor,
  PleMatchCard,
  PleMatchResultHint,
} from "@/lib/wwe-ple-matches";
import { isMultiMatch } from "@/lib/wwe-ple-matches";
import type { PleMatchResult } from "@/lib/ple-api";
import { isBookmakerFallback, toPercent, type AiPrediction } from "@/lib/ple-ai-predictions";
import { AiReportDialog } from "@/components/ple/ai-report-dialog";

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
  /** 근거·승률까지 받은 예측. 못 불러왔으면 `null`이고, 이름만으로 띠가 선다. */
  prediction?: AiPrediction | null;
  slug: string;
};

/**
 * AI 예측 띠.
 *
 * **예전에는 10px 한 줄이었다** (2026-10-06 사용자 — "예측이 너무 숨겨져 있어서
 * 찾기 힘들어"). 카드 머리말 아래 회색 글자 한 줄이라, 이 카드에 AI 의견이 있다는
 * 사실 자체가 안 읽혔다. 지금은 이름을 카드 제목과 같은 크기로 세우고 승률 미터와
 * 근거 버튼을 함께 둔다.
 *
 * **색은 블루다**(DESIGN.md §1 — 블루 = AI·데이터). 예전 골드는 "가져갈 수 있는
 * 것"이라는 뜻을 가진 액션 색이라 이 자리에 설 색이 아니었다.
 *
 * 승률은 **예측을 실제로 받아왔을 때만** 적는다. 보드가 주는 것은 고른 쪽 이름과
 * 채점 결과뿐이라, 못 불러온 경우에 숫자를 만들어 채우지 않는다(§7).
 */
function AiPickBanner({
  slug,
  matchTitle,
  aiPickName,
  aiCorrect,
  showResults,
  prediction,
}: {
  slug: string;
  matchTitle: string;
  aiPickName?: string | null;
  aiCorrect?: boolean | null;
  showResults?: boolean;
  prediction?: AiPrediction | null;
}) {
  const pickName = prediction?.pickName ?? aiPickName;
  if (!pickName) return null;

  const percent = prediction ? toPercent(prediction.winProbability) : null;
  const graded = showResults === true && aiCorrect != null;
  /* 면은 **하나만** 고른다 — 두 `bg-`를 겹쳐 두고 병합기가 뒤를 살려 주기를
     기대하지 않는다. 채점된 뒤에는 적중/실패가 이 띠의 주제이므로 블루가 빠진다. */
  const surface = !graded ? "bg-data-surface" : aiCorrect ? "bg-chart-win/10" : "bg-live/10";

  return (
    <div
      className={cn(
        "border-t border-stone-200/50 dark:border-white/8 px-3 py-2.5 sm:px-4",
        surface,
      )}
    >
      <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1.5">
        <span className="shrink-0 text-xs font-semibold text-data">AI 예측</span>
        <span className="min-w-0 flex-1 text-sm font-semibold text-stone-800 dark:text-stone-100">
          {pickName}
        </span>
        {percent !== null && (
          <span className="shrink-0 text-xs tabular-nums text-stone-600 dark:text-stone-300">
            승률 <span className="font-semibold">{percent}%</span>
          </span>
        )}
        {prediction && isBookmakerFallback(prediction) && (
          <span className="shrink-0 rounded-md border border-stone-300/70 dark:border-stone-600/70 px-1.5 py-0.5 text-[11px] text-stone-500">
            배당 폴백
          </span>
        )}
        {/* 적중/실패는 **색과 글자를 함께** 단다 — 이 초록↔빨강 짝은 적록 색각에서
            붙는다(DESIGN.md §2). */}
        {graded && (
          <span
            className={cn(
              "shrink-0 rounded-md px-1.5 py-0.5 text-[11px] font-semibold",
              aiCorrect
                ? "border border-chart-win/50 bg-chart-win/10 text-chart-win"
                : "border border-live/50 bg-live/10 text-live",
            )}
          >
            {aiCorrect ? "적중" : "실패"}
          </span>
        )}
        {prediction && (
          <AiReportDialog slug={slug} matchTitle={matchTitle} prediction={prediction} />
        )}
      </div>
      {percent !== null && (
        <div
          className="mt-2 h-1.5 overflow-hidden rounded-full bg-stone-200/70 dark:bg-white/10"
          role="img"
          aria-label={`AI가 매긴 ${pickName} 승률 ${percent}%`}
        >
          <div className="h-full bg-data-400" style={{ width: `${percent}%` }} />
        </div>
      )}
    </div>
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
  if (format === "multi" && typeof index === "number" && result.winnerIndex === index) {
    return "win";
  }
  if (format === "multi" && typeof result.winnerIndex === "number") {
    return "loss";
  }
  return null;
}

function ChampionBelt() {
  return (
    <span className="text-base leading-none" aria-hidden title={BRACKET_LABELS.championTitle}>
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
        "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-brand-400/60",
        outcome === "win" && "bg-emerald-950/50 ring-2 ring-inset ring-emerald-500/70",
        outcome === "loss" && "bg-stone-900/50 opacity-60",
        outcome == null && isSelected && "ple-pick-selected",
        outcome != null && isSelected && "ring-2 ring-inset ring-brand-400/50",
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
            outcome == null ? "bg-brand-600" : "bg-brand-700",
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
          <span className="font-medium text-stone-500">{BRACKET_LABELS.siteVote}</span>
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
          <span className="font-medium text-stone-500">{BRACKET_LABELS.siteVote}</span>
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
                <span className="truncate font-medium text-stone-400">{c.name}</span>
                <span className="shrink-0 tabular-nums font-semibold text-stone-300">{pct}%</span>
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
        <span className={cn("font-medium", muted ? "text-stone-400" : "text-stone-500")}>
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

/**
 * 합의가 **몇 곳에서 왔는지**를 적는다. 막대만 보여 주면 한 곳의 값과 다섯 곳의
 * 합의가 화면에서 똑같이 생겨서, 어느 쪽을 얼마나 믿을지 판단할 근거가 사라진다.
 *
 * 곳이 둘 이상일 때만 편차를 적는다 — 한 곳뿐인데 "편차 0%p"라고 쓰면 의견이
 * 일치한다는 뜻으로 읽히지만 사실은 대조한 적이 없다.
 */
function BookmakerSources({ consensus }: { consensus: { books: string[]; dispersion: number } }) {
  const books = consensus.books.filter(Boolean);
  if (books.length === 0) return null;

  return (
    <p className="text-center text-[9px] text-stone-600 tabular-nums">
      {books.length > 1
        ? `북메이커 ${books.length}곳 합의 · ${books.join(", ")} · 편차 ${Math.round(consensus.dispersion * 1000) / 10}%p`
        : `${books[0]} 단독`}
    </p>
  );
}

function BookmakerMulti({
  competitors,
  decimals,
  quotes,
}: {
  competitors: PleCompetitor[];
  decimals?: number[];
  quotes?: BookmakerQuote[];
}) {
  // 단일전과 같은 우선순위다 — 호가 합의 > 카드의 배당 한 벌 > 아무것도 안 그린다.
  const consensus = quotes ? consensusFromQuotes(quotes, competitors.length) : null;
  const percents = consensus
    ? consensus.probabilities.map((p) => Math.round(p * 1000) / 10)
    : decimals
      ? normalizedMultiMarket(decimals)
      : null;
  if (!percents) return null;

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
  prediction,
  slug,
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
            slug={slug}
            matchTitle={match.title}
            aiPickName={aiPickName}
            aiCorrect={aiCorrect}
            showResults={displayResults}
            prediction={prediction}
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
                    isOtherSelected={selectedIndex !== null && selectedIndex !== index}
                    locked={locked}
                    onSelect={() => onSelect(index)}
                    compact
                    outcome={displayResults ? pickOutcome(result, "multi", index) : null}
                  />
                );
              })}
            </div>
          </div>

          <div className="space-y-2.5 border-t border-stone-200/50 dark:border-white/8 bg-stone-50/50 dark:bg-white/[0.03] px-3 py-2.5 sm:px-4">
            <SiteVoteMulti competitors={match.competitors} votes={multiVotes} barClass={barClass} />
            <BookmakerMulti
              competitors={match.competitors}
              decimals={match.bookmakerDecimal}
              quotes={match.bookmakerQuotes}
            />
            <p className="text-center text-[9px] text-stone-600">{BRACKET_LABELS.bookNote}</p>
          </div>
        </div>
      </article>
    );
  }

  const singlesVotes = votes as SinglesVotes;
  // 호가가 있으면 그 합의가 이 경기의 배당이다. 없으면 카드에 직접 적힌 한 벌을 쓰고,
  // 그것도 없으면 막대를 통째로 접는다 — 없는 숫자를 그럴듯하게 채우지 않는다.
  const consensus = match.bookmakerQuotes ? consensusFromQuotes(match.bookmakerQuotes, 2) : null;
  const book = consensus
    ? {
        left: Math.round(consensus.probabilities[0] * 1000) / 10,
        right: Math.round(consensus.probabilities[1] * 1000) / 10,
      }
    : match.bookmakerDecimal
      ? normalizedTwoWayMarket(match.bookmakerDecimal.left, match.bookmakerDecimal.right)
      : null;

  return (
    <article className="ple-match-card overflow-hidden rounded-xl">
      <div className="min-w-0 flex-1">
        <div className="ple-match-card-header px-3 py-2.5 text-center text-xs font-semibold leading-snug text-white sm:text-sm">
          {match.title}
        </div>
        <AiPickBanner
          slug={slug}
          matchTitle={match.title}
          aiPickName={aiPickName}
          aiCorrect={aiCorrect}
          showResults={displayResults}
          prediction={prediction}
        />

        <div className="relative flex border-t border-stone-200/50 dark:border-white/8 bg-stone-50/50 dark:bg-black/20">
          <CompetitorPick
            competitor={match.left}
            nameStyle={leftStyle}
            isSelected={selected === "left"}
            isOtherSelected={selected === "right"}
            locked={locked}
            onSelect={() => onSelect("left")}
            outcome={displayResults ? pickOutcome(result, "singles", "left") : null}
          />
          <VsDivider />
          <CompetitorPick
            competitor={match.right}
            nameStyle={rightStyle}
            isSelected={selected === "right"}
            isOtherSelected={selected === "left"}
            locked={locked}
            onSelect={() => onSelect("right")}
            outcome={displayResults ? pickOutcome(result, "singles", "right") : null}
          />
        </div>

        <div className="space-y-2.5 border-t border-white/8 bg-white/[0.03] px-3 py-2.5 sm:px-4">
          <SiteVoteBarTwoWay
            votes={singlesVotes}
            leftBarClass={leftStyle.voteBar}
            rightBarClass={rightStyle.voteBar}
          />
          {book && (
            <DualStatBar
              label={BRACKET_LABELS.bookmaker}
              leftPercent={book.left}
              rightPercent={book.right}
              leftBarClass="bg-stone-500"
              rightBarClass="bg-stone-400"
              muted
            />
          )}
          {consensus && <BookmakerSources consensus={consensus} />}
          <p className="text-center text-[9px] text-stone-600">{BRACKET_LABELS.bookNote}</p>
        </div>
      </div>
    </article>
  );
}
