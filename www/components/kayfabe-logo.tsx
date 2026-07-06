"use client";

import Link from "next/link";
import { useId, type ReactNode } from "react";
import { cn } from "@/lib/utils";

/** KayFabe 마크 — 링 내부 1인칭, 로프 반동 직전 시점 + WWE W */
export function KayfabeMark({ className }: { className?: string }) {
  const uid = useId().replace(/:/g, "");

  return (
    <svg
      viewBox="0 0 32 32"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={cn("shrink-0", className)}
      aria-hidden
    >
      <rect width="32" height="32" rx="9" fill="#050505" />
      <rect
        width="32"
        height="32"
        rx="9"
        stroke="#52525b"
        strokeWidth="0.5"
        fill="none"
      />

      <rect width="32" height="32" rx="9" fill={`url(#kf-arena-${uid})`} />

      <path d="M0 32V24.5L16 19.8L32 24.5V32H0Z" fill={`url(#kf-mat-${uid})`} />
      <path
        d="M2 32V25.8L16 21.6L30 25.8V32H2Z"
        fill="#1c1917"
        opacity="0.55"
      />

      <path d="M1.5 8.2V21.5L4.2 20.8V9.4L1.5 8.2Z" fill="#3f3f46" />
      <path d="M30.5 8.2V21.5L27.8 20.8V9.4L30.5 8.2Z" fill="#3f3f46" />
      <rect x="3.8" y="7.6" width="2.2" height="13.8" rx="0.4" fill="#52525b" />
      <rect x="26" y="7.6" width="2.2" height="13.8" rx="0.4" fill="#52525b" />
      <rect x="3.4" y="7.2" width="3" height="2.2" rx="0.35" fill="#a16207" />
      <rect x="25.6" y="7.2" width="3" height="2.2" rx="0.35" fill="#a16207" />

      <path
        d="M3.2 10.1C10.5 10.85 21.5 10.85 28.8 10.1L28.55 11.05C21.35 11.75 10.65 11.75 3.45 11.05L3.2 10.1Z"
        fill={`url(#kf-rope-top-${uid})`}
      />
      <path
        d="M2.3 13.35C10.1 14.35 21.9 14.35 29.7 13.35L29.4 14.65C21.55 15.55 10.45 15.55 2.6 14.65L2.3 13.35Z"
        fill={`url(#kf-rope-mid-${uid})`}
      />
      <path
        d="M1.4 17.1C9.6 18.65 22.4 18.65 30.6 17.1L30.2 18.85C22.15 20.25 9.85 20.25 1.8 18.85L1.4 17.1Z"
        fill={`url(#kf-rope-bot-${uid})`}
      />

      <path
        d="M3.2 10.1C10.5 10.85 21.5 10.85 28.8 10.1"
        stroke="#fecaca"
        strokeWidth="0.35"
        strokeLinecap="round"
        opacity="0.55"
      />
      <path
        d="M2.3 13.35C10.1 14.35 21.9 14.35 29.7 13.35"
        stroke="#fecaca"
        strokeWidth="0.4"
        strokeLinecap="round"
        opacity="0.65"
      />
      <path
        d="M1.4 17.1C9.6 18.65 22.4 18.65 30.6 17.1"
        stroke="#fff1f2"
        strokeWidth="0.45"
        strokeLinecap="round"
        opacity="0.75"
      />

      <path
        d="M10.8 13.35L13.1 10.05L16 13.55L18.9 10.05L21.2 13.35L19.55 13.35L16 10.35L12.45 13.35H10.8Z"
        fill={`url(#kf-wwe-${uid})`}
        stroke="#7f1d1d"
        strokeWidth="0.2"
      />

      <path
        d="M16 20.2L14.2 18.8M16 20.2L17.8 18.8"
        stroke="#57534e"
        strokeWidth="0.45"
        strokeLinecap="round"
        opacity="0.5"
      />

      <defs>
        <radialGradient
          id={`kf-arena-${uid}`}
          cx="50%"
          cy="18%"
          r="72%"
          gradientUnits="objectBoundingBox"
        >
          <stop stopColor="#292524" stopOpacity="0.85" />
          <stop offset="0.55" stopColor="#0c0a09" stopOpacity="0.35" />
          <stop offset="1" stopColor="#050505" stopOpacity="0" />
        </radialGradient>
        <linearGradient
          id={`kf-mat-${uid}`}
          x1="16"
          y1="19"
          x2="16"
          y2="32"
          gradientUnits="userSpaceOnUse"
        >
          <stop stopColor="#44403c" />
          <stop offset="0.45" stopColor="#292524" />
          <stop offset="1" stopColor="#0c0a09" />
        </linearGradient>
        <linearGradient
          id={`kf-rope-top-${uid}`}
          x1="16"
          y1="9"
          x2="16"
          y2="12"
          gradientUnits="userSpaceOnUse"
        >
          <stop stopColor="#991b1b" />
          <stop offset="0.5" stopColor="#dc2626" />
          <stop offset="1" stopColor="#7f1d1d" />
        </linearGradient>
        <linearGradient
          id={`kf-rope-mid-${uid}`}
          x1="16"
          y1="12"
          x2="16"
          y2="15.5"
          gradientUnits="userSpaceOnUse"
        >
          <stop stopColor="#b91c1c" />
          <stop offset="0.45" stopColor="#ef4444" />
          <stop offset="1" stopColor="#991b1b" />
        </linearGradient>
        <linearGradient
          id={`kf-rope-bot-${uid}`}
          x1="16"
          y1="15"
          x2="16"
          y2="20"
          gradientUnits="userSpaceOnUse"
        >
          <stop stopColor="#dc2626" />
          <stop offset="0.45" stopColor="#f87171" />
          <stop offset="1" stopColor="#b91c1c" />
        </linearGradient>
        <linearGradient
          id={`kf-wwe-${uid}`}
          x1="11"
          y1="10"
          x2="21"
          y2="13.5"
          gradientUnits="userSpaceOnUse"
        >
          <stop stopColor="#fafafa" />
          <stop offset="0.5" stopColor="#e7e5e4" />
          <stop offset="1" stopColor="#d6d3d1" />
        </linearGradient>
      </defs>
    </svg>
  );
}

type KayfabeLogoProps = {
  className?: string;
  markClassName?: string;
  showTagline?: boolean;
  href?: string | null;
  children?: ReactNode;
};

export function KayfabeLogo({
  className,
  markClassName = "h-9 w-9 rounded-xl",
  showTagline = true,
  href = "/",
  children,
}: KayfabeLogoProps) {
  const content = (
    <>
      <KayfabeMark className={markClassName} />
      <div className="min-w-0">
        <span className="font-sport block text-2xl font-semibold leading-none tracking-[-0.04em] text-stone-900 dark:text-stone-50">
          KayFabe
        </span>
        {showTagline && (
          <span className="mt-0.5 block text-sm tracking-wide text-stone-500 dark:text-stone-400">
            WWE PLE 예측 게임
          </span>
        )}
        {children}
      </div>
    </>
  );

  const rootClass = cn(
    "inline-flex items-center gap-2.5 transition-opacity hover:opacity-90",
    className,
  );

  if (href) {
    return (
      <Link href={href} className={rootClass} aria-label="KayFabe 홈">
        {content}
      </Link>
    );
  }

  return <div className={rootClass}>{content}</div>;
}
