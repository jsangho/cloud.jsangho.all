"use client";

import { FormEvent, useCallback, useState } from "react";
import { Loader2, PlayCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import { parseApiError } from "@/lib/api";

type PipelineResult = {
  crawl: {
    website: string;
    keyword: string;
    status_code: number;
    fetched_at: string;
    content_length: number;
    saved_path: string;
  };
  scrape: {
    website: string;
    keyword: string;
    title: string | null;
    meta_description: string | null;
    body_text: string;
    keyword_found: boolean;
    scraped_at: string;
    saved_path: string;
  };
};

type Tab = "crawler" | "scraper";

const TABS: { id: Tab; label: string }[] = [
  { id: "crawler", label: "크롤러" },
  { id: "scraper", label: "스크래퍼" },
];

export function DatasetCollectionPipeline() {
  const [tab, setTab] = useState<Tab>("crawler");
  const [website, setWebsite] = useState("");
  const [instruction, setInstruction] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<PipelineResult | null>(null);

  const run = useCallback(
    async (e: FormEvent) => {
      e.preventDefault();
      setLoading(true);
      setError(null);
      try {
        const res = await fetch("/api/ontology/crawl-scrape-pipeline", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            website: website.trim() || undefined,
            keyword: instruction.trim() || undefined,
          }),
        });
        const data = await res.json().catch(() => null);
        if (!res.ok) {
          throw new Error(parseApiError(data, res.status));
        }
        setResult(data as PipelineResult);
      } catch (e) {
        setError(
          e instanceof Error
            ? e.message
            : "파이프라인 실행 중 오류가 발생했습니다.",
        );
      } finally {
        setLoading(false);
      }
    },
    [website, instruction],
  );

  return (
    <div className="space-y-6">
      <div
        role="tablist"
        aria-label="크롤러/스크래퍼 전환"
        className="inline-flex rounded-xl border border-zinc-200 bg-zinc-50/80 p-1 dark:border-zinc-700 dark:bg-zinc-900/80"
      >
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={tab === t.id}
            onClick={() => setTab(t.id)}
            className={cn(
              "rounded-lg px-4 py-1.5 text-sm font-medium transition-colors",
              tab === t.id
                ? "bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900"
                : "text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100",
            )}
          >
            {t.label}
          </button>
        ))}
      </div>

      <form onSubmit={run} className="space-y-3">
        <div>
          <label
            htmlFor="dataset-collection-website"
            className="mb-1.5 block text-sm font-medium text-zinc-700 dark:text-zinc-300"
          >
            사이트 주소
          </label>
          <input
            id="dataset-collection-website"
            type="url"
            value={website}
            onChange={(e) => setWebsite(e.target.value)}
            placeholder="https://example.com"
            className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 outline-none focus:border-zinc-500 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-100"
          />
        </div>
        <div>
          <label
            htmlFor="dataset-collection-instruction"
            className="mb-1.5 block text-sm font-medium text-zinc-700 dark:text-zinc-300"
          >
            자연어 명령어
          </label>
          <input
            id="dataset-collection-instruction"
            type="text"
            value={instruction}
            onChange={(e) => setInstruction(e.target.value)}
            placeholder="예: 이 페이지에서 가격 정보만 추출해줘"
            className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 outline-none focus:border-zinc-500 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-100"
          />
        </div>
        <button
          type="submit"
          disabled={loading}
          className={cn(
            "inline-flex items-center gap-2 rounded-xl border px-6 py-3 text-sm font-semibold shadow-sm transition-colors",
            loading
              ? "cursor-wait border-zinc-300 bg-zinc-200 text-zinc-500"
              : "border-zinc-900 bg-zinc-900 text-white hover:bg-zinc-800",
          )}
        >
          {loading ? (
            <Loader2 className="size-4 animate-spin" aria-hidden />
          ) : (
            <PlayCircle className="size-4" aria-hidden />
          )}
          {loading ? "실행 중..." : "실행"}
        </button>
      </form>

      <p className="text-sm text-zinc-500">
        사이트 주소를 입력하면 그 페이지를 바로 크롤링·스크래핑합니다. 비워두면
        레디스 큐(
        <code className="rounded bg-zinc-100 dark:bg-zinc-800 px-1.5 py-0.5 text-xs">
          ontology:crawl:jobs
        </code>
        )에서 다음 작업을 꺼내 실행합니다. 자연어 명령어는 스크래핑 시
        키워드로 함께 전달되어 결과에 등장 여부가 표시됩니다.
      </p>

      {error && (
        <p
          className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
          role="alert"
        >
          {error}
        </p>
      )}

      {result && tab === "crawler" && (
        <div className="space-y-1.5 rounded-xl border border-zinc-200 bg-zinc-50/80 p-4 text-sm dark:border-zinc-700 dark:bg-zinc-900/80">
          <p className="font-semibold text-zinc-800 dark:text-zinc-200">
            크롤링 결과
          </p>
          <p>웹사이트: {result.crawl.website}</p>
          <p>키워드: {result.crawl.keyword || "(없음)"}</p>
          <p>상태 코드: {result.crawl.status_code}</p>
          <p>
            본문 길이: {result.crawl.content_length.toLocaleString("ko-KR")}
            자
          </p>
          <p className="break-all">저장 경로: {result.crawl.saved_path}</p>
        </div>
      )}

      {result && tab === "scraper" && (
        <div className="space-y-1.5 rounded-xl border border-zinc-200 bg-zinc-50/80 p-4 text-sm dark:border-zinc-700 dark:bg-zinc-900/80">
          <p className="font-semibold text-zinc-800 dark:text-zinc-200">
            스크래핑 결과
          </p>
          <p>제목: {result.scrape.title ?? "(없음)"}</p>
          <p>메타 설명: {result.scrape.meta_description ?? "(없음)"}</p>
          <p>키워드 포함 여부: {result.scrape.keyword_found ? "예" : "아니오"}</p>
          <p className="whitespace-pre-wrap">{result.scrape.body_text}</p>
          <p className="break-all">저장 경로: {result.scrape.saved_path}</p>
        </div>
      )}
    </div>
  );
}
