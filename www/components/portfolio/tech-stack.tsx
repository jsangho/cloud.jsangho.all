"use client";

import * as React from "react";

import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

/**
 * 포트폴리오 기술 스택 — 칩에 마우스를 올리면 **그 기술이 실제로 도는 자리**가 뜬다.
 *
 * 칩 이름만으로는 "이력서용 나열"과 구분되지 않는다. 어디서 돌아가는지를 붙여야
 * 면접에서 물어볼 수 있는 문장이 된다.
 *
 * 클라이언트 컴포넌트인 이유는 툴팁 하나뿐이다 — 데이터는 전부 서버에서 내려온다.
 */

export type StackChip = {
  name: string;
  /** 이 기술이 실제로 쓰이는 자리. 호버·포커스·탭에서 보인다. */
  where: string;
  /** 비우면 이 저장소(KAYFABE)의 것. 팀 프로젝트 몫은 칩 색이 갈린다. */
  project?: "supersub";
};

export type StackGroup = { group: string; items: StackChip[] };

const SUPERSUB_LABEL = "SUPER-SUB 팀 프로젝트 · AI 영상 분석 에이전트";

/** 블루는 이 시스템에서 AI·데이터의 색이다 (DESIGN.md §2) — 네 번째 색을 만들지 않는다. */
const TEAM_CHIP = "border-data/40 bg-data/10 text-data hover:bg-data/20";
const OWN_CHIP = "border-border bg-card text-muted-foreground hover:bg-card-2";

export function TechStack({ groups }: { groups: readonly StackGroup[] }) {
  return (
    <TooltipProvider delayDuration={120}>
      <p className="mt-3 flex items-center gap-1.5 text-xs text-muted-foreground">
        <span className={cn("rounded-md border px-2 py-0.5", TEAM_CHIP)}>파란 칩</span>
        {SUPERSUB_LABEL}
      </p>

      <dl className="mt-5 flex flex-col gap-4">
        {groups.map(({ group, items }) => (
          <div
            key={group}
            className="grid grid-cols-1 gap-2 border-t border-border pt-4 sm:grid-cols-[7rem_minmax(0,1fr)] sm:gap-4"
          >
            <dt className="text-sm font-semibold text-foreground">{group}</dt>
            <dd className="flex flex-wrap gap-1.5">
              {items.map((item) => (
                <StackChipButton key={item.name} item={item} />
              ))}
            </dd>
          </div>
        ))}
      </dl>
    </TooltipProvider>
  );
}

function StackChipButton({ item }: { item: StackChip }) {
  // 호버·포커스는 Radix가 열어 주지만 터치는 열어 주지 않는다. 탭으로도 보이게
  // 열림 상태를 직접 쥔다 — 휴대폰에서 읽을 수 없는 설명은 없는 것과 같다.
  const [open, setOpen] = React.useState(false);
  const isTeam = item.project === "supersub";

  return (
    <Tooltip open={open} onOpenChange={setOpen}>
      <TooltipTrigger
        onClick={() => setOpen(true)}
        className={cn(
          "cursor-help rounded-md border px-2 py-1 text-xs transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-link",
          isTeam ? TEAM_CHIP : OWN_CHIP,
        )}
      >
        {item.name}
      </TooltipTrigger>
      <TooltipContent side="top" className="max-w-80 text-left leading-relaxed">
        {isTeam && <p className="font-semibold text-background/70">{SUPERSUB_LABEL}</p>}
        <p>{item.where}</p>
      </TooltipContent>
    </Tooltip>
  );
}
