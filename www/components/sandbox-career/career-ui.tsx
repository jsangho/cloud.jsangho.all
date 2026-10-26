"use client";

import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/**
 * 커리어 화면 여섯 탭이 공유하는 표면 조각. **값을 계산하지 않는다** — 받은 것만
 * 그린다. 여기에 파생 로직이 들어가기 시작하면 탭마다 다른 숫자가 나온다.
 */
export function Stat({ label, value, tone }: { label: string; value: string; tone?: "warn" }) {
  return (
    <div className="rounded-lg border border-border bg-card px-3 py-2">
      <div className="text-[11px] font-bold text-muted-foreground">{label}</div>
      <div
        className={cn(
          "mt-0.5 text-sm font-semibold tabular-nums",
          tone === "warn" ? "text-live" : "text-foreground",
        )}
      >
        {value}
      </div>
    </div>
  );
}

export function Panel({
  title,
  hint,
  action,
  children,
}: {
  title: string;
  hint?: string;
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="rounded-xl border border-border bg-card p-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-xs font-bold text-muted-foreground">{title}</h3>
        {action}
      </div>
      <div className="mt-2">{children}</div>
      {hint ? <p className="mt-2 text-[11px] text-muted-foreground">{hint}</p> : null}
    </section>
  );
}

export function SectionTitle({ children, aside }: { children: ReactNode; aside?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-baseline justify-between gap-2">
      <h2 className="font-sport text-lg text-foreground">{children}</h2>
      {aside}
    </div>
  );
}

/**
 * 빈 상태. **로딩과 다른 문구를 쓴다**(사용자 요구 §7 — "로딩, 오류, 빈 상태를
 * 구분한다"). 없는 데이터를 가짜로 채우는 자리가 바로 여기라서, 이 컴포넌트는
 * 숫자를 받지 않는다.
 */
export function Empty({ children }: { children: ReactNode }) {
  return (
    <p className="rounded-lg border border-dashed border-border px-3 py-4 text-center text-xs text-muted-foreground">
      {children}
    </p>
  );
}

export function Loading({ children = "불러오는 중…" }: { children?: ReactNode }) {
  return (
    <p className="rounded-lg border border-dashed border-border px-3 py-4 text-center text-xs text-muted-foreground">
      {children}
    </p>
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
            "shrink-0 rounded-full border px-3 py-1 text-xs font-medium transition-colors",
            option.value === value
              ? "border-brand-400/70 bg-brand-500/15 text-brand-600 dark:text-brand-300"
              : "border-border bg-card text-muted-foreground hover:bg-card-2",
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
    <span className="shrink-0 tabular-nums text-muted-foreground">
      S{season} W{week}
    </span>
  );
}
