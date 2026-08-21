"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Search } from "lucide-react";
import {
  DataCenterShell,
  DataUnavailable,
  LoadingBlock,
} from "@/components/data-center/data-center-shell";
import { MatchRowCard } from "@/components/data-center/match-row-card";
import { Pager } from "@/components/data-center/pager";
import { fetchMatchPage, type MatchPage } from "@/lib/data-center-api";
import { cn } from "@/lib/utils";

const PAGE_SIZE = 20;

const STATUS_OPTIONS = [
  { value: "", label: "전체" },
  { value: "finished", label: "종료" },
  { value: "scheduled", label: "예정" },
] as const;

/**
 * 경기 탐색 (Phase 2 §7).
 *
 * 대회·선수·상태 필터와 페이지네이션을 **서버에 넘긴다** — 화면이 68건을 다 받아
 * 걸러 내면 데이터가 늘었을 때 그대로 무너진다 (§12).
 */
function MatchesContent() {
  const params = useSearchParams();
  const [event, setEvent] = useState(params.get("event") ?? "");
  const [competitor, setCompetitor] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [result, setResult] = useState<MatchPage | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    const timer = setTimeout(() => {
      void (async () => {
        const data = await fetchMatchPage({
          event,
          competitor,
          status,
          page,
          size: PAGE_SIZE,
        });
        if (cancelled) return;
        setResult(data);
        setFailed(data === null);
        setLoading(false);
      })();
    }, 250);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [event, competitor, status, page]);

  const events = result?.events ?? [];

  return (
    <DataCenterShell
      title="Matches"
      description="DB에 기록된 PLE 경기입니다. 참가자는 카드에서 개인 이름으로 펼치고, 승자를 되짚지 못한 경기는 그렇게 적습니다."
    >
      <div className="mb-5 flex flex-col gap-3">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <label className="relative block">
            <span className="sr-only">선수로 검색</span>
            <Search
              className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
              aria-hidden
            />
            <input
              type="search"
              value={competitor}
              onChange={(e) => {
                setCompetitor(e.target.value);
                setPage(1);
              }}
              placeholder="선수 이름으로 검색"
              className="h-10 w-full rounded-lg border border-border bg-card pl-9 pr-3 text-sm text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            />
          </label>

          <label className="block">
            <span className="sr-only">대회 선택</span>
            <select
              value={event}
              onChange={(e) => {
                setEvent(e.target.value);
                setPage(1);
              }}
              className="h-10 w-full rounded-lg border border-border bg-card px-3 text-sm text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <option value="">모든 대회</option>
              {events.map((option) => (
                <option key={option.slug} value={option.slug}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
        </div>

        <ul className="flex flex-wrap items-center gap-1.5" aria-label="상태 필터">
          {STATUS_OPTIONS.map((option) => (
            <li key={option.value || "all"}>
              <button
                type="button"
                aria-pressed={status === option.value}
                onClick={() => {
                  setStatus(option.value);
                  setPage(1);
                }}
                className={cn(
                  "inline-flex h-8 items-center rounded-lg border px-3 text-sm font-medium transition-colors",
                  status === option.value
                    ? "border-data-500/50 bg-data-surface text-data"
                    : "border-border bg-card text-muted-foreground hover:bg-card-2 hover:text-foreground",
                )}
              >
                {option.label}
              </button>
            </li>
          ))}
        </ul>
      </div>

      {loading ? (
        <LoadingBlock rows={5} />
      ) : failed || !result ? (
        <DataUnavailable what="경기 목록" />
      ) : result.items.length === 0 ? (
        <p className="rounded-xl border border-dashed border-border px-4 py-8 text-center text-sm text-muted-foreground">
          조건에 맞는 경기가 없습니다.
        </p>
      ) : (
        <>
          <p className="mb-3 text-sm text-muted-foreground">
            <span className="tabular-nums text-foreground">{result.total}</span>경기 중{" "}
            {result.items.length}경기
          </p>
          <ul className="flex flex-col gap-2">
            {result.items.map((match) => (
              <li key={`${match.eventSlug}-${match.matchKey}`}>
                <MatchRowCard match={match} />
              </li>
            ))}
          </ul>
          <Pager page={result.page} size={result.size} total={result.total} onChange={setPage} />
        </>
      )}
    </DataCenterShell>
  );
}

export default function DataCenterMatchesPage() {
  return (
    <Suspense
      fallback={
        <DataCenterShell title="Matches">
          <LoadingBlock />
        </DataCenterShell>
      }
    >
      <MatchesContent />
    </Suspense>
  );
}
