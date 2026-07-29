import { pleMatchPicksBaseUrl, requestTimeoutMs } from "@/lib/api";

export type RankingRow = {
  rank: number;
  nickname: string;
  score: number;
  accuracy: number;
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

/**
 * 보유 포인트 = 적중한 예측의 배점 합계(순위표 `score`)와 같다.
 * 요청 실패는 `null`, 채점된 예측이 없어 순위 집계에서 빠진 사용자는 `0`.
 */
export async function fetchMyPoints(nickname: string): Promise<number | null> {
  const data = await fetchRankings({ nickname, limit: 1 });
  if (data === null) return null;
  return data.myRank?.score ?? 0;
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
