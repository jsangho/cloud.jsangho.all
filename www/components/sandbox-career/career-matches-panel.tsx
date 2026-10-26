"use client";

import { useMemo, useState } from "react";

import type { CareerLogEntry, CareerView } from "@/lib/career-api";

import { matchesFilter, rivalNames, toMatchRows, type MatchFilter } from "./career-derive";
import { CARD_KIND_LABEL, labelOf } from "./career-labels";
import { Empty, FilterChips, Loading, Panel, SectionTitle, WeekTag } from "./career-ui";
import type { FilterOption } from "./career-ui";

/**
 * 경기 및 대진 — **커리어 로그의 `match` 줄을 탐색하는 화면.**
 *
 * 경기 전용 API가 없다. 경기는 `kind === "match"` 로그이고, 그 줄이 주는 것은
 * 상대(`other`) · 승패(`result`) · 타이틀(`title`) · 서버 문장(`summary`)이다.
 * **`summary` 를 쪼개지 않는다** — 경기 유형("방어전"·"타이틀전"·"태그"·"경기")과
 * 승리 방식이 그 문장 안에 들어 있고, 정규식으로 뜯으면 서버가 문장을 바꿀 때
 * 화면이 조용히 틀린 분류를 한다. 구조적으로 확실한 것(타이틀 유무)만 칸으로
 * 세운다.
 *
 * **라이벌전은 관계 데이터로만 판정한다.** 관계가 없으면 라이벌전이라고 적지
 * 않는다. 다만 서버는 관계의 **현재 상태**만 보내므로 이 표시는 "그 상대는 지금
 * 라이벌" 이라는 뜻이고, 화면도 그렇게 적는다.
 */
export function CareerMatchesPanel({
  view,
  log,
  logLoading,
}: {
  view: CareerView;
  /** 전체 기록. `null` 이면 아직 읽는 중이다 — 「경기 없음」으로 적지 않는다. */
  log: readonly CareerLogEntry[] | null;
  logLoading: boolean;
}) {
  const [filters, setFilters] = useState<{ kind: MatchFilter; season: string }>({
    kind: "all",
    season: "all",
  });

  const rivals = useMemo(
    () => rivalNames(view.relationships, view.player.name),
    [view.relationships, view.player.name],
  );
  const all = useMemo(() => (log ? toMatchRows(log, rivals) : null), [log, rivals]);

  const rows = useMemo(() => {
    if (!all) return null;
    return all.filter(
      (row) =>
        matchesFilter(row, filters.kind) &&
        (filters.season === "all" || row.season === Number(filters.season)),
    );
  }, [all, filters]);

  // 시즌 목록은 기록에 실제로 있는 시즌들이다 — 1..현재로 만들어 두면 빈 시즌이 생긴다.
  const seasons = useMemo(
    () => (all ? [...new Set(all.map((row) => row.season))].sort((a, b) => b - a) : []),
    [all],
  );

  const kindOptions: readonly FilterOption<MatchFilter>[] = all
    ? [
        { value: "all", label: "전체", count: all.length },
        {
          value: "normal",
          label: "일반 경기",
          count: all.filter((row) => matchesFilter(row, "normal")).length,
        },
        {
          value: "title",
          label: "타이틀전",
          count: all.filter((row) => matchesFilter(row, "title")).length,
        },
        {
          value: "rival",
          label: "라이벌전",
          count: all.filter((row) => matchesFilter(row, "rival")).length,
        },
      ]
    : [
        { value: "all", label: "전체" },
        { value: "normal", label: "일반 경기" },
        { value: "title", label: "타이틀전" },
        { value: "rival", label: "라이벌전" },
      ];

  const seasonOptions: readonly FilterOption<string>[] = [
    { value: "all", label: "모든 시즌" },
    ...seasons.map((season) => ({ value: String(season), label: `시즌 ${season}` })),
  ];

  return (
    <div className="space-y-5">
      <NextCard view={view} />

      <section>
        <SectionTitle
          aside={
            rows ? <span className="text-xs text-muted-foreground">{rows.length}경기</span> : null
          }
        >
          경기 기록
        </SectionTitle>

        <div className="mt-3 space-y-2">
          <FilterChips
            label="경기 유형"
            options={kindOptions}
            value={filters.kind}
            onChange={(kind) => setFilters((s) => ({ ...s, kind }))}
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
            <Loading>{logLoading ? "경기 기록을 읽는 중…" : "기록을 준비하는 중…"}</Loading>
          ) : rows.length === 0 ? (
            <Empty>
              {all && all.length === 0
                ? "아직 치른 경기가 없습니다. 주차를 진행하면 대진이 배정됩니다."
                : "이 조건에 해당하는 경기가 없습니다."}
            </Empty>
          ) : (
            <ul className="space-y-2">
              {rows.map((row) => (
                <li
                  key={row.key}
                  className="rounded-xl border border-border bg-card px-3 py-2.5 text-sm"
                >
                  <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
                    <WeekTag season={row.season} week={row.week} />
                    {row.won != null ? (
                      <span
                        className={
                          row.won
                            ? "rounded-md border border-chart-win/50 bg-chart-win/10 px-1.5 text-[11px] font-bold text-chart-win"
                            : "rounded-md border border-live/50 bg-live/10 px-1.5 text-[11px] font-bold text-live"
                        }
                      >
                        {/* 색만으로 말하지 않는다 — 글자가 함께 선다 (DESIGN.md §2). */}
                        {row.won ? "승" : "패"}
                      </span>
                    ) : null}
                    <span className="min-w-0 font-semibold text-foreground">
                      {row.subject}
                      {row.opponent ? ` vs ${row.opponent}` : ""}
                    </span>
                    {row.title ? (
                      <span className="rounded-md border border-brand-400/60 px-1.5 text-[11px] font-bold text-brand-600 dark:text-brand-300">
                        {row.title}
                      </span>
                    ) : null}
                    {row.rival ? (
                      <span className="rounded-md border border-border px-1.5 text-[11px] text-muted-foreground">
                        라이벌
                      </span>
                    ) : null}
                  </div>
                  {/* 경기 유형과 승리 방식은 이 서버 문장 안에 있다. 쪼개지 않는다. */}
                  <p className="mt-1 text-xs text-muted-foreground">{row.summary}</p>
                </li>
              ))}
            </ul>
          )}
        </div>

        <p className="mt-3 text-[11px] text-muted-foreground">
          「라이벌전」은 서버가 <strong className="text-foreground">격화됐다고 판정한</strong>{" "}
          관계의 상대와 치른 경기입니다 — 라이벌 표시 자체는 경기마다 붙으므로 그것만으로는 세지
          않습니다. 또한 서버는 관계의 <strong className="text-foreground">현재</strong> 상태만
          보내므로, 이 표시는 「그 상대는 지금 라이벌」이라는 뜻입니다. 경기 유형과 승리 방식은
          서버가 보낸 문장 그대로 적습니다.
        </p>
      </section>
    </div>
  );
}

function NextCard({ view }: { view: CareerView }) {
  const card = view.nextCard;
  if (view.player.retirement != null) {
    return (
      <Panel title="다음 대진">
        <Empty>은퇴한 선수에게는 대진이 배정되지 않습니다.</Empty>
      </Panel>
    );
  }
  if (view.phase !== "in_season") {
    return (
      <Panel title="다음 대진">
        <Empty>시즌이 진행 중일 때만 대진이 배정됩니다.</Empty>
      </Panel>
    );
  }
  const foe = card.opponents.length > 0 ? card.opponents.join(" · ") : card.opponent;
  return (
    <Panel title={`다음 대진 — 시즌 ${view.season} · ${view.week}주차`}>
      <p className="text-sm font-semibold text-foreground">
        {card.kind === "tag" && card.partner
          ? `태그 경기 — ${card.partner} 조`
          : card.title
            ? `타이틀전 — ${card.title}`
            : labelOf(CARD_KIND_LABEL, card.kind)}
      </p>
      {card.kind !== "rest" ? (
        <p className="mt-0.5 text-sm text-muted-foreground">상대 {foe ?? "미정"}</p>
      ) : null}
      {card.note ? <p className="mt-1 text-xs text-muted-foreground">{card.note}</p> : null}
    </Panel>
  );
}
