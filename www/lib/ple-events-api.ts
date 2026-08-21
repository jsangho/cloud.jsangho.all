import { pleEventsBaseUrl, pleMatchesBaseUrl, requestTimeoutMs } from "@/lib/api";

/**
 * PLE 이벤트 목록과 KPI — **서버가 아는 것만 읽는다** (KAYFABE 2.0 §12).
 *
 * 지금까지 `/ple`과 홈은 정적 상수(`WWE_PLE_MONTHLY_ORDER`)와 날짜 계산만으로
 * 상태를 그렸다. 그러면 DB가 "끝났다"고 아는 대회도 화면에서는 날짜로 짐작한
 * 상태가 뜬다. 여기서 받는 `status`·`matchCount`가 그 원본이다.
 *
 * **API를 새로 만들지 않았다.** 아래 둘은 이미 있던 엔드포인트다 —
 * `GET /api/ple_events/events`와 `GET /api/ple-matches/competitors`.
 */
export type PleEventRow = {
  slug: string;
  label: string;
  month: number | null;
  year: number;
  /** 서버가 아는 상태 — `upcoming` · `live` · `finished` */
  status: string;
  matchCount: number;
};

export async function fetchPleEvents(): Promise<PleEventRow[]> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), requestTimeoutMs);
  try {
    const res = await fetch(`${pleEventsBaseUrl}/events`, { signal: controller.signal });
    if (!res.ok) return [];
    const data = (await res.json()) as PleEventRow[];
    return Array.isArray(data) ? data : [];
  } catch {
    return [];
  } finally {
    clearTimeout(timer);
  }
}

/** 명부에 이름이 오른 선수 수. `/competitors`가 돌려주는 목록의 크기다. */
export async function fetchCompetitorCount(): Promise<number | null> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), requestTimeoutMs);
  try {
    const res = await fetch(`${pleMatchesBaseUrl}/competitors`, { signal: controller.signal });
    if (!res.ok) return null;
    const data = (await res.json()) as { names?: string[] };
    return Array.isArray(data.names) ? data.names.length : null;
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}

export type KayfabeKpi = {
  events: number;
  matches: number;
  wrestlers: number | null;
};

/**
 * 홈 KPI — **세는 것 말고는 아무것도 하지 않는다** (§12).
 *
 * 이벤트 수는 목록의 길이, 경기 수는 그 목록이 들고 온 `matchCount`의 합이다.
 * 없는 값을 추정하거나 예시 숫자로 채우지 않는다 — 못 받으면 그 타일은 안 그린다.
 */
export async function fetchKayfabeKpi(): Promise<KayfabeKpi | null> {
  const [events, wrestlers] = await Promise.all([fetchPleEvents(), fetchCompetitorCount()]);
  if (events.length === 0) return null;
  return {
    events: events.length,
    matches: events.reduce((sum, e) => sum + (e.matchCount ?? 0), 0),
    wrestlers,
  };
}
