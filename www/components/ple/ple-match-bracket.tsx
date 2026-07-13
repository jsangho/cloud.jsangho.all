"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { cn } from "@/lib/utils";
import { BRACKET_LABELS } from "@/lib/bracket-labels";
import type { PleSlug } from "@/lib/wwe-ple";
import { getBracketTheme } from "@/lib/wwe-ple-bracket-theme";
import {
  getPleMatches,
  isMultiMatch,
  type PleMatchCard,
} from "@/lib/wwe-ple-matches";
import {
  boardMatchesToCards,
  fetchPleBoard,
  submitPlePredictionsBatch,
  subscribePleLive,
  syncPleFromClient,
  type PleBoard,
  type PleBoardMatch,
} from "@/lib/ple-api";
import { useAuth } from "@/context/auth-context";
import { getPleClientId } from "@/lib/ple-client-id";
import { MatchBracketCard } from "@/components/ple/match-bracket-card";

type Side = "left" | "right";

type SinglesVoteState = {
  kind: "singles";
  votes: { left: number; right: number };
  selected: Side | null;
};

type MultiVoteState = {
  kind: "multi";
  votes: number[];
  selected: number | null;
};

type VoteState = SinglesVoteState | MultiVoteState;

type StoredBracketState = Record<string, VoteState>;

function storageKey(slug: PleSlug) {
  return `kayfabe-ple-votes-${slug}`;
}

function myPicksStorageKey(slug: PleSlug) {
  return `kayfabe-ple-mypicks-${slug}`;
}

function loadMyPicks(slug: PleSlug): Record<string, string> {
  try {
    const raw = localStorage.getItem(myPicksStorageKey(slug));
    if (!raw) return {};
    const parsed = JSON.parse(raw) as Record<string, string>;
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function saveMyPick(slug: PleSlug, matchId: string, pick: string) {
  try {
    const prev = loadMyPicks(slug);
    prev[matchId] = pick;
    localStorage.setItem(myPicksStorageKey(slug), JSON.stringify(prev));
  } catch {
    /* quota */
  }
}

function staticMatchFingerprint(cards: PleMatchCard[]): string {
  return cards
    .map((c) => c.id)
    .sort()
    .join("|");
}

function boardMatchFingerprint(board: PleBoard): string {
  return board.matches
    .map((m) => m.id)
    .sort()
    .join("|");
}

function needsStaticResync(
  board: PleBoard | null,
  staticCards: PleMatchCard[],
): boolean {
  if (!board || board.matches.length === 0) return true;
  return boardMatchFingerprint(board) !== staticMatchFingerprint(staticCards);
}

function emptySinglesVotes() {
  return { left: 0, right: 0 };
}

function emptyMultiVotes(count: number) {
  return Array.from({ length: count }, () => 0);
}

function buildInitialState(matches: PleMatchCard[]): StoredBracketState {
  const state: StoredBracketState = {};
  for (const m of matches) {
    if (isMultiMatch(m)) {
      state[m.id] = {
        kind: "multi",
        votes: emptyMultiVotes(m.competitors.length),
        selected: null,
      };
    } else {
      state[m.id] = {
        kind: "singles",
        votes: emptySinglesVotes(),
        selected: null,
      };
    }
  }
  return state;
}

function resolveMyPick(
  m: PleBoardMatch,
  savedPicks: Record<string, string>,
): Side | number | null {
  const raw = m.myPick ?? savedPicks[m.id];
  if (raw == null) return null;
  if (m.format === "multi") {
    const idx = Number(raw);
    return Number.isNaN(idx) ? null : idx;
  }
  if (raw === "left" || raw === "right") return raw;
  return null;
}

function stateFromBoard(
  board: PleBoard,
  savedPicks: Record<string, string> = {},
): StoredBracketState {
  const state: StoredBracketState = {};
  for (const m of board.matches) {
    if (m.format === "multi") {
      const votes = m.siteVotes.multi.length
        ? [...m.siteVotes.multi]
        : emptyMultiVotes(m.competitors?.length ?? 0);
      const selected = resolveMyPick(m, savedPicks);
      const pickIdx = typeof selected === "number" ? selected : null;
      state[m.id] = { kind: "multi", votes, selected: pickIdx };
    } else {
      const selected = resolveMyPick(m, savedPicks);
      const side =
        selected === "left" || selected === "right" ? selected : null;
      state[m.id] = {
        kind: "singles",
        votes: { left: m.siteVotes.left, right: m.siteVotes.right },
        selected: side,
      };
    }
  }
  return state;
}

function mergePreservedSelections(
  prev: StoredBracketState,
  next: StoredBracketState,
): StoredBracketState {
  const merged = { ...next };
  for (const [id, entry] of Object.entries(prev)) {
    if (entry.selected === null) continue;
    const target = merged[id];
    if (!target || target.selected !== null) continue;
    merged[id] =
      target.kind === entry.kind
        ? ({ ...target, selected: entry.selected } as VoteState)
        : target;
  }
  return merged;
}

function matchShowsResult(m: PleBoardMatch): boolean {
  return m.status === "finished" || !!m.result;
}

function normalizeStoredEntry(
  entry: VoteState,
  match: PleMatchCard,
): VoteState {
  if (isMultiMatch(match)) {
    const count = match.competitors.length;
    const base =
      entry.kind === "multi" ? [...entry.votes] : emptyMultiVotes(count);
    while (base.length < count) base.push(0);
    const votes = base.slice(0, count);

    if (
      entry.kind === "multi" &&
      entry.selected !== null &&
      entry.selected < count
    ) {
      votes[entry.selected] = 1;
      return { kind: "multi", votes, selected: entry.selected };
    }
    return { kind: "multi", votes: emptyMultiVotes(count), selected: null };
  }

  if (entry.kind === "singles") {
    if (entry.selected === "left") {
      return {
        kind: "singles",
        votes: { left: 1, right: 0 },
        selected: "left",
      };
    }
    if (entry.selected === "right") {
      return {
        kind: "singles",
        votes: { left: 0, right: 1 },
        selected: "right",
      };
    }
  }

  return { kind: "singles", votes: emptySinglesVotes(), selected: null };
}

type PleMatchBracketProps = {
  slug: PleSlug;
  className?: string;
};

type BracketUiState = {
  board: PleBoard | null;
  useApi: boolean;
  offline: boolean;
  committed: boolean;
  submitting: boolean;
  submitError: string | null;
};

const initialBracketUiState: BracketUiState = {
  board: null,
  useApi: false,
  offline: false,
  committed: false,
  submitting: false,
  submitError: null,
};

function countDraftPicks(
  matchIds: string[],
  state: StoredBracketState,
): number {
  return matchIds.filter((id) => state[id]?.selected != null).length;
}

/** 이벤트·경기 모두 예측 가능할 때만 true (종료 PLE는 예측 UI 비활성) */
function matchPickable(m: PleBoardMatch, eventFinished: boolean): boolean {
  return !eventFinished && m.status !== "finished";
}

function ensureVoteEntry(
  prev: StoredBracketState,
  match: PleMatchCard,
): VoteState {
  const existing = prev[match.id];
  if (existing) return existing;
  if (isMultiMatch(match)) {
    return {
      kind: "multi",
      votes: emptyMultiVotes(match.competitors.length),
      selected: null,
    };
  }
  return { kind: "singles", votes: emptySinglesVotes(), selected: null };
}

function allPredictionsCommitted(
  board: PleBoard,
  eventFinished: boolean,
): boolean {
  const open = board.matches.filter((m) => matchPickable(m, eventFinished));
  if (open.length === 0) return false;
  return open.every((m) => m.myPick != null);
}

export function PleMatchBracket({ slug, className }: PleMatchBracketProps) {
  const { user, isReady } = useAuth();
  const staticMatches = getPleMatches(slug);
  const bracketTheme = getBracketTheme(slug);
  const clientId = useMemo(() => getPleClientId(), []);
  const accountUserId = user?.id;
  const boardQuery = useMemo(
    () => ({ clientId, userId: accountUserId }),
    [clientId, accountUserId],
  );

  const [ui, setUi] = useState<BracketUiState>(initialBracketUiState);
  const [state, setState] = useState<StoredBracketState>(() =>
    buildInitialState(staticMatches),
  );

  const patchUi = (
    patch:
      | Partial<BracketUiState>
      | ((prev: BracketUiState) => Partial<BracketUiState>),
  ) =>
    setUi((prev) => {
      const p = typeof patch === "function" ? patch(prev) : patch;
      return { ...prev, ...p };
    });

  const matches: PleBoardMatch[] =
    ui.useApi && ui.board
      ? ui.board.matches
      : (staticMatches as unknown as PleBoardMatch[]);
  const eventFinished = ui.useApi && ui.board?.status === "finished";

  useEffect(() => {
    let cancelled = false;
    const staticCards = getPleMatches(slug);

    async function bootstrap() {
      try {
        let data: PleBoard | null = await fetchPleBoard(slug, boardQuery);
        if (needsStaticResync(data, staticCards)) {
          data = await syncPleFromClient(slug, staticCards);
        }
        if (!data) throw new Error("no board");
        if (cancelled) return;
        const finished = data.status === "finished";
        patchUi({
          board: data,
          useApi: true,
          offline: false,
          committed: !finished && allPredictionsCommitted(data, finished),
        });
        setState(stateFromBoard(data, loadMyPicks(slug)));
      } catch {
        if (cancelled) return;
        patchUi({ board: null, useApi: false, offline: true });
        setState(buildInitialState(staticCards));
        try {
          const raw = localStorage.getItem(storageKey(slug));
          if (raw) {
            const parsed = JSON.parse(raw) as StoredBracketState;
            setState((prev) => {
              const next = { ...prev };
              for (const m of staticCards) {
                if (parsed[m.id]) {
                  next[m.id] = normalizeStoredEntry(parsed[m.id], m);
                }
              }
              return next;
            });
          }
        } catch {
          /* ignore */
        }
      }
    }

    bootstrap();
    return () => {
      cancelled = true;
    };
  }, [slug, boardQuery]);

  useEffect(() => {
    if (!ui.offline) return;

    let cancelled = false;
    const staticCards = getPleMatches(slug);

    async function retryConnect() {
      try {
        let data: PleBoard | null = await fetchPleBoard(slug, boardQuery);
        if (needsStaticResync(data, staticCards)) {
          data = await syncPleFromClient(slug, staticCards);
        }
        if (!data) throw new Error("no board");
        if (cancelled) return;
        const finished = data.status === "finished";
        patchUi({
          board: data,
          useApi: true,
          offline: false,
          committed: !finished && allPredictionsCommitted(data, finished),
        });
        setState(stateFromBoard(data, loadMyPicks(slug)));
      } catch {
        // keep offline until next retry
      }
    }

    const timer = setInterval(() => {
      void retryConnect();
    }, 4000);

    void retryConnect();
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [slug, boardQuery, ui.offline]);

  useEffect(() => {
    if (!ui.useApi || accountUserId == null) return;
    return subscribePleLive(
      slug,
      clientId,
      (live) => {
        const finished = live.status === "finished";
        patchUi((prev) => ({
          board: live,
          committed:
            prev.committed ||
            (!finished && allPredictionsCommitted(live, finished)),
        }));
        setState((prev) =>
          mergePreservedSelections(
            prev,
            stateFromBoard(live, loadMyPicks(slug)),
          ),
        );
      },
      () => {
        /* SSE 실패 시 폴링 없이 마지막 스냅샷 유지 */
      },
      accountUserId,
    );
  }, [slug, clientId, accountUserId, ui.useApi]);

  const _persistLocal = useCallback(
    (next: StoredBracketState) => {
      if (ui.useApi) return;
      try {
        localStorage.setItem(storageKey(slug), JSON.stringify(next));
      } catch {
        /* quota */
      }
    },
    [slug, ui.useApi],
  );

  const handleSelect = useCallback(
    (match: PleMatchCard, pick: Side | number) => {
      if (!user || ui.committed) return;

      setState((prev) => {
        const current = ensureVoteEntry(prev, match);

        if (
          isMultiMatch(match) &&
          current.kind === "multi" &&
          typeof pick === "number"
        ) {
          return {
            ...prev,
            [match.id]: { ...current, selected: pick },
          };
        }

        if (
          !isMultiMatch(match) &&
          current.kind === "singles" &&
          (pick === "left" || pick === "right")
        ) {
          return {
            ...prev,
            [match.id]: { ...current, selected: pick },
          };
        }

        return prev;
      });
    },
    [user, ui.committed],
  );

  const canPredict = Boolean(user) && !eventFinished;

  const pickableIds = useMemo(
    () =>
      matches.filter((m) => matchPickable(m, !!eventFinished)).map((m) => m.id),
    [matches, eventFinished],
  );

  const draftCount = useMemo(
    () => countDraftPicks(pickableIds, state),
    [pickableIds, state],
  );

  const canConfirm =
    canPredict &&
    !ui.committed &&
    pickableIds.length > 0 &&
    draftCount === pickableIds.length;

  const showActionBar = matches.length > 0;

  const handleConfirm = useCallback(async () => {
    if (!canConfirm || ui.submitting || accountUserId == null) return;

    const items = pickableIds
      .map((matchId) => {
        const entry = state[matchId];
        if (!entry || entry.selected == null) return null;
        const pick =
          typeof entry.selected === "number"
            ? String(entry.selected)
            : entry.selected;
        return { matchKey: matchId, pick };
      })
      .filter((x): x is { matchKey: string; pick: string } => x != null);

    patchUi({ submitting: true, submitError: null });

    if (!ui.useApi) {
      patchUi({
        submitting: false,
        submitError: "서버에 연결된 뒤 로그인 상태에서 예측을 확정해 주세요.",
      });
      return;
    }

    try {
      const updated = await submitPlePredictionsBatch(
        slug,
        clientId,
        items,
        accountUserId,
      );
      for (const item of items) {
        saveMyPick(slug, item.matchKey, item.pick);
      }
      patchUi({ board: updated, committed: true, submitting: false });
      setState(stateFromBoard(updated, loadMyPicks(slug)));
    } catch (e) {
      patchUi({
        submitting: false,
        submitError: e instanceof Error ? e.message : "예측 저장 실패",
      });
    }
  }, [
    canConfirm,
    ui.submitting,
    ui.useApi,
    pickableIds,
    state,
    slug,
    clientId,
    accountUserId,
  ]);

  const handleEditDraft = useCallback(() => {
    patchUi({ committed: false, submitError: null });
  }, []);

  if (matches.length === 0) return null;

  if (!isReady) {
    return (
      <section className={cn("space-y-4", className)}>
        <p className="text-sm text-stone-500">예측 보드 불러오는 중…</p>
      </section>
    );
  }

  return (
    <section className={cn("space-y-4 pb-28", className)}>
      <div>
        <h2 className="font-kr-hero text-xl text-stone-900 dark:text-white sm:text-2xl">
          전체 경기 · 예측
        </h2>
        <p className="mt-1.5 text-xs text-stone-500">
          {user
            ? ui.committed
              ? "예측이 확정되었습니다 · 아래에서 다시 정할 수 있습니다"
              : "모든 경기를 고른 뒤 맨 아래 「예측 확정」을 눌러 주세요"
            : "승부 예측은 로그인한 회원만 할 수 있습니다 · 경기 카드는 조회만 가능"}
          {" · 사이트 투표와 북메이커 승률은 별도 표시"}
          {eventFinished && (
            <span className="ml-1 text-emerald-400">
              · {BRACKET_LABELS.liveResults}
            </span>
          )}
        </p>
        {!user && !eventFinished && (
          <div className="ple-login-callout mt-3 rounded-xl px-4 py-3 text-sm text-stone-700 dark:text-stone-300">
            <Link
              href={`/login?next=${encodeURIComponent(`/ple/${slug}`)}`}
              className="font-semibold text-amber-400 underline decoration-amber-500/40 underline-offset-2 transition-colors hover:text-amber-300"
            >
              로그인
            </Link>
            하면 승부 예측에 참여할 수 있습니다.
          </div>
        )}
        {ui.offline && (
          <p className="mt-2 flex items-start gap-2 rounded-lg border border-amber-500/25 bg-amber-100/60 dark:bg-amber-950/20 px-3 py-2 text-xs text-amber-700 dark:text-amber-200/90">
            <span className="shrink-0 font-bold text-amber-400">!</span>
            서버 연결 없음 — 예측 확정은 연결 후 로그인 상태에서만 가능합니다
          </p>
        )}
      </div>
      <ul className="space-y-4">
        {matches.map((matchRow) => {
          const match = boardMatchesToCards([matchRow])[0]!;
          const entry =
            state[match.id] ??
            (isMultiMatch(match)
              ? {
                  kind: "multi" as const,
                  votes: emptyMultiVotes(match.competitors.length),
                  selected: null,
                }
              : {
                  kind: "singles" as const,
                  votes: emptySinglesVotes(),
                  selected: null,
                });

          const votes = entry.kind === "multi" ? entry.votes : entry.votes;
          const selected = entry.selected;
          const pickable = matchPickable(matchRow, !!eventFinished);
          const cardLocked = !user || ui.committed || !pickable;

          return (
            <li key={match.id}>
              <MatchBracketCard
                match={match}
                bracketTheme={bracketTheme}
                votes={votes}
                selected={selected}
                locked={cardLocked}
                onSelect={(pick) => handleSelect(match, pick)}
                result={matchRow.result}
                showResults={ui.useApi && matchShowsResult(matchRow)}
                aiPickName={matchRow.aiPickName}
                aiCorrect={matchRow.aiCorrect}
              />
            </li>
          );
        })}
      </ul>

      {showActionBar && user && (
        <div className="fixed bottom-0 left-0 right-0 z-30 border-t border-stone-200/80 dark:border-white/10 bg-white/95 dark:bg-[#0a0a0c]/95 px-4 py-4 backdrop-blur-md">
          <div className="mx-auto flex max-w-3xl flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-center text-sm text-stone-400 sm:text-left">
              {!canPredict ? (
                <span>이 PLE는 종료되어 새 예측을 받지 않습니다.</span>
              ) : ui.committed ? (
                <span className="text-emerald-700 dark:text-emerald-300/90">
                  예측 확정 완료
                </span>
              ) : pickableIds.length === 0 ? (
                <span>예측 가능한 경기가 없습니다.</span>
              ) : (
                <>
                  선택{" "}
                  <span className="font-semibold tabular-nums text-stone-800 dark:text-stone-200">
                    {draftCount}/{pickableIds.length}
                  </span>
                  {draftCount < pickableIds.length && (
                    <span className="mt-0.5 block text-xs text-stone-500">
                      모든 경기를 고르면 확정할 수 있습니다
                    </span>
                  )}
                </>
              )}
            </p>
            <div className="flex flex-col gap-2 sm:flex-row sm:justify-end">
              {canPredict && ui.committed && (
                <button
                  type="button"
                  onClick={handleEditDraft}
                  className="rounded-lg border border-stone-300/70 dark:border-white/15 bg-stone-100/60 dark:bg-white/5 px-4 py-2.5 text-sm font-medium text-stone-700 dark:text-stone-200 backdrop-blur-sm hover:bg-stone-200 dark:hover:bg-white/10"
                >
                  예측 다시 정하기
                </button>
              )}
              {canPredict && !ui.committed && pickableIds.length > 0 && (
                <button
                  type="button"
                  disabled={!canConfirm || ui.submitting}
                  onClick={() => void handleConfirm()}
                  className={cn(
                    "rounded-lg px-6 py-2.5 text-sm font-bold transition-all",
                    canConfirm && !ui.submitting
                      ? "btn-predict-confirm"
                      : "cursor-not-allowed bg-stone-200 dark:bg-stone-800 text-stone-500 dark:text-stone-600",
                  )}
                >
                  {ui.submitting ? "저장 중…" : "예측 확정"}
                </button>
              )}
            </div>
          </div>
          {ui.submitError && (
            <p className="mt-2 text-center text-sm text-red-400" role="alert">
              {ui.submitError}
            </p>
          )}
        </div>
      )}
    </section>
  );
}
