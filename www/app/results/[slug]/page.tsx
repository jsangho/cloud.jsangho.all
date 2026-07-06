import Link from "next/link";
import { notFound } from "next/navigation";
import { PleResultsBoard } from "@/components/results/ple-results-board";
import {
  formatPleMonth,
  getPleBySlug,
  WWE_PLE_MONTHLY_ORDER,
} from "@/lib/wwe-ple";
import type { PleSlug } from "@/lib/wwe-ple";

type Props = { params: Promise<{ slug: string }> };

export function generateStaticParams() {
  return WWE_PLE_MONTHLY_ORDER.map((e) => ({ slug: e.slug }));
}

export default async function ResultsEventPage({ params }: Props) {
  const { slug } = await params;
  const ple = getPleBySlug(slug);
  if (!ple) notFound();

  const idx = WWE_PLE_MONTHLY_ORDER.findIndex((e) => e.slug === slug);
  const prev = idx > 0 ? WWE_PLE_MONTHLY_ORDER[idx - 1] : undefined;
  const next =
    idx >= 0 && idx < WWE_PLE_MONTHLY_ORDER.length - 1
      ? WWE_PLE_MONTHLY_ORDER[idx + 1]
      : undefined;

  return (
    <main className="min-h-[calc(100dvh-5.5rem)] w-full min-w-0 bg-stone-50 dark:bg-stone-900 px-4 py-10 text-stone-900 dark:text-stone-100">
      <div className="mx-auto w-full max-w-3xl min-w-0">
        <nav className="mb-8 flex flex-wrap items-center justify-between gap-3 text-sm">
          <Link
            href="/results"
            className="text-stone-500 transition-colors hover:text-stone-800 dark:hover:text-stone-200"
          >
            ← 결과 목록
          </Link>
          <div className="flex gap-2">
            {prev && (
              <Link
                href={`/results/${prev.slug}`}
                className="rounded-lg border border-stone-300/60 dark:border-stone-700/60 px-3 py-1 text-stone-500 dark:text-stone-400 hover:border-stone-500 hover:text-stone-800 dark:hover:text-stone-200"
              >
                {formatPleMonth(prev.month)}
              </Link>
            )}
            {next && (
              <Link
                href={`/results/${next.slug}`}
                className="rounded-lg border border-stone-300/60 dark:border-stone-700/60 px-3 py-1 text-stone-500 dark:text-stone-400 hover:border-stone-500 hover:text-stone-800 dark:hover:text-stone-200"
              >
                {formatPleMonth(next.month)}
              </Link>
            )}
          </div>
        </nav>

        <header className="mb-8 rounded-2xl border border-stone-300/70 dark:border-stone-600/70 bg-stone-100/50 dark:bg-stone-800/50 p-6">
          <span className="text-sm font-medium text-stone-500">
            {formatPleMonth(ple.month)} PLE
          </span>
          <h1 className="mt-1 text-3xl font-bold tracking-tight text-stone-900 dark:text-stone-50">
            {ple.label}
          </h1>
          <p className="mt-2 text-sm text-stone-400">
            등록된 승자는 누구나 확인할 수 있습니다. 등록·수정은 관리자 인증
            후에만 가능합니다.
          </p>
        </header>

        <PleResultsBoard slug={ple.slug as PleSlug} />
      </div>
    </main>
  );
}
