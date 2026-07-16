import { DatasetCollectionPipeline } from "@/components/dataset-collection-pipeline";

export default function LessonDatasetCollectionCrawlerScraperPage() {
  return (
    <main className="px-4 py-8 md:px-6">
      <div className="mx-auto max-w-2xl">
        <div className="mb-8 border-b border-neutral-100 pb-8 dark:border-gray-800">
          <p className="text-[10px] uppercase tracking-[0.3em] text-neutral-400">
            Lesson · Dataset Collection
          </p>
          <h1 className="mt-2 text-2xl font-semibold uppercase tracking-[0.06em] text-neutral-900 dark:text-neutral-100">
            Crawler / Scraper
          </h1>
          <p className="mt-4 text-sm text-neutral-600 dark:text-neutral-400">
            사이트 주소와 자연어 명령어를 입력해 크롤링·스크래핑을 실행하고,
            탭으로 각 단계 결과를 확인합니다.
          </p>
        </div>
        <DatasetCollectionPipeline />
      </div>
    </main>
  );
}
