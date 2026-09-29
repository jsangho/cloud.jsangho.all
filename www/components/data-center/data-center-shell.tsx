"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { WweArenaShell } from "@/components/wwe-arena-shell";
import { cn } from "@/lib/utils";

/**
 * 데이터 센터 공통 껍데기 (Phase 2).
 *
 * 여섯 화면이 같은 머리와 같은 탭을 쓴다. **탭은 여기 한 곳에만 있다** — 화면마다
 * 적으면 하나를 더할 때 여섯 곳을 고쳐야 한다.
 *
 * WWE 다크는 그대로 두되(같은 `WweArenaShell`) 안쪽은 대시보드 쪽으로 조인다:
 * 카드 표면·경계선 토큰을 쓰고, 장식보다 숫자가 먼저 오게 배치한다.
 *
 * **라벨은 한글이다** (2026-09-29 사용자 — "너무 AI 느낌이 나고 일반 유저가 보기
 * 어렵다"). 영어 대문자 여섯 탭은 이 화면을 아는 사람만 읽을 수 있었다. 라우트는
 * 그대로다 — 북마크와 외부 링크를 깨뜨리지 않는다.
 */
export const DATA_CENTER_TABS = [
  { href: "/data-center/wrestlers", label: "선수" },
  { href: "/data-center/matches", label: "경기" },
  { href: "/data-center/ple", label: "대회" },
  { href: "/data-center/championships", label: "벨트" },
  { href: "/data-center/analytics", label: "차트" },
] as const;

const ROOT_HREF = "/data-center";
const ROOT_LABEL = "데이터 센터";

function isActive(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function DataCenterShell({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: ReactNode;
}) {
  const pathname = usePathname();
  const isRoot = pathname === ROOT_HREF;

  return (
    <WweArenaShell>
      <div className="mx-auto w-full max-w-6xl min-w-0 px-4 py-8 sm:py-10">
        <header className="mb-5">
          {/* 예전 이 자리는 파란 `DATA CENTER` eyebrow였다. 모든 화면에 같은 영어
              대문자가 서 있어 "여기가 기계 쪽 화면"이라는 인상을 먼저 줬다.
              돌아갈 곳이 있는 화면에서만 상위 링크를 세운다. */}
          {!isRoot && (
            <Link
              href={ROOT_HREF}
              className="inline-flex items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-foreground"
            >
              <span aria-hidden>←</span>
              {ROOT_LABEL}
            </Link>
          )}
          <h1 className={cn("font-sport text-3xl text-foreground sm:text-4xl", !isRoot && "mt-2")}>
            {title}
          </h1>
          {description && (
            <p className="mt-2 max-w-2xl text-sm text-muted-foreground sm:text-base">
              {description}
            </p>
          )}
        </header>

        {/* 탭 — 모바일에서는 가로로 스크롤한다(줄바꿈보다 자리를 덜 먹는다). */}
        <nav aria-label="데이터 센터 메뉴" className="-mx-4 mb-6 overflow-x-auto px-4 pb-1">
          <ul className="flex min-w-max items-center gap-1.5">
            {DATA_CENTER_TABS.map((tab) => {
              const active = isActive(pathname, tab.href);
              return (
                <li key={tab.href}>
                  <Link
                    href={tab.href}
                    aria-current={active ? "page" : undefined}
                    className={cn(
                      "inline-flex h-8 items-center rounded-lg border px-3 text-sm font-medium transition-colors",
                      active
                        ? "border-data-500/50 bg-data-surface text-data"
                        : "border-border bg-card text-muted-foreground hover:bg-card-2 hover:text-foreground",
                    )}
                  >
                    {tab.label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>

        {children}
      </div>
    </WweArenaShell>
  );
}

/** 큰 숫자 한 칸. **값이 `null`이면 대시**를 세운다 — 0으로 채우지 않는다. */
export function StatTile({
  value,
  label,
  note,
  tone = "default",
}: {
  value: number | string | null;
  label: string;
  note?: string;
  tone?: "default" | "data" | "gold";
}) {
  return (
    <div className="flex flex-col justify-center rounded-xl border border-border bg-card px-4 py-3 sm:px-5 sm:py-4">
      <p
        className={cn(
          "text-2xl font-bold tabular-nums sm:text-3xl",
          tone === "data" && "text-data",
          tone === "gold" && "text-brand-link",
          tone === "default" && "text-foreground",
        )}
      >
        {value === null ? "—" : value}
      </p>
      {/* 한글 라벨이라 `uppercase tracking-[0.14em]`을 뺐다 — 자간을 벌린 한글은
          읽는 속도를 떨어뜨리고, 대문자 변환은 한글에 아무 일도 하지 않으면서
          영어 라벨만 남았을 때의 기계적인 인상만 남긴다. */}
      <p className="mt-1 text-xs font-medium text-muted-foreground">{label}</p>
      {note && <p className="mt-0.5 text-xs text-muted-foreground">{note}</p>}
    </div>
  );
}

/** 데이터를 못 받았을 때. **비어 있음과 고장을 구분해서 적는다.** */
export function DataUnavailable({ what }: { what: string }) {
  return (
    <div className="rounded-xl border border-dashed border-border bg-card/50 px-4 py-8 text-center">
      <p className="text-sm text-muted-foreground">{what}을(를) 불러오지 못했습니다.</p>
      <p className="mt-1 text-xs text-muted-foreground">
        서버가 응답하면 이 자리에 실제 데이터가 섭니다 — 임시 숫자를 채우지 않습니다.
      </p>
    </div>
  );
}

export function LoadingBlock({ rows = 3 }: { rows?: number }) {
  return (
    <div className="flex flex-col gap-3" aria-hidden>
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="h-16 animate-pulse rounded-xl border border-border bg-card" />
      ))}
    </div>
  );
}
