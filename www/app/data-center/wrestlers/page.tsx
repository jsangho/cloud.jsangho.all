"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Search } from "lucide-react";
import {
  DataCenterShell,
  DataUnavailable,
  LoadingBlock,
} from "@/components/data-center/data-center-shell";
import { Pager } from "@/components/data-center/pager";
import { fetchWrestlerPage, formatWinRate, type WrestlerPage } from "@/lib/data-center-api";
import { cn } from "@/lib/utils";

const PAGE_SIZE = 24;

type ListState = {
  page: WrestlerPage | null;
  loading: boolean;
  failed: boolean;
};

/**
 * 선수 목록 (Phase 2 §5).
 *
 * **한 번에 다 받지 않는다** (§12) — 검색·브랜드·페이지를 서버에 넘기고 그 페이지만 받는다.
 * 브랜드 후보는 응답이 들고 오는 실제 DB 값이다: 화면에 목록을 박지 않는다 (§2).
 */
export default function DataCenterWrestlersPage() {
  const [query, setQuery] = useState("");
  const [brand, setBrand] = useState("");
  const [page, setPage] = useState(1);
  const [state, setState] = useState<ListState>({
    page: null,
    loading: true,
    failed: false,
  });

  useEffect(() => {
    let cancelled = false;
    setState((prev) => ({ ...prev, loading: true }));
    // 타이핑마다 부르지 않는다 — 멈춘 뒤에 한 번 간다.
    const timer = setTimeout(() => {
      void (async () => {
        const result = await fetchWrestlerPage({
          q: query,
          brand,
          page,
          size: PAGE_SIZE,
        });
        if (cancelled) return;
        setState({ page: result, loading: false, failed: result === null });
      })();
    }, 250);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [query, brand, page]);

  const brands = state.page?.brands ?? [];

  return (
    <DataCenterShell
      title="Wrestlers"
      description="DB에 등록된 선수와 그 전적입니다. 승·패는 실제 경기 카드에서 세고, 판정이 끝나지 않았으면 승률을 비웁니다."
    >
      <div className="mb-5 flex flex-col gap-3">
        <label className="relative block">
          <span className="sr-only">선수 검색</span>
          <Search
            className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
            aria-hidden
          />
          <input
            type="search"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setPage(1);
            }}
            placeholder="링네임 또는 본명으로 검색"
            className="h-10 w-full rounded-lg border border-border bg-card pl-9 pr-3 text-sm text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          />
        </label>

        {brands.length > 0 && (
          <div className="-mx-4 overflow-x-auto px-4 pb-1">
            <ul className="flex min-w-max items-center gap-1.5" aria-label="브랜드 필터">
              <li>
                <FilterChip
                  active={brand === ""}
                  onClick={() => {
                    setBrand("");
                    setPage(1);
                  }}
                >
                  전체
                </FilterChip>
              </li>
              {brands.map((name) => (
                <li key={name}>
                  <FilterChip
                    active={brand === name}
                    onClick={() => {
                      setBrand(name);
                      setPage(1);
                    }}
                  >
                    {name}
                  </FilterChip>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {state.loading ? (
        <LoadingBlock rows={5} />
      ) : state.failed || !state.page ? (
        <DataUnavailable what="선수 목록" />
      ) : state.page.items.length === 0 ? (
        <p className="rounded-xl border border-dashed border-border px-4 py-8 text-center text-sm text-muted-foreground">
          조건에 맞는 선수가 없습니다.
        </p>
      ) : (
        <>
          <p className="mb-3 text-sm text-muted-foreground">
            <span className="tabular-nums text-foreground">{state.page.total}</span>명 중{" "}
            {state.page.items.length}명
          </p>
          <ul className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {state.page.items.map((row) => (
              <li key={row.name}>
                <Link
                  href={`/records/${encodeURIComponent(row.name)}`}
                  className="flex h-full flex-col gap-2 rounded-xl border border-border bg-card p-4 transition-colors hover:bg-card-2"
                >
                  <div className="flex items-start justify-between gap-2">
                    <span className="min-w-0 truncate font-sport text-lg text-foreground">
                      {row.name}
                    </span>
                    {row.brand && (
                      <span className="shrink-0 rounded-md border border-border px-1.5 py-0.5 text-[11px] text-muted-foreground">
                        {row.brand}
                      </span>
                    )}
                  </div>

                  {row.matches === 0 ? (
                    <p className="text-xs text-muted-foreground">
                      기록된 PLE 경기가 아직 없습니다.
                    </p>
                  ) : (
                    <p className="flex flex-wrap items-baseline gap-x-2 text-sm">
                      <span className="font-bold tabular-nums text-foreground">
                        {formatWinRate(row.winRate)}
                      </span>
                      <span className="tabular-nums text-muted-foreground">
                        {row.wins}승 {row.losses}패
                      </span>
                      <span className="text-xs text-muted-foreground">· {row.matches}경기</span>
                    </p>
                  )}

                  <p className="mt-auto flex flex-wrap gap-x-2 text-xs text-muted-foreground">
                    {row.titles > 0 && <span className="text-brand-link">벨트 {row.titles}회</span>}
                    {row.stableTeam && <span>{row.stableTeam}</span>}
                  </p>
                </Link>
              </li>
            ))}
          </ul>
          <Pager
            page={state.page.page}
            size={state.page.size}
            total={state.page.total}
            onChange={setPage}
          />
        </>
      )}
    </DataCenterShell>
  );
}

function FilterChip({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        "inline-flex h-8 items-center rounded-lg border px-3 text-sm font-medium transition-colors",
        active
          ? "border-data-500/50 bg-data-surface text-data"
          : "border-border bg-card text-muted-foreground hover:bg-card-2 hover:text-foreground",
      )}
    >
      {children}
    </button>
  );
}
