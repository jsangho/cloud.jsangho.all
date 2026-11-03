"use client";

import type { ReactNode } from "react";

import {
  CAREER_TRAINABLE,
  type CareerGoal,
  type CareerLogEntry,
  type CareerRelationship,
  type CareerView,
  type CareerWeekReport,
  type CareerWrestler,
} from "@/lib/career-api";
import { cn } from "@/lib/utils";

import { isMilestone, logKey, rivalNames, toMatchRows, type MatchRow } from "./career-derive";
import { CareerEventCard } from "./career-event-card";
import {
  ABILITY_KEY,
  ALIGNMENT_LABEL,
  CARD_KIND_LABEL,
  CAUSE_LABEL,
  LOG_KIND_LABEL,
  PHASE_LABEL,
  RELATION_LABEL,
  SEVERITY_LABEL,
  STAT_LABEL,
  STATUS_LABEL,
  deltaText,
  labelOf,
} from "./career-labels";
import type { CareerTab } from "./career-tabs";
import { Emblem, Empty, Meter, Panel, PanelLink, RingGauge, WeekTag } from "./career-ui";
import { PhaseAction } from "./career-phase-action";

/**
 * 대시보드 — **접속하자마자 다음에 할 일이 보여야 하는 화면.**
 *
 * 시각 위계는 셋이다(다크 아레나 시안 · 2026-11-02):
 *
 *   1. 히어로 — 선수와 「주차 진행」. 커리어에서 가장 자주 누르는 버튼이 여기 있다.
 *   2. 능력치 · 결정할 일 · 시즌 목표 — 이번 주에 판단할 재료.
 *   3. 최근 경기 · 라이벌 · 커리어 기록 — 흐름을 읽는 칸.
 *
 * 미해결 사건이 이 탭에 그대로 들어온다. 「결정할 일」을 다른 탭으로 보내면 사건이
 * 열린 줄도 모르고 주차를 넘긴다.
 *
 * **여기서 숫자를 만들지 않는다.** 전적·인기도·능력치·위험 단계·목표 진행은 전부
 * 서버 값이다. 화면이 계산하는 것은 셋뿐이다 — 「남은 주차」(서버의 `seasonWeeks`
 * 에서 뺀 값), 「승률」(서버 전적의 나눗셈, 분모를 함께 적는다), 「상대 전적」
 * (불러온 기록에서 센 값, 몇 경기 기준인지 함께 적는다).
 */
export function CareerDashboard({
  view,
  busy,
  log,
  onResolve,
  onGoTo,
  reportMatchId,
  onOpenMatch,
  onAdvance,
  onSettle,
  onNextSeason,
}: {
  view: CareerView;
  busy: string | null;
  /** 전체 기록. 아직 안 읽었으면 `null` — 그러면 `recentLog` 로 그린다. */
  log: readonly CareerLogEntry[] | null;
  onResolve: (eventId: string, choice: string) => void;
  onGoTo: (tab: CareerTab) => void;
  /** 지난 주 경기의 기록 id. 기록이 없거나 아직 모르면 `null` — 링크를 달지 않는다. */
  reportMatchId: string | null;
  onOpenMatch: (matchId: string) => void;
  onAdvance: () => void;
  onSettle: () => void;
  onNextSeason: () => void;
}) {
  const me = view.player;
  const source = log ?? view.recentLog;
  const rivals = rivalNames(view.relationships, me.name);
  const matches = toMatchRows(source, rivals);
  const milestones = source.filter(isMilestone).slice(0, 5);

  return (
    <div className="space-y-5">
      <Hero
        view={view}
        busy={busy}
        onAdvance={onAdvance}
        onSettle={onSettle}
        onNextSeason={onNextSeason}
        onGoTo={onGoTo}
      />

      <div className="grid gap-5 lg:grid-cols-12">
        <AbilityPanel me={me} className="lg:col-span-5" />
        <div className="space-y-3 lg:col-span-4">
          {view.pending.length > 0 ? (
            <>
              <CareerEventCard
                event={view.pending[0]}
                busy={busy}
                onChoose={(choice) => onResolve(view.pending[0].id, choice)}
              />
              {view.pending.length > 1 ? (
                <div className="flex items-center justify-between rounded-lg border border-live/30 bg-live/10 px-3 py-2 text-xs text-red-100">
                  <span>결정할 일이 {view.pending.length - 1}건 더 있습니다</span>
                  <PanelLink onClick={() => onGoTo("week")}>주간 진행</PanelLink>
                </div>
              ) : null}
              <p className="text-[11px] text-stone-400">처리하지 않아도 주차는 진행됩니다.</p>
            </>
          ) : (
            <Panel title="다음 이벤트">
              <Empty>
                지금 결정할 일이 없습니다. 연패·부상·타이틀 기회 같은 순간에 이 자리로 사건이
                들어옵니다.
              </Empty>
              {view.lastReport ? <LastWeekLine report={view.lastReport} /> : null}
            </Panel>
          )}
        </div>
        <GoalsPanel goals={view.goals ?? []} season={view.season} className="lg:col-span-3" />
      </div>

      <div className="grid gap-5 lg:grid-cols-3">
        <RecentMatchesPanel rows={matches.slice(0, 5)} onGoTo={onGoTo} />
        <RivalPanel me={me} relationships={view.relationships} matches={matches} onGoTo={onGoTo} />
        <RecordPanel view={view} onGoTo={onGoTo} />
      </div>

      <div className="grid gap-5 lg:grid-cols-3">
        <Panel
          title="보유 타이틀"
          action={<PanelLink onClick={() => onGoTo("titles")}>타이틀</PanelLink>}
        >
          {me.held.length > 0 ? (
            <ul className="space-y-1.5">
              {me.held.map((belt) => (
                <li
                  key={belt}
                  className="flex items-center gap-2 rounded-lg border border-brand-400/30 bg-brand-400/10 px-3 py-2 text-sm font-semibold text-brand-200"
                >
                  <BeltIcon />
                  {belt}
                </li>
              ))}
            </ul>
          ) : (
            <Empty>보유한 벨트가 없습니다.</Empty>
          )}
          <p className="mt-3 text-xs text-stone-400">
            역대 획득{" "}
            <span className="font-semibold tabular-nums text-stone-100">{me.reigns.length}회</span>
            {me.reigns.length > 0 ? ` — ${me.reigns.join(" · ")}` : ""}
          </p>
        </Panel>

        <Panel
          title="주요 커리어 이벤트"
          action={<PanelLink onClick={() => onGoTo("log")}>커리어 기록</PanelLink>}
        >
          {milestones.length === 0 ? (
            <Empty>아직 기록된 분기점이 없습니다.</Empty>
          ) : (
            <ul className="space-y-2 text-xs">
              {milestones.map((entry, index) => (
                <li key={logKey(entry, index)} className="flex gap-2">
                  <WeekTag season={entry.season} week={entry.week} />
                  <span className="min-w-0 text-stone-200">
                    {entry.summary || labelOf(LOG_KIND_LABEL, entry.kind)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Panel>

        <RiskPanel me={me} />
      </div>

      {me.injuries.length > 0 ? (
        <Panel title="부상 이력">
          <ul className="grid gap-1 text-xs text-stone-300 sm:grid-cols-2">
            {me.injuries.map((injury, index) => (
              <li key={`${injury.season}:${injury.week}:${index}`} className="flex gap-2">
                <WeekTag season={injury.season} week={injury.week} />
                <span>
                  {injury.kind} · {labelOf(SEVERITY_LABEL, injury.severity)} · {injury.weeksOut}주
                  {injury.recurrence ? " · 재발" : ""}
                  {injury.permanent ? " · 영구 불가" : ""}
                  {injury.recovered ? "" : " · 회복 중"}
                </span>
              </li>
            ))}
          </ul>
        </Panel>
      ) : null}

      <RetirementPanel me={me} />
      {view.lastReport ? (
        <ReportPanel report={view.lastReport} matchId={reportMatchId} onOpenMatch={onOpenMatch} />
      ) : null}
    </div>
  );
}

/* ── 히어로 ─────────────────────────────────────────────────────────── */

function Hero({
  view,
  busy,
  onAdvance,
  onSettle,
  onNextSeason,
  onGoTo,
}: {
  view: CareerView;
  busy: string | null;
  onAdvance: () => void;
  onSettle: () => void;
  onNextSeason: () => void;
  onGoTo: (tab: CareerTab) => void;
}) {
  const me = view.player;
  const weeksLeft = Math.max(0, view.seasonWeeks - view.week);
  const played = me.wins + me.losses;
  const chips = [
    me.style,
    `${me.age}세`,
    me.brand,
    labelOf(ALIGNMENT_LABEL, me.alignment),
    labelOf(STATUS_LABEL, me.status),
  ];

  return (
    <section className="arena-panel arena-hero relative overflow-hidden">
      <WrestlerSilhouette />
      <div className="relative grid gap-6 p-5 sm:p-7 lg:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)] lg:gap-10">
        <div className="min-w-0">
          <p className="arena-eyebrow">My Career · {labelOf(PHASE_LABEL, view.phase)}</p>
          <h2 className="mt-2 break-words font-sport text-4xl font-semibold uppercase leading-[1.05] tracking-wide text-stone-50 sm:text-5xl lg:text-6xl">
            {me.name}
          </h2>
          <ul className="mt-3 flex flex-wrap gap-1.5">
            {chips.map((chip, index) => (
              <li
                key={`${chip}:${index}`}
                className="rounded-md border border-white/12 bg-black/30 px-2 py-0.5 text-xs font-semibold text-stone-200"
              >
                {chip}
              </li>
            ))}
          </ul>

          <div className="mt-6">
            <div className="flex items-baseline justify-between gap-3 text-xs">
              <span className="font-semibold uppercase tracking-wider text-stone-400">
                시즌 {view.season} 진행
              </span>
              <span className="tabular-nums text-stone-300">
                <span className="text-base font-bold text-stone-50">{view.week}</span> /{" "}
                {view.seasonWeeks}주
              </span>
            </div>
            <div className="mt-2">
              <Meter value={view.week} max={view.seasonWeeks} label="시즌 진행" />
            </div>
          </div>

          <dl className="mt-6 grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-4">
            <HeroStat label="인기도" value={`${me.popularity}`} unit="/ 100">
              <Meter value={me.popularity} max={100} label="인기도" />
            </HeroStat>
            <HeroStat
              label="전적"
              value={`${me.wins}승 ${me.losses}패`}
              sub={
                played > 0
                  ? `승률 ${Math.round((me.wins / played) * 100)}% (${me.wins}/${played})`
                  : "아직 경기 없음"
              }
            />
            <HeroStat
              label="시즌 종료까지"
              value={
                view.phase === "in_season" ? `${weeksLeft}주` : labelOf(PHASE_LABEL, view.phase)
              }
            />
            <HeroStat
              label="행동 포인트"
              value={`${view.actionPoints}`}
              unit={`/ ${view.maxActionPoints}`}
              sub="주간 진행 탭에서 사용"
            />
          </dl>
        </div>

        <div className="flex min-w-0 flex-col justify-center gap-4">
          <NextCardStrip view={view} onGoTo={onGoTo} />
          <PhaseAction
            view={view}
            busy={busy}
            size="lg"
            onAdvance={onAdvance}
            onSettle={onSettle}
            onNextSeason={onNextSeason}
          />
        </div>
      </div>
    </section>
  );
}

function HeroStat({
  label,
  value,
  unit,
  sub,
  children,
}: {
  label: string;
  value: string;
  unit?: string;
  sub?: string;
  children?: ReactNode;
}) {
  return (
    <div className="min-w-0">
      <dt className="text-[11px] font-semibold uppercase tracking-wider text-stone-400">{label}</dt>
      <dd className="mt-1">
        <span className="text-2xl font-bold tabular-nums text-stone-50">{value}</span>
        {unit ? <span className="ml-1 text-xs text-stone-400">{unit}</span> : null}
        {children ? <div className="mt-2">{children}</div> : null}
        {sub ? <div className="mt-1 text-[11px] text-stone-400">{sub}</div> : null}
      </dd>
    </div>
  );
}

function NextCardStrip({ view, onGoTo }: { view: CareerView; onGoTo: (tab: CareerTab) => void }) {
  const card = view.nextCard;
  if (view.player.retirement != null) {
    return <Empty>은퇴해 더 배정되지 않습니다. 기록은 그대로 남습니다.</Empty>;
  }
  const foe = card.opponents.length > 0 ? card.opponents.join(" · ") : (card.opponent ?? "미정");
  const kind =
    card.kind === "tag" && card.partner
      ? `태그 경기 — ${card.partner} 조`
      : card.title
        ? `타이틀전 — ${card.title}`
        : labelOf(CARD_KIND_LABEL, card.kind);

  return (
    <div className="rounded-xl border border-white/10 bg-black/40 p-4">
      <div className="flex items-center justify-between gap-2">
        <span className="arena-eyebrow">다음 경기</span>
        <PanelLink onClick={() => onGoTo("matches")}>대진</PanelLink>
      </div>
      {card.kind === "rest" ? (
        <p className="mt-2 text-sm text-stone-300">{kind}</p>
      ) : (
        <div className="mt-3 flex items-center gap-3">
          <Emblem name={view.player.name} size={40} />
          <span className="font-sport text-lg text-stone-500">VS</span>
          <Emblem name={foe} size={40} tone="live" />
          <div className="min-w-0">
            <p className="truncate font-sport text-lg text-stone-50">{foe}</p>
            <p className="truncate text-xs text-stone-400">{kind}</p>
          </div>
        </div>
      )}
      {card.note ? <p className="mt-2 text-[11px] text-stone-500">{card.note}</p> : null}
    </div>
  );
}

/**
 * 링에 들어서는 레슬러 실루엣. **사진이 아니다** — 저작권 있는 이미지를 쓰지 않고,
 * 세계의 선수는 가상이다. 글자 뒤로 물러나도록 아주 어둡게 깐다.
 */
function WrestlerSilhouette() {
  return (
    <svg
      aria-hidden
      viewBox="0 0 400 300"
      preserveAspectRatio="xMaxYMax meet"
      className="pointer-events-none absolute inset-y-0 right-0 h-full w-auto max-w-[70%] opacity-60"
    >
      <defs>
        <radialGradient id="hero-spot" cx="50%" cy="0%" r="90%">
          <stop offset="0%" stopColor="rgba(255,236,196,0.22)" />
          <stop offset="100%" stopColor="rgba(255,236,196,0)" />
        </radialGradient>
        <linearGradient id="hero-figure" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#1c1917" />
          <stop offset="100%" stopColor="#08090b" />
        </linearGradient>
        <linearGradient id="hero-rim" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor="rgba(230,57,70,0.6)" />
          <stop offset="100%" stopColor="rgba(252,187,0,0.5)" />
        </linearGradient>
      </defs>
      {/* 위에서 떨어지는 조명 원뿔 */}
      <path d="M170 0 L230 0 L330 300 L70 300 Z" fill="url(#hero-spot)" />
      {/* 링 로프 세 줄 */}
      {[238, 258, 278].map((y) => (
        <line
          key={y}
          x1="20"
          y1={y}
          x2="400"
          y2={y - 14}
          stroke="rgba(250,250,250,0.08)"
          strokeWidth="2"
        />
      ))}
      {/* 두 팔을 든 레슬러 */}
      <g fill="url(#hero-figure)" stroke="url(#hero-rim)" strokeWidth="1.5" strokeLinejoin="round">
        <circle cx="200" cy="74" r="19" />
        <path d="M168 104 Q200 92 232 104 L242 186 Q200 198 158 186 Z" />
        <path d="M170 108 L132 44 L144 36 L186 98 Z" />
        <path d="M230 108 L268 44 L256 36 L214 98 Z" />
        <path d="M162 186 L152 292 L176 292 L198 196 Z" />
        <path d="M238 186 L248 292 L224 292 L202 196 Z" />
      </g>
    </svg>
  );
}

/* ── 능력치 ─────────────────────────────────────────────────────────── */

function AbilityPanel({ me, className }: { me: CareerWrestler; className?: string }) {
  const injured = me.outWeeks > 0;
  return (
    <Panel
      title="선수 능력치"
      className={className}
      hint={me.trend ? undefined : "변화 추이는 시즌이 둘 쌓이면 나옵니다."}
    >
      <div className="grid grid-cols-4 gap-2">
        {CAREER_TRAINABLE.map((key) => (
          <RingGauge
            key={key}
            value={me.ability[ABILITY_KEY[key]]}
            label={STAT_LABEL[key]}
            size={72}
          />
        ))}
      </div>
      <dl className="mt-4 space-y-2.5">
        {CAREER_TRAINABLE.map((key) => {
          const value = me.ability[ABILITY_KEY[key]];
          const delta = me.trend?.[ABILITY_KEY[key]];
          return (
            <div
              key={key}
              className="grid grid-cols-[4.5rem_minmax(0,1fr)_3.5rem] items-center gap-3"
            >
              <dt className="text-xs text-stone-400">{STAT_LABEL[key]}</dt>
              <Meter value={value} max={100} label={STAT_LABEL[key]} />
              <dd className="text-right text-sm font-bold tabular-nums text-stone-50">
                {value}
                {delta != null && delta !== 0 ? (
                  <span
                    className={cn(
                      "ml-1 text-[10px] font-semibold",
                      delta > 0 ? "text-chart-win" : "text-live",
                    )}
                  >
                    {delta > 0 ? `▲${delta}` : `▼${-delta}`}
                  </span>
                ) : null}
              </dd>
            </div>
          );
        })}
      </dl>
      {me.trend ? (
        <p className="mt-2 text-[11px] text-stone-500">최근 시즌 변화 {deltaText(me.trend)}</p>
      ) : null}

      <div className="mt-4 grid grid-cols-2 gap-3 border-t border-white/10 pt-4">
        <div>
          <div className="flex items-baseline justify-between text-xs">
            <span className="font-semibold uppercase tracking-wider text-stone-400">컨디션</span>
            <span className="text-sm font-bold tabular-nums text-stone-50">{me.condition}</span>
          </div>
          <div className="mt-2">
            <Meter
              value={me.condition}
              max={100}
              tone={me.condition < 40 ? "live" : "win"}
              label="컨디션"
            />
          </div>
        </div>
        <div>
          <span className="text-xs font-semibold uppercase tracking-wider text-stone-400">
            부상 상태
          </span>
          <p
            className={cn(
              "mt-1.5 inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs font-bold",
              injured
                ? "border border-live/50 bg-live/15 text-red-100"
                : "border border-chart-win/40 bg-chart-win/10 text-emerald-200",
            )}
          >
            <span
              aria-hidden
              className={cn("size-1.5 rounded-full", injured ? "bg-live" : "bg-chart-win")}
            />
            {injured ? `결장 — ${me.outWeeks}주 남음` : "출전 가능"}
          </p>
        </div>
      </div>
    </Panel>
  );
}

/* ── 시즌 목표 ──────────────────────────────────────────────────────── */

function GoalsPanel({
  goals,
  season,
  className,
}: {
  goals: readonly CareerGoal[];
  season: number;
  className?: string;
}) {
  const done = goals.filter((g) => g.done).length;
  return (
    <Panel
      title={`시즌 ${season} 목표`}
      className={className}
      action={
        goals.length > 0 ? (
          <span className="text-xs font-bold tabular-nums text-stone-300">
            {done} / {goals.length}
          </span>
        ) : null
      }
      hint="달성하면 인기도 보상이 다음 주차 진행에서 들어갑니다."
    >
      {goals.length === 0 ? (
        <Empty>서버가 아직 목표를 보내지 않습니다 — 백엔드 배포 뒤에 나타납니다.</Empty>
      ) : (
        <ul className="space-y-4">
          {goals.map((goal) => (
            <li key={goal.code}>
              <div className="flex items-start gap-2.5">
                <GoalCheck done={goal.done} />
                <div className="min-w-0 flex-1">
                  <p
                    className={cn(
                      "text-sm font-semibold",
                      goal.done ? "text-brand-200" : "text-stone-100",
                    )}
                  >
                    {goal.label}
                  </p>
                  <div className="mt-1.5 flex items-center gap-2">
                    <div className="flex-1">
                      <Meter value={goal.current} max={goal.target} label={goal.label} />
                    </div>
                    <span className="shrink-0 text-xs tabular-nums text-stone-300">
                      {Math.min(goal.current, goal.target)} / {goal.target}
                    </span>
                  </div>
                  <p className="mt-1 text-[11px] text-stone-500">
                    {goal.rewarded
                      ? `보상 받음 · 인기도 +${goal.rewardPopularity}`
                      : goal.done
                        ? `달성 — 다음 주차에 인기도 +${goal.rewardPopularity}`
                        : `보상 인기도 +${goal.rewardPopularity}`}
                  </p>
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

function GoalCheck({ done }: { done: boolean }) {
  return (
    <span
      aria-label={done ? "달성" : "미달성"}
      role="img"
      className={cn(
        "mt-0.5 inline-flex size-5 shrink-0 items-center justify-center rounded-full",
        done ? "bg-brand-400 text-primary-foreground" : "border border-white/20 text-transparent",
      )}
    >
      <svg viewBox="0 0 16 16" className="size-3" aria-hidden>
        <path
          d="M3.5 8.5l3 3 6-7"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </span>
  );
}

/* ── 하단 셋 ────────────────────────────────────────────────────────── */

function RecentMatchesPanel({
  rows,
  onGoTo,
}: {
  rows: readonly MatchRow[];
  onGoTo: (tab: CareerTab) => void;
}) {
  return (
    <Panel
      title="최근 경기 결과"
      action={<PanelLink onClick={() => onGoTo("matches")}>전체 경기</PanelLink>}
    >
      {rows.length === 0 ? (
        <Empty>아직 치른 경기가 없습니다.</Empty>
      ) : (
        <ul className="divide-y divide-white/[0.06]">
          {rows.map((row) => (
            <li key={row.key} className="flex items-center gap-3 py-2 first:pt-0 last:pb-0">
              <ResultBadge won={row.won} />
              <div className="min-w-0 flex-1">
                <p className="flex items-center gap-1.5 truncate text-sm font-semibold text-stone-100">
                  {row.opponent ?? "상대 미상"}
                  {row.title ? (
                    <span className="rounded-sm border border-brand-400/40 px-1 text-[10px] font-bold text-brand-200">
                      TITLE
                    </span>
                  ) : null}
                  {row.rival ? (
                    <span className="rounded-sm border border-live/50 px-1 text-[10px] font-bold text-red-200">
                      RIVAL
                    </span>
                  ) : null}
                </p>
                {/* 결과 방식과 경기 평가가 서버 문장에 들어 있다 — 파싱하지 않는다. */}
                <p className="truncate text-[11px] text-stone-400">{row.summary}</p>
              </div>
              <WeekTag season={row.season} week={row.week} />
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

function ResultBadge({ won }: { won: boolean | null }) {
  if (won == null) {
    return (
      <span className="inline-flex size-8 shrink-0 items-center justify-center rounded-md bg-white/5 text-xs text-stone-400">
        —
      </span>
    );
  }
  return (
    <span
      className={cn(
        "inline-flex size-8 shrink-0 items-center justify-center rounded-md font-sport text-base font-semibold",
        won
          ? "bg-chart-win/20 text-emerald-200 ring-1 ring-chart-win/50"
          : "bg-live/15 text-red-200 ring-1 ring-live/50",
      )}
    >
      {/* 색만으로 말하지 않는다 — 글자가 함께 선다(DESIGN.md §2 적중/실패 짝). */}
      {won ? "승" : "패"}
    </span>
  );
}

/**
 * 라이벌 셋. **끓는 관계(`feud`)가 먼저다** — `kind === "rival"` 은 경기마다 붙어서
 * 그대로 세면 전원이 라이벌이다(`career-derive.rivalNames`).
 *
 * 상대 전적은 **불러온 기록에서 센다** — 서버가 상대별 전적을 따로 주지 않는다.
 * 그래서 몇 경기 기준인지 함께 적는다.
 */
function RivalPanel({
  me,
  relationships,
  matches,
  onGoTo,
}: {
  me: CareerWrestler;
  relationships: readonly CareerRelationship[];
  matches: readonly MatchRow[];
  onGoTo: (tab: CareerTab) => void;
}) {
  const mine = relationships
    .filter((r) => r.a === me.name || r.b === me.name)
    // 동맹·태그팀·사제는 라이벌이 아니다. 끓는 관계는 kind 와 무관하게 넣는다.
    .filter((r) => r.kind === "rival" || r.feud)
    .sort((a, b) => Number(b.feud) - Number(a.feud) || Math.abs(b.heat) - Math.abs(a.heat))
    .slice(0, 3);

  return (
    <Panel
      title="라이벌"
      action={<PanelLink onClick={() => onGoTo("world")}>세계관</PanelLink>}
      hint={
        matches.length > 0 ? `상대 전적은 불러온 기록 ${matches.length}경기 기준입니다.` : undefined
      }
    >
      {mine.length === 0 ? (
        <Empty>아직 맞선 상대가 없습니다. 경기를 치르면 라이벌 관계가 생깁니다.</Empty>
      ) : (
        <ul className="space-y-3">
          {mine.map((relation) => {
            const foe = relation.a === me.name ? relation.b : relation.a;
            const vs = matches.filter((m) => m.opponent === foe);
            const w = vs.filter((m) => m.won === true).length;
            const l = vs.filter((m) => m.won === false).length;
            return (
              <li
                key={`${relation.a}:${relation.b}:${relation.kind}`}
                className="flex items-center gap-3"
              >
                <Emblem name={foe} size={44} tone={relation.feud ? "live" : "gold"} />
                <div className="min-w-0 flex-1">
                  <p className="flex items-center gap-1.5 truncate text-sm font-semibold text-stone-50">
                    {foe}
                    {relation.feud ? (
                      <span className="rounded-sm bg-live px-1 text-[10px] font-bold text-stone-50">
                        격화
                      </span>
                    ) : null}
                  </p>
                  <p className="text-[11px] text-stone-400">
                    {labelOf(RELATION_LABEL, relation.kind)} · 상대 전적{" "}
                    <span className="tabular-nums text-stone-200">
                      {w}승 {l}패
                    </span>
                  </p>
                  <div className="mt-1.5 flex items-center gap-2">
                    <div className="flex-1">
                      <Meter
                        value={Math.abs(relation.heat)}
                        max={100}
                        tone="live"
                        label={`${foe} 관계 강도`}
                      />
                    </div>
                    <span className="text-[10px] tabular-nums text-stone-400">
                      강도 {relation.heat}
                    </span>
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </Panel>
  );
}

function RecordPanel({ view, onGoTo }: { view: CareerView; onGoTo: (tab: CareerTab) => void }) {
  const me = view.player;
  const rows: [string, string][] = [
    ["현재", `시즌 ${view.season} · ${view.week}주차`],
    ["누적 전적", `${me.wins}승 ${me.losses}패`],
    ["인기도", `${me.popularity}`],
    ["타이틀 획득", `${me.reigns.length}회`],
    ["치른 시즌", `${view.seasons.length}시즌`],
    ["데뷔 나이", `${me.debutAge}세`],
  ];
  return (
    <Panel title="커리어 기록">
      <dl className="grid grid-cols-2 gap-x-4 gap-y-3">
        {rows.map(([label, value]) => (
          <div key={label} className="min-w-0">
            <dt className="text-[11px] uppercase tracking-wider text-stone-500">{label}</dt>
            <dd className="mt-0.5 truncate text-sm font-bold tabular-nums text-stone-50">
              {value}
            </dd>
          </div>
        ))}
      </dl>
      <button
        type="button"
        onClick={() => onGoTo("log")}
        className="arena-ghost mt-4 w-full px-4 py-2 text-xs font-semibold uppercase tracking-wider"
      >
        전체 기록 보기
      </button>
    </Panel>
  );
}

function BeltIcon() {
  return (
    <svg viewBox="0 0 20 12" aria-hidden className="h-3 w-5 shrink-0">
      <rect x="0.5" y="3" width="19" height="6" rx="2" fill="none" stroke="currentColor" />
      <ellipse cx="10" cy="6" rx="4" ry="5" fill="currentColor" />
    </svg>
  );
}

/* ── 위험 · 은퇴 · 지난 주 ──────────────────────────────────────────── */

/**
 * 은퇴 위험. **퍼센트를 적지 않는다.**
 *
 * 서버가 점수 칸을 아예 내보내지 않는다 — 검증되지 않은 가중합을 확률처럼 적지
 * 않기 위해서다. 그래서 여기도 단계와 근거만 그린다.
 */
function RiskPanel({ me }: { me: CareerWrestler }) {
  if (!me.risk) {
    return (
      <Panel title="은퇴 위험">
        <Empty>은퇴한 선수는 위험을 재지 않습니다.</Empty>
      </Panel>
    );
  }
  return (
    <Panel
      title="은퇴 위험"
      hint="단계는 설명 가능한 구간입니다 — 퍼센트로 환산되지 않습니다."
      action={
        <span className="rounded-md border border-white/15 px-2 py-0.5 text-xs font-bold text-stone-50">
          {me.risk.band}
        </span>
      }
    >
      {me.risk.reasons.length > 0 ? (
        <ul className="space-y-1 text-xs text-stone-300">
          {me.risk.reasons.map((reason, index) => (
            <li key={`${reason}:${index}`}>· {reason}</li>
          ))}
        </ul>
      ) : (
        <p className="text-xs text-stone-400">지금은 특별한 근거가 없습니다.</p>
      )}
    </Panel>
  );
}

function RetirementPanel({ me }: { me: CareerWrestler }) {
  if (me.retirement) {
    const r = me.retirement;
    return (
      <div className="arena-panel border-brand-400/40 p-5">
        <p className="font-sport text-2xl uppercase text-brand-200">은퇴</p>
        <p className="mt-1 text-sm text-stone-300">
          S{r.season} W{r.week} · {r.age}세 · {r.wins}승 {r.losses}패 · 역대 획득 {r.reigns}회
          {r.titles.length > 0 ? ` (${r.titles.join(" · ")})` : ""}
        </p>
        <p className="mt-1 text-xs text-stone-400">
          사유 {labelOf(CAUSE_LABEL, r.cause)}
          {r.note ? ` · ${r.note}` : ""}
        </p>
      </div>
    );
  }
  if (!me.intent) return null;
  return (
    <p className="arena-panel px-4 py-3 text-xs text-stone-300">
      은퇴 <strong className="text-stone-50">의사</strong>가 있습니다 (
      {me.intent.origin === "self" ? "선수가 요청" : "결정을 요구받았다"} · 사유{" "}
      {labelOf(CAUSE_LABEL, me.intent.cause)}
      {me.intent.finalSeason ? " · 이번 시즌이 마지막" : ""}). 확정은 아닙니다 — 계속 경기합니다.
    </p>
  );
}

function reportParts(report: CareerWeekReport): string[] {
  const parts: string[] = [];
  if (report.won != null) {
    parts.push(report.won ? "승" : "패");
    if (report.opponent) parts.push(`vs ${report.opponent}`);
    if (report.title) {
      parts.push(report.titleChanged ? `${report.title} 이동` : `${report.title} 방어`);
    }
    if (report.finish) parts.push(report.finish);
    if (report.rating > 0) parts.push(`경기 평점 ${report.rating}`);
  }
  if (report.popularityDelta !== 0) {
    parts.push(`인기 ${report.popularityDelta > 0 ? "+" : ""}${report.popularityDelta}`);
  }
  if (report.injured) parts.push(`부상 ${report.injured} ${report.injuredWeeks}주`);
  if (report.promotedTo) parts.push(`${report.promotedTo} 승격`);
  if (report.retired) parts.push("은퇴");
  return parts;
}

function LastWeekLine({ report }: { report: CareerWeekReport }) {
  const parts = reportParts(report);
  return (
    <p className="mt-3 text-xs text-stone-400">
      지난 주 (W{report.week} · {report.kind}) —{" "}
      <span className="text-stone-200">
        {parts.length > 0 ? parts.join(" · ") : "특별한 일 없음"}
      </span>
    </p>
  );
}

/**
 * 지난 주에 일어난 일. **문장은 화면이 만든다** — 서버는 사실만 보낸다.
 *
 * `matchId` 는 서버 기록 목록에서 찾은 id 다(페이지가 찾는다). 없으면 링크를 달지
 * 않는다 — 시즌·주차로 id 를 지어내지 않는다.
 */
export function ReportPanel({
  report,
  matchId,
  onOpenMatch,
}: {
  report: CareerWeekReport;
  matchId: string | null;
  onOpenMatch: (matchId: string) => void;
}) {
  const parts = reportParts(report);
  return (
    <Panel
      title={`지난 주 — S${report.season} W${report.week} · ${report.kind}`}
      action={
        matchId != null ? (
          <PanelLink onClick={() => onOpenMatch(matchId)}>경기 상세</PanelLink>
        ) : undefined
      }
    >
      <p className="text-sm text-stone-100">
        {parts.length > 0 ? parts.join(" · ") : "특별한 일이 없었습니다."}
      </p>
      {report.probability > 0 ? (
        <p className="mt-1 text-[11px] text-stone-400">
          경기 전 승리 확률 {Math.round(report.probability * 100)}% — 확신에 닿지 않게 눌러 둔
          값이라 높은 쪽이 지는 일이 있습니다.
        </p>
      ) : null}
      {report.openedEvents.length > 0 ? (
        <p className="mt-1 text-[11px] text-stone-400">
          새 사건 {report.openedEvents.length}건이 열렸습니다.
        </p>
      ) : null}
    </Panel>
  );
}
