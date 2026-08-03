import { pleMatchPicksBaseUrl, requestTimeoutMs } from "@/lib/api";

/** 순위표에 노출되는 장착 아이템. `code`로 표시 규칙을 고르고 `name`을 보여준다. */
export type CosmeticItem = {
  code: string;
  name: string;
};

export type RankingRow = {
  rank: number;
  nickname: string;
  score: number;
  accuracy: number;
  /** 상점에서 사서 장착한 아이템 — 없으면 `null` */
  title?: CosmeticItem | null;
  nicknameColor?: CosmeticItem | null;
  badge?: CosmeticItem | null;
};

export type RankingsResponse = {
  rows: RankingRow[];
  myRank?: RankingRow | null;
};

export function clamp01(value: number) {
  return Math.min(1, Math.max(0, value));
}

export function formatAccuracy(value: number) {
  const pct = Math.round(clamp01(value) * 100);
  return `${pct}%`;
}

export async function fetchRankings(options?: {
  limit?: number;
  nickname?: string;
}): Promise<RankingsResponse | null> {
  const params = new URLSearchParams();
  if (options?.limit != null) {
    params.set("limit", String(options.limit));
  }
  if (options?.nickname) {
    params.set("nickname", options.nickname);
  }
  const q = params.toString();
  const url = `${pleMatchPicksBaseUrl}/${q ? `?${q}` : ""}`;

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
