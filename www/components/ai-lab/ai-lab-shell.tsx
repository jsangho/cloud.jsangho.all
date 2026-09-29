"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { WweArenaShell } from "@/components/wwe-arena-shell";
import { cn } from "@/lib/utils";

/**
 * AI LAB 공통 껍데기 (Phase 3-1).
 *
 * **AI LAB은 블루가 주인공인 유일한 화면이다**(DESIGN.md §1) — 다른 화면에서 블루는
 * 데이터가 있는 자리에만 서지만 여기서는 화면 자체가 데이터다. 그래도 네온 글로우나
 * 회로 무늬는 쓰지 않는다(§7 Don't) — 이건 대시보드지 SF가 아니다.
 *
 * **탭이 두 층이다** (2026-09-29 사용자 — "너무 AI 느낌이 나고 일반 유저가 보기
 * 어렵다"). 예전에는 일곱이 한 줄에 평평하게 서 있었고, 그중 넷(`Agents` ·
 * `Leakage` · `Readiness` · `Synthesis`)은 이 시스템을 만든 사람만 읽을 수 있는
 * 이름이었다. **화면은 하나도 지우지 않았다** — 앞줄에 셋을 두고 나머지 넷을
 * `개발 노트`로 접었다. 접힌 것은 숨긴 것과 다르다: 링크는 그대로 있고, 그 안에
 * 있는 화면을 보고 있으면 저절로 펼쳐진다.
 */
export const AI_LAB_TABS = [
  { href: "/ai-lab", label: "예측 성적" },
  { href: "/ai-lab/predictions", label: "이번 예측" },
  { href: "/ai-lab/knowledge", label: "근거 문서" },
] as const;

/**
 * 접히는 뒷줄 — **이 시스템이 자기를 의심하는 화면들**이다.
 *
 * 일반 유저가 먼저 만나야 할 것은 "얼마나 맞혔나"이고, "왜 그 숫자를 믿으면 안
 * 되는가"는 그다음이다. 순서를 뒤집으면 첫 화면이 변명으로 시작한다.
 */
export const AI_LAB_NOTE_TABS = [
  { href: "/ai-lab/agents", label: "분석기 활동" },
  // 근거 문서 바로 옆이다. 저쪽이 "어느 문서가 쓰였는가"를 세고 이쪽이 "그중 어느
  // 문서가 판정을 막았는가"를 세므로, 두 화면은 같은 목록을 다른 각도로 본다.
  { href: "/ai-lab/leakage", label: "근거 오염" },
  // 근거 오염 바로 옆이다. 저쪽이 **이미 만들어진** 예측을 놓고 무엇이 막았는지를 세고,
  // 이쪽이 **아직 없는** 예측을 놓고 무엇이 막을지를 센다 — 같은 코퍼스를 과거와
  // 미래에서 본다. 순서를 바꾸면 화면이 원인보다 대책을 먼저 말하게 된다.
  { href: "/ai-lab/readiness", label: "예측 가능성" },
  // 라우트는 `performance`, 라벨은 `승률 합성`이다. 이 화면은 정확도를 재지 않고 최종
  // 승률이 어떻게 만들어졌는지를 해부한다 — 이름이 재지 않는 것을 약속하면 화면이
  // 아무리 정직해도 탭이 먼저 거짓말을 한다. "성능"이라는 이름은 누수 없는 표본이
  // 생긴 뒤의 실제 성능 화면을 위해 남겨 둔다.
  { href: "/ai-lab/performance", label: "승률 합성" },
] as const;

function isActive(pathname: string, href: string): boolean {
  if (href === "/ai-lab") return pathname === "/ai-lab";
  return pathname === href || pathname.startsWith(`${href}/`);
}

const TAB_BASE =
  "inline-flex h-8 items-center rounded-lg border px-3 text-sm font-medium transition-colors";
const TAB_ACTIVE = "border-data-500/50 bg-data-surface text-data";
const TAB_IDLE =
  "border-border bg-card text-muted-foreground hover:bg-card-2 hover:text-foreground";

export function AiLabShell({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: ReactNode;
}) {
  const pathname = usePathname();
  const isRoot = pathname === "/ai-lab";
  const inNotes = AI_LAB_NOTE_TABS.some((tab) => isActive(pathname, tab.href));

  return (
    <WweArenaShell>
      <div className="mx-auto w-full max-w-6xl min-w-0 px-4 py-8 sm:py-10">
        <header className="mb-5">
          {/* 예전 이 자리는 파란 `AI LAB` eyebrow였다 — 데이터 센터와 같은 이유로
              뺐다. 돌아갈 곳이 있는 화면에서만 상위 링크를 세운다. */}
          {!isRoot && (
            <Link
              href="/ai-lab"
              className="inline-flex items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-foreground"
            >
              <span aria-hidden>←</span>
              AI 예측
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

        <nav aria-label="AI 예측 메뉴" className="mb-6 flex flex-col gap-2">
          <ul className="-mx-4 flex min-w-max items-center gap-1.5 overflow-x-auto px-4 pb-1">
            {AI_LAB_TABS.map((tab) => {
              const active = isActive(pathname, tab.href);
              return (
                <li key={tab.href}>
                  <Link
                    href={tab.href}
                    aria-current={active ? "page" : undefined}
                    className={cn(TAB_BASE, active ? TAB_ACTIVE : TAB_IDLE)}
                  >
                    {tab.label}
                  </Link>
                </li>
              );
            })}
          </ul>

          {/*
            `<details>`를 쓴 이유: 펼침 상태 하나 때문에 클라이언트 상태를 만들지
            않는다. 키보드·스크린리더 동작이 브라우저 기본으로 붙고, JS 없이도
            열린다. `open`은 **지금 그 안의 화면을 보고 있을 때** 참이다 — 접힌
            메뉴 뒤에 현재 위치가 숨는 일이 없어야 한다.
          */}
          <details open={inNotes} className="group">
            <summary className="inline-flex cursor-pointer list-none items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground [&::-webkit-details-marker]:hidden">
              <span aria-hidden className="transition-transform group-open:rotate-90">
                ›
              </span>
              개발 노트
              <span className="text-xs">— 이 예측을 어디까지 믿을 수 있는지</span>
            </summary>
            <ul className="-mx-4 mt-2 flex min-w-max items-center gap-1.5 overflow-x-auto px-4 pb-1">
              {AI_LAB_NOTE_TABS.map((tab) => {
                const active = isActive(pathname, tab.href);
                return (
                  <li key={tab.href}>
                    <Link
                      href={tab.href}
                      aria-current={active ? "page" : undefined}
                      className={cn(TAB_BASE, active ? TAB_ACTIVE : TAB_IDLE)}
                    >
                      {tab.label}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </details>
        </nav>

        {children}
      </div>
    </WweArenaShell>
  );
}
