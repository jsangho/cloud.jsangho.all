"use client";

import { cn } from "@/lib/utils";

/**
 * 커리어 내부 탭 여섯. **전역 KAYFABE 내비는 그대로 둔다** — 이 줄은 커리어 한
 * 세이브 안에서만 움직인다.
 *
 * `Tabs`(Radix)를 쓰지 않는다. 이 탭은 패널을 숨겨 두고 바꿔 끼우는 장치가 아니라
 * **탭마다 다른 데이터를 받는 화면**이고(기록 탭만 전체 로그를 읽는다), Radix
 * `Tabs` 는 비활성 패널도 트리에 두므로 여섯 패널이 전부 마운트된다. 저장소에서
 * 실제로 쓰이는 패턴도 pill 링크 줄(`chat-subnav.tsx`)이다.
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
      className="-mx-4 mb-5 overflow-x-auto px-4 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
    >
      <div className="flex w-max gap-1.5 border-b border-border pb-2">
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
                "shrink-0 rounded-full border px-4 py-1.5 text-xs font-medium transition-colors",
                isActive
                  ? "border-brand-400/70 bg-brand-500/15 text-brand-600 dark:text-brand-300"
                  : "border-border bg-card text-muted-foreground hover:bg-card-2",
              )}
            >
              {tab.label}
              {badge > 0 ? (
                <span className="ml-1.5 rounded-full bg-live px-1.5 text-[10px] font-bold tabular-nums text-foreground">
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
