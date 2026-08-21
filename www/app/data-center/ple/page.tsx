"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Bar, BarChart, ResponsiveContainer } from "recharts";
import {
  DataCenterShell,
  DataUnavailable,
  LoadingBlock,
  StatTile,
} from "@/components/data-center/data-center-shell";
import {
  CHART_COLORS,
  ChartFrame,
  ChartGrid,
  ChartLegend,
  ChartTooltip,
  ChartXAxis,
  ChartYAxis,
  seriesColor,
} from "@/components/charts/chart-theme";
import { fetchDataCenterAnalytics, type DataCenterAnalytics } from "@/lib/data-center-api";

/**
 * PLE 데이터 (Phase 2 §8).
 *
 * **예측 화면과 역할이 다르다.** `/ple`은 예측하러 가는 곳이고 여기는 대회를
 * 데이터로 보는 곳이다 — 예측 로직은 한 줄도 건드리지 않는다.
 */
export default function DataCenterPlePage() {
  const [analytics, setAnalytics] = useState<DataCenterAnalytics | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      const data = await fetchDataCenterAnalytics();
      if (cancelled) return;
      setAnalytics(data);
      setLoading(false);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const totalMatches = analytics?.events.reduce((sum, e) => sum + e.matches, 0) ?? 0;
  const totalFinished = analytics?.events.reduce((sum, e) => sum + e.finished, 0) ?? 0;
  const chartData =
    analytics?.events.map((event) => ({
      name: event.label,
      타이틀전: event.titleMatches,
      일반: event.matches - event.titleMatches,
    })) ?? [];

  return (
    <DataCenterShell
      title="PLE Events"
      description="대회별 경기 수와 구성입니다. 예측은 PLE 예측 화면에서 하고, 여기서는 데이터만 봅니다."
    >
      {loading ? (
        <LoadingBlock rows={3} />
      ) : !analytics ? (
        <DataUnavailable what="대회 데이터" />
      ) : (
        <div className="flex flex-col gap-6">
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <StatTile value={analytics.events.length} label="Events" />
            <StatTile value={totalMatches} label="Matches" />
            <StatTile value={totalFinished} label="Finished" />
            <StatTile value={analytics.titleMatches} label="Title Matches" tone="gold" />
          </div>

          <ChartFrame
            title="대회별 경기 구성"
            description="타이틀전과 일반 경기를 나눠 쌓았습니다."
            note={`대회 ${analytics.events.length}개 · 경기 ${totalMatches}건 기준입니다.`}
          >
            <div className="min-w-[34rem]">
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={chartData} margin={{ top: 8, right: 8, bottom: 8, left: 0 }}>
                  <ChartGrid />
                  <ChartXAxis
                    dataKey="name"
                    interval={0}
                    angle={-20}
                    textAnchor="end"
                    height={62}
                  />
                  <ChartYAxis allowDecimals={false} />
                  <ChartTooltip unit="경기" />
                  <ChartLegend />
                  {/* 쌓은 칸 사이에 2px 표면 간격을 둔다 (DESIGN.md §16). */}
                  <Bar
                    dataKey="타이틀전"
                    stackId="matches"
                    fill={seriesColor(1)}
                    stroke="var(--card)"
                    strokeWidth={2}
                  />
                  <Bar
                    dataKey="일반"
                    stackId="matches"
                    fill={seriesColor(0)}
                    stroke="var(--card)"
                    strokeWidth={2}
                    radius={[4, 4, 0, 0]}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </ChartFrame>

          <section aria-labelledby="event-table">
            <h2 id="event-table" className="mb-3 font-sport text-lg text-foreground">
              대회 목록
            </h2>
            <ul className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {analytics.events.map((event) => (
                <li key={event.slug}>
                  <div className="flex h-full flex-col gap-2 rounded-xl border border-border bg-card p-4">
                    <div className="flex items-start justify-between gap-2">
                      <span className="min-w-0 truncate font-sport text-lg text-foreground">
                        {event.label}
                      </span>
                      <span className="shrink-0 text-xs tabular-nums text-muted-foreground">
                        {event.year}
                        {event.month ? `.${String(event.month).padStart(2, "0")}` : ""}
                      </span>
                    </div>
                    <dl className="grid grid-cols-3 gap-2 text-center">
                      <div>
                        <dd className="text-lg font-bold tabular-nums text-foreground">
                          {event.matches}
                        </dd>
                        <dt className="text-[11px] text-muted-foreground">경기</dt>
                      </div>
                      <div>
                        <dd className="text-lg font-bold tabular-nums text-foreground">
                          {event.finished}
                        </dd>
                        <dt className="text-[11px] text-muted-foreground">종료</dt>
                      </div>
                      <div>
                        <dd
                          className="text-lg font-bold tabular-nums"
                          style={{ color: CHART_COLORS.user }}
                        >
                          {event.titleMatches}
                        </dd>
                        <dt className="text-[11px] text-muted-foreground">타이틀전</dt>
                      </div>
                    </dl>
                    <div className="mt-auto flex flex-wrap gap-x-3 text-xs">
                      <Link
                        href={`/data-center/matches?event=${event.slug}`}
                        className="font-semibold text-brand-link underline-offset-4 hover:underline"
                      >
                        경기 보기 →
                      </Link>
                      <Link
                        href={`/ple/${event.slug}`}
                        className="text-muted-foreground underline-offset-4 hover:underline"
                      >
                        예측 화면
                      </Link>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          </section>
        </div>
      )}
    </DataCenterShell>
  );
}
