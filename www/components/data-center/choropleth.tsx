"use client";

import { useId } from "react";
import type { GeoShape } from "@/lib/geo/us-states-paths";
import { cn } from "@/lib/utils";

/**
 * 단계구분도 — **값이 있는 칸만 칠한다.**
 *
 * 지도 라이브러리를 쓰지 않는다. 투영은 `scripts/build_geo_paths.py`가 빌드
 * 시점에 끝내 두었고 여기서는 `<path>`에 `fill`만 고른다 (DESIGN.md §16 —
 * 새 의존성을 더하지 않는다).
 *
 * **색은 `--chart-seq-1..5` 다섯 단계 고정이다.** 연속 색을 쓰면 1명과 2명이
 * 구분되지 않고, 램프를 즉흥적으로 만들면 §2의 토큰 규칙이 깨진다. 라이트·다크가
 * 서로 다른 값을 쓰는 것도 그 토큰이 이미 해결해 둔 문제다.
 *
 * **색만으로 말하지 않는다.** 범례가 구간을 적고, 각 칸은 `<title>`로 이름과
 * 수를 들고 있어 마우스를 올리거나 스크린 리더로 읽으면 숫자가 나온다 (§16).
 */
type ChoroplethProps = {
  shapes: GeoShape[];
  viewBox: string;
  /** 도형 이름 → 인원. 여기 없는 도형은 "값 없음" 색으로 둔다. */
  values: Map<string, number>;
  /** 범례·툴팁에 쓰는 단위 (기본 "명"). */
  unit?: string;
  className?: string;
};

/** 다섯 단계의 경계값. `max`가 작으면 단계 수가 줄어든다 — 없는 칸을 만들지 않는다. */
export function buildScale(max: number): number[] {
  if (max <= 1) return [1];
  if (max <= 4) return Array.from({ length: max }, (_, i) => i + 1);
  const step = max / 5;
  return [1, 2, 3, 4, 5].map((i) => Math.max(i, Math.round(step * i)));
}

const RAMP = [
  "var(--chart-seq-1)",
  "var(--chart-seq-2)",
  "var(--chart-seq-3)",
  "var(--chart-seq-4)",
  "var(--chart-seq-5)",
];

function colorFor(count: number, scale: number[]): string {
  const index = scale.findIndex((bound) => count <= bound);
  const bucket = index === -1 ? scale.length - 1 : index;
  return RAMP[Math.min(bucket, RAMP.length - 1)];
}

export function Choropleth({ shapes, viewBox, values, unit = "명", className }: ChoroplethProps) {
  const titleId = useId();
  const max = Math.max(0, ...values.values());
  const scale = buildScale(max);

  return (
    <div className={cn("flex flex-col gap-3", className)}>
      <svg
        viewBox={viewBox}
        className="h-auto w-full"
        role="img"
        aria-labelledby={titleId}
        preserveAspectRatio="xMidYMid meet"
      >
        <title id={titleId}>출신 분포 지도</title>
        {shapes.map((shape) => {
          const count = values.get(shape.id);
          return (
            <path
              key={shape.id}
              d={shape.d}
              /* 값이 없는 칸은 **배경보다 아주 조금 밝은 면**이다. 윤곽이
                 보여야 지도로 읽히지만, 데이터가 있는 칸과 헷갈리면 안 된다. */
              fill={count ? colorFor(count, scale) : "var(--surface-2)"}
              stroke="var(--background)"
              strokeWidth={0.6}
              strokeLinejoin="round"
            >
              {count ? <title>{`${shape.name} · ${count}${unit}`}</title> : null}
            </path>
          );
        })}
      </svg>

      <ul className="flex flex-wrap items-center gap-x-3 gap-y-1" aria-label="범례">
        <li className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <span
            className="inline-block size-3 rounded-sm border border-border"
            style={{ background: "var(--surface-2)" }}
            aria-hidden
          />
          없음
        </li>
        {scale.map((bound, i) => {
          const low = i === 0 ? 1 : scale[i - 1] + 1;
          return (
            <li
              key={bound}
              className="flex items-center gap-1.5 text-xs tabular-nums text-muted-foreground"
            >
              <span
                className="inline-block size-3 rounded-sm"
                style={{ background: RAMP[Math.min(i, RAMP.length - 1)] }}
                aria-hidden
              />
              {low === bound ? bound : `${low}–${bound}`}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
