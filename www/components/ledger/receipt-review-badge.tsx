import { AlertTriangle } from "lucide-react";

/**
 * 판독 결과가 초안임을 드러내는 배지. 확정 내역처럼 보이지 않게 하는 것이 이 배지의 일이다.
 */
export function ReceiptReviewBadge() {
  return (
    <span className="inline-flex items-center gap-1 rounded border border-amber-300 bg-amber-50 px-1.5 py-0.5 text-[11px] font-medium text-amber-700 dark:border-amber-700/60 dark:bg-amber-950/40 dark:text-amber-300">
      <AlertTriangle className="size-3" aria-hidden />
      확인 필요
    </span>
  );
}
