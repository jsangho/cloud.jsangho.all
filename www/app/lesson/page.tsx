import Link from "next/link";
import { ArrowRight, Eye, FileText, MessagesSquare, Search } from "lucide-react";

const LESSONS = [
  {
    href: "/lesson/vision",
    icon: Eye,
    title: "비전 처리",
    description: "이미지를 업로드해 분류·객체 탐지 파이프라인으로 보냅니다.",
  },
  {
    href: "/lesson/rag-system/rag-chat",
    icon: MessagesSquare,
    title: "RAG 챗",
    description: "수집한 문서를 근거로 답하는 검색 증강 생성 연습입니다.",
  },
  {
    href: "/lesson/dataset-collection/crawler-scraper",
    icon: Search,
    title: "크롤러 · 스크레이퍼",
    description: "공개 페이지에서 데이터셋을 모으는 수집기 연습입니다.",
  },
  {
    href: "/lesson/ledger",
    icon: FileText,
    title: "원장",
    description: "영수증을 읽어 장부로 옮기는 연습입니다.",
  },
] as const;

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
          {LESSONS.map(({ href, icon: Icon, title, description }) => (
            <Link
              key={href}
              href={href}
              className="group rounded-3xl border border-stone-300/60 dark:border-stone-700/60 bg-stone-50/45 dark:bg-stone-950/45 p-6 shadow-lg shadow-black/20 backdrop-blur-sm transition-colors hover:border-stone-400/70 dark:hover:border-stone-500/70 hover:bg-stone-100/60 dark:hover:bg-stone-950/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-stone-500/50"
            >
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="flex items-center gap-2 text-sm font-semibold text-stone-800 dark:text-stone-100">
                    <Icon className="size-5 text-stone-500 dark:text-stone-300" aria-hidden />
                    {title}
                  </div>
                  <p className="mt-2 text-sm text-stone-600 dark:text-stone-300">{description}</p>
                </div>
                <ArrowRight
                  className="mt-1 size-5 text-stone-400 transition-transform group-hover:translate-x-0.5"
                  aria-hidden
                />
              </div>
            </Link>
          ))}
        </div>
      </div>
    </main>
  );
}
