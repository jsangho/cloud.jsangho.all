import type { ReceiptDraft } from "@/lib/receipt-api";
import { ReceiptReviewBadge } from "@/components/ledger/receipt-review-badge";

const UNREAD = "판독하지 못함";

/** 금액은 정수 원 단위로 받아 표시할 때만 포맷한다. null은 0으로 채우지 않는다. */
function formatAmount(value: number | null): string {
  if (value === null) return UNREAD;
  return `${value.toLocaleString("ko-KR")}원`;
}

function formatTransactedAt(value: string | null): string {
  if (!value) return UNREAD;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return UNREAD;
  return parsed.toLocaleString("ko-KR", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-1.5">
      <dt className="shrink-0 text-xs text-neutral-500 dark:text-neutral-400">{label}</dt>
      <dd className="text-right text-sm text-neutral-900 dark:text-neutral-100">{value}</dd>
    </div>
  );
}

export function ReceiptDraftPanel({ draft }: { draft: ReceiptDraft }) {
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-2">
        <p className="text-sm font-medium text-neutral-900 dark:text-neutral-100">
          {draft.merchantName ?? UNREAD}
        </p>
        {draft.needsReview ? <ReceiptReviewBadge /> : null}
      </div>

      <dl className="divide-y divide-neutral-100 dark:divide-neutral-800">
        <Row label="거래일시" value={formatTransactedAt(draft.transactedAt)} />
        <Row label="합계" value={formatAmount(draft.totalAmount)} />
        <Row label="부가세" value={formatAmount(draft.vatAmount)} />
        <Row label="사업자번호" value={draft.businessNo ?? UNREAD} />
      </dl>

      {draft.lineItems.length > 0 ? (
        // 좁은 화면에서 페이지 본문이 아니라 이 표만 가로로 스크롤되게 한다.
        <div className="overflow-x-auto">
          <table className="w-full min-w-[22rem] text-left text-xs">
            <thead className="text-neutral-500 dark:text-neutral-400">
              <tr>
                <th className="py-1.5 pr-3 font-medium">품목</th>
                <th className="py-1.5 pr-3 text-right font-medium">수량</th>
                <th className="py-1.5 pr-3 text-right font-medium">단가</th>
                <th className="py-1.5 text-right font-medium">금액</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-100 text-neutral-800 dark:divide-neutral-800 dark:text-neutral-200">
              {draft.lineItems.map((item, index) => (
                <tr key={`${item.name}-${index}`}>
                  <td className="py-1.5 pr-3">{item.name || UNREAD}</td>
                  <td className="py-1.5 pr-3 text-right tabular-nums">
                    {item.quantity.toLocaleString("ko-KR")}
                  </td>
                  <td className="py-1.5 pr-3 text-right tabular-nums">
                    {formatAmount(item.unitPrice)}
                  </td>
                  <td className="py-1.5 text-right tabular-nums">{formatAmount(item.amount)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="text-xs text-neutral-500 dark:text-neutral-400">
          품목을 판독하지 못했습니다.
        </p>
      )}
    </div>
  );
}
