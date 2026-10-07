"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  DataCenterShell,
  DataUnavailable,
  LoadingBlock,
  StatTile,
} from "@/components/data-center/data-center-shell";
import { MatchRowCard } from "@/components/data-center/match-row-card";
import {
  fetchChampionshipStats,
  fetchDataCenterAnalytics,
  fetchDataCenterOverview,
  formatWinRate,
  type ChampionshipStats,
  type DataCenterAnalytics,
  type DataCenterOverview,
} from "@/lib/data-center-api";

/**
 * 데이터 센터 개요 (Phase 2 §4).
 *
 * **1면이 얇은 축을 세우고 있었다** (2026-10-07 사용자 — "애매한 데이터 밖에 없어").
 * 원인은 데이터가 없는 것이 아니라 **어느 축을 먼저 세우느냐**였다. 실측하면:
 *
 * - 얇은 축: 끝난 경기 63건 / 선수 178명 → 1인당 0.35경기. 승률 순위에 오르는
 *   사람이 열 명뿐이고 표본이 3~5경기라, 1위가 「5승 0패 100%」로 찍힌다.
 * - 두꺼운 축: 타이틀 획득 **367건** · 기록에 남은 벨트 29개 · 챔피언 66명.
 *   John Cena 27회 6벨트처럼 셀 것이 실제로 있다.
 *
 * 그런데 이 허브는 벨트 페이지로 가는 링크를 **하나도 걸지 않았다**(탭에만 있었다).
 * 그래서 순서를 뒤집는다 — 벨트가 경기·승률보다 위에 선다.
 *
 * **모든 숫자는 DB에서 센 값이다** — 못 받으면 그 구역을 비운다.
 */
type TitleRankRow = {
  key: string;
  /** 선수는 기록 페이지로 보낸다. 벨트는 갈 곳이 없어 `undefined`다. */
  href?: string;
  name: string;
  value: string;
  note?: string | null;
};

/**
 * 타이틀 기록의 순위 목록.
 *
 * 차트가 아니라 **목록**이다 — 다섯 줄짜리 크기 비교에 막대를 깔면 잉크만 늘고
 * 이름이 읽히지 않는다 (DESIGN.md §16 「형태부터 고른다」).
 */
function TitleRankList({ title, rows }: { title: string; rows: TitleRankRow[] }) {
  if (rows.length === 0) return null;

  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <h3 className="mb-2 text-sm font-semibold text-foreground">{title}</h3>
      <ol className="flex flex-col">
        {rows.map((row, index) => {
          const body = (
            <>
              <span className="w-5 shrink-0 text-sm font-bold tabular-nums text-muted-foreground">
                {index + 1}
              </span>
              <span className="min-w-0 flex-1 truncate text-sm text-foreground">{row.name}</span>
              {row.note && (
                <span className="hidden shrink-0 text-xs text-muted-foreground sm:inline">
                  {row.note}
                </span>
              )}
              <span className="shrink-0 text-sm font-bold tabular-nums text-brand-link">
                {row.value}
              </span>
            </>
          );
          return (
            <li key={row.key} className="border-b border-border last:border-b-0">
              {row.href ? (
                <Link
                  href={row.href}
                  className="flex items-center gap-3 py-2 transition-colors hover:text-brand-link"
                >
                  {body}
                </Link>
              ) : (
                <div className="flex items-center gap-3 py-2">{body}</div>
              )}
            </li>
          );
        })}
      </ol>
    </div>
  );
}

export default function DataCenterPage() {
  const [overview, setOverview] = useState<DataCenterOverview | null>(null);
  const [analytics, setAnalytics] = useState<DataCenterAnalytics | null>(null);
  const [titles, setTitles] = useState<ChampionshipStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      const [o, a, t] = await Promise.all([
        fetchDataCenterOverview(),
        fetchDataCenterAnalytics(),
        fetchChampionshipStats(),
      ]);
      if (cancelled) return;
      setOverview(o);
      setAnalytics(a);
      setTitles(t);
      setLoading(false);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <DataCenterShell
      title="데이터 센터"
      description="KAYFABE가 실제로 들고 있는 데이터입니다. 선수·경기·대회·벨트를 DB에서 직접 셉니다."
    >
      {loading ? (
        <LoadingBlock rows={4} />
      ) : !overview ? (
        <DataUnavailable what="데이터 센터 요약" />
      ) : (
        <div className="flex flex-col gap-8">
          <section aria-label="핵심 수치">
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
              <StatTile value={overview.counts.wrestlers} label="선수" note="DB에 등록된 인원" />
              <StatTile
                value={overview.counts.matches}
                label="경기"
                note={`끝난 경기 ${overview.counts.finishedMatches}`}
              />
              <StatTile
                value={overview.counts.events}
                label="대회"
                note={`끝난 대회 ${overview.counts.finishedEvents}`}
              />
              {/*
               * **「벨트」가 두 가지를 뜻하고 있었다** (2026-10-07 실측). 이 타일은
               * `championship_titles` 테이블 행 수(= 지금 걸려 있는 벨트)인데, 벨트
               * 페이지의 29는 획득 기록에 등장하는 벨트 이름 수(폐지 포함)다. 같은
               * 이름으로 다른 것을 세고 있었으므로 라벨을 갈라 적는다.
               */}
              <StatTile
                value={overview.counts.championshipBelts}
                label="현역 벨트"
                note={`타이틀이 오간 기록 ${overview.counts.titleAcquisitions}`}
                tone="gold"
              />
            </div>
          </section>

          <section aria-labelledby="title-history">
            <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
              <h2 id="title-history" className="font-sport text-lg text-foreground">
                벨트는 누가 들었나
              </h2>
              <Link
                href="/data-center/championships"
                className="text-sm font-semibold text-brand-link underline-offset-4 hover:underline"
              >
                벨트 전체 보기 →
              </Link>
            </div>
            {!titles ? (
              <DataUnavailable what="타이틀 기록" />
            ) : (
              <>
                <p className="mb-3 text-sm text-muted-foreground">
                  이 사이트에서 가장 깊은 기록입니다 — 타이틀이 오간{" "}
                  <span className="font-semibold tabular-nums text-foreground">
                    {titles.totalAcquisitions}
                  </span>
                  건을 벨트{" "}
                  <span className="font-semibold tabular-nums text-foreground">
                    {titles.beltCount}
                  </span>
                  개 · 챔피언{" "}
                  <span className="font-semibold tabular-nums text-foreground">
                    {titles.holderCount}
                  </span>
                  명으로 셌습니다. 폐지된 벨트도 기록에 남아 있어 현역 수보다 많습니다.
                </p>
                <div className="grid gap-3 lg:grid-cols-2">
                  <TitleRankList
                    title="가장 많이 두른 사람"
                    rows={titles.topHolders.slice(0, 5).map((h) => ({
                      key: h.name,
                      href: `/records/${encodeURIComponent(h.name)}`,
                      name: h.name,
                      value: `${h.reigns}회`,
                      note: `벨트 ${h.belts}개`,
                    }))}
                  />
                  <TitleRankList
                    title="가장 많이 주인이 바뀐 벨트"
                    rows={titles.belts.slice(0, 5).map((b) => ({
                      key: b.beltName,
                      name: b.beltName,
                      value: `${b.reigns}회`,
                      note: b.topHolder ? `최다 ${b.topHolder} ${b.topHolderReigns}회` : null,
                    }))}
                  />
                </div>
              </>
            )}
          </section>

          <section aria-labelledby="recent-matches">
            <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
              <h2 id="recent-matches" className="font-sport text-lg text-foreground">
                최근에 무슨 경기가 있었나
              </h2>
              <Link
                href="/data-center/matches"
                className="text-sm font-semibold text-brand-link underline-offset-4 hover:underline"
              >
                경기 전체 보기 →
              </Link>
            </div>
            {overview.recentMatches.length === 0 ? (
              <p className="text-sm text-muted-foreground">아직 끝난 경기가 없습니다.</p>
            ) : (
              <ul className="flex flex-col gap-2">
                {overview.recentMatches.map((match) => (
                  <li key={`${match.eventSlug}-${match.matchKey}`}>
                    <MatchRowCard match={match} />
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section aria-labelledby="top-wrestlers">
            <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
              <h2 id="top-wrestlers" className="font-sport text-lg text-foreground">
                누가 제일 많이 이겼나
              </h2>
              <Link
                href="/data-center/wrestlers"
                className="text-sm font-semibold text-brand-link underline-offset-4 hover:underline"
              >
                선수 전체 보기 →
              </Link>
            </div>
            {!analytics || analytics.topWinRates.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                아직 순위를 낼 만큼 경기가 쌓이지 않았습니다.
              </p>
            ) : (
              <>
                {/*
                 * **분모를 값 옆에 붙인다** (DESIGN.md §14 「표본이 작은 채로 낼 때」).
                 * 「100%」만 적으면 5경기짜리와 50경기짜리가 화면에서 똑같이 생긴다.
                 */}
                <ul className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
                  {analytics.topWinRates.slice(0, 6).map((row, index) => (
                    <li key={row.name}>
                      <Link
                        href={`/records/${encodeURIComponent(row.name)}`}
                        className="flex items-center gap-3 rounded-xl border border-border bg-card px-4 py-3 transition-colors hover:bg-card-2"
                      >
                        <span className="w-5 shrink-0 text-sm font-bold tabular-nums text-muted-foreground">
                          {index + 1}
                        </span>
                        <span className="min-w-0 flex-1 truncate text-sm text-foreground">
                          {row.name}
                        </span>
                        <span className="shrink-0 text-sm font-bold tabular-nums text-foreground">
                          {formatWinRate(row.winRate)}
                        </span>
                        <span className="shrink-0 text-xs tabular-nums text-muted-foreground">
                          ({row.wins}/{row.wins + row.losses})
                        </span>
                      </Link>
                    </li>
                  ))}
                </ul>
                <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
                  판정이 끝난 경기 {analytics.minMatchesForRate}경기 이상만 순위에 올립니다. 지금
                  기준을 넘은 사람은{" "}
                  <span className="tabular-nums">
                    {overview.counts.wrestlers}명 중 {analytics.topWinRates.length}명
                  </span>
                  이고 표본이 한 자릿수라, 순위라기보다 <strong>참고</strong>에 가깝습니다 — 경기가
                  더 쌓이기 전까지는 위의 타이틀 기록이 더 믿을 만합니다.
                </p>
              </>
            )}
          </section>

          <section aria-labelledby="ple-analytics">
            <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
              <h2 id="ple-analytics" className="font-sport text-lg text-foreground">
                대회마다 몇 경기였나
              </h2>
              <Link
                href="/data-center/ple"
                className="text-sm font-semibold text-brand-link underline-offset-4 hover:underline"
              >
                대회 전체 보기 →
              </Link>
            </div>
            {!analytics ? (
              <DataUnavailable what="대회 통계" />
            ) : (
              <ul className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
                {analytics.events.map((event) => (
                  <li
                    key={event.slug}
                    className="rounded-xl border border-border bg-card px-4 py-3"
                  >
                    <p className="truncate text-sm text-foreground">{event.label}</p>
                    <p className="mt-1 text-lg font-bold tabular-nums text-foreground">
                      {event.matches}
                      <span className="ml-1 text-xs font-medium text-muted-foreground">경기</span>
                    </p>
                    <p className="text-xs text-muted-foreground">
                      종료 {event.finished} · 타이틀전 {event.titleMatches}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="rounded-xl border border-data-500/30 bg-data-surface p-5">
            <h2 className="font-sport text-lg text-foreground">그림으로 보고 싶다면</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              브랜드 분포 · 경기 형식 · 타이틀전 비율 · 승률 순위를 차트로 봅니다.
            </p>
            <Link
              href="/data-center/analytics"
              className="mt-4 inline-flex h-9 items-center rounded-lg border border-data-500/50 px-4 text-sm font-semibold text-data transition-colors hover:bg-card-2"
            >
              차트 보기
            </Link>
          </section>
        </div>
      )}
    </DataCenterShell>
  );
}
