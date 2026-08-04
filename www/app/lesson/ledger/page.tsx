export default function LessonLedgerPage() {
  return (
    <main className="px-4 py-8 md:px-6">
      <div className="mx-auto max-w-2xl">
        <div className="mb-8 border-b border-neutral-100 pb-8 dark:border-gray-800">
          <p className="text-[10px] uppercase tracking-[0.3em] text-neutral-400">Lesson · Ledger</p>
          <h1 className="mt-2 text-2xl font-semibold uppercase tracking-[0.06em] text-neutral-900 dark:text-neutral-100">
            가계부
          </h1>
          <p className="mt-4 text-sm text-neutral-600 dark:text-neutral-400">
            S3에 보관된 영수증을 서버가 꺼내 OCR로 판독하고, 상호명·거래일시·합계·품목을 가계부
            내역으로 정리하는 연습입니다.
          </p>
        </div>

        <p className="text-sm text-neutral-600 dark:text-neutral-400">
          아직 화면을 붙이지 않았습니다. 영수증 목록을 내려주는 백엔드 엔드포인트가 있어야 첫 화면을
          그릴 수 있습니다.
        </p>
      </div>
    </main>
  );
}
