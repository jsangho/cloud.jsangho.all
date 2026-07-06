import type { ChampionshipTier, TitleReign } from "@/lib/championship-api";

export type {
  ChampionshipTier,
  TitleReign,
  BrandRoster,
} from "@/lib/championship-api";

export const TIER_LABELS: Record<ChampionshipTier, string> = {
  main: "메인 챔피언십",
  secondary: "2선 타이틀",
  tag: "태그팀",
  other: "그 외",
};

export const TIER_ORDER: ChampionshipTier[] = [
  "main",
  "secondary",
  "tag",
  "other",
];

export function formatChampionshipDate(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  if (!y || !m || !d) return iso;
  return new Intl.DateTimeFormat("ko-KR", {
    year: "numeric",
    month: "long",
    day: "numeric",
  }).format(new Date(y, m - 1, d));
}

export function groupTitlesByTier(titles: TitleReign[]) {
  const map = new Map<ChampionshipTier, TitleReign[]>();
  for (const tier of TIER_ORDER) map.set(tier, []);
  for (const title of titles) {
    map.get(title.tier)?.push(title);
  }
  return TIER_ORDER.map((tier) => ({
    tier,
    label: TIER_LABELS[tier],
    titles: map.get(tier) ?? [],
  })).filter((g) => g.titles.length > 0);
}
