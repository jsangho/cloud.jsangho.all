"use client";

import Image from "next/image";
import { Loader2, ScanLine } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ReceiptDraftPanel } from "@/components/ledger/receipt-draft-panel";
import type { ReceiptDraft, ReceiptSummary } from "@/lib/receipt-api";

/** 카드 한 장의 판독 상태. 목록 전체가 아니라 이 카드 안에서만 로딩을 표시한다. */
export type ReceiptCardState =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "done"; draft: ReceiptDraft }
  | { kind: "error"; message: string; canRetry: boolean };

type ReceiptCardProps = {
  receipt: ReceiptSummary;
  state: ReceiptCardState;
  onRead: (key: string) => void;
};

const THUMBNAIL_SIZE = 56;

function formatCapturedAt(value: string | null): string {
  if (!value) return "촬영 시각 미상";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "촬영 시각 미상";
  return parsed.toLocaleString("ko-KR", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** 접힌 줄에 보이는 요약. 상호는 아래 패널이 맡으므로 여기서는 합계만 보여준다. */
function summaryLine(state: ReceiptCardState): string | null {
  if (state.kind !== "done") return null;
  return state.draft.totalAmount === null
    ? "합계를 판독하지 못함"
    : `합계 ${state.draft.totalAmount.toLocaleString("ko-KR")}원`;
}

export function ReceiptCard({ receipt, state, onRead }: ReceiptCardProps) {
  const isLoading = state.kind === "loading";
  const summary = summaryLine(state);

  return (
    <li className="overflow-hidden rounded-lg border border-neutral-200 dark:border-neutral-800">
      <div className="flex items-center gap-3 p-2.5">
        {/* 목록에서는 작게 보여주고, 원본은 새 탭에서 연다 — 세로로 긴 영수증을
            카드마다 크게 펼치면 한 화면에 두세 장밖에 들어가지 않는다. */}
        <a
          href={receipt.thumbnailUrl}
          target="_blank"
          rel="noreferrer"
          className="shrink-0"
          title="원본 보기"
        >
          <Image
            src={receipt.thumbnailUrl}
            alt="영수증 사진"
            width={THUMBNAIL_SIZE}
            height={THUMBNAIL_SIZE}
            className="size-14 rounded object-cover"
          />
        </a>

        <div className="min-w-0 flex-1">
          <p className="truncate text-xs text-neutral-500 dark:text-neutral-400">
            {formatCapturedAt(receipt.capturedAt)}
          </p>
          {summary ? (
            <p className="truncate text-sm font-medium text-neutral-900 dark:text-neutral-100">
              {summary}
            </p>
          ) : state.kind === "error" ? (
            <p className="truncate text-xs text-red-600 dark:text-red-400">{state.message}</p>
          ) : null}
        </div>

        {state.kind === "error" && !state.canRetry ? null : state.kind === "done" ? null : (
          <Button
            type="button"
            size="sm"
            variant="outline"
            className="shrink-0"
            disabled={isLoading}
            onClick={() => onRead(receipt.key)}
          >
            {isLoading ? (
              <>
                <Loader2 className="animate-spin" aria-hidden />
                판독 중
              </>
            ) : (
              <>
                <ScanLine aria-hidden />
                {state.kind === "error" ? "다시 시도" : "판독하기"}
              </>
            )}
          </Button>
        )}
      </div>

      {state.kind === "done" ? (
        <div className="border-t border-neutral-100 p-3 dark:border-neutral-800">
          <ReceiptDraftPanel draft={state.draft} />
        </div>
      ) : null}
    </li>
  );
}
