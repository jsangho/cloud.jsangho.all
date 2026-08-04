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

export function ReceiptCard({ receipt, state, onRead }: ReceiptCardProps) {
  const isLoading = state.kind === "loading";

  return (
    <li className="overflow-hidden rounded-lg border border-neutral-200 dark:border-neutral-800">
      <div className="relative aspect-[4/3] bg-neutral-100 dark:bg-neutral-900">
        <Image
          src={receipt.thumbnailUrl}
          alt="영수증 사진"
          fill
          sizes="(max-width: 640px) 100vw, 50vw"
          className="object-cover"
        />
      </div>

      <div className="space-y-3 p-3">
        <p className="text-xs text-neutral-500 dark:text-neutral-400">
          {formatCapturedAt(receipt.capturedAt)}
        </p>

        {state.kind === "done" ? (
          <ReceiptDraftPanel draft={state.draft} />
        ) : (
          <div className="space-y-2">
            {state.kind === "error" ? (
              <p className="text-xs text-red-600 dark:text-red-400">{state.message}</p>
            ) : null}

            {state.kind === "error" && !state.canRetry ? null : (
              <Button
                type="button"
                size="sm"
                variant="outline"
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
        )}
      </div>
    </li>
  );
}
