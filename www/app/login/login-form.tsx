"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { IdCard, LockKeyhole, Mail, UserRound } from "lucide-react";
import { useAuth, type AuthUser } from "@/context/auth-context";
import { parseUserProfile } from "@/lib/auth-api";
import {
  apiBaseUrl,
  getRequestTimeoutMessage,
  isAbortError,
  requestTimeoutMs,
} from "@/lib/api";
import { LoginBackdrop } from "./login-backdrop";

type AuthMode = "login" | "signup";

type LoginPageState = {
  mode: AuthMode;
  isSubmitting: boolean;
};

const initialState: LoginPageState = {
  mode: "login",
  isSubmitting: false,
};

function authFailureAlert(isSignup: boolean, error: unknown) {
  if (isAbortError(error)) {
    alert(getRequestTimeoutMessage());
    return;
  }
  alert(isSignup ? "회원가입에 실패했습니다." : "로그인에 실패했습니다.");
}

function readNextPath(): string {
  if (typeof window === "undefined") return "/";
  const next = new URLSearchParams(window.location.search).get("next");
  return next?.startsWith("/") ? next : "/";
}

export function LoginForm() {
  const router = useRouter();
  const { login: saveAuthUser } = useAuth();
  const [state, setState] = useState<LoginPageState>(initialState);
  const isSignup = state.mode === "signup";

  const patchState = (patch: Partial<LoginPageState>) =>
    setState((prev) => ({ ...prev, ...patch }));

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (state.isSubmitting) {
      return;
    }

    const form = event.currentTarget;
    const formData = new FormData(form);
    const formProps = Object.fromEntries(formData.entries());
    const userId = String(formProps.userId ?? "").trim();
    const password = String(formProps.password ?? "");

    if (isSignup) {
      const nickname = String(formProps.nickname ?? "").trim();
      const email = String(formProps.email ?? "").trim();
      const passwordConfirm = String(formProps.passwordConfirm ?? "");

      if (!userId || !nickname || !email || !password || !passwordConfirm) {
        alert("회원가입 입력란을 모두 작성해 주세요.");
        return;
      }

      if (password !== passwordConfirm) {
        alert("비밀번호와 비밀번호 확인이 일치하지 않습니다.");
        return;
      }

      patchState({ isSubmitting: true });
      const controller = new AbortController();
      const timeoutId = window.setTimeout(() => {
        controller.abort();
      }, requestTimeoutMs);

      try {
        const response = await fetch(`${apiBaseUrl}/signup`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          signal: controller.signal,
          body: JSON.stringify({
            userId,
            nickname,
            email,
            password,
            passwordConfirm,
          }),
        });

        if (!response.ok) {
          authFailureAlert(true, null);
          return;
        }

        alert("회원가입이 완료되었습니다.");
        form.reset();
        patchState({ mode: "login" });
      } catch (error) {
        authFailureAlert(true, error);
      } finally {
        window.clearTimeout(timeoutId);
        patchState({ isSubmitting: false });
      }
      return;
    }

    if (!userId || !password) {
      alert("ID와 비밀번호를 입력해 주세요.");
      return;
    }

    patchState({ isSubmitting: true });
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => {
      controller.abort();
    }, requestTimeoutMs);

    try {
      const response = await fetch(`${apiBaseUrl}/login`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        signal: controller.signal,
        body: JSON.stringify({ userId, password }),
      });

      const data = (await response.json().catch(() => null)) as {
        userId?: number;
        id?: number;
        loginId?: string;
        login_id?: string;
        nickname?: string;
        email?: string;
        role?: string;
      } | null;

      if (!response.ok) {
        authFailureAlert(false, null);
        return;
      }

      const profile = parseUserProfile(data);
      if (!profile) {
        authFailureAlert(false, null);
        return;
      }

      const authUser: AuthUser = {
        ...profile,
        loginId: profile.loginId || userId,
      };
      saveAuthUser(authUser);
      router.push(readNextPath());
    } catch (error) {
      authFailureAlert(false, error);
    } finally {
      window.clearTimeout(timeoutId);
      patchState({ isSubmitting: false });
    }
  }

  return (
    <main className="relative min-h-[calc(100dvh-5.5rem)] w-full min-w-0 overflow-x-hidden bg-stone-50 dark:bg-stone-900 text-stone-900 dark:text-stone-100">
      <LoginBackdrop />
      <section className="relative z-10 flex min-h-[calc(100dvh-5.5rem)] items-center justify-center px-4 py-10">
        <div className="w-full max-w-[460px] rounded-3xl border border-stone-300/70 dark:border-stone-700/70 bg-stone-50/80 dark:bg-stone-950/58 p-6 shadow-2xl shadow-black/35 backdrop-blur-xl sm:p-8">
          <div className="text-center">
            <p className="text-xs font-semibold uppercase tracking-[0.28em] text-stone-500">
              KayFabe
            </p>
            <h1 className="mt-3 text-2xl font-bold tracking-tight text-stone-900 dark:text-stone-50">
              {isSignup ? "회원가입" : "로그인"}
            </h1>
            <p className="mt-2 text-sm text-stone-400">
              {isSignup
                ? "계정을 만들고 WWE PLE 예측에 참여하세요."
                : "계정으로 접속해 예측 기록을 이어가세요."}
            </p>
          </div>

          <form onSubmit={handleSubmit} noValidate className="mt-8 space-y-4">
            {isSignup && (
              <label className="block">
                <span className="mb-2 block text-sm font-medium text-stone-700 dark:text-stone-300">
                  닉네임
                </span>
                <span className="flex items-center gap-3 rounded-2xl border border-stone-300/80 dark:border-stone-700/80 bg-stone-100/70 dark:bg-stone-900/70 px-4 py-3 text-stone-600 dark:text-stone-300 transition-colors focus-within:border-stone-500 dark:focus-within:border-stone-400 focus-within:bg-stone-100 dark:focus-within:bg-stone-900">
                  <UserRound className="size-5 text-stone-500" />
                  <input
                    type="text"
                    name="nickname"
                    autoComplete="nickname"
                    placeholder="KayFabe 닉네임"
                    className="w-full bg-transparent text-sm text-stone-900 dark:text-stone-100 placeholder:text-stone-400 dark:placeholder:text-stone-600 outline-none"
                  />
                </span>
              </label>
            )}

            <label className="block">
              <span className="mb-2 block text-sm font-medium text-stone-700 dark:text-stone-300">
                ID
              </span>
              <span className="flex items-center gap-3 rounded-2xl border border-stone-300/80 dark:border-stone-700/80 bg-stone-100/70 dark:bg-stone-900/70 px-4 py-3 text-stone-600 dark:text-stone-300 transition-colors focus-within:border-stone-500 dark:focus-within:border-stone-400 focus-within:bg-stone-100 dark:focus-within:bg-stone-900">
                <IdCard className="size-5 text-stone-500" />
                <input
                  type="text"
                  name="userId"
                  autoComplete="username"
                  placeholder="로그인 ID"
                  className="w-full bg-transparent text-sm text-stone-900 dark:text-stone-100 placeholder:text-stone-400 dark:placeholder:text-stone-600 outline-none"
                />
              </span>
            </label>

            {isSignup && (
              <label className="block">
                <span className="mb-2 block text-sm font-medium text-stone-700 dark:text-stone-300">
                  이메일
                </span>
                <span className="flex items-center gap-3 rounded-2xl border border-stone-300/80 dark:border-stone-700/80 bg-stone-100/70 dark:bg-stone-900/70 px-4 py-3 text-stone-600 dark:text-stone-300 transition-colors focus-within:border-stone-500 dark:focus-within:border-stone-400 focus-within:bg-stone-100 dark:focus-within:bg-stone-900">
                  <Mail className="size-5 text-stone-500" />
                  <input
                    type="email"
                    name="email"
                    autoComplete="email"
                    placeholder="you@example.com"
                    className="w-full bg-transparent text-sm text-stone-900 dark:text-stone-100 placeholder:text-stone-400 dark:placeholder:text-stone-600 outline-none"
                  />
                </span>
              </label>
            )}

            <label className="block">
              <span className="mb-2 block text-sm font-medium text-stone-700 dark:text-stone-300">
                비밀번호
              </span>
              <span className="flex items-center gap-3 rounded-2xl border border-stone-300/80 dark:border-stone-700/80 bg-stone-100/70 dark:bg-stone-900/70 px-4 py-3 text-stone-600 dark:text-stone-300 transition-colors focus-within:border-stone-500 dark:focus-within:border-stone-400 focus-within:bg-stone-100 dark:focus-within:bg-stone-900">
                <LockKeyhole className="size-5 text-stone-500" />
                <input
                  type="password"
                  name="password"
                  autoComplete={isSignup ? "new-password" : "current-password"}
                  placeholder="비밀번호"
                  className="w-full bg-transparent text-sm text-stone-900 dark:text-stone-100 placeholder:text-stone-400 dark:placeholder:text-stone-600 outline-none"
                />
              </span>
            </label>

            {isSignup && (
              <label className="block">
                <span className="mb-2 block text-sm font-medium text-stone-700 dark:text-stone-300">
                  비밀번호 확인
                </span>
                <span className="flex items-center gap-3 rounded-2xl border border-stone-300/80 dark:border-stone-700/80 bg-stone-100/70 dark:bg-stone-900/70 px-4 py-3 text-stone-600 dark:text-stone-300 transition-colors focus-within:border-stone-500 dark:focus-within:border-stone-400 focus-within:bg-stone-100 dark:focus-within:bg-stone-900">
                  <LockKeyhole className="size-5 text-stone-500" />
                  <input
                    type="password"
                    name="passwordConfirm"
                    autoComplete="new-password"
                    placeholder="비밀번호 확인"
                    className="w-full bg-transparent text-sm text-stone-900 dark:text-stone-100 placeholder:text-stone-400 dark:placeholder:text-stone-600 outline-none"
                  />
                </span>
              </label>
            )}

            <button
              type="submit"
              disabled={state.isSubmitting}
              className="mt-2 h-12 w-full rounded-2xl border border-stone-500/40 bg-stone-200 text-sm font-bold text-stone-950 shadow-lg shadow-black/20 transition-colors hover:bg-stone-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-stone-400 focus-visible:ring-offset-2 focus-visible:ring-offset-stone-950"
            >
              {state.isSubmitting
                ? "전송 중..."
                : isSignup
                  ? "회원가입"
                  : "로그인"}
            </button>
          </form>

          <div className="mt-5 text-center">
            <button
              type="button"
              onClick={() =>
                patchState({ mode: isSignup ? "login" : "signup" })
              }
              className="rounded-full border border-stone-300/80 dark:border-stone-700/80 bg-stone-100/55 dark:bg-stone-900/55 px-3 py-1.5 text-xs font-medium text-stone-600 dark:text-stone-400 transition-colors hover:border-stone-500 hover:bg-stone-200/80 dark:hover:bg-stone-800/80 hover:text-stone-900 dark:hover:text-stone-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-stone-500/60"
            >
              {isSignup ? "로그인으로 돌아가기" : "회원가입"}
            </button>
          </div>
        </div>
      </section>
    </main>
  );
}
