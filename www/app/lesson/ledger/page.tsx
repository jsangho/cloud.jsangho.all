"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { ReceiptCard, type ReceiptCardState } from "@/components/ledger/receipt-card";
import { useAuth } from "@/context/auth-context";
import {
  fetchReceipts,
  requestReceiptOcr,
  type ReceiptDraft,
  type ReceiptSummary,
} from "@/lib/receipt-api";

type ListState =
  | { kind: "loading" }
  | { kind: "ready"; items: ReceiptSummary[] }
  | { kind: "error"; message: string }
  /** 세션이 만료돼 목록을 부를 수 없는 상태. 빈 목록과 구분한다. */
  | { kind: "unauthorized" };

/**
 * 판독은 한 번에 한 장이다 — 불리언 3개 대신 판별 유니온으로 들어
 * "로딩 중인데 에러도 있는" 표현 불가능한 상태를 만들지 않는다.
 */
type OcrState =
  | { kind: "idle" }
  | { kind: "loading"; key: string }
  | { kind: "done"; key: string; draft: ReceiptDraft }
  | { kind: "error"; key: string; message: string; canRetry: boolean };

function cardStateOf(ocr: OcrState, key: string): ReceiptCardState {
  if (ocr.kind === "idle" || ocr.key !== key) return { kind: "idle" };
  if (ocr.kind === "loading") return { kind: "loading" };
  if (ocr.kind === "done") return { kind: "done", draft: ocr.draft };
  return { kind: "error", message: ocr.message, canRetry: ocr.canRetry };
}

function CardSkeleton() {
  return (
    <li className="overflow-hidden rounded-lg border border-neutral-200 dark:border-neutral-800">
      <div className="aspect-[4/3] animate-pulse bg-neutral-100 dark:bg-neutral-900" />
      <div className="space-y-2 p-3">
        <div className="h-3 w-24 animate-pulse rounded bg-neutral-100 dark:bg-neutral-900" />
        <div className="h-8 w-24 animate-pulse rounded bg-neutral-100 dark:bg-neutral-900" />
      </div>
    </li>
  );
}

export default function LessonLedgerPage() {
  const { user, isReady } = useAuth();
  const [list, setList] = useState<ListState>({ kind: "loading" });
  const [ocr, setOcr] = useState<OcrState>({ kind: "idle" });
  const [notice, setNotice] = useState<string | null>(null);

  /**
   * 401은 이 화면 안에서만 처리한다.
   *
   * `auth-context`의 `refresh()`를 부르면 `/auth/me`가 한 번 실패하는 것만으로
   * 전역 사용자 상태가 지워져 **다른 화면까지 로그아웃된다.** 목록 한 건이
   * 실패했다는 사실이 세션 종료를 뜻하지는 않으므로, 세션 판정은 auth-context에
   * 맡기고 여기서는 로그인 안내만 띄운다.
   */
  const loadList = useCallback(async () => {
    setList({ kind: "loading" });
    const result = await fetchReceipts();

    if (result.ok) {
      setList({ kind: "ready", items: result.items });
      return;
    }
    if (result.status === 401) {
      setList({ kind: "unauthorized" });
      return;
    }
    setList({ kind: "error", message: result.message });
  }, []);

  const userId = user?.id ?? null;

  useEffect(() => {
    if (!isReady || userId === null) return;
    void loadList();
  }, [isReady, userId, loadList]);

  const handleRead = useCallback(
    async (key: string) => {
      setNotice(null);
      setOcr({ kind: "loading", key });
      const result = await requestReceiptOcr(key);

      if (result.ok) {
        setOcr({ kind: "done", key, draft: result.draft });
        return;
      }
      if (result.status === 401) {
        setOcr({ kind: "idle" });
        setList({ kind: "unauthorized" });
        return;
      }
      if (result.status === 404) {
        // 이미 사라진 이미지다. 카드를 지우고 목록을 다시 맞춘다.
        setOcr({ kind: "idle" });
        setNotice(result.message);
        void loadList();
        return;
      }
      setOcr({ kind: "error", key, message: result.message, canRetry: result.canRetry });
    },
    [loadList],
  );

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

        {!isReady ? (
          <ul className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <CardSkeleton />
            <CardSkeleton />
          </ul>
        ) : !user || list.kind === "unauthorized" ? (
          <div className="space-y-3">
            <p className="text-sm text-neutral-600 dark:text-neutral-400">
              영수증은 촬영한 본인만 볼 수 있습니다. 로그인 후 이용해 주세요.
            </p>
            <Button asChild size="sm">
              <Link href="/login">로그인</Link>
            </Button>
          </div>
        ) : (
          <div className="space-y-4">
            {notice ? (
              <p className="text-sm text-neutral-600 dark:text-neutral-400">{notice}</p>
            ) : null}

            {list.kind === "loading" ? (
              <ul className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <CardSkeleton />
                <CardSkeleton />
              </ul>
            ) : list.kind === "error" ? (
              <div className="space-y-3">
                <p className="text-sm text-red-600 dark:text-red-400">{list.message}</p>
                <Button type="button" size="sm" variant="outline" onClick={() => void loadList()}>
                  다시 시도
                </Button>
              </div>
            ) : list.items.length === 0 ? (
              <p className="text-sm text-neutral-600 dark:text-neutral-400">
                촬영한 영수증이 없습니다. 앱에서 영수증을 촬영하면 여기에 표시됩니다.
              </p>
            ) : (
              <ul className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                {list.items.map((receipt) => (
                  <ReceiptCard
                    key={receipt.key}
                    receipt={receipt}
                    state={cardStateOf(ocr, receipt.key)}
                    onRead={(key) => void handleRead(key)}
                  />
                ))}
              </ul>
            )}
          </div>
        )}
      </div>
    </main>
  );
}
