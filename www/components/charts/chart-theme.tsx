"use client";

import type { ReactNode } from "react";
import { CartesianGrid, Legend, Tooltip, XAxis, YAxis } from "recharts";
import { cn } from "@/lib/utils";

/**
 * 공용 차트 스타일 (KAYFABE 2.0 Phase 2 · DESIGN.md §16).
 *
 * **색을 여기서 새로 만들지 않는다.** 전부 Phase 0의 `--chart-*` 토큰을 가리키고,
 * 그 토큰은 다크·라이트 두 표면에서 검증기를 통과한 값이다. 화면마다 hex를 적기
 * 시작하면 그 검증이 무의미해진다.
 *
 * `/admin`의 목업 차트(하드코딩 레드·인라인 툴팁 스타일)를 베끼지 않는다 —
 * 그건 가짜 데이터를 그리던 자리이고, 스타일도 토큰 이전 것이다.
 */

/** 계열 색. **순서가 고정이다** — 계열이 줄어도 색이 사람을 따라간다. */
export const CHART_SERIES = [
  "var(--chart-1)",
  "var(--chart-2)",
  "var(--chart-3)",
  "var(--chart-4)",
  "var(--chart-5)",
  "var(--chart-6)",
] as const;

export const CHART_COLORS = {
  ai: "var(--chart-ai)",
  user: "var(--chart-user)",
  win: "var(--chart-win)",
  loss: "var(--chart-loss)",
  pending: "var(--chart-pending)",
  grid: "var(--chart-grid)",
} as const;

/** 일곱 번째 계열은 새 색을 만들지 않고 순서를 돈다 — 그 전에 "기타"로 접는 게 맞다. */
export function seriesColor(index: number): string {
  return CHART_SERIES[index % CHART_SERIES.length];
}

const AXIS_TICK = {
  fill: "var(--muted-foreground)",
  fontSize: 11,
} as const;

/** 축 — 물러나 있는다. 선은 지우고 눈금 글자만 남긴다. */
export const axisProps = {
  tick: AXIS_TICK,
  tickLine: false,
  axisLine: false,
  stroke: "var(--chart-grid)",
} as const;

export function ChartGrid({ vertical = false }: { vertical?: boolean }) {
  return <CartesianGrid stroke={CHART_COLORS.grid} strokeDasharray="3 3" vertical={vertical} />;
}

export function ChartXAxis(props: Record<string, unknown>) {
  return <XAxis {...axisProps} {...props} />;
}

export function ChartYAxis(props: Record<string, unknown>) {
  return <YAxis {...axisProps} width={36} {...props} />;
}

type TooltipEntry = {
  name?: unknown;
  /** Recharts는 배열도 넘길 수 있어 넓게 받고 화면에서 좁힌다. */
  value?: unknown;
  color?: string;
  dataKey?: unknown;
};

function toText(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (Array.isArray(value)) return value.map(toText).join(" ~ ");
  return String(value);
}

/**
 * 툴팁 — **글자는 잉크 토큰**이고, 계열 색은 옆의 점이 든다 (§16).
 * 값을 계열 색으로 칠하면 대비가 계열마다 달라져 어떤 줄은 안 읽힌다.
 */
function TooltipBody({
  active,
  payload,
  label,
  unit,
}: {
  active?: boolean;
  payload?: TooltipEntry[];
  label?: string | number;
  unit?: string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-border bg-card px-3 py-2 text-xs shadow-none">
      {label !== undefined && <p className="mb-1 font-semibold text-foreground">{String(label)}</p>}
      <ul className="flex flex-col gap-0.5">
        {payload.map((entry, index) => (
          <li key={`${toText(entry.dataKey) || index}`} className="flex items-center gap-2">
            <span
              aria-hidden
              className="inline-block size-2 shrink-0 rounded-[2px]"
              style={{ background: entry.color }}
            />
            <span className="text-muted-foreground">{toText(entry.name)}</span>
            <span className="ml-auto tabular-nums text-foreground">
              {toText(entry.value)}
              {unit ?? ""}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function ChartTooltip({ unit }: { unit?: string } = {}) {
  return (
    <Tooltip
      cursor={{ fill: "var(--chart-grid)" }}
      content={(props) => (
        <TooltipBody
          active={props.active}
          payload={props.payload as TooltipEntry[] | undefined}
          label={props.label as string | number | undefined}
          unit={unit}
        />
      )}
    />
  );
}

/** 범례 — 계열이 둘 이상이면 **항상** 있다 (색만으로 정체를 말하지 않는다). */
export function ChartLegend() {
  return (
    <Legend
      verticalAlign="bottom"
      height={28}
      iconType="square"
      iconSize={9}
      formatter={(value) => <span className="text-xs text-muted-foreground">{String(value)}</span>}
    />
  );
}

/**
 * 차트 한 장의 액자 — 제목·설명·표본 각주를 같은 자리에 세운다.
 *
 * **표본 수를 적을 자리를 강제한다** (`note`). 68경기짜리 데이터에서 숫자만 크게 걸면
 * 실제보다 단단해 보인다.
 */
export function ChartFrame({
  title,
  description,
  note,
  children,
  className,
}: {
  title: string;
  description?: string;
  note?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={cn("rounded-xl border border-border bg-card p-4 sm:p-5", className)}>
      <header className="mb-3">
        <h3 className="font-sport text-base text-foreground">{title}</h3>
        {description && <p className="mt-0.5 text-xs text-muted-foreground">{description}</p>}
      </header>
      {/* 넓은 차트는 **자기 안에서** 가로로 스크롤한다 — 페이지가 밀리면 안 된다. */}
      <div className="w-full overflow-x-auto">{children}</div>
      {note && <p className="mt-2 text-xs text-muted-foreground">{note}</p>}
    </section>
  );
}
