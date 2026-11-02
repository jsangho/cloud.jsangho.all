"use client";

import {
  CAREER_ACTIONS,
  CAREER_TRAINABLE,
  type CareerAction,
  type CareerTrainable,
  type CareerView,
} from "@/lib/career-api";

import { ReportPanel } from "./career-dashboard";
import { CareerEventCard } from "./career-event-card";
import { PHASE_LABEL, STAT_LABEL, labelOf } from "./career-labels";
import { PhaseAction } from "./career-phase-action";
import { Empty, Panel, SectionTitle } from "./career-ui";

/**
 * 주간 진행 — **핵심 플레이 루프.**
 *
 * ## 서버가 전부 정한다
 *
 * 화면이 보내는 것은 행동 코드와 대상뿐이다(`action` · `target`). 능력치 증가폭,
 * 인기도, 남은 포인트, 조건 충족 여부는 서버 `career_actions.perform()` 이 정하고
 * 화면은 돌아온 `CareerView` 를 다시 그린다.
 *
 * ## 재시도는 사용자가 하고, 키는 화면이 지킨다
 *
 * 쓰기 요청에는 `Idempotency-Key`가 실린다. 결론이 나지 않은 실패(타임아웃·네트워크
 * 오류·5xx) 뒤에 사용자가 다시 누르면 **같은 키**가 실려 서버가 두 번 적용하지
 * 않는다 — 키 수명은 이 파일이 아니라 `app/(kayfabe)/sandbox/careers/page.tsx`의
 * `run`이 관리한다.
 *
 * 그래도 **자동으로는 다시 보내지 않는다.** 실패는 사유만 띄우고 사용자가 누르게
 * 한다. 그리고 아래 `disabled={busy != null}`도 그대로 남는다 — 화면의 중복 클릭
 * 방지가 서버 멱등성을 대신하지 않고, 서버 멱등성이 이 가드를 대신하지도 않는다.
 *
 * `휴식`·`협상` 은 대상을 받지 않는다. 서버 `ACTIONS` 다섯 중 대상이 필요한 것은
 * `훈련`(능력치 이름)과 `관계`(선수 이름) 둘이다.
 */
const ACTION_NOTE: Readonly<Record<CareerAction, string>> = {
  훈련: "능력치 ↑ · 컨디션 ↓",
  프로모: "인기도 ↑ (마이크가 폭을 정한다)",
  휴식: "컨디션 회복 · 결장도 줄인다",
  관계: "대상과 가까워진다 (라이벌이면 앙금이 식는다)",
  협상: "조건이 맞으면 도전권",
};

/** 대상이 필요한 행동. 서버가 대상 없이는 거부하는 것은 `관계` 하나다. */
const NEEDS_TARGET: Readonly<Record<CareerAction, "stat" | "wrestler" | null>> = {
  훈련: "stat",
  프로모: null,
  휴식: null,
  관계: "wrestler",
  협상: null,
};

export type WeekTargets = { stat: CareerTrainable; partner: string };

export function CareerWeekPanel({
  view,
  busy,
  targets,
  onTargets,
  onAct,
  onAdvance,
  onSettle,
  onNextSeason,
  onResolve,
}: {
  view: CareerView;
  busy: string | null;
  targets: WeekTargets;
  onTargets: (next: Partial<WeekTargets>) => void;
  onAct: (action: CareerAction, target?: string) => void;
  onAdvance: () => void;
  onSettle: () => void;
  onNextSeason: () => void;
  onResolve: (eventId: string, choice: string) => void;
}) {
  const me = view.player;
  const retired = me.retirement != null;
  const canAct = view.phase === "in_season" && !retired;
  // 은퇴한 선수는 대상이 될 수 없다 — 서버도 거부한다. 목록에서 미리 뺀다.
  const partners = view.roster.filter((w) => !w.isPlayer && w.status !== "retired");

  return (
    <div className="grid items-start gap-6 xl:grid-cols-2">
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 xl:col-span-2">
        <div className="col-span-2 rounded-lg border border-white/10 bg-black/30 px-3 py-2">
          <div className="text-[11px] font-bold text-stone-400">진행</div>
          <div className="mt-0.5 text-sm font-semibold tabular-nums text-stone-100">
            시즌 {view.season} · {view.week} / {view.seasonWeeks}주
          </div>
          <div
            className="mt-1.5 h-1 w-full overflow-hidden rounded-sm bg-white/[0.05]"
            role="presentation"
          >
            <div
              className="h-full bg-brand-500"
              style={{ width: `${Math.min(100, (view.week / view.seasonWeeks) * 100)}%` }}
            />
          </div>
        </div>
        <div className="rounded-lg border border-white/10 bg-black/30 px-3 py-2">
          <div className="text-[11px] font-bold text-stone-400">행동 포인트</div>
          <div className="mt-0.5 text-sm font-semibold tabular-nums text-stone-100">
            {view.actionPoints} / {view.maxActionPoints}
          </div>
        </div>
        <div className="rounded-lg border border-white/10 bg-black/30 px-3 py-2">
          <div className="text-[11px] font-bold text-stone-400">단계</div>
          <div className="mt-0.5 text-sm font-semibold text-stone-100">
            {labelOf(PHASE_LABEL, view.phase)}
          </div>
        </div>
      </div>

      {canAct ? (
        <section>
          <SectionTitle
            aside={
              <span className="text-xs font-semibold tabular-nums text-stone-400">
                남은 포인트 {view.actionPoints} / {view.maxActionPoints}
              </span>
            }
          >
            이번 주 행동
          </SectionTitle>

          <div className="mt-3 grid gap-2 sm:grid-cols-2">
            <label className="block">
              <span className="mb-1 block text-xs font-bold text-stone-400">훈련할 능력치</span>
              <select
                value={targets.stat}
                onChange={(e) => onTargets({ stat: e.target.value as CareerTrainable })}
                className="w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-sm text-stone-100"
              >
                {CAREER_TRAINABLE.map((stat) => (
                  <option key={stat} value={stat}>
                    {STAT_LABEL[stat]}
                  </option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="mb-1 block text-xs font-bold text-stone-400">관계를 만들 상대</span>
              <select
                value={targets.partner}
                onChange={(e) => onTargets({ partner: e.target.value })}
                className="w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-sm text-stone-100"
              >
                <option value="">선택 안 함</option>
                {partners.map((w) => (
                  <option key={w.name} value={w.name}>
                    {w.name} ({w.brand})
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div className="mt-3 grid gap-2 sm:grid-cols-2">
            {CAREER_ACTIONS.map((action) => {
              const need = NEEDS_TARGET[action];
              const missing = need === "wrestler" && !targets.partner;
              const spent = view.actionPoints <= 0;
              return (
                <button
                  key={action}
                  type="button"
                  onClick={() =>
                    onAct(
                      action,
                      need === "stat"
                        ? targets.stat
                        : need === "wrestler"
                          ? targets.partner
                          : undefined,
                    )
                  }
                  disabled={busy != null || spent || missing}
                  className="rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-left transition-colors hover:bg-white/[0.05] disabled:opacity-40"
                >
                  <span className="block text-sm font-bold text-stone-100">
                    {busy === `action:${action}` ? "적용 중…" : action}
                  </span>
                  <span className="block text-[11px] text-stone-400">
                    {/* 왜 못 누르는지 버튼 안에 적는다 — 비활성만 걸어 두면 이유를 알 수 없다. */}
                    {missing
                      ? "상대를 먼저 고르세요"
                      : spent
                        ? "행동 포인트를 다 썼습니다"
                        : ACTION_NOTE[action]}
                  </span>
                </button>
              );
            })}
          </div>
        </section>
      ) : (
        <Empty>
          {retired
            ? "은퇴해 더 행동할 수 없습니다. 기록은 커리어 기록 탭에 남습니다."
            : `지금은 ${labelOf(PHASE_LABEL, view.phase)} 단계라 주간 행동을 할 수 없습니다.`}
        </Empty>
      )}

      <section>
        <PhaseAction
          view={view}
          busy={busy}
          onAdvance={onAdvance}
          onSettle={onSettle}
          onNextSeason={onNextSeason}
        />
      </section>

      {view.pending.length > 0 ? (
        <section className="space-y-3">
          <SectionTitle
            aside={
              <span className="text-xs text-stone-400">주차 진행 전에 처리할 수 있습니다</span>
            }
          >
            결정할 일 {view.pending.length}건
          </SectionTitle>
          {view.pending.map((event) => (
            <CareerEventCard
              key={event.id}
              event={event}
              busy={busy}
              onChoose={(choice) => onResolve(event.id, choice)}
            />
          ))}
        </section>
      ) : null}

      {view.lastReport ? (
        <section>
          <SectionTitle>지난 주 결과</SectionTitle>
          <div className="mt-3">
            <ReportPanel report={view.lastReport} />
          </div>
        </section>
      ) : (
        <Panel title="지난 주 결과">
          <Empty>아직 진행한 주차가 없습니다. 위에서 한 주를 진행해 보세요.</Empty>
        </Panel>
      )}
    </div>
  );
}
