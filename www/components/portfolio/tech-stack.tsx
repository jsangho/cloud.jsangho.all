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
  project?: TeamProject;
};

/** 팀 프로젝트에서 맡은 몫. 팀마다 칩 색이 다르다. */
type TeamProject = "supersub" | "gaon";

export type StackGroup = { group: string; items: StackChip[] };

/**
 * 팀마다 **색을 따로 준다** (2026-10-07 사용자 결정). 전에는 둘 다 파랑이라
 * 「팀 프로젝트」까지만 말하고 어느 팀인지는 눌러야 나왔는데, 화면에서 둘이
 * 한 덩어리로 읽혔다.
 *
 * 🔴 **티얼은 네 번째 채도 높은 색이다** — DESIGN.md §7 의 금지 조항에 이
 * 예외를 적어 뒀다. 값은 눈으로 고르지 않았다: 첫 후보 바이올렛(`#7c3aed`)은
 * 녹색약 시뮬레이션에서 파랑과 ΔE 0.6 으로 붙어 탈락했고, 티얼은 정상시·
 * 적색약·녹색약 전부에서 ΔE 17.7 이상이다. 단계는 두 칩의 카드 대비가
 * 같아지게 잡았다(라이트 5.29 / 5.00 · 다크 4.97 / 5.06) — 한쪽이 더 튀면
 * 그 프로젝트가 더 중요해 보인다.
 *
 * **색만으로 말하지는 않는다.** 범례가 칩과 팀 이름을 짝지어 보여 주고,
 * 칩을 누르면 툴팁 첫 줄이 다시 팀 이름을 적는다 (DESIGN.md §2 의 원칙).
 */
const TEAM: Record<TeamProject, { label: string; chip: string; legend: string }> = {
  supersub: {
    label: "SUPER-SUB 팀 프로젝트 · AI 영상 분석 에이전트",
    legend: "SUPER-SUB",
    chip: "border-team-a/40 bg-team-a/10 text-team-a hover:bg-team-a/20",
  },
  gaon: {
    label: "GAON 팀 프로젝트 · 관광동선 지도 · 문화재 3D",
    legend: "GAON",
    chip: "border-team-b/40 bg-team-b/10 text-team-b hover:bg-team-b/20",
  },
};

const TEAM_ORDER: readonly TeamProject[] = ["supersub", "gaon"];

const OWN_CHIP = "border-border bg-card text-muted-foreground hover:bg-card-2";

export function TechStack({ groups }: { groups: readonly StackGroup[] }) {
  return (
    <TooltipProvider delayDuration={120}>
      <p className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1.5 text-xs text-muted-foreground">
        <span>색이 붙은 칩은 팀 프로젝트에서 맡은 몫입니다</span>
        {TEAM_ORDER.map((key) => (
          <span key={key} className="flex items-center gap-1.5">
            <span className={cn("rounded-md border px-2 py-0.5", TEAM[key].chip)}>
              {TEAM[key].legend}
            </span>
          </span>
        ))}
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
  const team = item.project ? TEAM[item.project] : null;

  return (
    <Tooltip open={open} onOpenChange={setOpen}>
      <TooltipTrigger
        onClick={() => setOpen(true)}
        className={cn(
          "cursor-help rounded-md border px-2 py-1 text-xs transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-link",
          team ? team.chip : OWN_CHIP,
        )}
      >
        {item.name}
      </TooltipTrigger>
      <TooltipContent side="top" className="max-w-80 text-left leading-relaxed">
        {team && <p className="font-semibold text-background/70">{team.label}</p>}
        <p>{item.where}</p>
      </TooltipContent>
    </Tooltip>
  );
}
