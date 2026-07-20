"use client";

import { useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/context/auth-context";
import { completeOAuthLogin } from "@/lib/auth-api";
import { OAUTH_POPUP_MESSAGE_TYPE } from "@/lib/oauth-popup";

export function OAuthCallbackHandler() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { login: saveAuthUser } = useAuth();

  useEffect(() => {
    const token = searchParams.get("token");
    const next = searchParams.get("next");

    // 팝업으로 열린 경우: 로그인 처리는 opener(원래 창)에 맡기고 결과만 전달한 뒤 닫는다.
    if (window.opener && window.opener !== window) {
      window.opener.postMessage(
        { type: OAUTH_POPUP_MESSAGE_TYPE, token, next },
        window.location.origin,
      );
      window.close();
      return;
    }

    async function finishLogin() {
      const profile = token ? await completeOAuthLogin(token) : null;
      if (!token || !profile) {
        alert("소셜 로그인에 실패했습니다.");
        router.replace("/login");
        return;
      }

      saveAuthUser({ ...profile, token });
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
