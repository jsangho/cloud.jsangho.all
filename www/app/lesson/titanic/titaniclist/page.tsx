"use client";

import { useEffect, useMemo, useState } from "react";
import { titanicApiBaseUrl } from "@/lib/api";

type TitanicRow = {
  PassengerId: number | null;
  Survived: number | null;
  Pclass: number | null;
  Name: string | null;
  gender: string | null;
  Age: number | null;
  SibSp: number | null;
  Parch: number | null;
  Ticket: string | null;
  Fare: number | null;
  Cabin: string | null;
  Embarked: string | null;
};

type TitanicPageResponse = {
  id: number;
  name: string;
  memo: string;
  page: number;
  pageSize: number;
  total: number;
  items: TitanicRow[];
};

const pageSize = 50;

type ListState = {
  rows: TitanicRow[];
  walterId: number | null;
  walterName: string | null;
  walterMemo: string | null;
  loading: boolean;
  error: string | null;
  page: number;
  total: number;
};

const initialListState: ListState = {
  rows: [],
  walterId: null,
  walterName: null,
  walterMemo: null,
  loading: false,
  error: null,
  page: 1,
  total: 0,
};

export default function LessonTitanicListPage() {
  const [state, setState] = useState<ListState>(initialListState);
  const {
    rows,
    walterId,
    walterName,
    walterMemo,
    loading,
    error,
    page,
    total,
  } = state;

  const columns = useMemo(
    () =>
      [
        "PassengerId",
        "Survived",
        "Pclass",
        "Name",
        "gender",
        "Age",
        "SibSp",
        "Parch",
        "Ticket",
        "Fare",
        "Cabin",
        "Embarked",
      ] as const,
    [],
  );

  useEffect(() => {
    const ac = new AbortController();

    const run = async () => {
      setState((s) => ({ ...s, loading: true, error: null }));
      try {
        const res = await fetch(
          `${titanicApiBaseUrl}/walter/openfile?page=${page}&pageSize=${pageSize}`,
          { cache: "no-store", signal: ac.signal },
        );
        const data = (await res
          .json()
          .catch(() => null)) as TitanicPageResponse | null;
        if (!res.ok) {
          const detail =
            (data &&
              typeof data === "object" &&
              "detail" in data &&
              (data as Record<string, unknown>).detail) ||
            "목록을 불러오지 못했습니다.";
          throw new Error(String(detail));
        }
        if (ac.signal.aborted) return;
        setState((s) => ({
          ...s,
          rows: Array.isArray(data?.items) ? data!.items : [],
          walterId: typeof data?.id === "number" ? data.id : null,
          walterName: typeof data?.name === "string" ? data.name : null,
          walterMemo: typeof data?.memo === "string" ? data.memo : null,
          total: typeof data?.total === "number" ? data.total : 0,
        }));
      } catch (e) {
        if (ac.signal.aborted) return;
        setState((s) => ({
          ...s,
          error: e instanceof Error ? e.message : "목록을 불러오지 못했습니다.",
        }));
      } finally {
        if (!ac.signal.aborted) {
          setState((s) => ({ ...s, loading: false }));
        }
      }
    };

    run();
    return () => ac.abort();
  }, [page]);

  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const safePage = Math.min(Math.max(page, 1), totalPages);

  const pageItems = useMemo(() => {
    // Google-style: 1 ... (p-1) p (p+1) ... n
    const items: Array<number | "..."> = [];
    const n = totalPages;
    const p = safePage;
    if (n <= 10) {
      for (let i = 1; i <= n; i += 1) items.push(i);
      return items;
    }
    items.push(1);
    const left = Math.max(2, p - 1);
    const right = Math.min(n - 1, p + 1);
    if (left > 2) items.push("...");
    for (let i = left; i <= right; i += 1) items.push(i);
    if (right < n - 1) items.push("...");
    items.push(n);
    return items;
  }, [totalPages, safePage]);

  return (
    <main className="px-4 py-8">
      <div className="mx-auto max-w-6xl">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight md:text-4xl">
              Titanic DB 리스트
            </h1>
            <p className="mt-2 text-sm text-stone-600 dark:text-stone-300">
              Neon DB의{" "}
              <code className="rounded bg-stone-200/40 dark:bg-stone-950/40 px-1.5 py-0.5 text-xs text-stone-800 dark:text-stone-100">
                titanic_persons
              </code>
              {" + "}
              <code className="rounded bg-stone-200/40 dark:bg-stone-950/40 px-1.5 py-0.5 text-xs text-stone-800 dark:text-stone-100">
                titanic_bookings
              </code>{" "}
              내용을 조회합니다.
            </p>
          </div>
          <div className="text-sm text-stone-300">
            {loading
              ? "불러오는 중..."
              : `rows: ${total.toLocaleString("ko-KR")} · page ${safePage}/${totalPages}`}
          </div>
        </div>

        {error && (
          <p className="mt-6 rounded-lg border border-red-900/40 bg-red-950/30 px-4 py-3 text-sm text-red-200">
            {error}
          </p>
        )}

        {!error && (walterId !== null || walterName || walterMemo) && (
          <section className="mt-6 rounded-xl border border-stone-200/70 dark:border-stone-800/70 bg-stone-100/40 dark:bg-stone-950/40 px-4 py-4">
            <h2 className="text-sm font-semibold text-stone-700 dark:text-stone-200">
              월터 (Walter Roaster)
            </h2>
            <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-3">
              <div>
                <dt className="text-stone-500">ID</dt>
                <dd className="font-medium text-stone-800 dark:text-stone-100">
                  {walterId ?? "-"}
                </dd>
              </div>
              <div>
                <dt className="text-stone-500">이름</dt>
                <dd className="font-medium text-stone-800 dark:text-stone-100">
                  {walterName ?? "-"}
                </dd>
              </div>
              <div className="sm:col-span-1">
                <dt className="text-stone-500">비고</dt>
                <dd className="font-medium text-stone-800 dark:text-stone-100">
                  {walterMemo ?? "-"}
                </dd>
              </div>
            </dl>
          </section>
        )}

        <div className="mt-6 overflow-auto rounded-xl border border-stone-200/70 dark:border-stone-800/70 bg-stone-50/30 dark:bg-stone-950/30">
          <table className="min-w-[1100px] w-full text-left text-sm">
            <thead className="sticky top-0 bg-stone-100/80 dark:bg-stone-950/80 backdrop-blur">
              <tr className="border-b border-stone-200/70 dark:border-stone-800/70">
                {columns.map((c) => (
                  <th
                    key={c}
                    className="px-3 py-2 font-semibold text-stone-700 dark:text-stone-200"
                  >
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r, idx) => (
                <tr
                  key={`${r.PassengerId ?? "-"}-${idx}`}
                  className="border-b border-stone-200/60 dark:border-stone-900/60"
                >
                  {columns.map((c) => (
                    <td
                      key={c}
                      className="px-3 py-2 text-stone-700 dark:text-stone-200/90"
                    >
                      {String(r[c as keyof TitanicRow] ?? "-")}
                    </td>
                  ))}
                </tr>
              ))}
              {!loading && !error && rows.length === 0 && (
                <tr>
                  <td
                    className="px-3 py-10 text-center text-stone-400"
                    colSpan={columns.length}
                  >
                    데이터가 없습니다.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {!loading && !error && total > 0 && (
          <nav
            className="mt-8 flex justify-center"
            aria-label="Titanic list pagination"
          >
            <div className="inline-flex items-center gap-2">
              <button
                type="button"
                onClick={() =>
                  setState((s) => ({ ...s, page: Math.max(1, s.page - 1) }))
                }
                disabled={safePage === 1}
                className={[
                  "inline-flex h-10 w-10 items-center justify-center rounded-lg border text-sm font-semibold transition-colors",
                  safePage === 1
                    ? "cursor-not-allowed border-stone-200/60 dark:border-stone-800/60 bg-stone-100/30 dark:bg-stone-950/30 text-stone-400 dark:text-stone-600"
                    : "border-stone-300/70 dark:border-stone-200/10 bg-stone-50/20 dark:bg-stone-950/20 text-stone-800 dark:text-stone-100 hover:bg-stone-200/60 dark:hover:bg-stone-800/60",
                ].join(" ")}
                aria-label="이전 페이지"
              >
                ‹
              </button>

              <div className="flex items-center gap-2">
                {pageItems.map((it, i) =>
                  it === "..." ? (
                    <span
                      key={`dots-${i}`}
                      className="px-1 text-sm text-stone-500"
                    >
                      …
                    </span>
                  ) : (
                    <button
                      key={it}
                      type="button"
                      onClick={() => setState((s) => ({ ...s, page: it }))}
                      aria-current={it === safePage ? "page" : undefined}
                      className={[
                        "inline-flex h-10 min-w-10 items-center justify-center rounded-lg border px-3 text-sm font-semibold transition-colors",
                        it === safePage
                          ? "border-stone-300/60 dark:border-stone-800/60 bg-stone-200 dark:bg-stone-50 text-stone-900 dark:text-stone-700 hover:bg-stone-300 dark:hover:bg-stone-100"
                          : "border-stone-300/70 dark:border-stone-200/10 bg-stone-50/20 dark:bg-stone-950/20 text-stone-800 dark:text-stone-100",
                      ].join(" ")}
                    >
                      {it}
                    </button>
                  ),
                )}
              </div>

              <button
                type="button"
                onClick={() =>
                  setState((s) => ({
                    ...s,
                    page: Math.min(totalPages, s.page + 1),
                  }))
                }
                disabled={safePage === totalPages}
                className={[
                  "inline-flex h-10 w-10 items-center justify-center rounded-lg border text-sm font-semibold transition-colors",
                  safePage === totalPages
                    ? "cursor-not-allowed border-stone-200/60 dark:border-stone-800/60 bg-stone-100/30 dark:bg-stone-950/30 text-stone-400 dark:text-stone-600"
                    : "border-stone-300/70 dark:border-stone-200/10 bg-stone-50/20 dark:bg-stone-950/20 text-stone-800 dark:text-stone-100 hover:bg-stone-200/60 dark:hover:bg-stone-800/60",
                ].join(" ")}
                aria-label="다음 페이지"
              >
                ›
              </button>
            </div>
          </nav>
        )}
      </div>
    </main>
  );
}
