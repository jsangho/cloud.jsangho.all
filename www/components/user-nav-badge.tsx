"use client";

import { useEffect, useState } from "react";
import { authDisplayName, type AuthUser } from "@/context/auth-context";
import { fetchMyPoints } from "@/lib/rankings-api";
import { cn } from "@/lib/utils";

type PointsState = { status: "loading" } | { status: "ok"; points: number } | { status: "error" };

function pointsLabel(state: PointsState): string {
  if (state.status === "ok") return state.points.toLocaleString("ko-KR");
  return state.status === "loading" ? "…" : "—";
}

/** 내비에 표시하는 로그인 사용자 칩 — 닉네임 + 보유 포인트(`P:`) */
export function UserNavBadge({ user, className }: { user: AuthUser; className?: string }) {
  const [state, setState] = useState<PointsState>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;
    setState({ status: "loading" });

    void (async () => {
      const points = await fetchMyPoints(user.nickname);
      if (cancelled) return;
      setState(points === null ? { status: "error" } : { status: "ok", points });
    })();

    return () => {
      cancelled = true;
    };
  }, [user.nickname]);

  const displayName = authDisplayName(user);
  const label = pointsLabel(state);

  return (
    <span
      className={cn(
        "inline-flex h-8 min-w-0 items-center gap-1.5 rounded-full border border-stone-300/70 dark:border-stone-600/70 bg-stone-200/45 dark:bg-stone-800/45 pl-2.5 pr-1.5 text-sm",
        className,
      )}
      title={state.status === "ok" ? `${displayName} · 보유 포인트 ${label}P` : displayName}
    >
      <span className="max-w-[7rem] truncate font-semibold text-stone-900 dark:text-stone-100">
        {displayName}
      </span>
      <span className="inline-flex shrink-0 items-center rounded-full border border-amber-500/35 bg-amber-500/10 px-1.5 py-0.5 text-xs font-bold tabular-nums text-amber-700 dark:text-amber-200">
        <span className="sr-only">보유 포인트 </span>P: {label}
      </span>
    </span>
  );
}
