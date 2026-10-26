"use client";

import type { CareerEvent } from "@/lib/career-api";

import { EVENT_KIND_LABEL, labelOf } from "./career-labels";

/**
 * 미해결 사건 하나. **대시보드와 주간 진행 탭이 같은 컴포넌트를 쓴다** — 사용자
 * 요구 §4.1 이 "다른 화면으로 이동하지 않고도 처리할 수 있도록" 이라고 적었고,
 * 두 자리에 각각 쓰면 선택지 판정이 갈라진다.
 */
export function CareerEventCard({
  event,
  busy,
  onChoose,
}: {
  event: CareerEvent;
  /** 진행 중인 요청 이름. 어느 버튼이 눌렸는지까지 보여 준다. */
  busy: string | null;
  onChoose: (choice: string) => void;
}) {
  return (
    <div className="rounded-xl border border-brand-700/50 bg-card p-4">
      <p className="text-xs font-bold text-muted-foreground">
        S{event.season} W{event.week} · {labelOf(EVENT_KIND_LABEL, event.kind)}
        {event.other ? ` · ${event.other}` : ""}
      </p>
      <p className="mt-1 text-sm font-bold text-foreground">{event.headline}</p>
      {event.detail ? (
        <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{event.detail}</p>
      ) : null}
      <div className="mt-3 space-y-2">
        {event.choices.map((choice) => {
          const key = `event:${event.id}:${choice.code}`;
          return (
            <button
              key={choice.code}
              type="button"
              onClick={() => onChoose(choice.code)}
              disabled={!choice.enabled || busy != null}
              className="w-full rounded-lg border border-border bg-card-2 px-3 py-2 text-left transition-colors hover:bg-card disabled:opacity-40"
            >
              <span className="block text-sm font-semibold text-foreground">
                {busy === key ? "처리 중…" : choice.label}
              </span>
              {/* 못 고르는 선택지도 남겨 둔다 — 이유를 읽을 수 있어야 한다. */}
              {choice.note ? (
                <span className="block text-[11px] text-muted-foreground">{choice.note}</span>
              ) : null}
            </button>
          );
        })}
      </div>
    </div>
  );
}
