"use client";

import Link from "next/link";
import { useState } from "react";
import { ChevronDown } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/**
 * More — 메인 내비에서 내려온 것들을 모은 자리 (KAYFABE 2.0 Phase 1).
 *
 * **아무것도 지우지 않았다.** 상점·킥오프(대화·커리어)·레슨은 그대로 살아 있고,
 * 메인 여섯 자리(홈·PLE 예측·데이터 센터·AI LAB·랭킹·기록)를 비우기 위해
 * 여기로 옮겼을 뿐이다 — 경로도 그대로라 기존 링크·북마크가 안 깨진다.
 *
 * 앞의 `KickoffMenu`를 일반화한 것이다: 그쪽은 항목 둘짜리 전용 메뉴였고,
 * 이제 그 둘이 이 메뉴의 한 묶음이 됐다.
 */
export type MoreItem = {
  label: string;
  description: string;
  href: string;
};

export type MoreGroup = {
  /** 묶음 제목. 한 묶음뿐이면 제목을 안 그린다. */
  title?: string;
  items: readonly MoreItem[];
};

export const MORE_GROUPS: readonly MoreGroup[] = [
  {
    items: [{ label: "상점", description: "포인트로 칭호·뱃지 사기", href: "/shop" }],
  },
  {
    title: "킥오프",
    items: [
      { label: "대화", description: "슈퍼스타와 이야기하기", href: "/chat" },
      { label: "커리어 시뮬레이터", description: "20세 데뷔, 30년", href: "/career" },
    ],
  },
  {
    title: "실습",
    items: [{ label: "레슨", description: "데이터 수집부터 모델까지", href: "/lesson" }],
  },
] as const;

/** More가 활성인 경로들. 항목이 늘면 여기도 함께 늘린다. */
export const MORE_PATHS: readonly string[] = MORE_GROUPS.flatMap((g) => g.items.map((i) => i.href));

export function isMorePath(pathname: string): boolean {
  return MORE_PATHS.some((p) => pathname === p || pathname.startsWith(`${p}/`));
}

/**
 * 데스크톱은 hover와 클릭 둘 다로 열린다. **트리거는 링크가 아니다** — 터치에는 hover가
 * 없어서 링크로 두면 탭 한 번에 드롭다운이 열리는 동시에 페이지가 넘어간다.
 */
export function MoreMenu({
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
            className={cn("gap-1", triggerClassName)}
            aria-expanded={open}
            aria-current={active ? "page" : undefined}
          >
            더보기
            <ChevronDown
              className={cn("size-3.5 transition-transform", open && "rotate-180")}
              aria-hidden
            />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" sideOffset={6} className="w-60">
          {MORE_GROUPS.map((group, index) => (
            <div key={group.title ?? `group-${index}`}>
              {index > 0 && <DropdownMenuSeparator />}
              {group.title && (
                <DropdownMenuLabel className="text-xs text-muted-foreground">
                  {group.title}
                </DropdownMenuLabel>
              )}
              {group.items.map((item) => (
                <DropdownMenuItem key={item.href} asChild className="cursor-pointer">
                  <Link href={item.href} className="flex flex-col items-start gap-0.5">
                    <span>{item.label}</span>
                    <span className="text-xs text-muted-foreground">{item.description}</span>
                  </Link>
                </DropdownMenuItem>
              ))}
            </div>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}
