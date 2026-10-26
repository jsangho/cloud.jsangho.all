"use client";

import {
  CAREER_TRAINABLE,
  type CareerLogEntry,
  type CareerView,
  type CareerWeekReport,
  type CareerWrestler,
} from "@/lib/career-api";

import { isMilestone, logKey, rivalNames, toMatchRows } from "./career-derive";
import { CareerEventCard } from "./career-event-card";
import {
  ABILITY_KEY,
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
import { Empty, Panel, SectionTitle, Stat, WeekTag } from "./career-ui";
import type { CareerTab } from "./career-tabs";

/**
 * 대시보드 — **접속하자마자 다음에 할 일이 보여야 하는 화면.**
 *
 * 그래서 이 탭에 미해결 사건이 그대로 들어온다. 「결정할 일」을 다른 탭으로
 * 보내면 사용자는 매번 두 번 움직여야 하고, 사건이 열린 줄도 모르고 주차를
 * 넘긴다.
 *
 * **여기서 숫자를 만들지 않는다.** 전적·인기도·재위 주차·위험 단계는 전부 서버가
 * 보낸 값이고, 화면이 만드는 것은 「남은 주차」 하나뿐이다 — 그것도 서버가 준
 * `seasonWeeks` 에서 뺀 값이다.
 */
export function CareerDashboard({
  view,
  busy,
  log,
  onResolve,
  onGoTo,
}: {
  view: CareerView;
  busy: string | null;
  /** 전체 기록. 아직 안 읽었으면 `null` — 그러면 `recentLog` 로 그린다. */
  log: readonly CareerLogEntry[] | null;
  onResolve: (eventId: string, choice: string) => void;
  onGoTo: (tab: CareerTab) => void;
}) {
  const me = view.player;
  const source = log ?? view.recentLog;
  const rivals = rivalNames(view.relationships, me.name);
  const recentMatches = toMatchRows(source, rivals).slice(0, 4);
  const milestones = source.filter(isMilestone).slice(0, 5);
  const myRelations = view.relationships.filter((r) => r.a === me.name || r.b === me.name);
  const weeksLeft = Math.max(0, view.seasonWeeks - view.week);

  return (
    <div className="space-y-5">
      <section>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          <Stat
            label="시즌 · 주차"
            value={`시즌 ${view.season} · ${view.week} / ${view.seasonWeeks}주`}
          />
          <Stat label="단계" value={labelOf(PHASE_LABEL, view.phase)} />
          <Stat
            label="나이 · 상태"
            value={`${me.age}세 · ${labelOf(STATUS_LABEL, me.status)}`}
            tone={me.status === "active" ? undefined : "warn"}
          />
          <Stat label="인기도" value={`${me.popularity}`} />
          <Stat label="전적" value={`${me.wins}승 ${me.losses}패`} />
          <Stat label="브랜드" value={me.brand} />
          <Stat
            label="컨디션"
            value={me.outWeeks > 0 ? `${me.condition} · 결장 ${me.outWeeks}주` : `${me.condition}`}
            tone={me.outWeeks > 0 ? "warn" : undefined}
          />
          <Stat
            label="시즌 종료까지"
            value={view.phase === "in_season" ? `${weeksLeft}주` : labelOf(PHASE_LABEL, view.phase)}
          />
        </div>
      </section>

      {view.pending.length > 0 ? (
        <section className="space-y-3">
          <SectionTitle
            aside={
              <span className="text-xs text-muted-foreground">
                {view.pending.length}건 — 처리하지 않아도 주차는 진행됩니다
              </span>
            }
          >
            결정할 일
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

      <div className="grid gap-3 sm:grid-cols-2">
        <Panel
          title="능력치"
          hint={me.trend ? undefined : "변화 추이는 시즌이 둘 쌓이면 나옵니다."}
        >
          <dl className="space-y-0.5 text-sm">
            {CAREER_TRAINABLE.map((key) => (
              <div key={key} className="flex justify-between gap-3">
                <dt className="text-muted-foreground">{STAT_LABEL[key]}</dt>
                <dd className="tabular-nums text-foreground">{me.ability[ABILITY_KEY[key]]}</dd>
              </div>
            ))}
          </dl>
          {me.trend ? (
            <p className="mt-2 text-[11px] text-muted-foreground">
              최근 시즌 변화 {deltaText(me.trend)}
            </p>
          ) : null}
        </Panel>

        <Panel
          title="보유 타이틀"
          action={
            <button
              type="button"
              onClick={() => onGoTo("titles")}
              className="text-[11px] text-brand-link underline"
            >
              타이틀 현황
            </button>
          }
        >
          <p className="text-sm text-foreground">
            {me.held.length > 0 ? me.held.join(" · ") : "없음"}
          </p>
          <p className="mt-2 text-xs font-bold text-muted-foreground">역대 획득</p>
          <p className="mt-0.5 text-sm text-foreground">
            {me.reigns.length > 0 ? `${me.reigns.length}회 — ${me.reigns.join(" · ")}` : "없음"}
          </p>
        </Panel>

        <NextCardPanel view={view} onGoTo={onGoTo} />

        <Panel
          title="라이벌 · 동맹"
          hint={
            myRelations.length > 6
              ? `관계 ${myRelations.length}건 중 끓는 쪽 먼저 여섯 — 전부는 세계관 탭에 있습니다.`
              : undefined
          }
          action={
            <button
              type="button"
              onClick={() => onGoTo("world")}
              className="text-[11px] text-brand-link underline"
            >
              세계관
            </button>
          }
        >
          {myRelations.length === 0 ? (
            <Empty>아직 관계가 없습니다. 주간 행동의 「관계」로 만들 수 있습니다.</Empty>
          ) : (
            <ul className="space-y-0.5 text-xs">
              {/* 끓는 관계를 위로 — 라이벌 kind 는 경기마다 붙어서 그냥 세면 전원이 뜬다. */}
              {[...myRelations]
                .sort((a, b) => Number(b.feud) - Number(a.feud) || b.heat - a.heat)
                .slice(0, 6)
                .map((relation) => (
                  <li key={`${relation.a}:${relation.b}:${relation.kind}`}>
                    <span className="text-foreground">
                      {relation.a === me.name ? relation.b : relation.a}
                    </span>{" "}
                    <span className="text-muted-foreground">
                      — {labelOf(RELATION_LABEL, relation.kind)} · 강도{" "}
                      <span className="tabular-nums">{relation.heat}</span>
                    </span>
                    {relation.feud ? (
                      <span className="ml-1 rounded-md border border-live/50 px-1 text-[10px] font-bold text-live">
                        격화
                      </span>
                    ) : null}
                  </li>
                ))}
            </ul>
          )}
        </Panel>

        <Panel
          title="최근 경기"
          action={
            <button
              type="button"
              onClick={() => onGoTo("matches")}
              className="text-[11px] text-brand-link underline"
            >
              전체 기록
            </button>
          }
        >
          {recentMatches.length === 0 ? (
            <Empty>아직 치른 경기가 없습니다.</Empty>
          ) : (
            <ul className="space-y-1 text-xs">
              {recentMatches.map((row) => (
                <li key={row.key} className="flex gap-2">
                  <WeekTag season={row.season} week={row.week} />
                  <span className="min-w-0 text-foreground">
                    {row.won != null ? (
                      <span
                        className={row.won ? "font-bold text-chart-win" : "font-bold text-live"}
                      >
                        {row.won ? "승" : "패"}
                      </span>
                    ) : null}{" "}
                    {row.summary}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Panel>

        <Panel
          title="주요 커리어 이벤트"
          action={
            <button
              type="button"
              onClick={() => onGoTo("log")}
              className="text-[11px] text-brand-link underline"
            >
              커리어 기록
            </button>
          }
        >
          {milestones.length === 0 ? (
            <Empty>아직 기록된 분기점이 없습니다.</Empty>
          ) : (
            <ul className="space-y-1 text-xs">
              {milestones.map((entry, index) => (
                <li key={logKey(entry, index)} className="flex gap-2">
                  <WeekTag season={entry.season} week={entry.week} />
                  <span className="min-w-0 text-foreground">
                    {entry.summary || labelOf(LOG_KIND_LABEL, entry.kind)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>

      <RiskPanel me={me} />

      {me.injuries.length > 0 ? (
        <Panel title="부상 이력">
          <ul className="space-y-0.5 text-xs text-muted-foreground">
            {me.injuries.map((injury, index) => (
              <li key={`${injury.season}:${injury.week}:${index}`}>
                S{injury.season} W{injury.week} · {injury.kind} ·{" "}
                {labelOf(SEVERITY_LABEL, injury.severity)} · {injury.weeksOut}주
                {injury.recurrence ? " · 재발" : ""}
                {injury.permanent ? " · 영구 불가" : ""}
                {injury.recovered ? "" : " · 회복 중"}
              </li>
            ))}
          </ul>
        </Panel>
      ) : null}

      <RetirementPanel me={me} />
      {view.lastReport ? <ReportPanel report={view.lastReport} /> : null}
    </div>
  );
}

function NextCardPanel({ view, onGoTo }: { view: CareerView; onGoTo: (tab: CareerTab) => void }) {
  const card = view.nextCard;
  const retired = view.player.retirement != null;
  const foe = card.opponents.length > 0 ? card.opponents.join(" · ") : (card.opponent ?? "미정");

  return (
    <Panel
      title="다음 경기"
      action={
        <button
          type="button"
          onClick={() => onGoTo("week")}
          className="text-[11px] text-brand-link underline"
        >
          주간 진행
        </button>
      }
    >
      {retired ? (
        <Empty>은퇴해 더 배정되지 않습니다. 기록은 그대로 남습니다.</Empty>
      ) : (
        <>
          <p className="text-sm font-semibold text-foreground">
            {card.kind === "tag" && card.partner
              ? `태그 경기 — ${card.partner} 조`
              : card.title
                ? `타이틀전 — ${card.title}`
                : labelOf(CARD_KIND_LABEL, card.kind)}
          </p>
          {card.kind !== "rest" ? (
            <p className="mt-0.5 text-sm text-muted-foreground">상대 {foe}</p>
          ) : null}
          {card.note ? <p className="mt-1 text-xs text-muted-foreground">{card.note}</p> : null}
        </>
      )}
    </Panel>
  );
}

/**
 * 은퇴 위험. **퍼센트를 적지 않는다.**
 *
 * 서버가 점수 칸을 아예 내보내지 않는다 — 검증되지 않은 가중합을 확률처럼 적지
 * 않기 위해서다. 그래서 여기도 단계와 근거만 그린다.
 */
function RiskPanel({ me }: { me: CareerWrestler }) {
  if (!me.risk) return null;
  return (
    <Panel
      title="은퇴 위험"
      hint="단계는 설명 가능한 구간입니다 — 퍼센트로 환산되지 않습니다."
      action={<span className="text-sm font-bold text-foreground">{me.risk.band}</span>}
    >
      {me.risk.reasons.length > 0 ? (
        <ul className="space-y-0.5 text-xs text-muted-foreground">
          {me.risk.reasons.map((reason, index) => (
            <li key={`${reason}:${index}`}>· {reason}</li>
          ))}
        </ul>
      ) : (
        <p className="text-xs text-muted-foreground">지금은 특별한 근거가 없습니다.</p>
      )}
    </Panel>
  );
}

function RetirementPanel({ me }: { me: CareerWrestler }) {
  if (me.retirement) {
    const r = me.retirement;
    return (
      <div className="rounded-xl border border-brand-700/50 bg-brand-500/10 p-4">
        <p className="font-sport text-xl text-foreground">은퇴</p>
        <p className="mt-1 text-sm text-muted-foreground">
          S{r.season} W{r.week} · {r.age}세 · {r.wins}승 {r.losses}패 · 역대 획득 {r.reigns}회
          {r.titles.length > 0 ? ` (${r.titles.join(" · ")})` : ""}
        </p>
        <p className="mt-1 text-xs text-muted-foreground">
          사유 {labelOf(CAUSE_LABEL, r.cause)}
          {r.note ? ` · ${r.note}` : ""}
        </p>
      </div>
    );
  }
  if (!me.intent) return null;
  return (
    <p className="rounded-lg border border-border bg-card px-3 py-2 text-xs text-muted-foreground">
      은퇴 <strong className="text-foreground">의사</strong>가 있습니다 (
      {me.intent.origin === "self" ? "선수가 요청" : "결정을 요구받았다"} · 사유{" "}
      {labelOf(CAUSE_LABEL, me.intent.cause)}
      {me.intent.finalSeason ? " · 이번 시즌이 마지막" : ""}). 확정은 아닙니다 — 계속 경기합니다.
    </p>
  );
}

/** 지난 주에 일어난 일. **문장은 화면이 만든다** — 서버는 사실만 보낸다. */
export function ReportPanel({ report }: { report: CareerWeekReport }) {
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

  return (
    <Panel title={`지난 주 — S${report.season} W${report.week} · ${report.kind}`}>
      <p className="text-sm text-foreground">
        {parts.length > 0 ? parts.join(" · ") : "특별한 일이 없었습니다."}
      </p>
      {report.probability > 0 ? (
        <p className="mt-1 text-[11px] text-muted-foreground">
          경기 전 승리 확률 {Math.round(report.probability * 100)}% — 확신에 닿지 않게 눌러 둔
          값이라 높은 쪽이 지는 일이 있습니다.
        </p>
      ) : null}
      {report.openedEvents.length > 0 ? (
        <p className="mt-1 text-[11px] text-muted-foreground">
          새 사건 {report.openedEvents.length}건이 열렸습니다.
        </p>
      ) : null}
    </Panel>
  );
}
