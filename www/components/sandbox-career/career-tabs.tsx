"use client";

import { cn } from "@/lib/utils";

/**
 * 커리어 내부 탭 여섯. **전역 KAYFABE 내비는 그대로 둔다** — 이 줄은 커리어 한
 * 세이브 안에서만 움직인다.
 *
 * `Tabs`(Radix)를 쓰지 않는다. 이 탭은 패널을 숨겨 두고 바꿔 끼우는 장치가 아니라
 * **탭마다 다른 데이터를 받는 화면**이고(기록 탭만 전체 로그를 읽는다), Radix
 * `Tabs` 는 비활성 패널도 트리에 두므로 여섯 패널이 전부 마운트된다.
 */
export const CAREER_TABS = [
  { id: "dashboard", label: "대시보드" },
  { id: "week", label: "주간 진행" },
  { id: "world", label: "세계관" },
  { id: "matches", label: "경기 · 대진" },
  { id: "titles", label: "타이틀" },
  { id: "log", label: "커리어 기록" },
] as const;

export type CareerTab = (typeof CAREER_TABS)[number]["id"];

export function CareerTabs({
  active,
  pending,
  onSelect,
}: {
  active: CareerTab;
  /** 미해결 사건 수. 0이면 배지를 달지 않는다. */
  pending: number;
  onSelect: (tab: CareerTab) => void;
}) {
  return (
    <nav
      aria-label="커리어 메뉴"
      className="-mx-4 mb-6 overflow-x-auto px-4 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
    >
      <div className="flex w-max min-w-full gap-1 border-b border-white/10">
        {CAREER_TABS.map((tab) => {
          const isActive = tab.id === active;
          // 배지는 사건을 처리할 수 있는 두 탭에만 — 다른 탭에 달면 갈 곳을 잘못 가리킨다.
          const badge = pending > 0 && (tab.id === "dashboard" || tab.id === "week") ? pending : 0;
          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => onSelect(tab.id)}
              aria-current={isActive ? "page" : undefined}
              className={cn(
                // 게임 메뉴처럼 — 활성 탭은 금색 밑줄과 밝은 글자, 나머지는 물러난다.
                "relative shrink-0 px-4 pb-3 pt-2 font-sport text-sm uppercase tracking-wider transition-colors",
                "after:absolute after:inset-x-3 after:-bottom-px after:h-0.5 after:rounded-full after:transition-colors",
                isActive
                  ? "text-brand-300 after:bg-[linear-gradient(90deg,var(--brand-600),var(--brand-300),var(--brand-600))]"
                  : "text-stone-400 after:bg-transparent hover:text-stone-100",
              )}
            >
              {tab.label}
              {badge > 0 ? (
                <span className="ml-1.5 rounded-full bg-live px-1.5 align-middle font-sans text-[10px] font-bold tabular-nums text-stone-50">
                  {badge}
                </span>
              ) : null}
            </button>
          );
        })}
      </div>
    </nav>
  );
}
