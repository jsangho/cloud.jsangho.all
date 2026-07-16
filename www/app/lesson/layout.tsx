"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { ChevronRight, Menu, X } from "lucide-react";
import { cn } from "@/lib/utils";

const TITANIC_HREF = "/lesson/titanic";
const DATA_COLLECTION_HREF = "/lesson/titanic/data-collection";
const TITANIC_LIST_HREF = "/lesson/titanic/titaniclist";
const SMITH_SAILOR_HREF = "/lesson/titanic/smith-sailor";
const VISION_HREF = "/lesson/titanic/vision";
const OBJECT_DETECTION_HREF = "/lesson/titanic/vision/object-detection";
const RAG_CHAT_HREF = "/lesson/rag-system/rag-chat";
const CRAWLER_SCRAPER_HREF = "/lesson/dataset-collection/crawler-scraper";
export default function LessonLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isTitanic = pathname === TITANIC_HREF;
  const isDataCollection = pathname === DATA_COLLECTION_HREF;
  const isTitanicList = pathname === TITANIC_LIST_HREF;
  const isSmithSailor = pathname === SMITH_SAILOR_HREF;
  const isVision = pathname === VISION_HREF;
  const isObjectDetection = pathname === OBJECT_DETECTION_HREF;
  const isRagChat = pathname === RAG_CHAT_HREF;
  const isCrawlerScraper = pathname === CRAWLER_SCRAPER_HREF;
  const isLessonSection = isTitanic || isDataCollection || isTitanicList || isSmithSailor;
  const isVisionSection = isVision || isObjectDetection;

  const [expanded, setExpanded] = useState(false);
  const [visionExpanded, setVisionExpanded] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    if (isDataCollection || isTitanicList || isSmithSailor) {
      setExpanded(true);
    }
  }, [isDataCollection, isTitanicList, isSmithSailor]);

  useEffect(() => {
    if (isObjectDetection) {
      setVisionExpanded(true);
    }
  }, [isObjectDetection]);

  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  const nav = (
    <nav className="flex flex-col gap-1" aria-label="수업 메뉴">
      <div
        className={cn(
          "flex items-center rounded-lg text-sm font-medium transition-colors",
          isLessonSection ? "bg-stone-100 text-stone-950" : "text-stone-600 dark:text-stone-300",
        )}
      >
        <Link
          href={TITANIC_HREF}
          aria-current={isTitanic ? "page" : undefined}
          className={cn(
            "min-w-0 flex-1 rounded-l-lg px-3 py-2.5 transition-colors",
            !isLessonSection &&
              "hover:bg-stone-100/60 dark:hover:bg-stone-800/60 hover:text-stone-900 dark:hover:text-stone-50",
            isLessonSection && "hover:bg-stone-50",
          )}
        >
          타이타닉
        </Link>
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          aria-expanded={expanded}
          aria-label={expanded ? "하위 메뉴 접기" : "하위 메뉴 펼치기"}
          className={cn(
            "flex shrink-0 items-center justify-center rounded-r-lg px-2 py-2.5 transition-colors",
            !isLessonSection &&
              "hover:bg-stone-100/60 dark:hover:bg-stone-800/60 hover:text-stone-900 dark:hover:text-stone-50",
            isLessonSection && "hover:bg-stone-50",
          )}
        >
          <ChevronRight
            className={cn("size-4 transition-transform duration-200", expanded && "rotate-90")}
            aria-hidden
          />
        </button>
      </div>

      {expanded && (
        <>
          <Link
            href={DATA_COLLECTION_HREF}
            aria-current={isDataCollection ? "page" : undefined}
            className={cn(
              "rounded-lg py-2 pl-6 pr-3 text-sm transition-colors",
              isDataCollection
                ? "bg-stone-100/90 font-semibold text-stone-950"
                : "text-stone-600 dark:text-stone-300 hover:bg-stone-100/60 dark:hover:bg-stone-800/60 hover:text-stone-900 dark:hover:text-stone-50",
            )}
          >
            1. 데이터 수집
          </Link>
          <Link
            href={TITANIC_LIST_HREF}
            aria-current={isTitanicList ? "page" : undefined}
            className={cn(
              "rounded-lg py-2 pl-6 pr-3 text-sm transition-colors",
              isTitanicList
                ? "bg-stone-100/90 font-semibold text-stone-950"
                : "text-stone-600 dark:text-stone-300 hover:bg-stone-100/60 dark:hover:bg-stone-800/60 hover:text-stone-900 dark:hover:text-stone-50",
            )}
          >
            2. DB 리스트
          </Link>
          <Link
            href={SMITH_SAILOR_HREF}
            aria-current={isSmithSailor ? "page" : undefined}
            className={cn(
              "rounded-lg py-2 pl-6 pr-3 text-sm transition-colors",
              isSmithSailor
                ? "bg-stone-100/90 font-semibold text-stone-950"
                : "text-stone-600 dark:text-stone-300 hover:bg-stone-100/60 dark:hover:bg-stone-800/60 hover:text-stone-900 dark:hover:text-stone-50",
            )}
          >
            3. 스미스 선장과 대화
          </Link>
        </>
      )}

      <div
        className={cn(
          "flex items-center rounded-lg text-sm font-medium transition-colors",
          isVisionSection ? "bg-stone-100 text-stone-950" : "text-stone-600 dark:text-stone-300",
        )}
      >
        <Link
          href={VISION_HREF}
          aria-current={isVision ? "page" : undefined}
          className={cn(
            "min-w-0 flex-1 rounded-l-lg px-3 py-2.5 transition-colors",
            !isVisionSection &&
              "hover:bg-stone-100/60 dark:hover:bg-stone-800/60 hover:text-stone-900 dark:hover:text-stone-50",
            isVisionSection && "hover:bg-stone-50",
          )}
        >
          비전 처리
        </Link>
        <button
          type="button"
          onClick={() => setVisionExpanded((v) => !v)}
          aria-expanded={visionExpanded}
          aria-label={visionExpanded ? "하위 메뉴 접기" : "하위 메뉴 펼치기"}
          className={cn(
            "flex shrink-0 items-center justify-center rounded-r-lg px-2 py-2.5 transition-colors",
            !isVisionSection &&
              "hover:bg-stone-100/60 dark:hover:bg-stone-800/60 hover:text-stone-900 dark:hover:text-stone-50",
            isVisionSection && "hover:bg-stone-50",
          )}
        >
          <ChevronRight
            className={cn(
              "size-4 transition-transform duration-200",
              visionExpanded && "rotate-90",
            )}
            aria-hidden
          />
        </button>
      </div>

      {visionExpanded && (
        <>
          <Link
            href={OBJECT_DETECTION_HREF}
            aria-current={isObjectDetection ? "page" : undefined}
            className={cn(
              "rounded-lg py-2 pl-6 pr-3 text-sm transition-colors",
              isObjectDetection
                ? "bg-stone-100/90 font-semibold text-stone-950"
                : "text-stone-600 dark:text-stone-300 hover:bg-stone-100/60 dark:hover:bg-stone-800/60 hover:text-stone-900 dark:hover:text-stone-50",
            )}
          >
            객체 탐지
          </Link>
        </>
      )}

      <Link
        href={RAG_CHAT_HREF}
        aria-current={isRagChat ? "page" : undefined}
        className={cn(
          "rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
          isRagChat
            ? "bg-stone-100 text-stone-950 hover:bg-stone-50"
            : "text-stone-600 dark:text-stone-300 hover:bg-stone-100/60 dark:hover:bg-stone-800/60 hover:text-stone-900 dark:hover:text-stone-50",
        )}
      >
        RAG 챗봇
      </Link>

      <Link
        href={CRAWLER_SCRAPER_HREF}
        aria-current={isCrawlerScraper ? "page" : undefined}
        className={cn(
          "rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
          isCrawlerScraper
            ? "bg-stone-100 text-stone-950 hover:bg-stone-50"
            : "text-stone-600 dark:text-stone-300 hover:bg-stone-100/60 dark:hover:bg-stone-800/60 hover:text-stone-900 dark:hover:text-stone-50",
        )}
      >
        크롤러/스크래퍼
      </Link>
    </nav>
  );

  return (
    <div className="relative flex min-h-[calc(100vh-1px)] bg-stone-50 dark:bg-stone-900 text-stone-900 dark:text-stone-100">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_130%_85%_at_50%_-35%,rgba(168,162,158,0.2),transparent_62%)]"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_70%_55%_at_0%_100%,rgba(120,113,108,0.14),transparent_58%)]"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_65%_50%_at_100%_0%,rgba(87,83,78,0.12),transparent_52%)]"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-[0.025] bg-[repeating-linear-gradient(118deg,#fafaf9_0px,#fafaf9_1px,transparent_1px,transparent_24px)]"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-gradient-to-b from-stone-950/25 via-transparent to-stone-950/75"
      />

      {/* Desktop sidebar */}
      <aside className="relative z-10 hidden w-52 shrink-0 border-r border-stone-200/70 dark:border-stone-800/70 bg-white/35 dark:bg-stone-950/35 px-3 py-6 backdrop-blur-sm md:block">
        {nav}
      </aside>

      {/* Mobile: hamburger + drawer */}
      <div
        className={cn(
          "relative z-10 flex min-h-0 min-w-0 flex-1 flex-col",
          isSmithSailor && "overflow-hidden",
        )}
      >
        <div className="sticky top-[4.25rem] z-20 flex items-center gap-2 border-b border-stone-200/60 dark:border-stone-800/60 bg-white/70 dark:bg-stone-900/70 px-4 py-3 backdrop-blur md:hidden">
          <button
            type="button"
            onClick={() => setMobileOpen(true)}
            className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-stone-300/70 dark:border-stone-700/70 bg-stone-100/40 dark:bg-stone-800/40 text-stone-700 dark:text-stone-100 hover:bg-stone-200/60 dark:hover:bg-stone-700/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-stone-500/50"
            aria-label="메뉴 열기"
          >
            <Menu className="size-5" aria-hidden />
          </button>
          <span className="text-sm font-semibold text-stone-700 dark:text-stone-200">타이타닉</span>
        </div>

        {children}
      </div>

      {mobileOpen && (
        <div className="fixed inset-0 z-[60] md:hidden" role="dialog" aria-modal="true">
          <button
            type="button"
            className="absolute inset-0 bg-black/55"
            aria-label="메뉴 닫기"
            onClick={() => setMobileOpen(false)}
          />
          <aside className="absolute left-0 top-0 h-full w-[18rem] border-r border-stone-200/70 dark:border-stone-800/70 bg-white/90 dark:bg-stone-950/90 px-3 py-6 backdrop-blur">
            <div className="mb-4 flex items-center justify-between">
              <span className="text-sm font-bold text-stone-900 dark:text-stone-100">타이타닉</span>
              <button
                type="button"
                onClick={() => setMobileOpen(false)}
                className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-stone-200/70 dark:border-stone-800/70 bg-stone-100/50 dark:bg-stone-900/50 text-stone-600 dark:text-stone-200 hover:bg-stone-200/70 dark:hover:bg-stone-800/70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-stone-500/50"
                aria-label="닫기"
              >
                <X className="size-5" aria-hidden />
              </button>
            </div>
            {nav}
          </aside>
        </div>
      )}
    </div>
  );
}
