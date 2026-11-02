"use client";

import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/**
 * 커리어 화면 여섯 탭이 공유하는 표면 조각. **값을 계산하지 않는다** — 받은 것만
 * 그린다. 여기에 파생 로직이 들어가기 시작하면 탭마다 다른 숫자가 나온다.
 *
 * **다크 아레나 전용이다.** 클래스 `arena-*` 는 `.career-arena` 아래에서만 정의된다
 * (`app/globals.css` — DESIGN.md 예외). 이 조각을 다른 페이지에서 쓰면 금속 테두리와
 * 조명이 빠진 평평한 상자로 보인다.
 */
export function Stat({
  label,
  value,
  tone,
  sub,
}: {
  label: string;
  value: string;
  tone?: "warn";
  /** 값 아래 한 줄 — 단위·근거. */
  sub?: string;
}) {
  return (
    <div className="arena-panel px-3 py-2.5">
      <div className="text-[11px] font-semibold uppercase tracking-wider text-stone-400">
        {label}
      </div>
      <div
        className={cn(
          "mt-1 text-lg font-bold leading-tight tabular-nums",
          tone === "warn" ? "text-live" : "text-stone-50",
        )}
      >
        {value}
      </div>
      {sub ? <div className="mt-0.5 text-[11px] text-stone-400">{sub}</div> : null}
    </div>
  );
}

export function Panel({
  title,
  hint,
  action,
  tone,
  className,
  children,
}: {
  title: string;
  hint?: string;
  action?: ReactNode;
  /** `alert` 는 레드 조명 — 결정이 필요한 사건에만 쓴다. */
  tone?: "alert";
  className?: string;
  children: ReactNode;
}) {
  return (
    <section className={cn("arena-panel p-4", tone === "alert" && "arena-panel-alert", className)}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="arena-eyebrow">{title}</h3>
        {action}
      </div>
      <div className="mt-3">{children}</div>
      {hint ? <p className="mt-3 text-[11px] leading-relaxed text-stone-400">{hint}</p> : null}
    </section>
  );
}

export function SectionTitle({ children, aside }: { children: ReactNode; aside?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-white/10 pb-2">
      <h2 className="font-sport text-xl uppercase tracking-wide text-stone-50">{children}</h2>
      {aside}
    </div>
  );
}

/** 패널 머리 오른쪽의 이동 링크. 골드 링크 단계(`--brand-link`)를 쓴다. */
export function PanelLink({ children, onClick }: { children: ReactNode; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="text-[11px] font-semibold uppercase tracking-wider text-brand-link transition-colors hover:text-brand-300"
    >
      {children} →
    </button>
  );
}

/**
 * 빈 상태. **로딩과 다른 문구를 쓴다**(사용자 요구 §7 — "로딩, 오류, 빈 상태를
 * 구분한다"). 없는 데이터를 가짜로 채우는 자리가 바로 여기라서, 이 컴포넌트는
 * 숫자를 받지 않는다.
 */
export function Empty({ children }: { children: ReactNode }) {
  return (
    <p className="rounded-lg border border-dashed border-white/12 px-3 py-4 text-center text-xs text-stone-400">
      {children}
    </p>
  );
}

export function Loading({ children = "불러오는 중…" }: { children?: ReactNode }) {
  return (
    <p className="animate-pulse rounded-lg border border-dashed border-white/12 px-3 py-4 text-center text-xs text-stone-400 motion-reduce:animate-none">
      {children}
    </p>
  );
}

/**
 * 가로 미터. `value / max` 를 그대로 칠한다 — **값을 만들지 않는다.**
 * 숫자는 옆에 따로 적어야 한다(색만으로 말하지 않는다).
 */
export function Meter({
  value,
  max,
  tone,
  label,
}: {
  value: number;
  max: number;
  tone?: "live" | "win";
  /** 스크린리더용 이름. */
  label: string;
}) {
  const pct = max > 0 ? Math.max(0, Math.min(100, (value / max) * 100)) : 0;
  return (
    <div
      className="arena-meter"
      data-tone={tone}
      role="meter"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={max}
      aria-valuenow={value}
    >
      <span style={{ width: `${pct}%` }} />
    </div>
  );
}

/** 원형 게이지 — 능력치 하나(1~100). 숫자가 가운데에 함께 선다. */
export function RingGauge({
  value,
  max = 100,
  label,
  size = 76,
}: {
  value: number;
  max?: number;
  label: string;
  size?: number;
}) {
  const stroke = 6;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const pct = max > 0 ? Math.max(0, Math.min(1, value / max)) : 0;
  const id = `ring-${label}`;
  return (
    <div className="flex flex-col items-center gap-1.5">
      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        role="img"
        aria-label={`${label} ${value}`}
      >
        <defs>
          <linearGradient id={id} x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="var(--brand-200)" />
            <stop offset="100%" stopColor="var(--brand-600)" />
          </linearGradient>
        </defs>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="rgba(255,255,255,0.08)"
          strokeWidth={stroke}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={`url(#${id})`}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={`${c * pct} ${c}`}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
        />
        <text
          x="50%"
          y="50%"
          dominantBaseline="central"
          textAnchor="middle"
          className="fill-stone-50 text-[20px] font-bold tabular-nums"
        >
          {value}
        </text>
      </svg>
      <span className="text-[11px] font-semibold uppercase tracking-wider text-stone-400">
        {label}
      </span>
    </div>
  );
}

/**
 * 선수 엠블럼 — **사진이 없다.** 세계의 선수는 가상이고 저작권 있는 이미지를 쓰지
 * 않는다. 이니셜과 링 로프 무늬로 사람을 구별한다.
 */
export function Emblem({
  name,
  size = 44,
  tone = "gold",
}: {
  name: string;
  size?: number;
  tone?: "gold" | "live";
}) {
  const initials =
    name
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0])
      .join("")
      .toUpperCase() || "?";
  return (
    <span
      aria-hidden
      className={cn(
        "relative inline-flex shrink-0 items-center justify-center rounded-full font-sport font-semibold text-stone-50",
        tone === "gold"
          ? "bg-[radial-gradient(circle_at_30%_25%,rgba(252,187,0,0.45),rgba(20,20,24,0.95)_70%)] ring-1 ring-brand-400/60"
          : "bg-[radial-gradient(circle_at_30%_25%,rgba(230,57,70,0.5),rgba(20,20,24,0.95)_70%)] ring-1 ring-live/60",
      )}
      style={{ width: size, height: size, fontSize: size * 0.38 }}
    >
      {initials}
    </span>
  );
}

export type FilterOption<T extends string> = { value: T; label: string; count?: number };

/** 필터 pill 한 줄. 모바일에서는 가로로 스크롤된다. */
export function FilterChips<T extends string>({
  options,
  value,
  onChange,
  label,
}: {
  options: readonly FilterOption<T>[];
  value: T;
  onChange: (next: T) => void;
  label: string;
}) {
  return (
    <div
      role="group"
      aria-label={label}
      className="-mx-1 flex gap-1.5 overflow-x-auto px-1 pb-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
    >
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          onClick={() => onChange(option.value)}
          aria-pressed={option.value === value}
          className={cn(
            "shrink-0 rounded-full border px-3 py-1 text-xs font-semibold transition-colors",
            option.value === value
              ? "border-brand-400/70 bg-brand-400/15 text-brand-300"
              : "border-white/10 bg-white/[0.03] text-stone-400 hover:bg-white/[0.07]",
          )}
        >
          {option.label}
          {option.count != null ? (
            <span className="ml-1 tabular-nums opacity-70">{option.count}</span>
          ) : null}
        </button>
      ))}
    </div>
  );
}

/** 시즌·주차 머리표. 기록 줄 왼쪽에 자릿수를 맞춰 세운다. */
export function WeekTag({ season, week }: { season: number; week: number }) {
  return (
    <span className="shrink-0 font-mono text-[11px] tabular-nums text-stone-500">
      S{season}·W{String(week).padStart(2, "0")}
    </span>
  );
}
