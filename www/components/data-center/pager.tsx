"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * 페이지 이동 (Phase 2 §12).
 *
 * **번호를 다 그리지 않는다.** 지금은 몇 페이지뿐이지만 데이터가 늘면 번호가 줄줄이
 * 늘어난다 — 이전/다음과 "n / m"이면 어느 크기에서도 같은 모양이다.
 */
export function Pager({
  page,
  size,
  total,
  onChange,
  className,
}: {
  page: number;
  size: number;
  total: number;
  onChange: (next: number) => void;
  className?: string;
}) {
  const last = Math.max(1, Math.ceil(total / size));
  if (last <= 1) return null;

  return (
    <nav
      className={cn("mt-5 flex items-center justify-center gap-2", className)}
      aria-label="페이지 이동"
    >
      <button
        type="button"
        onClick={() => onChange(Math.max(1, page - 1))}
        disabled={page <= 1}
        className="inline-flex h-9 items-center gap-1 rounded-lg border border-border bg-card px-3 text-sm text-foreground transition-colors hover:bg-card-2 disabled:opacity-40"
      >
        <ChevronLeft className="size-4" aria-hidden />
        이전
      </button>
      <span className="text-sm tabular-nums text-muted-foreground">
        {page} / {last}
      </span>
      <button
        type="button"
        onClick={() => onChange(Math.min(last, page + 1))}
        disabled={page >= last}
        className="inline-flex h-9 items-center gap-1 rounded-lg border border-border bg-card px-3 text-sm text-foreground transition-colors hover:bg-card-2 disabled:opacity-40"
      >
        다음
        <ChevronRight className="size-4" aria-hidden />
      </button>
    </nav>
  );
}
