import Link from "next/link";
import { PleEventGrid } from "@/components/ple-event-grid";

export default function ResultsPage() {
  return (
    <main className="min-h-[calc(100dvh-5.5rem)] w-full min-w-0 bg-stone-50 dark:bg-stone-900 px-4 py-10 text-stone-900 dark:text-stone-100">
      <div className="mx-auto w-full max-w-5xl min-w-0">
        <header className="mb-8 text-center">
          <h1 className="text-2xl font-bold tracking-tight text-stone-50 sm:text-3xl">
            PLE 경기 결과
          </h1>
          <p className="mt-2 text-sm text-stone-400 sm:text-base">
            이벤트를 선택한 뒤, 각 경기의 승자를 등록하세요. 등록된 결과는 Neon
            DB에 저장되며 예측·순위 화면에 반영됩니다.
          </p>
        </header>
        <PleEventGrid variant="large" hrefPrefix="/results" />
        <p className="mt-8 text-center text-sm text-stone-500">
          <Link
            href="/ple"
            className="text-stone-400 underline-offset-2 hover:text-stone-200 hover:underline"
          >
            예측 페이지로 이동
          </Link>
        </p>
      </div>
    </main>
  );
}
