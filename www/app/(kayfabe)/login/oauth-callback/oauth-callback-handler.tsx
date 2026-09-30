"use client";

import { useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/context/auth-context";
import { OAUTH_POPUP_MESSAGE_TYPE } from "@/lib/oauth-popup";

/**
 * 소셜 로그인 콜백 착지 지점.
 *
 * 서버가 이미 httpOnly 쿠키로 액세스 토큰을 심어 둔 상태로 여기에 도착한다.
 * 예전에는 쿼리스트링의 `token`을 읽어 localStorage에 넣었는데, 그러면 토큰이
 * 브라우저 히스토리·Referer에 남고 XSS 한 번에 통째로 털린다.
 * 이제 이 화면은 토큰을 만지지 않고 "누구로 로그인됐는지"만 서버에 묻는다.
 */
export function OAuthCallbackHandler() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { refresh } = useAuth();

  useEffect(() => {
    const next = searchParams.get("next");

    // 팝업으로 열린 경우: 쿠키는 이미 심겼으므로 opener에 완료만 알리고 닫는다.
    if (window.opener && window.opener !== window) {
      window.opener.postMessage({ type: OAUTH_POPUP_MESSAGE_TYPE, next }, window.location.origin);
      window.close();
      return;
    }

    async function finishLogin() {
      const profile = await refresh();
      if (!profile) {
        alert("소셜 로그인에 실패했습니다.");
        router.replace("/login");
        return;
      }
      router.replace(next?.startsWith("/") ? next : "/");
    }

    void finishLogin();
  }, [router, searchParams, refresh]);

  return (
    <main className="flex min-h-[calc(100dvh-5.5rem)] items-center justify-center bg-stone-50 dark:bg-stone-900 text-sm text-stone-500 dark:text-stone-400">
      로그인 처리 중...
    </main>
  );
}
