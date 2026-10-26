"use client";

import { useMemo, useState } from "react";

import type { CareerLogEntry, CareerTitle, CareerView } from "@/lib/career-api";

import { toMatchRows, toTitleRows } from "./career-derive";
import { LOG_KIND_LABEL, labelOf } from "./career-labels";
import { Empty, FilterChips, Loading, SectionTitle, WeekTag } from "./career-ui";
import type { FilterOption } from "./career-ui";

/**
 * 타이틀 — **현황은 `view.titles`, 이력은 커리어 로그.**
 *
 * ## 재계산하지 않는다
 *
 * `defenses` 와 `reignWeeks` 는 서버가 보낸 값을 그대로 적는다. 서버의 `reignWeeks`
 * 는 **절대 주차 차이**(`(시즌-1) × 시즌길이 + 주차 - 획득주차`)라 시즌을 넘겨도
 * 맞고, `defenses` 는 그 벨트의 **현재 재위** 기준 방어 수다. 화면이 로그를 세어
 * 두 번째 숫자를 만들면 둘이 어긋났을 때 어느 쪽도 설명할 수 없다.
 *
 * ## 공석
 *
 * `holder === null` 이 공석이다. 은퇴로 공석이 된 경우는 로그의 `title_vacated`
 * 줄이 남으므로 이력에서 읽힌다 — 선수 행도 기록도 지우지 않기 때문이다.
 */
export function CareerTitlesPanel({
  view,
  log,
  logLoading,
}: {
  view: CareerView;
  log: readonly CareerLogEntry[] | null;
  logLoading: boolean;
}) {
  const [brand, setBrand] = useState<string>("all");

  const brands = useMemo(
    () => [...new Set(view.titles.map((t) => t.brand))].sort((a, b) => a.localeCompare(b, "ko-KR")),
    [view.titles],
  );

  const titles = useMemo(
    () => (brand === "all" ? view.titles : view.titles.filter((t) => t.brand === brand)),
    [view.titles, brand],
  );

  const history = useMemo(() => (log ? toTitleRows(log) : null), [log]);
  // 「최근 타이틀전」은 경기 로그에서 타이틀이 걸린 줄이다 — 이력(획득·방어·공석)과 다른 축이다.
  const titleMatches = useMemo(
    () => (log ? toMatchRows(log, new Set()).filter((row) => row.title != null) : null),
    [log],
  );

  const brandOptions: readonly FilterOption<string>[] = [
    { value: "all", label: "전체 브랜드", count: view.titles.length },
    ...brands.map((b) => ({
      value: b,
      label: b,
      count: view.titles.filter((t) => t.brand === b).length,
    })),
  ];

  return (
    <div className="space-y-5">
      <section>
        <SectionTitle
          aside={
            <span className="text-xs text-muted-foreground">
              공석 {view.titles.filter((t) => t.holder == null).length}
            </span>
          }
        >
          타이틀 현황
        </SectionTitle>

        {brands.length > 1 ? (
          <div className="mt-3">
            <FilterChips label="브랜드" options={brandOptions} value={brand} onChange={setBrand} />
          </div>
        ) : null}

        <div className="mt-3">
          {titles.length === 0 ? (
            <Empty>이 브랜드에 걸린 타이틀이 없습니다.</Empty>
          ) : (
            <ul className="space-y-2">
              {titles.map((title) => (
                <li key={title.name}>
                  <TitleRow title={title} player={view.player.name} />
                </li>
              ))}
            </ul>
          )}
        </div>
        <p className="mt-3 text-[11px] text-muted-foreground">
          방어 횟수는 <strong className="text-foreground">현재 재위</strong> 기준이고, 재위 주차는
          절대 주차 차이입니다 — 둘 다 서버가 계산한 값을 그대로 적습니다.
        </p>
      </section>

      <section>
        <SectionTitle>최근 타이틀전</SectionTitle>
        <div className="mt-3">
          {titleMatches == null ? (
            <Loading>{logLoading ? "기록을 읽는 중…" : "기록을 준비하는 중…"}</Loading>
          ) : titleMatches.length === 0 ? (
            <Empty>아직 치른 타이틀전이 없습니다.</Empty>
          ) : (
            <ul className="space-y-1 text-xs">
              {titleMatches.slice(0, 10).map((row) => (
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
        </div>
      </section>

      <section>
        <SectionTitle
          aside={
            history ? (
              <span className="text-xs text-muted-foreground">{history.length}건</span>
            ) : null
          }
        >
          타이틀 변경 이력
        </SectionTitle>
        <div className="mt-3">
          {history == null ? (
            <Loading>{logLoading ? "기록을 읽는 중…" : "기록을 준비하는 중…"}</Loading>
          ) : history.length === 0 ? (
            <Empty>아직 타이틀이 움직인 기록이 없습니다.</Empty>
          ) : (
            <ul className="space-y-1 text-xs">
              {history.map((row) => (
                <li key={row.key} className="flex gap-2">
                  <WeekTag season={row.season} week={row.week} />
                  <span className="shrink-0 rounded-md border border-border px-1.5 text-[11px] text-muted-foreground">
                    {labelOf(LOG_KIND_LABEL, row.kind)}
                  </span>
                  <span className="min-w-0 text-foreground">
                    {row.summary || `${row.title} — ${row.subject}`}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>
    </div>
  );
}

function TitleRow({ title, player }: { title: CareerTitle; player: string }) {
  const mine = title.holder === player;
  const vacant = title.holder == null;
  return (
    <div className="rounded-xl border border-border bg-card px-3 py-2.5">
      <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
        <span className="text-sm font-semibold text-foreground">{title.name}</span>
        <span className="text-xs text-muted-foreground">{title.brand}</span>
        {mine ? (
          <span className="rounded-md border border-brand-400/60 px-1.5 text-[10px] font-bold text-brand-600 dark:text-brand-300">
            내 선수
          </span>
        ) : null}
        {vacant ? (
          <span className="rounded-md border border-live/50 px-1.5 text-[10px] font-bold text-live">
            공석
          </span>
        ) : null}
        <span className="ml-auto shrink-0 text-xs tabular-nums text-muted-foreground">
          요구 인기도 {title.requiredPopularity}
        </span>
      </div>
      <p className="mt-1 text-xs text-muted-foreground">
        {vacant ? (
          "보유자 없음 — 조건을 갖춘 선수가 나오면 다시 걸립니다."
        ) : (
          <>
            <span className="text-foreground">{title.holder}</span> · 방어{" "}
            <span className="tabular-nums">{title.defenses}</span>회
            {title.reignWeeks != null ? (
              <>
                {" "}
                · 재위 <span className="tabular-nums">{title.reignWeeks}</span>주
              </>
            ) : null}
          </>
        )}
      </p>
    </div>
  );
}
