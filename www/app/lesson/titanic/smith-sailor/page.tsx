import { SmithCaptainChat } from "@/components/smith-captain-chat";

export default function LessonSmithSailorPage() {
  return (
    <main className="flex h-[calc(100dvh-7.75rem)] max-h-[calc(100dvh-7.75rem)] flex-col overflow-hidden px-4 py-6 md:h-[calc(100dvh-4.25rem)] md:max-h-[calc(100dvh-4.25rem)] md:px-6">
      <div className="mx-auto flex w-full max-w-3xl shrink-0 flex-col gap-1 pb-3">
        <h1 className="text-2xl font-bold tracking-tight text-stone-900 dark:text-stone-50 md:text-3xl">
          3. 스미스 선장과 대화
        </h1>
        <p className="text-sm text-stone-400">
          타이타닉의 총책임자인 에드워드 스미스 선장과 대화해 보세요.
        </p>
      </div>
      <SmithCaptainChat className="mx-auto w-full max-w-3xl flex-1" />
    </main>
  );
}
