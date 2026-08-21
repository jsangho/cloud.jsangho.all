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
  fetchDataCenterAnalytics,
  fetchDataCenterOverview,
  formatWinRate,
  type DataCenterAnalytics,
  type DataCenterOverview,
} from "@/lib/data-center-api";

/**
 * 데이터 센터 개요 (Phase 2 §4).
 *
 * KPI → 최근 경기 → 주요 선수 → PLE 분석 → Analytics로 가는 CTA.
 * **모든 숫자는 DB에서 센 값이다** — 못 받으면 그 구역을 비운다.
 */
export default function DataCenterPage() {
  const [overview, setOverview] = useState<DataCenterOverview | null>(null);
  const [analytics, setAnalytics] = useState<DataCenterAnalytics | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      const [o, a] = await Promise.all([fetchDataCenterOverview(), fetchDataCenterAnalytics()]);
      if (cancelled) return;
      setOverview(o);
      setAnalytics(a);
      setLoading(false);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <DataCenterShell
      title="Overview"
      description="KAYFABE가 실제로 들고 있는 데이터입니다. 선수·경기·대회·챔피언십을 DB에서 직접 셉니다."
    >
      {loading ? (
        <LoadingBlock rows={4} />
      ) : !overview ? (
        <DataUnavailable what="데이터 센터 요약" />
      ) : (
        <div className="flex flex-col gap-8">
          <section aria-label="핵심 수치">
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
              <StatTile value={overview.counts.wrestlers} label="Wrestlers" note="DB 등록" />
              <StatTile
                value={overview.counts.matches}
                label="Matches"
                note={`종료 ${overview.counts.finishedMatches}`}
              />
              <StatTile
                value={overview.counts.events}
                label="PLE Events"
                note={`종료 ${overview.counts.finishedEvents}`}
              />
              <StatTile
                value={overview.counts.championshipBelts}
                label="Championships"
                note={`획득 기록 ${overview.counts.titleAcquisitions}`}
                tone="gold"
              />
            </div>
          </section>

          <section aria-labelledby="recent-matches">
            <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
              <h2 id="recent-matches" className="font-sport text-lg text-foreground">
                최근 경기
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
                승률 상위
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
                          {row.wins}승 {row.losses}패
                        </span>
                      </Link>
                    </li>
                  ))}
                </ul>
                <p className="mt-2 text-xs text-muted-foreground">
                  판정이 끝난 경기 {analytics.minMatchesForRate}경기 이상만 순위에 올립니다 — 한두
                  경기짜리 100%를 위에 세우지 않기 위해서입니다.
                </p>
              </>
            )}
          </section>

          <section aria-labelledby="ple-analytics">
            <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
              <h2 id="ple-analytics" className="font-sport text-lg text-foreground">
                대회별 경기 수
              </h2>
              <Link
                href="/data-center/ple"
                className="text-sm font-semibold text-brand-link underline-offset-4 hover:underline"
              >
                PLE 데이터 보기 →
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
            <h2 className="font-sport text-lg text-foreground">Analytics</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              브랜드 분포 · 경기 형식 · 타이틀전 비율 · 승률 순위를 차트로 봅니다.
            </p>
            <Link
              href="/data-center/analytics"
              className="mt-4 inline-flex h-9 items-center rounded-lg border border-data-500/50 px-4 text-sm font-semibold text-data transition-colors hover:bg-card-2"
            >
              분석 보기
            </Link>
          </section>
        </div>
      )}
    </DataCenterShell>
  );
}
