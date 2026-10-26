"use client";

import { useMemo, useState } from "react";

import type { CareerView, CareerWrestler } from "@/lib/career-api";
import { cn } from "@/lib/utils";

import { brandsOf, isRetired } from "./career-derive";
import {
  ALIGNMENT_LABEL,
  CAUSE_LABEL,
  RELATION_LABEL,
  STATUS_LABEL,
  labelOf,
} from "./career-labels";
import { Empty, FilterChips, Panel, SectionTitle, type FilterOption } from "./career-ui";

/**
 * 세계관 — **세계에 누가 있는지 읽는 화면.**
 *
 * `CareerView.roster` 하나로 전부 그린다. 선수별 조회 API를 추측해 만들지 않았다 —
 * 로스터 응답에 이름·브랜드·나이·상태·능력치·인기도·전적·성향·부상·은퇴가 다 들어
 * 있다.
 *
 * **`risk` 는 NPC 에게 `null` 이다.** 서버가 플레이어에게만 위험 단계를 계산해
 * 보낸다(`_wrestler_dto(..., with_risk=False)`). 그래서 이 표에 위험 칸을 두지
 * 않는다 — 빈칸이 늘어선 열은 "계산 중" 으로 읽힌다.
 */
type StatusFilter = "active" | "injured" | "pending" | "retired";

export function CareerWorldPanel({
  view,
  onOpenWrestler,
}: {
  view: CareerView;
  onOpenWrestler: (name: string) => void;
}) {
  const [filters, setFilters] = useState<{ status: StatusFilter; brand: string }>({
    status: "active",
    brand: "all",
  });

  const brands = useMemo(() => brandsOf(view.roster), [view.roster]);

  const counts = useMemo(() => {
    const retiredRows = view.roster.filter(isRetired);
    const living = view.roster.filter((w) => !isRetired(w));
    return {
      active: living.length,
      injured: living.filter((w) => w.status === "injured" || w.outWeeks > 0).length,
      pending: living.filter((w) => w.status === "retirement_pending" || w.intent != null).length,
      retired: retiredRows.length,
    };
  }, [view.roster]);

  const rows = useMemo(() => {
    const byStatus = view.roster.filter((w) => {
      const retired = isRetired(w);
      if (filters.status === "retired") return retired;
      if (retired) return false;
      if (filters.status === "injured") return w.status === "injured" || w.outWeeks > 0;
      if (filters.status === "pending")
        return w.status === "retirement_pending" || w.intent != null;
      return true;
    });
    const byBrand =
      filters.brand === "all" ? byStatus : byStatus.filter((w) => w.brand === filters.brand);
    // 인기도 내림차순 — 세계의 서열을 그대로 보여 주는 정렬이다.
    return [...byBrand].sort((a, b) => b.popularity - a.popularity);
  }, [view.roster, filters]);

  const statusOptions: readonly FilterOption<StatusFilter>[] = [
    { value: "active", label: "현역", count: counts.active },
    { value: "injured", label: "부상", count: counts.injured },
    { value: "pending", label: "은퇴 고민", count: counts.pending },
    { value: "retired", label: "은퇴 기록", count: counts.retired },
  ];

  const brandOptions: readonly FilterOption<string>[] = [
    { value: "all", label: "전체 브랜드" },
    ...brands.map((brand) => ({
      value: brand,
      label: brand,
      count: view.roster.filter((w) => w.brand === brand).length,
    })),
  ];

  const tagTeams = view.relationships.filter((r) => r.kind === "tag_team");
  const otherRelations = view.relationships.filter((r) => r.kind !== "tag_team");

  return (
    <div className="space-y-5">
      <section>
        <SectionTitle
          aside={<span className="text-xs text-muted-foreground">{rows.length}명</span>}
        >
          선수 명부
        </SectionTitle>
        <div className="mt-3 space-y-2">
          <FilterChips
            label="상태"
            options={statusOptions}
            value={filters.status}
            onChange={(status) => setFilters((s) => ({ ...s, status }))}
          />
          {brands.length > 1 ? (
            <FilterChips
              label="브랜드"
              options={brandOptions}
              value={filters.brand}
              onChange={(brand) => setFilters((s) => ({ ...s, brand }))}
            />
          ) : null}
        </div>

        {rows.length === 0 ? (
          <div className="mt-3">
            <Empty>
              {filters.status === "retired"
                ? "아직 은퇴한 선수가 없습니다. 은퇴는 나이·부상·부진이 쌓일 때 일어납니다."
                : "이 조건에 해당하는 선수가 없습니다."}
            </Empty>
          </div>
        ) : (
          <ul className="mt-3 space-y-2">
            {rows.map((wrestler) => (
              <li key={wrestler.name}>
                <RosterRow wrestler={wrestler} onOpen={() => onOpenWrestler(wrestler.name)} />
              </li>
            ))}
          </ul>
        )}

        {filters.status === "retired" && rows.length > 0 ? (
          <p className="mt-3 text-[11px] text-muted-foreground">
            은퇴 선수는 세계관에서 지워지지 않습니다 — 기록과 관계가 남고, 새 대진에만 들어가지
            않습니다. 헌액 규칙(명예의 전당)은 서버에 없으므로 여기 명부를 공식 헌액자로 적지
            않습니다.
          </p>
        ) : null}
      </section>

      <section>
        <SectionTitle>태그팀</SectionTitle>
        <div className="mt-3">
          {tagTeams.length === 0 ? (
            <Empty>결성된 태그팀이 없습니다. 태그팀 제안 사건을 수락하면 생깁니다.</Empty>
          ) : (
            <ul className="space-y-2">
              {tagTeams.map((team) => (
                <li
                  key={`${team.a}:${team.b}`}
                  className="rounded-lg border border-border bg-card px-3 py-2 text-sm"
                >
                  <span className="font-semibold text-foreground">
                    {team.a} &amp; {team.b}
                  </span>
                  <span className="ml-2 text-xs text-muted-foreground">
                    강도 <span className="tabular-nums">{team.heat}</span> · {team.startedWeek}주차
                    결성 · 최근 {team.lastWeek}주차
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>

      <section>
        <SectionTitle
          aside={
            <span className="text-xs text-muted-foreground">
              {otherRelations.length}건 · 격화 {otherRelations.filter((r) => r.feud).length}
            </span>
          }
        >
          관계
        </SectionTitle>
        <div className="mt-3">
          {otherRelations.length === 0 ? (
            <Empty>기록된 관계가 없습니다.</Empty>
          ) : (
            <ul className="space-y-1 text-xs">
              {/* 끓는 쪽 먼저. 라이벌 kind 는 경기마다 붙으므로 강도가 서열을 말한다. */}
              {[...otherRelations]
                .sort((a, b) => Number(b.feud) - Number(a.feud) || b.heat - a.heat)
                .map((relation) => (
                  <li key={`${relation.a}:${relation.b}:${relation.kind}`}>
                    <span className="text-foreground">
                      {relation.a} ↔ {relation.b}
                    </span>{" "}
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
        </div>
        <p className="mt-2 text-[11px] text-muted-foreground">
          「격화」는 서버가 경기로 풀어야 할 수준이라고 판정한 관계입니다 — 라이벌 표시는 경기마다
          붙으므로 그것만으로는 세지 않습니다.
        </p>
      </section>

      <Panel title="예정된 이벤트">
        <Empty>
          샌드박스 세계에는 PLE 일정이 없습니다 — 서버가 일정 데이터를 보내지 않으므로 가짜 달력을
          세우지 않습니다.
        </Empty>
      </Panel>
    </div>
  );
}

function RosterRow({ wrestler, onOpen }: { wrestler: CareerWrestler; onOpen: () => void }) {
  const retired = isRetired(wrestler);
  return (
    <button
      type="button"
      onClick={onOpen}
      className={cn(
        "flex w-full flex-wrap items-baseline gap-x-2 gap-y-1 rounded-xl border px-3 py-2.5 text-left transition-colors hover:bg-card-2",
        wrestler.isPlayer ? "border-brand-400/60 bg-brand-500/10" : "border-border bg-card",
      )}
    >
      <span className="text-sm font-semibold text-foreground">{wrestler.name}</span>
      {wrestler.isPlayer ? (
        <span className="rounded-md border border-brand-400/60 px-1.5 text-[10px] font-bold text-brand-600 dark:text-brand-300">
          내 선수
        </span>
      ) : null}
      <span className="text-xs text-muted-foreground">
        {wrestler.brand} · {labelOf(ALIGNMENT_LABEL, wrestler.alignment)} · {wrestler.age}세
      </span>
      <span className="ml-auto shrink-0 text-xs tabular-nums text-muted-foreground">
        인기 {wrestler.popularity} · {wrestler.wins}승 {wrestler.losses}패
      </span>
      <span className="w-full text-[11px] text-muted-foreground">
        {retired && wrestler.retirement
          ? `은퇴 — 시즌 ${wrestler.retirement.season} · ${wrestler.retirement.age}세 · ${labelOf(CAUSE_LABEL, wrestler.retirement.cause)}`
          : `${labelOf(STATUS_LABEL, wrestler.status)}${wrestler.outWeeks > 0 ? ` · 결장 ${wrestler.outWeeks}주` : ""}${wrestler.held.length > 0 ? ` · ${wrestler.held.join(" · ")}` : ""}`}
      </span>
    </button>
  );
}
