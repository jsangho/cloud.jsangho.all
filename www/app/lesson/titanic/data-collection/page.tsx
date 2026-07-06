import { TitanicCsvUpload } from "@/components/titanic-csv-upload";

export default function LessonTitanicDataCollectionPage() {
  return (
    <main className="px-4 py-8">
      <div className="mx-auto max-w-2xl">
        <h1 className="mb-2 text-3xl font-bold tracking-tight md:text-4xl">
          1. 데이터 수집
        </h1>
        <p className="mb-8 text-sm text-stone-600 dark:text-stone-300">
          준비된 데이터셋{" "}
          <code className="rounded bg-stone-200/40 dark:bg-stone-950/40 px-1.5 py-0.5 text-xs text-stone-800 dark:text-stone-100">
            Titanic.csv
          </code>
          를 업로드하세요.
        </p>
        <TitanicCsvUpload />
      </div>
    </main>
  );
}
