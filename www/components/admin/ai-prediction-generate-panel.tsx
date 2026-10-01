"use client";

import { useCallback, useEffect, useState } from "react";
import { Loader2, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  fetchAiPredictions,
  generateAiPredictions,
  isBookmakerFallback,
  toPercent,
  LLM_CALLS_PER_MATCH,
  type AiPrediction,
} from "@/lib/ple-ai-predictions";
import { getPleMatches } from "@/lib/wwe-ple-matches";
import { formatPleMonth, pickFeaturedPle, WWE_PLE_LISTED, type PleSlug } from "@/lib/wwe-ple";

/**
 * AI 예측 생성 — 어드민 전용 패널.
 *
 * 이 엔드포인트(`POST /ple_events/{slug}/ai-predictions`)는 전부터 있었고 관리자
 * 게이트도 붙어 있었는데 **부를 화면이 없어서** 스크립트·curl로만 돌았다. 화면이
 * 하는 일은 셋이다 — 지금 무엇이 비어 있는지 보여주고, 누를 때 몇 번 호출되는지
 * 미리 세고, 돌아온 건수를 그대로 비춘다.
 *
 * **경기를 한 건씩 보낸다.** 대회 전체를 한 요청으로 묶으면 경기 수에 비례해
 * 길어져 중간 프록시에 먼저 끊기고, 그러면 백엔드는 계속 만드는데 화면만 실패로
 * 보인다. 한 건씩 보내면 진행률이 실제 진행과 같아지고, 한 경기의 실패가 나머지를
 * 데려가지 않는다.
 */

/** 경기 하나의 결과. 서버가 주는 건수(requested·generated·skipped·failed)를 번역한 값이다. */
type Outcome =
  | { kind: "generated" }
  | { kind: "skipped" }
  | { kind: "failed"; message?: string }
  /** 서버가 "요청 0건"을 줬다 — DB에 그 경기 행이 없다는 뜻이다. */
  | { kind: "absent" };

type PanelState = {
  slug: PleSlug;
  loading: boolean;
  /** `null`은 "못 불러왔다"다 — "예측이 없다"(빈 객체)와 다르다. */
  predictions: Record<string, AiPrediction> | null;
  selected: Record<string, boolean>;
  force: boolean;
  running: boolean;
  done: number;
  outcomes: Record<string, Outcome>;
};

const OUTCOME_LABEL: Record<Outcome["kind"], string> = {
  generated: "생성됨",
  skipped: "건너뜀 (이미 있음)",
  failed: "실패",
  absent: "DB에 경기 없음",
};

const OUTCOME_CLASS: Record<Outcome["kind"], string> = {
  generated: "text-data",
  skipped: "text-stone-400",
  failed: "text-live",
  absent: "text-live",
};

function defaultSlug(): PleSlug {
  const featured = pickFeaturedPle();
  return (featured?.slug ?? WWE_PLE_LISTED[0]!.slug) as PleSlug;
}

export function AiPredictionGeneratePanel() {
  const [state, setState] = useState<PanelState>(() => ({
    slug: defaultSlug(),
    loading: true,
    predictions: null,
    selected: {},
    force: false,
    running: false,
    done: 0,
    outcomes: {},
  }));

  const patch = (next: Partial<PanelState> | ((prev: PanelState) => Partial<PanelState>)) =>
    setState((prev) => ({ ...prev, ...(typeof next === "function" ? next(prev) : next) }));

  const cards = getPleMatches(state.slug);

  const load = useCallback(async (slug: PleSlug) => {
    patch({ loading: true, outcomes: {}, done: 0 });
    const result = await fetchAiPredictions(slug);
    const predictions = result.status === "ready" ? result.byMatch : null;
    // 예측이 없는 경기를 기본 선택으로 둔다 — 비용이 드는 쪽을 기본으로 켜지 않는다.
    const selected: Record<string, boolean> = {};
    for (const card of getPleMatches(slug)) {
      selected[card.id] = predictions ? predictions[card.id] == null : false;
    }
    patch({ loading: false, predictions, selected });
  }, []);

  useEffect(() => {
    void load(state.slug);
  }, [load, state.slug]);

  const selectedKeys = cards.map((c) => c.id).filter((id) => state.selected[id]);

  const run = async () => {
    if (state.running || selectedKeys.length === 0) return;
    patch({ running: true, done: 0, outcomes: {} });

    for (const matchKey of selectedKeys) {
      let outcome: Outcome;
      try {
        const summary = await generateAiPredictions(state.slug, {
          matchKeys: [matchKey],
          force: state.force,
        });
        if (summary.requested === 0) outcome = { kind: "absent" };
        else if (summary.generated > 0) outcome = { kind: "generated" };
        else if (summary.skipped > 0) outcome = { kind: "skipped" };
        else outcome = { kind: "failed" };
      } catch (e) {
        outcome = {
          kind: "failed",
          message: e instanceof Error ? e.message : undefined,
        };
      }
      patch((prev) => ({
        outcomes: { ...prev.outcomes, [matchKey]: outcome },
        done: prev.done + 1,
      }));
    }

    patch({ running: false });
    // 방금 만든 것이 화면에 남은 "없음"을 덮어야 한다.
    const result = await fetchAiPredictions(state.slug);
    if (result.status === "ready") patch({ predictions: result.byMatch });
  };

  return (
    <div className="rounded-xl border border-stone-300/50 dark:border-stone-700/50 bg-stone-50/70 dark:bg-stone-950/70 p-6">
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-data" />
          <h2 className="text-sm font-semibold text-stone-100">AI 예측 생성</h2>
        </div>
        <select
          value={state.slug}
          disabled={state.running}
          onChange={(e) => patch({ slug: e.target.value as PleSlug })}
          className="rounded-lg border border-stone-700/60 bg-stone-900/60 px-3 py-1.5 text-xs text-stone-100 outline-none focus:border-stone-500 disabled:opacity-50"
        >
          {WWE_PLE_LISTED.map((ple) => (
            <option key={ple.slug} value={ple.slug}>
              {formatPleMonth(ple.month)} · {ple.label}
            </option>
          ))}
        </select>
      </div>

      {state.loading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-5 w-5 animate-spin text-stone-500" />
        </div>
      ) : cards.length === 0 ? (
        <p className="py-10 text-center text-[11px] text-stone-600">
          이 대회의 경기 카드가 아직 없습니다.
        </p>
      ) : (
        <>
          {state.predictions === null && (
            <p className="mb-3 rounded-lg border border-live/50 px-3 py-2 text-[11px] text-live">
              현재 예측을 불러오지 못했습니다 — 아래 목록의 &ldquo;없음&rdquo;은 사실이 아닐 수
              있습니다.
            </p>
          )}

          <ul className="divide-y divide-stone-800">
            {cards.map((card) => {
              const prediction = state.predictions?.[card.id];
              const outcome = state.outcomes[card.id];
              return (
                <li key={card.id} className="flex items-start gap-3 py-2.5">
                  <input
                    type="checkbox"
                    checked={!!state.selected[card.id]}
                    disabled={state.running}
                    onChange={(e) =>
                      patch((prev) => ({
                        selected: { ...prev.selected, [card.id]: e.target.checked },
                      }))
                    }
                    className="mt-0.5 h-3.5 w-3.5 shrink-0 accent-data-500"
                  />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[12px] text-stone-100">{card.title}</p>
                    <p className="mt-0.5 text-[10px] text-stone-500">
                      {prediction ? (
                        <>
                          {prediction.pickName} · {toPercent(prediction.winProbability)}%
                          {isBookmakerFallback(prediction) && " · 북메이커 폴백"} ·{" "}
                          {new Date(prediction.generatedAt).toLocaleString("ko-KR")}
                        </>
                      ) : (
                        "예측 없음"
                      )}
                    </p>
                  </div>
                  {outcome && (
                    <span
                      className={cn("shrink-0 text-[10px]", OUTCOME_CLASS[outcome.kind])}
                      title={outcome.kind === "failed" ? outcome.message : undefined}
                    >
                      {OUTCOME_LABEL[outcome.kind]}
                    </span>
                  )}
                </li>
              );
            })}
          </ul>

          <div className="mt-5 flex flex-col gap-3 border-t border-stone-800 pt-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="text-[11px] text-stone-400">
              <p>
                선택{" "}
                <span className="font-semibold tabular-nums text-stone-200">
                  {selectedKeys.length}/{cards.length}
                </span>{" "}
                · LLM 호출{" "}
                <span className="font-semibold tabular-nums text-stone-200">
                  {selectedKeys.length * LLM_CALLS_PER_MATCH}회
                </span>{" "}
                예상
              </p>
              {/* 지어낸 잔량을 세우지 않는다 — 한도는 모델당 하루 20요청이라는 사실만 적는다. */}
              <p className="mt-0.5 text-stone-500">
                경기당 서사·루머 두 번. 오즈 축은 LLM을 쓰지 않습니다.
              </p>
            </div>

            <div className="flex shrink-0 items-center gap-3">
              <label className="flex items-center gap-1.5 text-[11px] text-stone-400">
                <input
                  type="checkbox"
                  checked={state.force}
                  disabled={state.running}
                  onChange={(e) => patch({ force: e.target.checked })}
                  className="h-3.5 w-3.5 accent-data-500"
                />
                이미 있는 예측도 다시 만들기
              </label>
              <button
                type="button"
                onClick={() => void run()}
                disabled={state.running || selectedKeys.length === 0}
                className="flex items-center gap-1.5 rounded-lg bg-data-500 px-4 py-2 text-xs font-semibold text-white transition-colors hover:bg-data-400 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {state.running ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Sparkles className="h-3.5 w-3.5" />
                )}
                {state.running ? `생성 중… ${state.done}/${selectedKeys.length}` : "예측 생성"}
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
