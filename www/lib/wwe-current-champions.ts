import type { BrandRoster, ChampionshipTier, TitleReign } from "@/lib/championship-api";

export type { ChampionshipTier, TitleReign, BrandRoster } from "@/lib/championship-api";

export type ChampionBeltInfo = {
  beltName: string;
  tier: ChampionshipTier;
  accent: BrandRoster["accent"];
};

export const TIER_LABELS: Record<ChampionshipTier, string> = {
  main: "메인 챔피언십",
  secondary: "2선 타이틀",
  tag: "태그팀",
  other: "그 외",
};

export const TIER_ORDER: ChampionshipTier[] = ["main", "secondary", "tag", "other"];

export function formatChampionshipDate(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  if (!y || !m || !d) return iso;
  return new Intl.DateTimeFormat("ko-KR", {
    year: "numeric",
    month: "long",
    day: "numeric",
  }).format(new Date(y, m - 1, d));
}

/** 선수 이름 → 보유 중인 벨트 목록 (기록 페이지에서 챔피언 뱃지 표시용) */
export function buildChampionBeltMap(brands: BrandRoster[]): Map<string, ChampionBeltInfo[]> {
  const map = new Map<string, ChampionBeltInfo[]>();
  for (const brand of brands) {
    for (const title of brand.titles) {
      for (const champion of title.champions) {
        const belts = map.get(champion) ?? [];
        belts.push({ beltName: title.beltName, tier: title.tier, accent: brand.accent });
        map.set(champion, belts);
      }
    }
  }
  return map;
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
