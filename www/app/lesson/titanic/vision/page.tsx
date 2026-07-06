import { TitanicVisionUpload } from "@/components/titanic-vision-upload";

export default function LessonTitanicVisionPage() {
  return (
    <main className="px-4 py-8">
      <div className="mx-auto max-w-2xl">
        <h1 className="mb-2 text-3xl font-bold tracking-tight md:text-4xl">
          비전 처리
        </h1>
        <p className="mb-8 text-sm text-stone-600 dark:text-stone-300">
          <code className="rounded bg-stone-200/40 dark:bg-stone-950/40 px-1.5 py-0.5 text-xs text-stone-800 dark:text-stone-100">
            jpg
          </code>
          ,{" "}
          <code className="rounded bg-stone-200/40 dark:bg-stone-950/40 px-1.5 py-0.5 text-xs text-stone-800 dark:text-stone-100">
            png
          </code>{" "}
          이미지 파일을 업로드하면 비전 파이프라인으로 전달됩니다.
        </p>
        <TitanicVisionUpload />
      </div>
    </main>
  );
}
