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
 * 아직 안 만든 탭은 **링크가 아니라 '준비 중'** 으로 세운다. 데이터 센터 때와 같은
 * 규칙이다 — 없는 화면으로 보내 404를 만들지 않는다.
 */
export const AI_LAB_TABS = [
  { href: "/ai-lab", label: "Overview", ready: true },
  { href: "/ai-lab/predictions", label: "Predictions", ready: true },
  { href: "/ai-lab/agents", label: "Agents", ready: true },
  { href: "/ai-lab/knowledge", label: "Knowledge", ready: true },
  // 라우트는 `performance`, 라벨은 `Synthesis`다. 이 화면은 정확도를 재지 않고 최종
  // 승률이 어떻게 만들어졌는지를 해부한다 — 이름이 재지 않는 것을 약속하면 화면이
  // 아무리 정직해도 탭이 먼저 거짓말을 한다. "Performance"라는 이름은 누수 없는 표본이
  // 생긴 뒤의 실제 성능 화면을 위해 남겨 둔다.
  { href: "/ai-lab/performance", label: "Synthesis", ready: true },
] as const;

function isActive(pathname: string, href: string): boolean {
  if (href === "/ai-lab") return pathname === "/ai-lab";
  return pathname === href || pathname.startsWith(`${href}/`);
}

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

  return (
    <WweArenaShell>
      <div className="mx-auto w-full max-w-6xl min-w-0 px-4 py-8 sm:py-10">
        <header className="mb-5">
          <p className="font-sport text-xs tracking-[0.3em] text-data">AI LAB</p>
          <h1 className="mt-2 font-sport text-3xl text-foreground sm:text-4xl">{title}</h1>
          {description && (
            <p className="mt-2 max-w-2xl text-sm text-muted-foreground sm:text-base">
              {description}
            </p>
          )}
        </header>

        <nav aria-label="AI LAB 메뉴" className="-mx-4 mb-6 overflow-x-auto px-4 pb-1">
          <ul className="flex min-w-max items-center gap-1.5">
            {AI_LAB_TABS.map((tab) => {
              const active = isActive(pathname, tab.href);
              if (!tab.ready) {
                return (
                  <li key={tab.href}>
                    <span
                      aria-disabled
                      title="준비 중입니다"
                      className="inline-flex h-8 cursor-default items-center gap-1.5 rounded-lg border border-dashed border-border bg-card/50 px-3 text-sm font-medium text-muted-foreground/70"
                    >
                      {tab.label}
                      <span className="text-[10px] uppercase tracking-[0.12em]">soon</span>
                    </span>
                  </li>
                );
              }
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
