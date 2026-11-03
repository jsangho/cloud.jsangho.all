"use client";

import { useEffect, useMemo, useState } from "react";

import {
  fetchCareerMatches,
  type CareerLogEntry,
  type CareerMatchSummary,
  type CareerView,
} from "@/lib/career-api";
import { MATCH_PAGE, hasNextPage } from "@/lib/career-match";
import { cn } from "@/lib/utils";

import { matchesFilter, rivalNames, toMatchRows, type MatchFilter } from "./career-derive";
import { CARD_KIND_LABEL, labelOf } from "./career-labels";
import { Empty, FilterChips, Loading, Panel, SectionTitle, WeekTag } from "./career-ui";
import type { FilterOption } from "./career-ui";

/**
 * 경기 및 대진 — **저장된 경기 기록(상세 가능)과 커리어 로그의 `match` 줄 둘을 본다.**
 *
 * 위쪽 「경기 기록」은 P1 조회 API(`/matches`)가 주는 기록이고 누르면 상세가 열린다.
 * 아래 「경기 로그」는 로그의 경기 줄이다 — 기록 도입 전·보존 상한 밖의 경기도 여기엔
 * 남아 있어서 지우지 않았다. 로그의 경기는 `kind === "match"` 줄이고, 그 줄이 주는 것은
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
  onOpenMatch,
}: {
  view: CareerView;
  /** 전체 기록. `null` 이면 아직 읽는 중이다 — 「경기 없음」으로 적지 않는다. */
  log: readonly CareerLogEntry[] | null;
  logLoading: boolean;
  /** 경기 상세 열기. 페이지가 URL(`?match=`)에 적는다. */
  onOpenMatch: (matchId: string) => void;
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
    <div className="grid items-start gap-6 xl:grid-cols-2">
      <NextCard view={view} />

      <MatchRecords
        careerId={view.id}
        maxSeason={view.season}
        // 주차가 넘어가면 새 기록이 생긴다 — 이 값이 바뀔 때 다시 읽는다.
        refreshKey={`${view.season}:${view.week}:${view.phase}`}
        onOpen={onOpenMatch}
      />

      <section className="xl:col-span-2">
        <SectionTitle
          aside={rows ? <span className="text-xs text-stone-400">{rows.length}경기</span> : null}
        >
          경기 로그
        </SectionTitle>
        <p className="mt-1 text-[11px] text-stone-400">
          커리어 기록의 경기 줄입니다. 상세 기록이 없는 오래된 경기도 여기에는 남아 있습니다.
        </p>

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
                <li key={row.key} className="arena-panel px-3 py-2.5 text-sm">
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
                    <span className="min-w-0 font-semibold text-stone-100">
                      {row.subject}
                      {row.opponent ? ` vs ${row.opponent}` : ""}
                    </span>
                    {row.title ? (
                      <span className="rounded-md border border-brand-400/60 px-1.5 text-[11px] font-bold text-brand-600 dark:text-brand-300">
                        {row.title}
                      </span>
                    ) : null}
                    {row.rival ? (
                      <span className="rounded-md border border-white/10 px-1.5 text-[11px] text-stone-400">
                        라이벌
                      </span>
                    ) : null}
                  </div>
                  {/* 경기 유형과 승리 방식은 이 서버 문장 안에 있다. 쪼개지 않는다. */}
                  <p className="mt-1 text-xs text-stone-400">{row.summary}</p>
                </li>
              ))}
            </ul>
          )}
        </div>

        <p className="mt-3 text-[11px] text-stone-400">
          「라이벌전」은 서버가 <strong className="text-stone-100">격화됐다고 판정한</strong> 관계의
          상대와 치른 경기입니다 — 라이벌 표시 자체는 경기마다 붙으므로 그것만으로는 세지 않습니다.
          또한 서버는 관계의 <strong className="text-stone-100">현재</strong> 상태만 보내므로, 이
          표시는 「그 상대는 지금 라이벌」이라는 뜻입니다. 경기 유형과 승리 방식은 서버가 보낸 문장
          그대로 적습니다.
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
      <p className="text-sm font-semibold text-stone-100">
        {card.kind === "tag" && card.partner
          ? `태그 경기 — ${card.partner} 조`
          : card.title
            ? `타이틀전 — ${card.title}`
            : labelOf(CARD_KIND_LABEL, card.kind)}
      </p>
      {card.kind !== "rest" ? (
        <p className="mt-0.5 text-sm text-stone-400">상대 {foe ?? "미정"}</p>
      ) : null}
      {card.note ? <p className="mt-1 text-xs text-stone-400">{card.note}</p> : null}
    </Panel>
  );
}

// ── 저장된 경기 기록 (P1 API) ─────────────────────────────────────

type RecordsState =
  | { key: string; status: "loading" }
  | { key: string; status: "ok"; rows: CareerMatchSummary[] }
  | { key: string; status: "error"; message: string };

/**
 * 경기 기록 목록 — **서버가 저장한 경기만** 보인다(`GET /{career}/matches`).
 *
 * 최신 경기부터 온다(서버 정렬). 서버가 `total` 을 주지 않으므로 「다음」은 **꽉 찬
 * 페이지일 때만** 켠다(`hasNextPage`). 마지막 페이지가 정확히 꽉 차 있으면 다음
 * 페이지가 빈 채로 열리고, 그건 「더 없음」으로 그린다.
 *
 * 응답은 **요청 키와 함께** 저장된다 — 필터·페이지를 빠르게 바꿔도 늦게 온 앞 요청이
 * 지금 화면을 덮지 않는다. 앞 요청은 취소한다.
 */
function MatchRecords({
  careerId,
  maxSeason,
  refreshKey,
  onOpen,
}: {
  careerId: number;
  maxSeason: number;
  refreshKey: string;
  onOpen: (matchId: string) => void;
}) {
  const [query, setQuery] = useState<{ season: string; offset: number }>({
    season: "all",
    offset: 0,
  });
  const [state, setState] = useState<RecordsState | null>(null);

  const season = query.season === "all" ? null : Number(query.season);
  const key = `${careerId}:${season ?? "all"}:${query.offset}:${refreshKey}`;

  useEffect(() => {
    const controller = new AbortController();
    setState({ key, status: "loading" });
    void fetchCareerMatches(
      careerId,
      { season, limit: MATCH_PAGE, offset: query.offset },
      controller.signal,
    ).then((result) => {
      if (controller.signal.aborted) return;
      setState(
        result.ok
          ? { key, status: "ok", rows: result.rows }
          : { key, status: "error", message: result.message },
      );
    });
    return () => controller.abort();
  }, [careerId, season, query.offset, key]);

  // 키가 다른 결과는 앞 요청의 것이다 — 그리지 않는다.
  const current: RecordsState = state && state.key === key ? state : { key, status: "loading" };
  const page = Math.floor(query.offset / MATCH_PAGE) + 1;

  const seasonOptions: readonly FilterOption<string>[] = [
    { value: "all", label: "모든 시즌" },
    ...Array.from({ length: maxSeason }, (_, i) => maxSeason - i).map((s) => ({
      value: String(s),
      label: `시즌 ${s}`,
    })),
  ];

  return (
    <section aria-label="경기 기록">
      <SectionTitle aside={<span className="text-xs text-stone-400">최신 경기부터</span>}>
        경기 기록
      </SectionTitle>

      {maxSeason > 1 ? (
        <div className="mt-3">
          <FilterChips
            label="시즌"
            options={seasonOptions}
            value={query.season}
            onChange={(next) => setQuery({ season: next, offset: 0 })}
          />
        </div>
      ) : null}

      <div className="mt-3">
        {current.status === "loading" ? (
          <Loading>경기 기록을 읽는 중…</Loading>
        ) : current.status === "error" ? (
          <p
            role="alert"
            className="rounded-lg border border-live/50 bg-live/10 px-3 py-4 text-center text-xs text-live"
          >
            경기 기록을 불러오지 못했습니다 — {current.message}
          </p>
        ) : current.rows.length === 0 ? (
          <Empty>
            {query.offset > 0
              ? "더 이상 경기가 없습니다."
              : season != null
                ? `시즌 ${season}에 남은 경기 기록이 없습니다.`
                : "아직 상세 기록이 남은 경기가 없습니다. 주차를 진행하면 경기마다 기록이 쌓입니다."}
          </Empty>
        ) : (
          <ul className="space-y-2">
            {current.rows.map((row) => (
              <li key={row.id}>
                <MatchRecordRow row={row} onOpen={onOpen} />
              </li>
            ))}
          </ul>
        )}
      </div>

      {current.status === "ok" && (query.offset > 0 || hasNextPage(current.rows.length)) ? (
        <nav aria-label="경기 기록 페이지" className="mt-3 flex items-center justify-between gap-2">
          <button
            type="button"
            disabled={query.offset === 0}
            onClick={() => setQuery((q) => ({ ...q, offset: Math.max(0, q.offset - MATCH_PAGE) }))}
            className="arena-ghost px-3 py-1 text-xs font-semibold disabled:opacity-40"
          >
            ← 최근 경기
          </button>
          <span className="text-xs tabular-nums text-stone-400">{page}쪽</span>
          <button
            type="button"
            disabled={!hasNextPage(current.rows.length)}
            onClick={() => setQuery((q) => ({ ...q, offset: q.offset + MATCH_PAGE }))}
            className="arena-ghost px-3 py-1 text-xs font-semibold disabled:opacity-40"
          >
            지난 경기 →
          </button>
        </nav>
      ) : null}
    </section>
  );
}

function MatchRecordRow({
  row,
  onOpen,
}: {
  row: CareerMatchSummary;
  onOpen: (matchId: string) => void;
}) {
  const won = row.winnerSide === 0;
  const [mine, theirs] = [row.teams[0] ?? [], row.teams[1] ?? []];
  return (
    <button
      type="button"
      onClick={() => onOpen(row.id)}
      aria-label={`S${row.season} W${row.week} 경기 상세 보기`}
      className="arena-panel block w-full px-3 py-2.5 text-left text-sm transition-colors hover:bg-white/[0.04] focus-visible:outline-2 focus-visible:outline-brand-400"
    >
      <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
        <WeekTag season={row.season} week={row.week} />
        <span
          className={
            won
              ? "rounded-md border border-chart-win/50 bg-chart-win/10 px-1.5 text-[11px] font-bold text-chart-win"
              : "rounded-md border border-live/50 bg-live/10 px-1.5 text-[11px] font-bold text-live"
          }
        >
          {/* 색만으로 말하지 않는다 — 글자가 함께 선다 (DESIGN.md §2). */}
          {won ? "승" : "패"}
        </span>
        <span className="text-[11px] text-stone-400">
          {row.brand} · {labelOf(CARD_KIND_LABEL, row.kind)} · {row.reason}
        </span>
        {row.title ? (
          <span className="rounded-md border border-brand-400/60 px-1.5 text-[11px] font-bold text-brand-600 dark:text-brand-300">
            {row.title}
            {row.titleChanged ? " · 이동" : ""}
          </span>
        ) : null}
      </div>
      <p className="mt-1 font-semibold text-stone-100">
        <span className={cn(won && "text-brand-300")}>{mine.join(" & ")}</span>
        <span className="mx-1.5 text-xs font-normal text-stone-500">vs</span>
        <span className={cn(!won && "text-brand-300")}>{theirs.join(" & ")}</span>
      </p>
      <p className="mt-0.5 text-xs text-stone-400">
        {row.finish} · 평점 <span className="tabular-nums">{row.rating}</span>
      </p>
    </button>
  );
}
