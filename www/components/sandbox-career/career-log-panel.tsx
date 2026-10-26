"use client";

import { useMemo, useState } from "react";

import type { CareerLogEntry, CareerView } from "@/lib/career-api";

import { logKey } from "./career-derive";
import { LOG_KIND_LABEL, deltaText, labelOf } from "./career-labels";
import { Empty, FilterChips, Loading, SectionTitle, WeekTag } from "./career-ui";
import type { FilterOption } from "./career-ui";

/**
 * 커리어 기록 — **연대기.**
 *
 * ## 중복 표시를 막는 것
 *
 * 서버가 기록 줄에 id를 주지 않는다(`LogSchema` 에 id 칸이 없다). 그래서 키는
 * `시즌:주차:종류:순번` 조합이고(`logKey`), 순번은 **읽어 온 배열의 위치**다.
 * 이것이 안전한 이유는 로그가 **추가만 되는 목록**이고 서버가 항상 같은 순서로
 * (최신부터) 잘라 주기 때문이다 — 페이지가 겹치지 않는다. 대신 **쓰기 요청 뒤에는
 * 읽어 둔 기록을 버린다**(세이브가 바뀌면 앞쪽에 줄이 끼어들어 순번이 밀린다).
 *
 * ## 필터가 도는 범위
 *
 * 종류 필터는 **읽어 온 줄 안에서** 돈다 — 서버 `/log` 는 `season` 만 받고 `kind`
 * 는 받지 않는다. 그래서 「더 보기」로 다 읽지 않았으면 그 사실을 화면이 적는다.
 * 없는 쿼리 파라미터를 추측해서 붙이지 않는다.
 */
type LogGroup = "all" | "match" | "title" | "relation" | "injury" | "season";

/** 묶음 → 서버 `kind` 들. 서버가 쓰는 이름만 넣는다. */
const GROUP_KINDS: Readonly<Record<Exclude<LogGroup, "all">, readonly string[]>> = {
  match: ["match"],
  title: ["title_won", "title_defended", "title_vacated"],
  relation: ["action", "event"],
  injury: ["injury", "out", "rest", "retired", "promoted"],
  season: ["season_start", "season_end", "debut"],
};

const GROUP_LABEL: Readonly<Record<LogGroup, string>> = {
  all: "전체",
  match: "경기",
  title: "타이틀",
  relation: "관계 · 사건",
  injury: "부상 · 상태",
  season: "시즌",
};

export function CareerLogPanel({
  view,
  log,
  logLoading,
  exhausted,
  onLoadMore,
}: {
  view: CareerView;
  log: readonly CareerLogEntry[] | null;
  logLoading: boolean;
  exhausted: boolean;
  onLoadMore: () => void;
}) {
  const [filters, setFilters] = useState<{ group: LogGroup; season: string }>({
    group: "all",
    season: "all",
  });

  const entries = log ?? null;

  const seasons = useMemo(
    () => (entries ? [...new Set(entries.map((e) => e.season))].sort((a, b) => b - a) : []),
    [entries],
  );

  const rows = useMemo(() => {
    if (!entries) return null;
    return entries
      .map((entry, index) => ({ entry, key: logKey(entry, index) }))
      .filter(({ entry }) => {
        if (filters.season !== "all" && entry.season !== Number(filters.season)) return false;
        if (filters.group === "all") return true;
        return GROUP_KINDS[filters.group].includes(entry.kind);
      });
  }, [entries, filters]);

  const groupOptions: readonly FilterOption<LogGroup>[] = (
    ["all", "match", "title", "relation", "injury", "season"] as const
  ).map((group) => ({
    value: group,
    label: GROUP_LABEL[group],
    count: entries
      ? group === "all"
        ? entries.length
        : entries.filter((e) => GROUP_KINDS[group].includes(e.kind)).length
      : undefined,
  }));

  const seasonOptions: readonly FilterOption<string>[] = [
    { value: "all", label: "모든 시즌" },
    ...seasons.map((season) => ({ value: String(season), label: `시즌 ${season}` })),
  ];

  return (
    <div className="space-y-5">
      <section>
        <SectionTitle
          aside={
            rows ? <span className="text-xs text-muted-foreground">{rows.length}건</span> : null
          }
        >
          커리어 기록
        </SectionTitle>

        <div className="mt-3 space-y-2">
          <FilterChips
            label="기록 유형"
            options={groupOptions}
            value={filters.group}
            onChange={(group) => setFilters((s) => ({ ...s, group }))}
          />
          {seasons.length > 1 ? (
            <FilterChips
              label="시즌"
              options={seasonOptions}
              value={filters.season}
              onChange={(season) => setFilters((s) => ({ ...s, season }))}
            />
          ) : null}
        </div>

        <div className="mt-3">
          {rows == null ? (
            <Loading>{logLoading ? "기록을 읽는 중…" : "기록을 준비하는 중…"}</Loading>
          ) : rows.length === 0 ? (
            <Empty>이 조건에 해당하는 기록이 없습니다.</Empty>
          ) : (
            <ul className="space-y-1 text-xs">
              {rows.map(({ entry, key }) => (
                <li key={key} className="flex gap-2">
                  <WeekTag season={entry.season} week={entry.week} />
                  <span className="shrink-0 rounded-md border border-border px-1.5 text-[11px] text-muted-foreground">
                    {labelOf(LOG_KIND_LABEL, entry.kind)}
                  </span>
                  <span className="min-w-0 text-foreground">
                    {entry.summary || labelOf(LOG_KIND_LABEL, entry.kind)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>

        {exhausted ? (
          <p className="mt-3 text-[11px] text-muted-foreground">
            기록을 끝까지 읽었습니다 — 필터는 전체 기록에서 돕니다.
          </p>
        ) : (
          <>
            <button
              type="button"
              onClick={onLoadMore}
              disabled={logLoading}
              className="mt-3 w-full rounded-lg border border-dashed border-border px-3 py-2 text-xs text-muted-foreground hover:bg-card-2 disabled:opacity-50"
            >
              {logLoading ? "불러오는 중…" : "기록 더 보기"}
            </button>
            <p className="mt-2 text-[11px] text-muted-foreground">
              아직 끝까지 읽지 않았습니다 — 위 필터는{" "}
              <strong className="text-foreground">읽어 온 줄</strong> 안에서만 돕니다.
            </p>
          </>
        )}
      </section>

      <section>
        <SectionTitle
          aside={
            <span className="text-xs text-muted-foreground">{view.seasons.length}개 시즌</span>
          }
        >
          시즌 결산
        </SectionTitle>
        <div className="mt-3">
          {view.seasons.length === 0 ? (
            <Empty>
              아직 결산된 시즌이 없습니다. 시즌 {view.seasonWeeks}주를 다 쓰면 결산이 쌓입니다.
            </Empty>
          ) : (
            <div className="space-y-2">
              {[...view.seasons].reverse().map((season) => (
                <div key={season.season} className="rounded-xl border border-border bg-card p-3">
                  <div className="flex flex-wrap items-baseline justify-between gap-2">
                    <p className="text-sm font-bold text-foreground">시즌 {season.season}</p>
                    <p className="text-xs tabular-nums text-muted-foreground">
                      {season.age}세 · {season.wins}승 {season.losses}패 · 방어 {season.defenses} ·
                      부상 {season.injuries}
                    </p>
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">
                    능력치 변화 {deltaText(season.abilityDelta)}
                  </p>
                  {season.titlesWon.length > 0 ? (
                    <p className="mt-1 text-xs text-foreground">
                      획득: {season.titlesWon.join(" · ")}
                    </p>
                  ) : null}
                  {season.highlights.length > 0 ? (
                    <ul className="mt-2 space-y-0.5 text-xs text-muted-foreground">
                      {season.highlights.map((highlight, index) => (
                        <li key={`${season.season}:${index}`}>· {highlight}</li>
                      ))}
                    </ul>
                  ) : null}
                  {season.retired.length > 0 ? (
                    <p className="mt-1 text-xs text-muted-foreground">
                      이 시즌 은퇴: {season.retired.join(" · ")}
                    </p>
                  ) : null}
                  {season.riskBand ? (
                    <p className="mt-1 text-[11px] text-muted-foreground">
                      시즌 종료 당시 은퇴 위험 단계 {season.riskBand}
                    </p>
                  ) : null}
                </div>
              ))}
            </div>
          )}
        </div>
      </section>

      <section>
        <SectionTitle>시즌 목표</SectionTitle>
        <div className="mt-3">
          <Empty>
            서버에 목표 데이터가 없습니다 — 목표 시스템이 생기면 이 자리에 들어옵니다. 지금 숫자를
            만들어 적지 않습니다.
          </Empty>
        </div>
      </section>
    </div>
  );
}
