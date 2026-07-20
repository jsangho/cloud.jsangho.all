"use client";

import { useRouter } from "next/navigation";
import { apiBaseUrl } from "@/lib/api";
import { useAuth } from "@/context/auth-context";
import { completeOAuthLogin } from "@/lib/auth-api";
import { openOAuthPopup } from "@/lib/oauth-popup";
import { readNextPath } from "./login-form";

const COMING_SOON_LABELS: Record<string, string> = {
  apple: "애플",
  instagram: "인스타그램",
};

function handleComingSoon(providerKey: string) {
  alert(`${COMING_SOON_LABELS[providerKey]} 로그인은 준비 중입니다.`);
}

function NaverIcon() {
  return (
    <svg viewBox="0 0 24 24" className="size-6" aria-hidden>
      <rect width="24" height="24" rx="12" fill="#03C75A" />
      <path d="M13.6 12.6 10.2 7.5H7.5v9h2.9v-5.1l3.4 5.1h2.7v-9h-2.9z" fill="#fff" />
    </svg>
  );
}

function KakaoIcon() {
  return (
    <svg viewBox="0 0 24 24" className="size-6" aria-hidden>
      <rect width="24" height="24" rx="12" fill="#FEE500" />
      <path
        d="M12 6.5c-3.31 0-6 2.07-6 4.63 0 1.63 1.1 3.06 2.76 3.89-.12.44-.44 1.6-.5 1.85-.08.31.11.31.24.22.1-.07 1.62-1.1 2.28-1.55.39.06.8.09 1.22.09 3.31 0 6-2.07 6-4.63S15.31 6.5 12 6.5z"
        fill="#3C1E1E"
      />
    </svg>
  );
}

function GoogleIcon() {
  return (
    <svg viewBox="0 0 24 24" className="size-6" aria-hidden>
      <rect width="24" height="24" rx="12" fill="#fff" />
      <path
        fill="#4285F4"
        d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
      />
      <path
        fill="#34A853"
        d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
      />
      <path
        fill="#FBBC05"
        d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
      />
      <path
        fill="#EA4335"
        d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
      />
    </svg>
  );
}

function AppleIcon() {
  return (
    <svg viewBox="0 0 24 24" className="size-6" aria-hidden>
      <rect width="24" height="24" rx="12" className="fill-stone-900 dark:fill-stone-50" />
      <path
        className="fill-stone-50 dark:fill-stone-900"
        d="M15.6 6.9c-.5.6-1.3 1.1-2.1 1-.1-.8.3-1.6.8-2.1.5-.6 1.4-1 2.1-1.1.1.9-.2 1.7-.8 2.2zm.8 1.3c-1.2-.1-2.2.7-2.8.7-.6 0-1.4-.6-2.4-.6-1.2 0-2.4.7-3 1.9-1.3 2.2-.3 5.5.9 7.3.6.9 1.3 1.9 2.3 1.8.9 0 1.3-.6 2.4-.6s1.4.6 2.4.6c1 0 1.6-.9 2.2-1.8.7-1 1-2 1-2.1-.1 0-1.9-.7-1.9-2.8 0-1.7 1.4-2.5 1.5-2.6-.8-1.2-2-1.3-2.6-1.4z"
      />
    </svg>
  );
}

function InstagramIcon() {
  return (
    <svg viewBox="0 0 24 24" className="size-6" aria-hidden>
      <defs>
        <linearGradient id="ig-gradient" x1="0%" y1="100%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="#FEE411" />
          <stop offset="30%" stopColor="#FD5949" />
          <stop offset="65%" stopColor="#D6249F" />
          <stop offset="100%" stopColor="#285AEB" />
        </linearGradient>
      </defs>
      <rect width="24" height="24" rx="12" fill="url(#ig-gradient)" />
      <rect
        x="6.5"
        y="6.5"
        width="11"
        height="11"
        rx="3"
        fill="none"
        stroke="#fff"
        strokeWidth="1.4"
      />
      <circle cx="12" cy="12" r="2.8" fill="none" stroke="#fff" strokeWidth="1.4" />
      <circle cx="15.4" cy="8.6" r="0.6" fill="#fff" />
    </svg>
  );
}

const SNS_PROVIDERS = [
  { key: "naver", label: "네이버 로그인", Icon: NaverIcon, onClick: null },
  { key: "kakao", label: "카카오 로그인", Icon: KakaoIcon, onClick: null },
  { key: "google", label: "구글 로그인", Icon: GoogleIcon, onClick: null },
  { key: "apple", label: "애플 로그인", Icon: AppleIcon, onClick: handleComingSoon },
  {
    key: "instagram",
    label: "인스타그램 로그인",
    Icon: InstagramIcon,
    onClick: handleComingSoon,
  },
] as const;

type OAuthProvider = "google" | "naver" | "kakao";

export function SnsLoginButtons() {
  const router = useRouter();
  const { login: saveAuthUser } = useAuth();

  async function finishPopupLogin(token: string | null, next: string | null) {
    const profile = token ? await completeOAuthLogin(token) : null;
    if (!token || !profile) {
      alert("소셜 로그인에 실패했습니다.");
      return;
    }
    saveAuthUser({ ...profile, token });
    router.replace(next?.startsWith("/") ? next : "/");
  }

  function startOAuthLogin(provider: OAuthProvider) {
    const next = encodeURIComponent(readNextPath());
    const url = `${apiBaseUrl}/api/auth/${provider}/login?next=${next}`;

    // 팝업이 차단된 브라우저에서는 기존 방식(전체 페이지 리다이렉트)으로 폴백한다.
    const opened = openOAuthPopup(
      url,
      (resultToken, resultNext) => void finishPopupLogin(resultToken, resultNext),
    );
    if (!opened) {
      window.location.href = url;
    }
  }

  const functionalHandlers: Record<string, () => void> = {
    google: () => startOAuthLogin("google"),
    naver: () => startOAuthLogin("naver"),
    kakao: () => startOAuthLogin("kakao"),
  };

  return (
    <div className="mt-6">
      <div className="flex items-center gap-3">
        <span className="h-px flex-1 bg-stone-300/70 dark:bg-stone-700/70" />
        <span className="text-[11px] font-semibold uppercase tracking-[0.2em] text-stone-400">
          SNS 로그인
        </span>
        <span className="h-px flex-1 bg-stone-300/70 dark:bg-stone-700/70" />
      </div>

      <div className="mt-4 flex items-center justify-center gap-3">
        {SNS_PROVIDERS.map(({ key, label, Icon, onClick }) => (
          <button
            key={key}
            type="button"
            aria-label={label}
            onClick={functionalHandlers[key] ?? (() => onClick?.(key))}
            className="flex size-11 items-center justify-center overflow-hidden rounded-full border border-stone-300/80 dark:border-stone-700/80 shadow-md shadow-black/10 transition-transform hover:scale-105 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-stone-400"
          >
            <Icon />
          </button>
        ))}
      </div>
    </div>
  );
}
