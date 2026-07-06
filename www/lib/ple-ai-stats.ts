import { pleEventsBaseUrl, requestTimeoutMs } from "@/lib/api";

export type PleAiRecord = {
  eventSlug: string;
  eventLabel: string;
  matchKey: string;
  matchTitle: string;
  aiPickName: string;
  winnerName?: string | null;
  correct: boolean;
};

export type PleAiStats = {
  totalGraded: number;
  correct: number;
  incorrect: number;
  accuracyPercent: number | null;
  /** 채점된 경기 전체 (PLE·카드 순, API recent 필드) */
  recent: PleAiRecord[];
};

export async function fetchPleAiStats(): Promise<PleAiStats | null> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), requestTimeoutMs);
  try {
    const res = await fetch(`${pleEventsBaseUrl}/ai-stats`, {
      signal: controller.signal,
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}
