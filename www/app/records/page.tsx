"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Loader2, Search } from "lucide-react";
import { WweArenaShell } from "@/components/wwe-arena-shell";
import { fetchCompetitorNames } from "@/lib/records-api";
import { cn } from "@/lib/utils";

type RecordsPageState = {
  query: string;
  names: string[];
  loading: boolean;
};

const initialState: RecordsPageState = {
  query: "",
  names: [],
  loading: true,
};

export default function RecordsPage() {
  const [state, setState] = useState<RecordsPageState>(initialState);
  const patchState = (patch: Partial<RecordsPageState>) =>
    setState((prev) => ({ ...prev, ...patch }));

  useEffect(() => {
    let cancelled = false;
    const timer = setTimeout(
      async () => {
        patchState({ loading: true });
        const names = await fetchCompetitorNames(state.query);
        if (!cancelled) patchState({ names, loading: false });
      },
      state.query ? 250 : 0,
    );

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [state.query]);

  const emptyMessage = useMemo(() => {
    if (state.loading) return null;
    if (state.query.trim()) return "검색 결과가 없습니다.";
    return "동기화된 PLE 카드에 출전 선수가 없습니다.";
  }, [state.loading, state.query]);

  return (
    <WweArenaShell>
      <div className="mx-auto w-full max-w-5xl px-4 py-8 sm:py-10">
        <header className="relative mb-8 text-center sm:mb-10">
          <div
            aria-hidden
            className="hero-title-backdrop mx-auto"
            style={{ height: "8rem", width: "min(100%, 22rem)" }}
          />
          <h1 className="font-kr-hero relative z-10 text-2xl text-stone-900 dark:text-white sm:text-3xl md:text-4xl">
            기록
          </h1>
          <p className="relative z-10 mx-auto mt-3 max-w-lg text-sm font-medium leading-relaxed text-stone-400 sm:text-base">
            PLE 출전 선수 목록에서 선택하면{" "}
            <span className="font-semibold text-stone-700 dark:text-stone-200">
              승패 기록
            </span>
            을 확인할 수 있습니다.
          </p>
        </header>

        <section className="ple-section-glow mb-6 rounded-2xl border border-stone-300/50 dark:border-stone-700/50 bg-stone-50/60 dark:bg-stone-950/60 p-4 backdrop-blur-sm sm:rounded-3xl sm:p-5">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <label
              className="font-sport text-sm font-semibold tracking-[-0.04em] text-stone-600 dark:text-stone-300"
              htmlFor="records-search"
            >
              선수 검색
            </label>
            <div className="relative w-full sm:max-w-sm">
              <Search
                className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-stone-500"
                aria-hidden
              />
              <input
                id="records-search"
                type="search"
                value={state.query}
                onChange={(e) => patchState({ query: e.target.value })}
                placeholder="이름으로 검색"
                className={cn(
                  "records-search-input h-10 w-full rounded-xl pl-9 pr-3 text-sm text-stone-900 dark:text-white",
                  "placeholder:text-stone-500",
                )}
              />
            </div>
          </div>
        </section>

        <section aria-label="선수 목록">
          {state.loading ? (
            <div className="flex items-center justify-center gap-2 rounded-2xl border border-stone-300/50 dark:border-stone-700/50 bg-stone-100/50 dark:bg-stone-950/50 px-4 py-10 text-sm text-stone-500 dark:text-stone-400">
              <Loader2 className="h-4 w-4 animate-spin text-amber-400/80" />
              불러오는 중…
            </div>
          ) : (
            <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {state.names.map((name) => (
                <li key={name} className="min-w-0">
                  <Link
                    href={`/records/${encodeURIComponent(name)}`}
                    className="records-competitor-card group block rounded-xl border px-4 py-3.5"
                  >
                    <div className="truncate text-sm font-bold text-stone-900 dark:text-white transition-colors group-hover:text-amber-50 dark:group-hover:text-amber-50">
                      {name}
                    </div>
                    <div className="mt-1 text-xs font-medium text-stone-500 transition-colors group-hover:text-amber-200/70">
                      상세 기록 보기 →
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          )}

          {!state.loading && state.names.length === 0 && emptyMessage && (
            <div className="mt-6 rounded-2xl border border-dashed border-stone-300/50 dark:border-stone-700/50 bg-stone-100/40 dark:bg-stone-950/40 px-4 py-10 text-center text-sm text-stone-500 dark:text-stone-400">
              {emptyMessage}
            </div>
          )}
        </section>
      </div>
    </WweArenaShell>
  );
}
