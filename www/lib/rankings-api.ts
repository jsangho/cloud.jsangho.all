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
  /**
   * 적중률의 분자·분모. 이 둘을 내보내기 전 백엔드가 떠 있을 수 있어 옵셔널이다 —
   * 프론트(Vercel)와 백엔드(EC2)는 따로 배포된다.
   */
  correct?: number;
  graded?: number;
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

/**
 * 적중률의 표본을 "2/3 경기"로 적는다 — 분모 없는 백분율은 과장이다 (DESIGN.md §14).
 *
 * 분모를 못 받았으면 `null`이다. 지어내지 않는다.
 */
export function formatAccuracySample(row: RankingRow): string | null {
  if (row.correct == null || row.graded == null || row.graded <= 0) return null;
  return `${row.correct}/${row.graded} 경기`;
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
