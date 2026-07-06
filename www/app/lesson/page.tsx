import Link from "next/link";
import { BookOpen, Database, ArrowRight, ListChecks } from "lucide-react";

export default function LessonHomePage() {
  return (
    <main className="px-4 py-10">
      <div className="mx-auto max-w-4xl">
        <h1 className="text-balance text-3xl font-extrabold tracking-tight text-stone-900 dark:text-stone-50 md:text-4xl">
          Lesson
        </h1>
        <p className="mt-2 max-w-2xl text-sm leading-relaxed text-stone-600 dark:text-stone-300">
          수업용 연습 페이지 모음입니다. 아래 메뉴에서 연습 주제를 선택하세요.
        </p>

        <div className="mt-8 grid gap-4 sm:grid-cols-2">
          <Link
            href="/lesson/titanic"
            className="group rounded-3xl border border-stone-300/60 dark:border-stone-700/60 bg-stone-50/45 dark:bg-stone-950/45 p-6 shadow-lg shadow-black/20 backdrop-blur-sm transition-colors hover:border-stone-400/70 dark:hover:border-stone-500/70 hover:bg-stone-100/60 dark:hover:bg-stone-950/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-stone-500/50"
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="flex items-center gap-2 text-sm font-semibold text-stone-800 dark:text-stone-100">
                  <BookOpen
                    className="size-5 text-stone-500 dark:text-stone-300"
                    aria-hidden
                  />
                  분석 연습
                </div>
                <p className="mt-2 text-sm text-stone-600 dark:text-stone-300">
                  수업용 연습 페이지(분석)로 이동합니다.
                </p>
              </div>
              <ArrowRight
                className="mt-1 size-5 text-stone-400 transition-transform group-hover:translate-x-0.5"
                aria-hidden
              />
            </div>
          </Link>

          <Link
            href="/lesson/titanic/data-collection"
            className="group rounded-3xl border border-stone-300/60 dark:border-stone-700/60 bg-stone-50/45 dark:bg-stone-950/45 p-6 shadow-lg shadow-black/20 backdrop-blur-sm transition-colors hover:border-stone-400/70 dark:hover:border-stone-500/70 hover:bg-stone-100/60 dark:hover:bg-stone-950/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-stone-500/50"
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="flex items-center gap-2 text-sm font-semibold text-stone-800 dark:text-stone-100">
                  <Database
                    className="size-5 text-stone-500 dark:text-stone-300"
                    aria-hidden
                  />
                  데이터 수집
                </div>
                <p className="mt-2 text-sm text-stone-600 dark:text-stone-300">
                  CSV 업로드(브라우저) 등 데이터 준비 연습으로 이동합니다.
                </p>
              </div>
              <ArrowRight
                className="mt-1 size-5 text-stone-400 transition-transform group-hover:translate-x-0.5"
                aria-hidden
              />
            </div>
          </Link>

          <Link
            href="/lesson/titanic/titaniclist"
            className="group rounded-3xl border border-stone-300/60 dark:border-stone-700/60 bg-stone-50/45 dark:bg-stone-950/45 p-6 shadow-lg shadow-black/20 backdrop-blur-sm transition-colors hover:border-stone-400/70 dark:hover:border-stone-500/70 hover:bg-stone-100/60 dark:hover:bg-stone-950/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-stone-500/50"
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="flex items-center gap-2 text-sm font-semibold text-stone-800 dark:text-stone-100">
                  <ListChecks
                    className="size-5 text-stone-500 dark:text-stone-300"
                    aria-hidden
                  />
                  DB 리스트
                </div>
                <p className="mt-2 text-sm text-stone-600 dark:text-stone-300">
                  Neon DB의 타이타닉 테이블 데이터를 50개씩 조회합니다.
                </p>
              </div>
              <ArrowRight
                className="mt-1 size-5 text-stone-400 transition-transform group-hover:translate-x-0.5"
                aria-hidden
              />
            </div>
          </Link>
        </div>
      </div>
    </main>
  );
}
