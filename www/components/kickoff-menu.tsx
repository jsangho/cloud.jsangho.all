"use client";

import Link from "next/link";
import { useState } from "react";
import { ChevronDown } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/** 킥오프에 들어가는 항목. `href`가 없으면 아직 열리지 않은 자리다. */
type KickoffItem = {
  label: string;
  description: string;
  href?: string;
};

export const KICKOFF_ITEMS: readonly KickoffItem[] = [
  { label: "대화", description: "슈퍼스타와 이야기하기", href: "/chat" },
  { label: "커리어 시뮬레이터", description: "20세 데뷔, 30년", href: "/career" },
] as const;

/** 킥오프가 활성인 경로들. 항목이 늘면 여기도 함께 늘린다. */
export const KICKOFF_PATHS: readonly string[] = ["/chat", "/career"] as const;

export function isKickoffPath(pathname: string): boolean {
  return KICKOFF_PATHS.some((p) => pathname === p || pathname.startsWith(`${p}/`));
}

/**
 * 킥오프 — 본 방송 옆에서 하는 것들을 모은 메뉴.
 *
 * 데스크톱은 hover와 클릭 둘 다로 열린다. **트리거는 링크가 아니다** — 터치에는 hover가
 * 없어서 링크로 두면 탭 한 번에 드롭다운이 열리는 동시에 페이지가 넘어간다.
 */
export function KickoffMenu({
  active,
  triggerClassName,
}: {
  active: boolean;
  triggerClassName: string;
}) {
  const [open, setOpen] = useState(false);

  return (
    <div
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      className="relative"
    >
      <DropdownMenu open={open} onOpenChange={setOpen} modal={false}>
        <DropdownMenuTrigger asChild>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className={cn("gap-1.5", triggerClassName)}
            {...(active ? { "aria-current": "page" as const } : {})}
          >
            킥오프
            <ChevronDown
              className={cn(
                "h-3.5 w-3.5 shrink-0 transition-transform duration-200 ease-out",
                open && "rotate-180",
              )}
              aria-hidden
            />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent
          align="start"
          sideOffset={6}
          // 이 시스템은 평면이다 — 드롭다운도 그림자 대신 보더로 뜬다 (DESIGN.md §6).
          className="w-56 border-stone-300/70 dark:border-stone-600/70 shadow-none"
        >
          {KICKOFF_ITEMS.map((item) =>
            item.href ? (
              <DropdownMenuItem key={item.label} asChild className="cursor-pointer">
                <Link href={item.href} className="flex flex-col items-start gap-0.5">
                  <span>{item.label}</span>
                  <span className="text-xs text-muted-foreground">{item.description}</span>
                </Link>
              </DropdownMenuItem>
            ) : (
              <DropdownMenuItem key={item.label} disabled className="flex-col items-start gap-0.5">
                <span>{item.label}</span>
                <span className="text-xs text-muted-foreground">{item.description}</span>
              </DropdownMenuItem>
            ),
          )}
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}
