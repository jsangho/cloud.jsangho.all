"use client";

import { useId, useState } from "react";
import type { GeoShape } from "@/lib/geo/us-states-paths";
import { cn } from "@/lib/utils";

/**
 * 단계구분도 — **값이 있는 칸만 칠하고, 그 칸만 누를 수 있다.**
 *
 * 지도 라이브러리를 쓰지 않는다. 투영은 `scripts/build_geo_paths.py`가 빌드
 * 시점에 끝내 두었고 여기서는 `<path>`에 `fill`만 고른다 (DESIGN.md §16 —
 * 새 의존성을 더하지 않는다).
 *
 * **색은 `--chart-seq-1..5` 다섯 단계 고정이다.** 연속 색을 쓰면 1명과 2명이
 * 구분되지 않고, 램프를 즉흥적으로 만들면 §2의 토큰 규칙이 깨진다.
 *
 * **색만으로 말하지 않는다.** 범례가 구간을 적고, 올리면 이름이 뜨고, 누르면
 * 명단이 고정된다. 값이 없는 칸은 아예 상호작용하지 않는다 — 누를 수 있는
 * 것처럼 보이는데 아무 일도 안 일어나는 쪽이 더 나쁘다.
 */
type ChoroplethProps = {
  shapes: GeoShape[];
  viewBox: string;
  /** 도형 이름 → 인원. 여기 없는 도형은 "값 없음" 색으로 둔다. */
  values: Map<string, number>;
  /** 도형 이름 → 그 지역 사람들. 올렸을 때 미리보기로 몇 명 보여 준다. */
  members?: Map<string, string[]>;
  /** 고정된 선택. 지도 밖(목록)에서 고른 것도 여기로 들어온다. */
  selected?: string | null;
  onSelect?: (shapeId: string | null) => void;
  unit?: string;
  className?: string;
};

/** 호버 미리보기에 적는 최대 인원. 넘으면 "외 N명"으로 접는다. */
const PREVIEW_LIMIT = 5;

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

type Hover = { id: string; x: number; y: number };

export function Choropleth({
  shapes,
  viewBox,
  values,
  members,
  selected = null,
  onSelect,
  unit = "명",
  className,
}: ChoroplethProps) {
  const titleId = useId();
  const [hover, setHover] = useState<Hover | null>(null);
  const max = Math.max(0, ...values.values());
  const scale = buildScale(max);

  const hoverNames = hover ? (members?.get(hover.id) ?? []) : [];

  return (
    <div className={cn("relative flex flex-col gap-3", className)}>
      <svg
        viewBox={viewBox}
        className="h-auto w-full"
        role="img"
        aria-labelledby={titleId}
        preserveAspectRatio="xMidYMid meet"
        onMouseLeave={() => setHover(null)}
      >
        <title id={titleId}>출신 분포 지도</title>
        {shapes.map((shape) => {
          const count = values.get(shape.id);
          const isSelected = selected === shape.id;
          return (
            <path
              key={shape.id}
              d={shape.d}
              /* 값이 없는 칸은 **배경보다 아주 조금 밝은 면**이다. 윤곽이
                 보여야 지도로 읽히지만, 데이터가 있는 칸과 헷갈리면 안 된다. */
              fill={count ? colorFor(count, scale) : "var(--surface-2)"}
              stroke={isSelected ? "var(--foreground)" : "var(--background)"}
              strokeWidth={isSelected ? 2.4 : 0.6}
              strokeLinejoin="round"
              className={count ? "cursor-pointer outline-none" : undefined}
              tabIndex={count ? 0 : undefined}
              role={count ? "button" : undefined}
              aria-label={count ? `${shape.name} ${count}${unit}` : undefined}
              onMouseMove={
                count
                  ? (event) => {
                      const box = event.currentTarget.ownerSVGElement?.getBoundingClientRect();
                      setHover({
                        id: shape.id,
                        x: event.clientX - (box?.left ?? 0),
                        y: event.clientY - (box?.top ?? 0),
                      });
                    }
                  : undefined
              }
              onClick={count ? () => onSelect?.(isSelected ? null : shape.id) : undefined}
              onKeyDown={
                count
                  ? (event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        onSelect?.(isSelected ? null : shape.id);
                      }
                    }
                  : undefined
              }
            >
              {count ? <title>{`${shape.name} · ${count}${unit}`}</title> : null}
            </path>
          );
        })}
      </svg>

      {hover && (
        /* 포인터를 따라다니는 미리보기. **고정 패널과 내용이 겹치지만 역할이
           다르다** — 이쪽은 "여기 누구 있나"를 훑는 용도라 몇 명만 적는다. */
        <div
          className="pointer-events-none absolute z-10 max-w-56 rounded-lg border border-border bg-card px-3 py-2 text-xs shadow-lg"
          style={{
            left: `min(${hover.x + 12}px, calc(100% - 15rem))`,
            top: Math.max(0, hover.y - 8),
          }}
          role="presentation"
        >
          <p className="font-semibold text-foreground">
            {hover.id} · {values.get(hover.id)}
            {unit}
          </p>
          {hoverNames.length > 0 && (
            <p className="mt-1 text-muted-foreground">
              {hoverNames.slice(0, PREVIEW_LIMIT).join(" · ")}
              {hoverNames.length > PREVIEW_LIMIT && ` 외 ${hoverNames.length - PREVIEW_LIMIT}명`}
            </p>
          )}
          <p className="mt-1 text-[11px] text-muted-foreground">누르면 전체 명단</p>
        </div>
      )}

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
