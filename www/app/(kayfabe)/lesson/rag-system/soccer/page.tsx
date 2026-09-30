import { SoccerChat } from "@/components/soccer-chat";

export default function LessonRagSystemMoneyballPage() {
  return (
    <main className="flex h-[calc(100dvh-7.75rem)] max-h-[calc(100dvh-7.75rem)] flex-col overflow-hidden px-4 py-6 md:h-[calc(100dvh-4.25rem)] md:max-h-[calc(100dvh-4.25rem)] md:px-6">
      <div className="mx-auto w-full max-w-3xl shrink-0 border-b border-neutral-100 pb-6 dark:border-gray-800">
        <p className="text-[10px] uppercase tracking-[0.3em] text-neutral-400 dark:text-neutral-500">
          Lesson · RAG Bot
        </p>
        <h1 className="mt-2 text-2xl font-semibold uppercase tracking-[0.06em] text-neutral-900 dark:text-neutral-100">
          Soccer RAG
        </h1>
        <p className="mt-4 text-sm text-neutral-600 dark:text-neutral-400">
          경기장·구단·경기 일정·선수 데이터를 검색 증강 생성(RAG)으로 연결하는 실습입니다.
        </p>
      </div>
      <SoccerChat className="mx-auto mt-6 w-full max-w-3xl flex-1" />
    </main>
  );
}
