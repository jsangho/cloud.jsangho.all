"use client";

import { useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/context/auth-context";
import { decodeJwtUserId, fetchUserProfile } from "@/lib/auth-api";

export function OAuthCallbackHandler() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { login: saveAuthUser } = useAuth();

  useEffect(() => {
    async function finishLogin() {
      const token = searchParams.get("token");
      const userId = token ? decodeJwtUserId(token) : null;

      const profile = token && userId != null ? await fetchUserProfile(userId, token) : null;
      if (!token || !profile) {
        alert("소셜 로그인에 실패했습니다.");
        router.replace("/login");
        return;
      }

      saveAuthUser({ ...profile, token });

      const next = searchParams.get("next");
      router.replace(next?.startsWith("/") ? next : "/");
    }

    void finishLogin();
  }, [router, searchParams, saveAuthUser]);

  return (
    <main className="flex min-h-[calc(100dvh-5.5rem)] items-center justify-center bg-stone-50 dark:bg-stone-900 text-sm text-stone-500 dark:text-stone-400">
      로그인 처리 중...
    </main>
  );
}
