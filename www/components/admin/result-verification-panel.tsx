"use client";

import { useCallback, useEffect, useState } from "react";
import { Loader2, ScanSearch } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  fetchPendingResults,
  runResultVerification,
  HOLD_LABEL,
  type MatchVerification,
  type PendingMatch,
} from "@/lib/result-verification-api";

/**
 * 결과 확정 패널.
 *
 * **고르는 것도 쓰는 것도 사람이 한다.** 모델이 하는 일은 위키를 읽고 "승자는 이 사람,
 * 근거는 이 구절"이라고 주장하는 것까지이고, 그 주장을 쓸지는 서버의 순수 함수가
 * 판정한다. 화면은 그 판정을 비추고 쓰기 버튼을 따로 둔다.
 *
 * 기본이 **드라이런**이다 — 쓰는 값이 모델이 읽은 문서에서 파생되기 때문이다.
 * 기본 선택도 **아무것도 없다**: 여기 있는 모든 줄이 비용이 드는 대상이라, 켜 두면
 * 실수로 전부 돌린다.
 */

type Outcome =
  | { kind: "result"; value: MatchVerification }
  /** 요청이 끊겼다. **쓰였는지 아닌지 알 수 없다** — 목록이 사실이다. */
  | { kind: "unknown"; message: string };

type PanelState = {
  loading: boolean;
  pending: PendingMatch[];
  error: string | null;
  selected: Record<string, boolean>;
  apply: boolean;
  running: boolean;
  done: number;
  outcomes: Record<string, Outcome>;
};

export function ResultVerificationPanel() {
  const [state, setState] = useState<PanelState>({
    loading: true,
    pending: [],
    error: null,
    selected: {},
    apply: false,
    running: false,
    done: 0,
    outcomes: {},
  });

  const patch = (next: Partial<PanelState> | ((prev: PanelState) => Partial<PanelState>)) =>
    setState((prev) => ({ ...prev, ...(typeof next === "function" ? next(prev) : next) }));

  const load = useCallback(async () => {
    patch({ loading: true, error: null });
    try {
      const pending = await fetchPendingResults();
      // 선택은 비운 채로 시작한다 — 전부 비용이 드는 줄이다.
      patch({ loading: false, pending, selected: {} });
    } catch (e) {
      patch({
        loading: false,
        pending: [],
        error: e instanceof Error ? e.message : "불러오지 못했습니다.",
      });
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const selectedKeys = state.pending.map((m) => m.matchKey).filter((k) => state.selected[k]);

  const run = async () => {
    if (state.running || selectedKeys.length === 0) return;
    if (
      state.apply &&
      !window.confirm(
        `${selectedKeys.length}건을 확정해 DB에 씁니다. 승자는 채점·랭킹의 입력입니다.`,
      )
    ) {
      return;
    }
    patch({ running: true, done: 0, outcomes: {} });

    for (const matchKey of selectedKeys) {
      const event = state.pending.find((m) => m.matchKey === matchKey);
      let outcome: Outcome;
      try {
        const run = await runResultVerification({
          matchKeys: [matchKey],
          apply: state.apply,
          eventSlug: event?.eventSlug,
        });
        const match = run.matches[0];
        outcome = match
          ? { kind: "result", value: match }
          : { kind: "unknown", message: "서버가 이 경기를 대상으로 잡지 않았습니다." };
      } catch (e) {
        outcome = {
          kind: "unknown",
          message: e instanceof Error ? e.message : "요청이 끊겼습니다.",
        };
      }
      patch((prev) => ({
        outcomes: { ...prev.outcomes, [matchKey]: outcome },
        done: prev.done + 1,
      }));
    }

    patch({ running: false });
    // 쓰기였다면 목록에서 빠진다. 끊긴 요청이 실제로 썼는지도 여기서 드러난다.
    if (state.apply) await load();
  };

  return (
    <div className="rounded-xl border border-stone-300/50 dark:border-stone-700/50 bg-stone-50/70 dark:bg-stone-950/70 p-6">
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <ScanSearch className="h-4 w-4 text-data" />
          <h2 className="text-sm font-semibold text-stone-100">결과 확정</h2>
        </div>
        <button
          onClick={() => void load()}
          disabled={state.loading || state.running}
          className="text-[11px] text-stone-500 transition-colors hover:text-stone-300 disabled:opacity-50"
        >
          새로고침
        </button>
      </div>

      <p className="mb-4 text-[11px] leading-relaxed text-stone-500">
        끝난 대회(<code className="text-stone-400">finished</code>)의 승자 미기록 경기를 위키에서
        찾습니다. <strong className="text-stone-300">모델에게 쓰기 권한은 없습니다</strong> — 읽고
        주장만 하고, 쓸지는 서버가 인용을 대조해 판정합니다. 보류는 실패가 아닙니다.
        <br />
        대상이 안 보이면 「대회 상태」 탭에서 지난 대회를 먼저 닫아야 할 수 있습니다.
      </p>

      {state.error && (
        <p
          className="mb-3 rounded-lg border border-live/50 px-3 py-2 text-[11px] text-live"
          role="alert"
        >
          {state.error}
        </p>
      )}

      {state.loading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-5 w-5 animate-spin text-stone-500" />
        </div>
      ) : state.pending.length === 0 ? (
        <p className="py-10 text-center text-[11px] text-stone-600">승자 미기록 경기가 없습니다.</p>
      ) : (
        <>
          <ul className="divide-y divide-stone-800">
            {state.pending.map((match) => {
              const outcome = state.outcomes[match.matchKey];
              return (
                <li key={match.matchKey} className="flex items-start gap-3 py-2.5">
                  <input
                    type="checkbox"
                    checked={!!state.selected[match.matchKey]}
                    disabled={state.running}
                    onChange={(e) =>
                      patch((prev) => ({
                        selected: { ...prev.selected, [match.matchKey]: e.target.checked },
                      }))
                    }
                    className="mt-0.5 h-3.5 w-3.5 shrink-0 accent-data-500"
                  />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[12px] text-stone-100">{match.title}</p>
                    <p className="mt-0.5 truncate text-[10px] text-stone-500">
                      {match.eventLabel} · {match.options.join(" vs ")}
                    </p>
                    {outcome?.kind === "result" && (
                      <div className="mt-1.5 rounded-lg border border-stone-700/60 bg-stone-900/40 px-2.5 py-2">
                        {outcome.value.hold ? (
                          <p className="text-[10px] text-live">
                            보류 — {HOLD_LABEL[outcome.value.hold] ?? outcome.value.hold}
                          </p>
                        ) : (
                          <p className="text-[10px] text-stone-200">
                            승자 <span className="font-semibold">{outcome.value.winnerName}</span>
                            {outcome.value.written ? (
                              <span className="ml-1 text-data">· 기록됨</span>
                            ) : (
                              <span className="ml-1 text-stone-500">· 드라이런(쓰지 않음)</span>
                            )}
                          </p>
                        )}
                        {outcome.value.quote && (
                          <p className="mt-1 text-[10px] leading-relaxed text-stone-400">
                            “{outcome.value.quote}”
                            {outcome.value.sourceTitle && (
                              <span className="text-stone-600"> — {outcome.value.sourceTitle}</span>
                            )}
                          </p>
                        )}
                        <p className="mt-1 text-[10px] text-stone-600">
                          도구 호출 {outcome.value.toolCalls}회
                        </p>
                      </div>
                    )}
                    {outcome?.kind === "unknown" && (
                      <p className="mt-1.5 text-[10px] text-live">
                        확인 불가 — {outcome.message} 쓰였는지는 목록을 새로고침해 판단하세요.
                      </p>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>

          <div className="mt-5 flex flex-col gap-3 border-t border-stone-800 pt-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="text-[11px] text-stone-400">
              <p>
                선택{" "}
                <span className="font-semibold tabular-nums text-stone-200">
                  {selectedKeys.length}/{state.pending.length}
                </span>
              </p>
              {/* 호출 수는 미리 알 수 없다 — 걸음이 데이터에 따라 갈린다. 지어내지 않고
                  상한과 간격만 적는다. */}
              <p className="mt-0.5 text-stone-500">
                경기당 최대 6걸음 · 호출 간격 15초(분당 한도) — 한 건이 1분을 넘길 수 있습니다.
              </p>
            </div>

            <div className="flex shrink-0 items-center gap-3">
              <label className="flex items-center gap-1.5 text-[11px] text-stone-400">
                <input
                  type="checkbox"
                  checked={state.apply}
                  disabled={state.running}
                  onChange={(e) => patch({ apply: e.target.checked })}
                  className="h-3.5 w-3.5 accent-live"
                />
                DB에 쓰기
              </label>
              <button
                type="button"
                onClick={() => void run()}
                disabled={state.running || selectedKeys.length === 0}
                className={cn(
                  "flex items-center gap-1.5 rounded-lg px-4 py-2 text-xs font-semibold text-white transition-colors disabled:cursor-not-allowed disabled:opacity-50",
                  state.apply ? "bg-live hover:opacity-90" : "bg-data-500 hover:bg-data-400",
                )}
              >
                {state.running ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <ScanSearch className="h-3.5 w-3.5" />
                )}
                {state.running
                  ? `확인 중… ${state.done}/${selectedKeys.length}`
                  : state.apply
                    ? "확정해서 쓰기"
                    : "돌려만 보기"}
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
