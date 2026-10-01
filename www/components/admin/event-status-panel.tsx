"use client";

import { useCallback, useEffect, useState } from "react";
import { CalendarCheck, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  closePastEvents,
  fetchEventStatusDrift,
  type EventStatusDrift,
} from "@/lib/event-status-api";

/**
 * 대회 상태 점검 패널.
 *
 * **보기와 쓰기가 다른 버튼이다.** 여기서 `finished`는 사람이 확인한 사실이 아니라
 * 오늘 날짜로부터 파생된 판정이므로(`close_past_events.py`가 기본 드라이런인 이유),
 * 화면을 열면 미리보기만 돌고 쓰기는 눌러야 일어난다.
 *
 * 이 화면은 숫자를 만들지 않는다 — 줄마다 서버가 준 판정을 그대로 비춘다.
 */

const VERDICT_LABEL: Record<string, string> = {
  needs_close: "닫아야 함",
  already_finished: "이미 finished",
  upcoming: "아직 안 지남",
  unknown_date: "날짜 미상 — 보류",
};

const VERDICT_CLASS: Record<string, string> = {
  needs_close: "text-stone-100 font-semibold",
  already_finished: "text-stone-500",
  upcoming: "text-stone-400",
  unknown_date: "text-stone-500",
};

type PanelState = {
  loading: boolean;
  drift: EventStatusDrift | null;
  error: string | null;
  closing: boolean;
  /** 방금 쓴 건수. `null`이면 이번 세션에서 아직 쓰지 않았다. */
  written: number | null;
};

function formatRange(item: { startDate: string | null; endDate: string | null }): string {
  if (!item.startDate) return "날짜 미상";
  return item.endDate ? `${item.startDate} ~ ${item.endDate}` : item.startDate;
}

export function EventStatusPanel() {
  const [state, setState] = useState<PanelState>({
    loading: true,
    drift: null,
    error: null,
    closing: false,
    written: null,
  });

  const patch = (next: Partial<PanelState>) => setState((prev) => ({ ...prev, ...next }));

  const load = useCallback(async () => {
    patch({ loading: true, error: null });
    try {
      patch({ drift: await fetchEventStatusDrift(), loading: false });
    } catch (e) {
      patch({
        loading: false,
        drift: null,
        error: e instanceof Error ? e.message : "불러오지 못했습니다.",
      });
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const pending = state.drift?.pending ?? 0;

  const close = async () => {
    if (state.closing || pending === 0) return;
    if (!window.confirm(`${pending}건의 status를 finished로 넘깁니다. 되돌릴 수 없습니다.`)) {
      return;
    }
    patch({ closing: true, error: null });
    try {
      const result = await closePastEvents();
      patch({ closing: false, written: result.written ?? 0 });
      // 쓰기 응답은 **쓰기 전 판정**이다. 지금 상태를 보려면 다시 읽는다.
      await load();
    } catch (e) {
      patch({
        closing: false,
        error: e instanceof Error ? e.message : "반영하지 못했습니다.",
      });
    }
  };

  return (
    <div className="rounded-xl border border-stone-300/50 dark:border-stone-700/50 bg-stone-50/70 dark:bg-stone-950/70 p-6">
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <CalendarCheck className="h-4 w-4 text-stone-400" />
          <h2 className="text-sm font-semibold text-stone-100">대회 상태 점검</h2>
        </div>
        <button
          onClick={() => void load()}
          disabled={state.loading || state.closing}
          className="text-[11px] text-stone-500 transition-colors hover:text-stone-300 disabled:opacity-50"
        >
          새로고침
        </button>
      </div>

      <p className="mb-4 text-[11px] text-stone-500">
        날짜가 지났는데 <code className="text-stone-400">status</code>가 아직 닫히지 않은 대회를
        찾습니다. 경기와 <code className="text-stone-400">finished_at</code>은 건드리지 않고
        <code className="text-stone-400"> status</code> 한 칸만 바꿉니다.
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
      ) : state.drift === null ? (
        <p className="py-10 text-center text-[11px] text-stone-600">
          점검 결과가 없습니다 — 새로고침을 눌러 보세요.
        </p>
      ) : (
        <>
          <ul className="divide-y divide-stone-800">
            {state.drift.items.map((item) => (
              <li key={item.slug} className="flex items-center gap-3 py-2">
                <span className="min-w-0 flex-1 truncate text-[12px] text-stone-200">
                  {item.slug}
                </span>
                <span className="shrink-0 text-[10px] tabular-nums text-stone-500">
                  {formatRange(item)}
                </span>
                <span className="w-14 shrink-0 text-right text-[10px] text-stone-500">
                  {item.status}
                </span>
                <span
                  className={cn(
                    "w-32 shrink-0 text-right text-[10px]",
                    VERDICT_CLASS[item.verdict] ?? "text-stone-400",
                  )}
                >
                  {VERDICT_LABEL[item.verdict] ?? item.verdict}
                </span>
              </li>
            ))}
          </ul>

          <div className="mt-5 flex flex-col gap-3 border-t border-stone-800 pt-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="text-[11px] text-stone-400">
              <p>
                기준일(UTC) <span className="tabular-nums text-stone-200">{state.drift.today}</span>{" "}
                · 대회{" "}
                <span className="tabular-nums text-stone-200">{state.drift.items.length}</span>건 중
                닫아야 할 것{" "}
                <span className="font-semibold tabular-nums text-stone-100">{pending}</span>건
              </p>
              {state.written !== null && (
                <p className="mt-0.5 text-stone-500">
                  방금 반영: <span className="tabular-nums">{state.written}</span>건
                </p>
              )}
            </div>

            <button
              type="button"
              onClick={() => void close()}
              disabled={state.closing || pending === 0}
              className="flex shrink-0 items-center gap-1.5 rounded-lg border border-stone-400 bg-stone-600 px-4 py-2 text-xs font-semibold text-stone-50 transition-colors hover:bg-stone-500 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {state.closing && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
              {state.closing ? "반영 중…" : pending === 0 ? "닫을 대회 없음" : `${pending}건 닫기`}
            </button>
          </div>
        </>
      )}
    </div>
  );
}
