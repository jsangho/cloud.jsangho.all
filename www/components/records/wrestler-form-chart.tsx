"use client";

import { Bar, BarChart, ResponsiveContainer } from "recharts";
import {
  CHART_COLORS,
  ChartFrame,
  ChartGrid,
  ChartLegend,
  ChartTooltip,
  ChartXAxis,
  ChartYAxis,
} from "@/components/charts/chart-theme";
import type { CompetitorMatchRecord } from "@/lib/records-api";

/**
 * 선수 상세의 PLE별 성적 (Phase 2 §6).
 *
 * **데이터가 얇으면 아예 안 그린다.** 대회 하나짜리 막대 그래프는 성적이 아니라
 * 장식이다 — 판정이 끝난 대회가 둘 미만이면 `null`을 돌려준다.
 *
 * 색은 `--chart-win` / `--chart-loss`이고, 색각 이상에서 이 짝은 붙기 때문에
 * (검증기 ΔE 6.5) **범례와 툴팁이 글자를 함께 단다** — DESIGN.md §2의 사용 조건이다.
 */
type EventRow = { name: string; 승: number; 패: number };

function toRows(matches: CompetitorMatchRecord[]): EventRow[] {
  const byEvent = new Map<string, EventRow>();
  for (const match of matches) {
    if (match.result !== "win" && match.result !== "loss") continue;
    const row = byEvent.get(match.pleLabel) ?? { name: match.pleLabel, 승: 0, 패: 0 };
    if (match.result === "win") row.승 += 1;
    else row.패 += 1;
    byEvent.set(match.pleLabel, row);
  }
  return [...byEvent.values()];
}

export function WrestlerFormChart({ matches }: { matches: CompetitorMatchRecord[] }) {
  const rows = toRows(matches);
  if (rows.length < 2) return null;

  const decided = rows.reduce((sum, row) => sum + row.승 + row.패, 0);

  return (
    <ChartFrame
      title="PLE별 성적"
      description="판정이 끝난 경기만 셉니다 (무효·대기 제외)."
      note={`대회 ${rows.length}개 · 경기 ${decided}건 기준입니다.`}
    >
      <div className="min-w-[26rem]">
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={rows} margin={{ top: 8, right: 8, bottom: 8, left: 0 }}>
            <ChartGrid />
            <ChartXAxis dataKey="name" interval={0} angle={-15} textAnchor="end" height={52} />
            <ChartYAxis allowDecimals={false} />
            <ChartTooltip unit="경기" />
            <ChartLegend />
            <Bar
              dataKey="승"
              stackId="record"
              fill={CHART_COLORS.win}
              stroke="var(--card)"
              strokeWidth={2}
            />
            <Bar
              dataKey="패"
              stackId="record"
              fill={CHART_COLORS.loss}
              stroke="var(--card)"
              strokeWidth={2}
              radius={[4, 4, 0, 0]}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </ChartFrame>
  );
}
