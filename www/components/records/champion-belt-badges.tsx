import { Crown, Medal, Users } from "lucide-react";
import { cn } from "@/lib/utils";
import type { BrandRoster, ChampionshipTier } from "@/lib/championship-api";
import type { ChampionBeltInfo } from "@/lib/wwe-current-champions";

const TIER_ICON: Record<ChampionshipTier, typeof Crown> = {
  main: Crown,
  secondary: Medal,
  tag: Users,
  other: Medal,
};

const ACCENT_CLASS: Record<BrandRoster["accent"], string> = {
  red: "text-red-500 dark:text-red-400",
  blue: "text-blue-500 dark:text-blue-400",
  gold: "text-brand-500 dark:text-brand-400",
  purple: "text-violet-500 dark:text-violet-400",
};

/** 선수 이름 옆에 붙는 소유 벨트 아이콘 (브랜드 색상 + 체급 아이콘으로 벨트 구분) */
export function ChampionBeltBadges({
  belts,
  className,
}: {
  belts: ChampionBeltInfo[];
  className?: string;
}) {
  if (belts.length === 0) return null;

  return (
    <span className={cn("inline-flex shrink-0 items-center gap-1", className)}>
      {belts.map((belt) => {
        const Icon = TIER_ICON[belt.tier];
        return (
          <span key={belt.beltName} title={belt.beltName}>
            <Icon
              className={cn("h-3.5 w-3.5", ACCENT_CLASS[belt.accent])}
              aria-label={belt.beltName}
            />
          </span>
        );
      })}
    </span>
  );
}
