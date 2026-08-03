import { cn } from "@/lib/utils";
import type { CosmeticItem } from "@/lib/rankings-api";

/**
 * 상점 `nickname_color` 상품 코드 → 닉네임 색상 클래스.
 *
 * Tailwind는 빌드 시 소스의 클래스 문자열을 스캔하므로 코드로 조립하지 않고 표로 둔다.
 * 카탈로그에 여기 없는 코드가 들어오면 색상 없이 기본색으로 표시된다 — 상품을 추가하면
 * 이 표에도 넣어야 한다.
 */
const NICKNAME_COLOR_CLASSES: Readonly<Record<string, string>> = {
  nickname_color_gold: "text-amber-600 dark:text-amber-300",
  nickname_color_crimson: "text-red-600 dark:text-red-400",
  nickname_color_azure: "text-sky-600 dark:text-sky-400",
  nickname_color_emerald: "text-emerald-600 dark:text-emerald-400",
  nickname_color_violet: "text-violet-600 dark:text-violet-400",
};

export function nicknameColorClass(item?: CosmeticItem | null): string | undefined {
  return item ? NICKNAME_COLOR_CLASSES[item.code] : undefined;
}

/** 닉네임 앞에 붙는 칭호 */
export function RankingTitleTag({ item }: { item?: CosmeticItem | null }) {
  if (!item) return null;
  return <span className="mr-1.5 text-xs font-semibold text-stone-500">{item.name}</span>;
}

/** 닉네임 뒤에 붙는 뱃지 */
export function RankingBadgeTag({
  item,
  className,
}: {
  item?: CosmeticItem | null;
  className?: string;
}) {
  if (!item) return null;
  return (
    <span
      title={item.name}
      className={cn(
        "shrink-0 rounded-md border border-stone-300/60 dark:border-stone-600/60 bg-stone-200/40 dark:bg-stone-800/40 px-1.5 py-0.5 text-[10px] font-bold tracking-wide text-stone-600 dark:text-stone-300",
        className,
      )}
    >
      {item.name}
    </span>
  );
}
