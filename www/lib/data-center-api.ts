import { apiBaseUrl, requestTimeoutMs } from "@/lib/api";

/**
 * 데이터 센터 API 클라이언트 (Phase 2).
 *
 * **원본은 DB다.** 홈 KPI가 쓰는 `/ple-matches/competitors`(정적 로스터 166명)와 달리
 * 여기 숫자는 `wrestlers`·`ple_matches`·`title_acquisitions`를 센 값이다 — 둘은 다른
 * 뜻이라 어느 한쪽에 맞춰 보정하지 않는다.
 *
 * 못 받으면 `null`을 돌려준다. 화면은 그 자리를 비우고, **0으로 채우지 않는다.**
 */
const dataCenterBaseUrl = `${apiBaseUrl}/api/data-center`;

export type DataCenterCounts = {
  wrestlers: number;
  matches: number;
  finishedMatches: number;
  events: number;
  finishedEvents: number;
  championshipBelts: number;
  titleAcquisitions: number;
};

export type DataCenterMatch = {
  eventSlug: string;
  eventLabel: string;
  month: number | null;
  year: number;
  matchKey: string;
  title: string;
  format: string;
  status: string;
  participants: string[];
  /** 승자를 못 되짚으면 `null`이다 — 태그 경기에 흔하다. */
  winnerName: string | null;
  isTitleMatch: boolean;
};

export type DataCenterOverview = {
  counts: DataCenterCounts;
  recentMatches: DataCenterMatch[];
};

export type DataCenterWrestler = {
  name: string;
  brand: string | null;
  realName: string | null;
  birthDate: string | null;
  finisher: string | null;
  stableTeam: string | null;
  matches: number;
  wins: number;
  losses: number;
  /** 끝난 경기가 없으면 `null` — 0이 아니다. */
  winRate: number | null;
  titles: number;
};

export type WrestlerPage = {
  items: DataCenterWrestler[];
  total: number;
  page: number;
  size: number;
  /** DB에 실제로 있는 브랜드만 온다 — 목록을 화면에 박지 않는다. */
  brands: string[];
};

export type EventOption = { slug: string; label: string };

export type MatchPage = {
  items: DataCenterMatch[];
  total: number;
  page: number;
  size: number;
  events: EventOption[];
};

export type BeltStat = {
  beltName: string;
  reigns: number;
  holders: number;
  topHolder: string | null;
  topHolderReigns: number;
  /** 이 집계에 합쳐진 옛 이름. 없으면 빈 배열이다. */
  formerNames: string[];
};

/** 현 벨트로 이어지지 않아 집계에서 뺀 이름 — 화면이 사유를 그대로 적는다. */
export type ExcludedBelt = { beltName: string; reigns: number; reason: string };

export type HolderStat = { name: string; reigns: number; belts: number };

/**
 * **`belts`는 지금 있는 벨트만** 담는다 (20종 · 현 챔피언 보드 기준).
 * `totalAcquisitions`·`holderCount`·`topHolders`는 폐지 벨트까지 포함한 전체 기록이라
 * 범위가 다르다 — 화면이 그 차이를 적는다.
 */
export type ChampionshipStats = {
  totalAcquisitions: number;
  beltCount: number;
  holderCount: number;
  belts: BeltStat[];
  topHolders: HolderStat[];
  excludedBelts: ExcludedBelt[];
};

/** 획득 한 건. `beltName`은 **그때 불리던 이름**이다. */
export type BeltReign = { competitorName: string; beltName: string; wonAt: string };

export type BeltHolder = { name: string; reigns: number; history: BeltReign[] };

export type BeltDetail = {
  beltName: string;
  formerNames: string[];
  reigns: number;
  holderCount: number;
  holders: BeltHolder[];
};

export type EventStat = {
  slug: string;
  label: string;
  month: number | null;
  year: number;
  matches: number;
  finished: number;
  titleMatches: number;
  multiMatches: number;
};

export type BrandCount = { brand: string; wrestlers: number };

export type RatedWrestler = {
  name: string;
  wins: number;
  losses: number;
  winRate: number;
};

export type DataCenterAnalytics = {
  events: EventStat[];
  brands: BrandCount[];
  singlesMatches: number;
  multiMatches: number;
  titleMatches: number;
  nonTitleMatches: number;
  topWinRates: RatedWrestler[];
  /** 승률 순위에 오르는 최소 경기 수. **화면이 이 숫자를 함께 적는다.** */
  minMatchesForRate: number;
};

async function getJson<T>(path: string): Promise<T | null> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), requestTimeoutMs);
  try {
    const res = await fetch(`${dataCenterBaseUrl}${path}`, { signal: controller.signal });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}

export function fetchDataCenterOverview(): Promise<DataCenterOverview | null> {
  return getJson<DataCenterOverview>("/overview");
}

export function fetchWrestlerPage(options?: {
  q?: string;
  brand?: string;
  page?: number;
  size?: number;
}): Promise<WrestlerPage | null> {
  const params = new URLSearchParams();
  if (options?.q?.trim()) params.set("q", options.q.trim());
  if (options?.brand?.trim()) params.set("brand", options.brand.trim());
  if (options?.page) params.set("page", String(options.page));
  if (options?.size) params.set("size", String(options.size));
  const query = params.toString();
  return getJson<WrestlerPage>(`/wrestlers${query ? `?${query}` : ""}`);
}

export function fetchMatchPage(options?: {
  event?: string;
  competitor?: string;
  status?: string;
  page?: number;
  size?: number;
}): Promise<MatchPage | null> {
  const params = new URLSearchParams();
  if (options?.event?.trim()) params.set("event", options.event.trim());
  if (options?.competitor?.trim()) params.set("competitor", options.competitor.trim());
  if (options?.status?.trim()) params.set("status", options.status.trim());
  if (options?.page) params.set("page", String(options.page));
  if (options?.size) params.set("size", String(options.size));
  const query = params.toString();
  return getJson<MatchPage>(`/matches${query ? `?${query}` : ""}`);
}

export function fetchChampionshipStats(): Promise<ChampionshipStats | null> {
  return getJson<ChampionshipStats>("/championships");
}

/** 벨트 하나의 획득 이력. **현 챔피언 보드가 쓰는 이름**으로 묻는다 — 옛 이름은 404다. */
export function fetchBeltDetail(beltName: string): Promise<BeltDetail | null> {
  return getJson<BeltDetail>(`/championships/${encodeURIComponent(beltName)}`);
}

export function fetchDataCenterAnalytics(): Promise<DataCenterAnalytics | null> {
  return getJson<DataCenterAnalytics>("/analytics");
}

/** 승률 표기 — **`null`이면 대시**다. 0%로 그리면 "다 졌다"로 읽힌다. */
export function formatWinRate(rate: number | null): string {
  if (rate === null) return "—";
  return `${Math.round(rate * 100)}%`;
}
