"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { cn } from "@/lib/utils";
import {
  boardMatchesToCards,
  fetchPleBoard,
  submitPleResultsBatch,
  syncPleFromClient,
  type PleBoard,
  type PleBoardMatch,
} from "@/lib/ple-api";
import type { PleSlug } from "@/lib/wwe-ple";
import { PleResultsAdminGate } from "@/components/results/ple-results-admin-gate";
import {
  getPleMatches,
  isMultiMatch,
  type PleMatchCard,
} from "@/lib/wwe-ple-matches";

type PleResultsBoardProps = {
  slug: PleSlug;
};

type DraftPick =
  | { kind: "singles"; side: "left" | "right"; name: string }
  | { kind: "multi"; index: number; name: string };

type ResultsUiState = {
  drafts: Record<string, DraftPick | null>;
  submitting: boolean;
  submitError: string | null;
};

function draftFromMatch(
  match: PleBoardMatch,
  pick: DraftPick | null,
): {
  winnerSide?: "left" | "right";
  winnerIndex?: number;
  winnerName?: string;
} {
  if (!pick) return {};
  if (pick.kind === "singles") {
    return { winnerSide: pick.side, winnerName: pick.name };
  }
  return { winnerIndex: pick.index, winnerName: pick.name };
}

function pickFromExisting(
  matchRow: PleBoardMatch,
  matchCard: PleMatchCard,
): DraftPick | null {
  const r = matchRow.result;
  if (!r) return null;
  if (matchCard.format === "multi" && r.winnerIndex != null) {
    const name =
      matchCard.competitors[r.winnerIndex]?.name ?? r.winnerName ?? "";
    return { kind: "multi", index: r.winnerIndex, name };
  }
  if (r.winnerSide === "left" || r.winnerSide === "right") {
    const name =
      r.winnerSide === "left"
        ? matchCard.format === "singles"
          ? matchCard.left.name
          : ""
        : matchCard.format === "singles"
          ? matchCard.right.name
          : "";
    return {
      kind: "singles",
      side: r.winnerSide,
      name: r.winnerName ?? name,
    };
  }
  return null;
}

function winnerLabel(
  matchRow: PleBoardMatch,
  matchCard: PleMatchCard,
): string | null {
  const r = matchRow.result;
  if (!r) return null;
  if (r.winnerName) return r.winnerName;
  if (matchCard.format === "singles" && r.winnerSide) {
    return r.winnerSide === "left" ? matchCard.left.name : matchCard.right.name;
  }
  if (matchCard.format === "multi" && r.winnerIndex != null) {
    return matchCard.competitors[r.winnerIndex]?.name ?? null;
  }
  return null;
}

/** API 카드에 isChampion이 빠진 경우 정적 시드에서 보강 */
function mergeChampionFromStatic(
  card: PleMatchCard,
  staticCard: PleMatchCard | undefined,
): PleMatchCard {
  if (!staticCard) return card;
  if (isMultiMatch(card) && isMultiMatch(staticCard)) {
    return {
      ...card,
      competitors: card.competitors.map((c, i) => ({
        ...c,
        isChampion: c.isChampion ?? staticCard.competitors[i]?.isChampion,
      })),
    };
  }
  if (!isMultiMatch(card) && !isMultiMatch(staticCard)) {
    return {
      ...card,
      left: {
        ...card.left,
        isChampion: card.left.isChampion ?? staticCard.left.isChampion,
      },
      right: {
        ...card.right,
        isChampion: card.right.isChampion ?? staticCard.right.isChampion,
      },
    };
  }
  return card;
}

function buildInitialDrafts(
  matches: PleBoardMatch[],
  cardsById: Record<string, PleMatchCard>,
): Record<string, DraftPick | null> {
  const drafts: Record<string, DraftPick | null> = {};
  for (const m of matches) {
    const card = cardsById[m.id];
    drafts[m.id] = card ? pickFromExisting(m, card) : null;
  }
  return drafts;
}

function MatchResultRow({
  matchRow,
  matchCard,
  pick,
  onPick,
  canEdit,
}: {
  matchRow: PleBoardMatch;
  matchCard: PleMatchCard;
  pick: DraftPick | null;
  onPick: (next: DraftPick) => void;
  canEdit: boolean;
}) {
  const hasResult = !!matchRow.result;
  const readonlyWinner = winnerLabel(matchRow, matchCard);

  return (
    <li
      className={cn(
        "rounded-xl border p-4",
        hasResult
          ? "border-emerald-500/50 bg-emerald-50/60 dark:bg-emerald-950/25"
          : "border-stone-300/70 dark:border-stone-600/70 bg-stone-100/50 dark:bg-stone-800/50",
      )}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <h3 className="font-semibold text-stone-800 dark:text-stone-100">
          {matchRow.title}
        </h3>
        {hasResult && (
          <span className="rounded-full bg-emerald-900/80 px-2.5 py-0.5 text-xs font-medium text-emerald-300">
            결과 등록됨
          </span>
        )}
      </div>

      {!canEdit && hasResult && readonlyWinner && (
        <p className="mt-3 text-sm font-medium text-emerald-800 dark:text-emerald-200/90">
          승자: {readonlyWinner}
        </p>
      )}

      {!canEdit && !hasResult && (
        <p className="mt-3 text-sm text-stone-500">
          아직 등록된 결과가 없습니다.
        </p>
      )}

      {canEdit && (
        <div className="mt-3 flex flex-wrap gap-2">
          {!isMultiMatch(matchCard)
            ? (["left", "right"] as const).map((side) => {
                const competitor =
                  side === "left" ? matchCard.left : matchCard.right;
                const selected = pick?.kind === "singles" && pick.side === side;
                return (
                  <button
                    key={side}
                    type="button"
                    onClick={() =>
                      onPick({
                        kind: "singles",
                        side,
                        name: competitor.name,
                      })
                    }
                    className={cn(
                      "rounded-lg border px-4 py-2.5 text-sm font-medium transition-colors",
                      selected
                        ? "border-amber-500/80 bg-amber-100 dark:bg-amber-950/50 text-amber-800 dark:text-amber-100"
                        : "border-stone-300 dark:border-stone-600 bg-stone-100/60 dark:bg-stone-900/60 text-stone-700 dark:text-stone-300 hover:border-stone-400 dark:hover:border-stone-500 hover:bg-stone-200 dark:hover:bg-stone-800",
                    )}
                  >
                    {competitor.name}
                    {competitor.isChampion && (
                      <span className="ml-1 text-xs text-amber-400">(C)</span>
                    )}
                  </button>
                );
              })
            : matchCard.competitors.map((c, idx) => {
                const selected = pick?.kind === "multi" && pick.index === idx;
                return (
                  <button
                    key={idx}
                    type="button"
                    onClick={() =>
                      onPick({ kind: "multi", index: idx, name: c.name })
                    }
                    className={cn(
                      "rounded-lg border px-3 py-2 text-sm font-medium transition-colors",
                      selected
                        ? "border-amber-500/80 bg-amber-100 dark:bg-amber-950/50 text-amber-800 dark:text-amber-100"
                        : "border-stone-300 dark:border-stone-600 bg-stone-100/60 dark:bg-stone-900/60 text-stone-700 dark:text-stone-300 hover:border-stone-400 dark:hover:border-stone-500 hover:bg-stone-200 dark:hover:bg-stone-800",
                    )}
                  >
                    {c.name}
                    {c.isChampion && (
                      <span className="ml-1 text-xs text-amber-400">(C)</span>
                    )}
                  </button>
                );
              })}
        </div>
      )}

      {canEdit && pick && (
        <p className="mt-2 text-xs text-stone-400">
          선택:{" "}
          <span className="text-stone-800 dark:text-stone-200">
            {pick.name}
          </span>
        </p>
      )}
    </li>
  );
}

export function PleResultsBoard({ slug }: PleResultsBoardProps) {
  const staticMatches = getPleMatches(slug);
  const [board, setBoard] = useState<PleBoard | null>(null);
  const [loading, setLoading] = useState(true);
  const [syncError, setSyncError] = useState<string | null>(null);
  const [canEdit, setCanEdit] = useState(false);
  const [ui, setUi] = useState<ResultsUiState>({
    drafts: {},
    submitting: false,
    submitError: null,
  });

  const patchUi = (patch: Partial<ResultsUiState>) =>
    setUi((prev) => ({ ...prev, ...patch }));

  const load = useCallback(async () => {
    const cards = getPleMatches(slug);
    setLoading(true);
    try {
      let data = await fetchPleBoard(slug);
      const needSync =
        !data ||
        data.matches.length === 0 ||
        cards
          .map((c) => c.id)
          .sort()
          .join("|") !==
          data.matches
            .map((m) => m.id)
            .sort()
            .join("|");
      if (needSync && cards.length > 0) {
        data = await syncPleFromClient(slug, cards);
      }
      setBoard(data);
      setSyncError(null);
      if (data) {
        const cardsById: Record<string, PleMatchCard> = {};
        for (const m of data.matches) {
          cardsById[m.id] = boardMatchesToCards([m])[0]!;
        }
        patchUi({ drafts: buildInitialDrafts(data.matches, cardsById) });
      }
    } catch (e) {
      setSyncError(e instanceof Error ? e.message : "서버 연결 실패");
      setBoard(null);
    } finally {
      setLoading(false);
    }
  }, [slug]);

  useEffect(() => {
    load();
  }, [load]);

  const matches: PleBoardMatch[] =
    board?.matches ??
    staticMatches.map((m, i) => ({
      id: m.id,
      dbId: i,
      title: m.title,
      cardVariant: m.cardVariant,
      format: m.format,
      left: !isMultiMatch(m) ? m.left : undefined,
      right: !isMultiMatch(m) ? m.right : undefined,
      competitors: isMultiMatch(m) ? m.competitors : undefined,
      bookmakerDecimal: m.bookmakerDecimal,
      status: "scheduled",
      siteVotes: { left: 0, right: 0, multi: [] },
      locked: false,
    }));

  const staticById = useMemo(() => {
    const map: Record<string, PleMatchCard> = {};
    for (const m of staticMatches) {
      map[m.id] = m;
    }
    return map;
  }, [staticMatches]);

  const matchCards = useMemo(() => {
    const map: Record<string, PleMatchCard> = {};
    for (const m of matches) {
      const card = boardMatchesToCards([m])[0]!;
      map[m.id] = mergeChampionFromStatic(card, staticById[m.id]);
    }
    return map;
  }, [matches, staticById]);

  const draftCount = useMemo(
    () => matches.filter((m) => ui.drafts[m.id] != null).length,
    [matches, ui.drafts],
  );

  const canSubmit =
    canEdit &&
    board != null &&
    !syncError &&
    draftCount === matches.length &&
    matches.length > 0;

  const handleSubmitAll = async () => {
    if (!canSubmit || ui.submitting) return;

    patchUi({ submitting: true, submitError: null });
    try {
      const results = matches.map((m) => {
        const pick = ui.drafts[m.id];
        if (!pick) throw new Error("모든 경기의 승자를 선택해 주세요.");
        return {
          matchKey: m.id,
          ...draftFromMatch(m, pick),
          status: "finished" as const,
        };
      });
      const updated = await submitPleResultsBatch(slug, results);
      setBoard(updated);
      const cardsById: Record<string, PleMatchCard> = {};
      for (const m of updated.matches) {
        cardsById[m.id] = boardMatchesToCards([m])[0]!;
      }
      patchUi({
        drafts: buildInitialDrafts(updated.matches, cardsById),
        submitting: false,
      });
    } catch (e) {
      patchUi({
        submitting: false,
        submitError: e instanceof Error ? e.message : "등록 실패",
      });
    }
  };

  if (staticMatches.length === 0) {
    return (
      <p className="rounded-xl border border-stone-300/60 dark:border-stone-700/60 bg-stone-100/40 dark:bg-stone-800/40 px-4 py-8 text-center text-sm text-stone-500 dark:text-stone-400">
        이 PLE의 경기 카드가 아직 등록되지 않았습니다.
      </p>
    );
  }

  return (
    <div className="space-y-4">
      <PleResultsAdminGate onAdminChange={setCanEdit} />
      {syncError && (
        <p className="rounded-lg border border-amber-500/60 bg-amber-100/60 dark:bg-amber-950/30 px-4 py-3 text-sm text-amber-800 dark:text-amber-200">
          서버 연결 없음 — 결과를 등록하려면 백엔드가 실행 중이어야 합니다. (
          {syncError})
        </p>
      )}
      {loading && (
        <p className="text-center text-sm text-stone-500">
          경기 목록 불러오는 중…
        </p>
      )}
      {!loading && (
        <>
          {canEdit && (
            <p className="text-sm text-stone-400">
              모든 경기의 승자를 고른 뒤 맨 아래 「결과 일괄 등록」을 눌러
              주세요. 확정 전까지 언제든지 변경할 수 있습니다.
            </p>
          )}
          <ul className="space-y-4">
            {matches.map((matchRow) => {
              const matchCard = matchCards[matchRow.id]!;
              return (
                <MatchResultRow
                  key={matchRow.id}
                  matchRow={matchRow}
                  matchCard={matchCard}
                  pick={ui.drafts[matchRow.id] ?? null}
                  onPick={(next) =>
                    patchUi({
                      drafts: { ...ui.drafts, [matchRow.id]: next },
                    })
                  }
                  canEdit={canEdit}
                />
              );
            })}
          </ul>
          {canEdit && (
            <div className="sticky bottom-0 z-20 border-t border-stone-200/80 dark:border-stone-700/80 bg-white/95 dark:bg-stone-900/95 py-4 backdrop-blur-md">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <p className="text-center text-sm text-stone-400 sm:text-left">
                  선택{" "}
                  <span className="font-semibold tabular-nums text-stone-700 dark:text-stone-200">
                    {draftCount}/{matches.length}
                  </span>
                </p>
                <button
                  type="button"
                  disabled={!canSubmit || ui.submitting}
                  onClick={() => void handleSubmitAll()}
                  className={cn(
                    "rounded-lg px-6 py-2.5 text-sm font-bold transition-colors",
                    canSubmit && !ui.submitting
                      ? "bg-amber-600 text-stone-950 hover:bg-amber-500"
                      : "cursor-not-allowed bg-stone-200 dark:bg-stone-700 text-stone-500",
                  )}
                >
                  {ui.submitting ? "등록 중…" : "결과 일괄 등록"}
                </button>
              </div>
              {ui.submitError && (
                <p
                  className="mt-2 text-center text-sm text-red-400"
                  role="alert"
                >
                  {ui.submitError}
                </p>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
