"use client";

import { useCallback, useEffect, useState } from "react";
import { Loader2, Users } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/context/auth-context";
import { changeUserRole, fetchAdminUsers, type AdminUser } from "@/lib/user-admin-api";

/**
 * 사용자 관리 패널.
 *
 * **지금까지 역할을 주는 경로가 코드에 없었다** — 회원가입은 늘 `user`로 만들고,
 * 저장소 어디에도 `admin`을 쓰는 코드가 없었다. 기존 관리자 계정은 사람이 DB를 고쳐
 * 만든 것이고, 둘째 관리자가 필요하면 또 그래야 했다. 이 화면이 그 자리를 메운다.
 *
 * 거절은 서버가 한다 — 자기 권한을 떼는 것과 마지막 관리자를 떼는 것(둘 다 409).
 * 화면은 그 두 경우에 **버튼을 미리 잠그고 이유를 적지만**, 그것은 설명이고 판정이
 * 아니다. 서버가 거절하면 그 문구를 그대로 보여준다.
 */

type PanelState = {
  loading: boolean;
  users: AdminUser[];
  admins: number;
  query: string;
  error: string | null;
  /** 지금 바꾸는 중인 사용자. 한 번에 하나만 바꾼다. */
  busyId: number | null;
};

export function UserAdminPanel() {
  const { user } = useAuth();
  const [state, setState] = useState<PanelState>({
    loading: true,
    users: [],
    admins: 0,
    query: "",
    error: null,
    busyId: null,
  });

  const patch = (next: Partial<PanelState>) => setState((prev) => ({ ...prev, ...next }));

  const load = useCallback(async (query: string) => {
    patch({ loading: true, error: null });
    try {
      const list = await fetchAdminUsers(query || undefined);
      patch({ loading: false, users: list.items, admins: list.admins });
    } catch (e) {
      patch({
        loading: false,
        users: [],
        error: e instanceof Error ? e.message : "불러오지 못했습니다.",
      });
    }
  }, []);

  useEffect(() => {
    void load("");
  }, [load]);

  /** 잠그는 이유. `null`이면 바꿀 수 있다. */
  const blockedReason = (target: AdminUser): string | null => {
    if (target.role !== "admin") return null;
    if (user?.id === target.userId) return "자신의 권한은 뗄 수 없습니다";
    if (state.admins <= 1) return "마지막 관리자입니다";
    return null;
  };

  const toggle = async (target: AdminUser) => {
    const next = target.role === "admin" ? "user" : "admin";
    if (!window.confirm(`${target.nickname}의 역할을 ${next}로 바꿉니다.`)) return;
    patch({ busyId: target.userId, error: null });
    try {
      await changeUserRole(target.userId, next);
      await load(state.query);
    } catch (e) {
      patch({ error: e instanceof Error ? e.message : "바꾸지 못했습니다." });
    } finally {
      patch({ busyId: null });
    }
  };

  return (
    <div className="rounded-xl border border-stone-300/50 dark:border-stone-700/50 bg-stone-50/70 dark:bg-stone-950/70 p-6">
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Users className="h-4 w-4 text-stone-400" />
          <h2 className="text-sm font-semibold text-stone-100">사용자</h2>
          <span className="rounded-full bg-stone-700 px-1.5 py-0.5 text-[10px] text-stone-300">
            관리자 {state.admins}
          </span>
        </div>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void load(state.query);
          }}
          className="flex items-center gap-1.5"
        >
          <input
            type="text"
            value={state.query}
            onChange={(e) => patch({ query: e.target.value })}
            placeholder="닉네임·아이디·이메일"
            className="w-44 rounded-lg border border-stone-700/60 bg-stone-900/60 px-3 py-1.5 text-xs text-stone-100 placeholder-stone-600 outline-none focus:border-stone-500"
          />
          <button
            type="submit"
            disabled={state.loading}
            className="rounded-lg border border-stone-600/70 bg-stone-800/45 px-2.5 py-1.5 text-[11px] text-stone-200 transition-colors hover:bg-stone-700/65 disabled:opacity-50"
          >
            찾기
          </button>
        </form>
      </div>

      {state.error && (
        <p
          className="mb-3 rounded-lg border border-live/50 px-3 py-2 text-[11px] text-live"
          role="alert"
        >
          {state.error}
        </p>
      )}

      {state.loading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-5 w-5 animate-spin text-stone-500" />
        </div>
      ) : state.users.length === 0 ? (
        <p className="py-10 text-center text-[11px] text-stone-600">사용자가 없습니다.</p>
      ) : (
        <ul className="divide-y divide-stone-800">
          {state.users.map((target) => {
            const blocked = blockedReason(target);
            const isAdmin = target.role === "admin";
            return (
              <li key={target.userId} className="flex items-center gap-3 py-2.5">
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[12px] text-stone-100">
                    {target.nickname}
                    {user?.id === target.userId && (
                      <span className="ml-1 text-[10px] text-stone-500">(나)</span>
                    )}
                  </p>
                  <p className="truncate text-[10px] text-stone-500">
                    #{target.userId} · {target.loginId}
                    {target.email && ` · ${target.email}`}
                    {target.oauthProvider && ` · ${target.oauthProvider}`}
                  </p>
                </div>
                <span
                  className={cn(
                    "w-12 shrink-0 text-right text-[10px]",
                    isAdmin ? "font-semibold text-stone-100" : "text-stone-500",
                  )}
                >
                  {target.role}
                </span>
                <button
                  type="button"
                  onClick={() => void toggle(target)}
                  disabled={state.busyId !== null || blocked !== null}
                  title={blocked ?? undefined}
                  className="flex w-24 shrink-0 items-center justify-center gap-1 rounded-lg border border-stone-600/70 bg-stone-800/45 px-2.5 py-1 text-[11px] text-stone-200 transition-colors hover:bg-stone-700/65 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  {state.busyId === target.userId ? (
                    <Loader2 className="h-3 w-3 animate-spin" />
                  ) : isAdmin ? (
                    "관리자 해제"
                  ) : (
                    "관리자 지정"
                  )}
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
