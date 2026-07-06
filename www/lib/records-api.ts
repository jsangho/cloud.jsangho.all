import { pleMatchesBaseUrl, requestTimeoutMs } from "@/lib/api";

export type CompetitorSummary = {
  total: number;
  wins: number;
  losses: number;
  noContest: number;
  pending: number;
  singlesTotal: number;
  multiTotal: number;
  championAppearances: number;
};

export type CompetitorMatchRecord = {
  slug: string;
  pleLabel: string;
  matchKey: string;
  title: string;
  format: "singles" | "multi";
  result: "win" | "loss" | "no-contest" | "pending";
  winnerName?: string | null;
  opponents?: string[];
  participants?: string[];
  wasChampion?: boolean;
};

export type CompetitorProfile = {
  name: string;
  matches: CompetitorMatchRecord[];
  summary: CompetitorSummary;
};

export async function fetchCompetitorNames(q?: string): Promise<string[]> {
  const params = new URLSearchParams();
  if (q?.trim()) params.set("q", q.trim());
  const query = params.toString();
  const url = `${pleMatchesBaseUrl}/competitors${query ? `?${query}` : ""}`;

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), requestTimeoutMs);
  try {
    const res = await fetch(url, { signal: controller.signal });
    if (!res.ok) return [];
    const data = (await res.json()) as { names?: string[] };
    return Array.isArray(data.names) ? data.names : [];
  } catch {
    return [];
  } finally {
    clearTimeout(timer);
  }
}

export async function fetchCompetitorProfile(
  name: string,
): Promise<CompetitorProfile | null> {
  const url = `${pleMatchesBaseUrl}/competitors/${encodeURIComponent(name)}`;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), requestTimeoutMs);
  try {
    const res = await fetch(url, { signal: controller.signal });
    if (res.status === 404) return null;
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}
