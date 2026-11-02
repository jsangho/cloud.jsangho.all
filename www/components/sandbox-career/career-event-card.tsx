"use client";

import type { CareerEvent } from "@/lib/career-api";

import { EVENT_KIND_LABEL, labelOf } from "./career-labels";
import { Emblem } from "./career-ui";

/**
 * 미해결 사건 하나. **대시보드와 주간 진행 탭이 같은 컴포넌트를 쓴다** — 사용자
 * 요구 §4.1 이 "다른 화면으로 이동하지 않고도 처리할 수 있도록" 이라고 적었고,
 * 두 자리에 각각 쓰면 선택지 판정이 갈라진다.
 *
 * 스토리 컷처럼 그린다 — 레드 조명 패널과 당사자 엠블럼. 레드는 "결정이 필요하다"
 * 는 뜻으로만 쓴다.
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
    <article className="arena-panel arena-panel-alert overflow-hidden p-4">
      <div className="flex items-start gap-3">
        <Emblem name={event.other ?? event.subject} tone="live" size={48} />
        <div className="min-w-0 flex-1">
          <p className="flex flex-wrap items-center gap-2 text-[11px] font-semibold uppercase tracking-wider text-red-200/80">
            <span className="rounded-sm bg-live px-1.5 py-0.5 text-[10px] font-bold text-stone-50">
              STORY
            </span>
            {labelOf(EVENT_KIND_LABEL, event.kind)} · 시즌 {event.season} · {event.week}주차
            {event.other ? ` · ${event.other}` : ""}
          </p>
          <h4 className="mt-1.5 font-sport text-xl leading-tight text-stone-50">
            {event.headline}
          </h4>
          {event.detail ? (
            <p className="mt-1.5 text-sm leading-relaxed text-stone-300">{event.detail}</p>
          ) : null}
        </div>
      </div>
      <div className="mt-4 grid gap-2 sm:grid-cols-2">
        {event.choices.map((choice) => {
          const key = `event:${event.id}:${choice.code}`;
          return (
            <button
              key={choice.code}
              type="button"
              onClick={() => onChoose(choice.code)}
              disabled={!choice.enabled || busy != null}
              className="group rounded-lg border border-white/10 bg-black/35 px-3 py-2.5 text-left transition-colors hover:border-live/60 hover:bg-live/10 disabled:cursor-not-allowed disabled:opacity-40"
            >
              <span className="block text-sm font-semibold text-stone-50">
                {busy === key ? "처리 중…" : choice.label}
              </span>
              {/* 못 고르는 선택지도 남겨 둔다 — 이유를 읽을 수 있어야 한다. */}
              {choice.note ? (
                <span className="mt-0.5 block text-[11px] leading-snug text-stone-400">
                  {choice.note}
                </span>
              ) : null}
            </button>
          );
        })}
      </div>
    </article>
  );
}
