"use client";

import {
  CAREER_TRAINABLE,
  type CareerLogEntry,
  type CareerRelationship,
  type CareerSeason,
  type CareerWrestler,
} from "@/lib/career-api";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

import { honoursOf, isRetired, relationsOf, toMatchRows } from "./career-derive";
import {
  ABILITY_KEY,
  ALIGNMENT_LABEL,
  CAUSE_LABEL,
  RELATION_LABEL,
  SEVERITY_LABEL,
  STAT_LABEL,
  STATUS_LABEL,
  deltaText,
  labelOf,
} from "./career-labels";
import { Empty, Panel, Stat, WeekTag } from "./career-ui";

/**
 * 선수 상세 — **현역과 은퇴가 같은 화면이다.**
 *
 * 은퇴 선수를 위한 별도 프로필을 만들지 않았다. 은퇴로 달라지는 것은 칸 하나
 * (`retirement`)와 "더 경기하지 않는다" 뿐이고, 나머지(능력치·전적·관계·벨트)는
 * 같은 데이터다. 화면을 둘로 가르면 두 곳이 서로 다르게 낡는다.
 *
 * **새 API를 쓰지 않는다.** 선수별 조회 엔드포인트가 없고, 필요한 값은 이미
 * `CareerView.roster` · `relationships` · `seasons` 와 커리어 로그에 다 있다.
 *
 * 로그가 아직 안 읽혔으면(`log === null`) 경기·타이틀 절은 **비어 있다고 적지 않고
 * 「기록을 읽는 중」으로 적는다** — 없는 것과 아직 모르는 것은 다르다.
 */
export function CareerWrestlerDetail({
  wrestler,
  relationships,
  seasons,
  log,
  onClose,
}: {
  wrestler: CareerWrestler | null;
  relationships: readonly CareerRelationship[];
  /** 시즌 결산. **플레이어 기준 기록이라 NPC 에게는 쓰지 않는다.** */
  seasons: readonly CareerSeason[];
  log: readonly CareerLogEntry[] | null;
  onClose: () => void;
}) {
  if (!wrestler) return null;

  const retired = isRetired(wrestler);
  const honours = log ? honoursOf(log, wrestler.name) : null;
  // 경기 로그는 플레이어 기준으로만 쌓인다(`subject` 가 플레이어다). NPC 는 상대로
  // 등장한 줄을 센다 — 그래서 승패를 뒤집어 읽는다.
  const matches = log
    ? toMatchRows(log, new Set()).filter(
        (row) => row.subject === wrestler.name || row.opponent === wrestler.name,
      )
    : null;
  const relations = relationsOf(relationships, wrestler.name);

  return (
    <Dialog open onOpenChange={(open) => (open ? undefined : onClose())}>
      <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="font-sport text-xl">{wrestler.name}</DialogTitle>
          <DialogDescription>
            {wrestler.brand} · {wrestler.style} · {labelOf(ALIGNMENT_LABEL, wrestler.alignment)} ·{" "}
            {labelOf(STATUS_LABEL, wrestler.status)}
            {wrestler.isPlayer ? " · 내 선수" : ""}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-2">
            <Stat label="나이" value={`${wrestler.age}세 (데뷔 ${wrestler.debutAge}세)`} />
            <Stat label="전적" value={`${wrestler.wins}승 ${wrestler.losses}패`} />
            <Stat label="인기도" value={`${wrestler.popularity}`} />
            <Stat
              label="컨디션"
              value={
                wrestler.outWeeks > 0
                  ? `${wrestler.condition} · 결장 ${wrestler.outWeeks}주`
                  : `${wrestler.condition}`
              }
              tone={wrestler.outWeeks > 0 ? "warn" : undefined}
            />
          </div>

          {wrestler.retirement ? (
            <div className="rounded-xl border border-brand-700/50 bg-brand-500/10 p-3">
              <p className="text-xs font-bold text-muted-foreground">은퇴</p>
              <p className="mt-0.5 text-sm text-foreground">
                시즌 {wrestler.retirement.season} · {wrestler.retirement.week}주차 ·{" "}
                {wrestler.retirement.age}세
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                원인 {labelOf(CAUSE_LABEL, wrestler.retirement.cause)} · 최종{" "}
                {wrestler.retirement.wins}승 {wrestler.retirement.losses}패 · 역대 획득{" "}
                {wrestler.retirement.reigns}회
              </p>
              {wrestler.retirement.titles.length > 0 ? (
                <p className="mt-1 text-xs text-foreground">
                  주요 타이틀: {wrestler.retirement.titles.join(" · ")}
                </p>
              ) : null}
              {wrestler.retirement.held.length > 0 ? (
                <p className="mt-1 text-xs text-muted-foreground">
                  은퇴 당시 보유: {wrestler.retirement.held.join(" · ")} — 은퇴와 함께 공석이
                  됩니다.
                </p>
              ) : null}
              {wrestler.retirement.note ? (
                <p className="mt-1 text-xs text-muted-foreground">{wrestler.retirement.note}</p>
              ) : null}
            </div>
          ) : wrestler.intent ? (
            <p className="rounded-lg border border-border bg-card px-3 py-2 text-xs text-muted-foreground">
              은퇴 <strong className="text-foreground">의사</strong>가 있습니다 (사유{" "}
              {labelOf(CAUSE_LABEL, wrestler.intent.cause)}
              {wrestler.intent.finalSeason ? " · 이번 시즌이 마지막" : ""}). 확정은 아닙니다.
            </p>
          ) : null}

          <Panel
            title="능력치"
            hint={wrestler.trend ? `최근 시즌 변화 ${deltaText(wrestler.trend)}` : undefined}
          >
            <dl className="space-y-0.5 text-sm">
              {CAREER_TRAINABLE.map((key) => (
                <div key={key} className="flex justify-between gap-3">
                  <dt className="text-muted-foreground">{STAT_LABEL[key]}</dt>
                  <dd className="tabular-nums text-foreground">
                    {wrestler.ability[ABILITY_KEY[key]]}
                  </dd>
                </div>
              ))}
            </dl>
          </Panel>

          <Panel title="벨트">
            <p className="text-sm text-foreground">
              현재 보유: {wrestler.held.length > 0 ? wrestler.held.join(" · ") : "없음"}
            </p>
            <p className="mt-1 text-sm text-foreground">
              역대 획득:{" "}
              {wrestler.reigns.length > 0
                ? `${wrestler.reigns.length}회 — ${wrestler.reigns.join(" · ")}`
                : "없음"}
            </p>
            {honours == null ? (
              <p className="mt-2 text-[11px] text-muted-foreground">
                방어 기록은 커리어 기록을 읽은 뒤에 나옵니다.
              </p>
            ) : (
              <p className="mt-2 text-[11px] text-muted-foreground">
                읽어 온 기록에서 센 방어 {honours.defenses.length}회 · 획득{" "}
                {honours.titleWins.length}회 · 공석 {honours.vacated.length}회 — 서버 집계가 아니라
                기록 줄을 센 수입니다.
              </p>
            )}
          </Panel>

          <Panel title="관계 · 태그팀">
            {relations.length === 0 ? (
              <Empty>기록된 관계가 없습니다.</Empty>
            ) : (
              <ul className="space-y-0.5 text-xs">
                {[...relations]
                  .sort(
                    (a, b) =>
                      Number(b.relation.feud) - Number(a.relation.feud) ||
                      b.relation.heat - a.relation.heat,
                  )
                  .map(({ other, relation }) => (
                    <li key={`${relation.a}:${relation.b}:${relation.kind}`}>
                      <span className="text-foreground">{other}</span>{" "}
                      <span className="text-muted-foreground">
                        — {labelOf(RELATION_LABEL, relation.kind)} · 강도{" "}
                        <span className="tabular-nums">{relation.heat}</span>
                        {relation.history.length > 0 ? ` (${relation.history.join(" → ")})` : ""}
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

          {wrestler.injuries.length > 0 ? (
            <Panel title="부상 이력">
              <ul className="space-y-0.5 text-xs text-muted-foreground">
                {wrestler.injuries.map((injury, index) => (
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

          <Panel
            title="주요 경기"
            hint={
              matches != null && matches.length > 8
                ? `읽어 온 기록 ${matches.length}경기 중 최근 8경기`
                : undefined
            }
          >
            {matches == null ? (
              <Empty>커리어 기록을 읽는 중입니다.</Empty>
            ) : matches.length === 0 ? (
              <Empty>기록에 남은 경기가 없습니다.</Empty>
            ) : (
              <ul className="space-y-1 text-xs">
                {matches.slice(0, 8).map((row) => (
                  <li key={row.key} className="flex gap-2">
                    <WeekTag season={row.season} week={row.week} />
                    <span className="min-w-0 text-foreground">{row.summary}</span>
                  </li>
                ))}
              </ul>
            )}
          </Panel>

          {/* 시즌 결산은 플레이어 커리어의 기록이다 — NPC 에 붙이면 남의 성적이 된다. */}
          {wrestler.isPlayer && seasons.length > 0 ? (
            <Panel title="시즌별 성과">
              <ul className="space-y-1 text-xs">
                {[...seasons].reverse().map((season) => (
                  <li key={season.season} className="text-muted-foreground">
                    <span className="text-foreground">시즌 {season.season}</span> · {season.age}세 ·{" "}
                    {season.wins}승 {season.losses}패 · 방어 {season.defenses} · 부상{" "}
                    {season.injuries}
                    {season.titlesWon.length > 0 ? ` · 획득 ${season.titlesWon.join(" · ")}` : ""}
                  </li>
                ))}
              </ul>
            </Panel>
          ) : null}

          {retired ? (
            <p className="text-[11px] text-muted-foreground">
              은퇴 선수도 세계관에 남습니다 — 기록이 지워지지 않고, 새 대진에만 들어가지 않습니다.
            </p>
          ) : null}
        </div>
      </DialogContent>
    </Dialog>
  );
}
