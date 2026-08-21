"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Bar, BarChart, Cell, ResponsiveContainer } from "recharts";
import {
  DataCenterShell,
  DataUnavailable,
  LoadingBlock,
} from "@/components/data-center/data-center-shell";
import {
  CHART_COLORS,
  ChartFrame,
  ChartGrid,
  ChartTooltip,
  ChartXAxis,
  ChartYAxis,
  seriesColor,
} from "@/components/charts/chart-theme";
import {
  fetchDataCenterAnalytics,
  formatWinRate,
  type DataCenterAnalytics,
} from "@/lib/data-center-api";

/**
 * 분석 (Phase 2 §10).
 *
 * **지금 데이터로 실제 계산되는 것만 그린다.** 연도별 추이는 없다 — 대회가 전부
 * 2026년이라 점이 하나뿐이고, 한 점짜리 선그래프는 추이가 아니라 장식이다.
 */
export default function DataCenterAnalyticsPage() {
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

  if (loading) {
    return (
      <DataCenterShell title="Analytics">
        <LoadingBlock rows={4} />
      </DataCenterShell>
    );
  }

  if (!analytics) {
    return (
      <DataCenterShell title="Analytics">
        <DataUnavailable what="분석 데이터" />
      </DataCenterShell>
    );
  }

  const totalMatches = analytics.singlesMatches + analytics.multiMatches;
  const brandData = analytics.brands.map((b) => ({ name: b.brand, 선수: b.wrestlers }));
  const rateData = analytics.topWinRates.map((r) => ({
    name: r.name,
    승률: Math.round(r.winRate * 100),
    wins: r.wins,
    losses: r.losses,
  }));

  return (
    <DataCenterShell
      title="Analytics"
      description="DB에 있는 것만 셉니다. 표본이 얇은 지표는 순위에서 빼고, 없는 축은 그리지 않습니다."
    >
      <div className="flex flex-col gap-6">
        <ChartFrame
          title="브랜드별 선수 분포"
          description="wrestlers 테이블의 brand 값을 그대로 셉니다."
          note={`선수 ${analytics.brands.reduce((s, b) => s + b.wrestlers, 0)}명 기준.`}
        >
          <div className="min-w-[30rem]">
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={brandData} margin={{ top: 8, right: 8, bottom: 8, left: 0 }}>
                <ChartGrid />
                <ChartXAxis dataKey="name" />
                <ChartYAxis allowDecimals={false} />
                <ChartTooltip unit="명" />
                <Bar dataKey="선수" radius={[4, 4, 0, 0]}>
                  {brandData.map((entry, index) => (
                    <Cell key={entry.name} fill={seriesColor(index)} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </ChartFrame>

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <SplitCard
            title="경기 형식"
            left={{ label: "싱글", value: analytics.singlesMatches, color: seriesColor(0) }}
            right={{ label: "다인전", value: analytics.multiMatches, color: seriesColor(2) }}
            total={totalMatches}
          />
          <SplitCard
            title="타이틀전 비율"
            left={{
              label: "타이틀전",
              value: analytics.titleMatches,
              color: CHART_COLORS.user,
            }}
            right={{
              label: "일반",
              value: analytics.nonTitleMatches,
              color: seriesColor(0),
            }}
            total={totalMatches}
          />
        </div>

        {rateData.length === 0 ? (
          <section className="rounded-xl border border-dashed border-border px-4 py-8 text-center">
            <p className="text-sm text-muted-foreground">
              승률 순위를 낼 만큼 판정된 경기가 아직 없습니다.
            </p>
          </section>
        ) : (
          <ChartFrame
            title="승률 상위"
            description="승 / (승+패). 무효·미판정 경기는 분모에서 뺍니다."
            note={`판정 ${analytics.minMatchesForRate}경기 이상만 올립니다 — 한두 경기짜리 100%를 위에 세우지 않기 위해서입니다.`}
          >
            <div className="min-w-[30rem]">
              <ResponsiveContainer width="100%" height={Math.max(220, rateData.length * 34)}>
                <BarChart
                  data={rateData}
                  layout="vertical"
                  margin={{ top: 4, right: 16, bottom: 4, left: 0 }}
                >
                  <ChartGrid vertical />
                  <ChartXAxis type="number" domain={[0, 100]} unit="%" />
                  <ChartYAxis type="category" dataKey="name" width={110} />
                  <ChartTooltip unit="%" />
                  <Bar dataKey="승률" fill={CHART_COLORS.win} radius={[0, 4, 4, 0]} barSize={14} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </ChartFrame>
        )}

        <section aria-labelledby="rate-table">
          <h2 id="rate-table" className="mb-3 font-sport text-lg text-foreground">
            승률 표
          </h2>
          {/* 차트 옆에 **표를 함께 둔다** — 색을 못 읽는 경우에도 값이 남아야 한다. */}
          <div className="overflow-x-auto rounded-xl border border-border">
            <table className="w-full min-w-[28rem] border-collapse text-sm">
              <thead>
                <tr className="bg-card-2 text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="px-4 py-2 font-medium">선수</th>
                  <th className="px-4 py-2 text-right font-medium">승</th>
                  <th className="px-4 py-2 text-right font-medium">패</th>
                  <th className="px-4 py-2 text-right font-medium">승률</th>
                </tr>
              </thead>
              <tbody>
                {analytics.topWinRates.map((row) => (
                  <tr key={row.name} className="border-t border-border bg-card">
                    <td className="px-4 py-2">
                      <Link
                        href={`/records/${encodeURIComponent(row.name)}`}
                        className="text-foreground underline-offset-4 hover:underline"
                      >
                        {row.name}
                      </Link>
                    </td>
                    <td className="px-4 py-2 text-right tabular-nums text-foreground">
                      {row.wins}
                    </td>
                    <td className="px-4 py-2 text-right tabular-nums text-muted-foreground">
                      {row.losses}
                    </td>
                    <td className="px-4 py-2 text-right font-semibold tabular-nums text-foreground">
                      {formatWinRate(row.winRate)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <p className="text-xs text-muted-foreground">
          연도별 추이는 만들지 않았습니다 — 지금 DB의 대회가 전부{" "}
          {analytics.events[0]?.year ?? 2026}
          년이라 점이 하나뿐이고, 한 점짜리 선그래프는 추이가 아니라 장식입니다.
        </p>
      </div>
    </DataCenterShell>
  );
}

/** 두 갈래 비율 한 칸 — 막대 하나 + 숫자. **원형 차트를 쓰지 않는다** (§16). */
function SplitCard({
  title,
  left,
  right,
  total,
}: {
  title: string;
  left: { label: string; value: number; color: string };
  right: { label: string; value: number; color: string };
  total: number;
}) {
  const leftPct = total > 0 ? Math.round((left.value / total) * 100) : 0;

  return (
    <section className="rounded-xl border border-border bg-card p-4 sm:p-5">
      <h3 className="font-sport text-base text-foreground">{title}</h3>
      <div className="mt-3 flex h-3 w-full overflow-hidden rounded-full bg-card-2">
        <div style={{ width: `${leftPct}%`, background: left.color }} />
        {/* 두 칸 사이 2px 표면 간격 (§16). */}
        <div className="w-0.5 shrink-0 bg-card" />
        <div style={{ width: `${100 - leftPct}%`, background: right.color }} />
      </div>
      <dl className="mt-3 flex flex-wrap gap-x-6 gap-y-1 text-sm">
        <div className="flex items-center gap-2">
          <span
            aria-hidden
            className="inline-block size-2 rounded-[2px]"
            style={{ background: left.color }}
          />
          <dt className="text-muted-foreground">{left.label}</dt>
          <dd className="font-bold tabular-nums text-foreground">{left.value}</dd>
        </div>
        <div className="flex items-center gap-2">
          <span
            aria-hidden
            className="inline-block size-2 rounded-[2px]"
            style={{ background: right.color }}
          />
          <dt className="text-muted-foreground">{right.label}</dt>
          <dd className="font-bold tabular-nums text-foreground">{right.value}</dd>
        </div>
      </dl>
    </section>
  );
}
