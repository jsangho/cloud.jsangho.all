import { titleAcquisitionsBaseUrl, requestTimeoutMs } from "@/lib/api";

export type ChampionshipTier = "main" | "secondary" | "tag" | "other";

export type TitleReign = {
  beltName: string;
  champions: string[];
  teamName?: string | null;
  wonAt: string;
  wonEvent?: string | null;
  tier: ChampionshipTier;
};

export type BrandRoster = {
  id: "raw" | "smackdown" | "nxt" | "global";
  label: string;
  tagline: string;
  accent: "red" | "blue" | "gold" | "purple";
  titles: TitleReign[];
};

export type ChampionshipBoard = {
  asOf: string;
  brands: BrandRoster[];
};

export async function fetchChampionshipBoard(): Promise<ChampionshipBoard | null> {
  const url = `${titleAcquisitionsBaseUrl}/`;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), requestTimeoutMs);
  try {
    const res = await fetch(url, { signal: controller.signal });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}
