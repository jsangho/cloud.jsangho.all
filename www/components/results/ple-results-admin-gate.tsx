"use client";

import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  isResultsAdmin,
  lockResultsAdmin,
  unlockResultsAdmin,
} from "@/lib/ple-results-admin";

type PleResultsAdminGateProps = {
  onAdminChange?: (isAdmin: boolean) => void;
};

export function PleResultsAdminGate({
  onAdminChange,
}: PleResultsAdminGateProps) {
  const [isAdmin, setIsAdmin] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const ok = isResultsAdmin();
    setIsAdmin(ok);
    onAdminChange?.(ok);
  }, [onAdminChange]);

  const notify = useCallback(
    (ok: boolean) => {
      setIsAdmin(ok);
      onAdminChange?.(ok);
    },
    [onAdminChange],
  );

  const handleUnlock = (e: React.FormEvent) => {
    e.preventDefault();
    if (unlockResultsAdmin(password)) {
      setPassword("");
      setError(null);
      setDialogOpen(false);
      notify(true);
      return;
    }
    setError("비밀번호가 올바르지 않습니다.");
  };

  const handleLock = () => {
    lockResultsAdmin();
    notify(false);
  };

  return (
    <>
      <div className="flex flex-col gap-3 rounded-xl border border-stone-300/70 dark:border-stone-600/70 bg-stone-100/45 dark:bg-stone-800/45 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm text-stone-400">
          {isAdmin
            ? "관리자 모드 — 경기 결과를 등록·수정할 수 있습니다."
            : "경기 결과 등록·수정은 관리자만 할 수 있습니다."}
        </p>
        <div className="flex shrink-0 gap-2">
          {isAdmin ? (
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="border-stone-300 dark:border-stone-600 bg-stone-100/60 dark:bg-stone-900/60 text-stone-600 dark:text-stone-300 hover:bg-stone-200 dark:hover:bg-stone-800"
              onClick={handleLock}
            >
              관리자 종료
            </Button>
          ) : (
            <Button
              type="button"
              size="sm"
              className="bg-amber-600 text-stone-950 hover:bg-amber-500"
              onClick={() => {
                setError(null);
                setDialogOpen(true);
              }}
            >
              관리자 인증
            </Button>
          )}
        </div>
      </div>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="border-stone-300 dark:border-stone-700 bg-stone-50 dark:bg-stone-900 text-stone-900 dark:text-stone-100 sm:max-w-sm">
          <DialogHeader>
            <DialogTitle className="text-stone-900 dark:text-stone-50">
              관리자 인증
            </DialogTitle>
            <DialogDescription className="text-stone-400">
              결과를 등록·수정하려면 비밀번호를 입력하세요.
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleUnlock} className="space-y-4">
            <div className="space-y-2">
              <label
                htmlFor="ple-results-admin-password"
                className="text-sm font-medium text-stone-700 dark:text-stone-300"
              >
                비밀번호
              </label>
              <input
                id="ple-results-admin-password"
                type="password"
                autoComplete="off"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full rounded-lg border border-stone-300 dark:border-stone-600 bg-stone-100 dark:bg-stone-950 px-3 py-2 text-sm text-stone-900 dark:text-stone-100 outline-none focus:border-amber-500/80 focus:ring-1 focus:ring-amber-500/40"
              />
            </div>
            {error && (
              <p className="text-sm text-red-400" role="alert">
                {error}
              </p>
            )}
            <Button
              type="submit"
              className="w-full bg-amber-600 text-stone-950 hover:bg-amber-500"
            >
              확인
            </Button>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}
