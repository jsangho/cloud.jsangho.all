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
  /** 실제 출생지. */
  birthPlace: string | null;
  /** 방송이 부르는 연고지. `|`로 여럿일 수 있다. */
  billedFrom: string | null;
  /** 둘이 다른가. **`null`은 비교 불가**이고 "같다"가 아니다. */
  hometownDiffers: boolean | null;
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
  /** 소개 연고지가 실제와 다른 선수 수 — **검색·브랜드와 무관한 전체 수**다. */
  hometownDiffersTotal: number;
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

/** 다가오는 생일 한 건. `age`는 **그 생일에 맞이할** 나이다. */
export type Birthday = {
  name: string;
  /** 선수는 브랜드, 비선수는 CSV 구역(`Executives` 등). */
  group: string | null;
  kind: "wrestler" | "staff";
  /** 비선수만 있다 — `Commentator` 등. */
  role: string | null;
  /** `MM-DD` */
  monthDay: string;
  birthDate: string;
  /** **`null`이면 태어난 해를 모른다** — 그 사람도 목록에는 선다. */
  age: number | null;
  /** 오늘이면 0. */
  daysAway: number;
};

export type BirthdayBoard = {
  /** 서버가 KST로 센 오늘. 클라이언트 시계를 믿지 않는다. */
  today: string;
  entries: Birthday[];
  /** 생일을 아는 사람 수 / 명부 전체 — 선수와 비선수가 함께 들어간다. */
  dated: number;
  total: number;
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
  /** `"differs"`면 소개 연고지가 실제와 다른 선수만. */
  hometown?: string;
  page?: number;
  size?: number;
}): Promise<WrestlerPage | null> {
  const params = new URLSearchParams();
  if (options?.q?.trim()) params.set("q", options.q.trim());
  if (options?.brand?.trim()) params.set("brand", options.brand.trim());
  if (options?.hometown?.trim()) params.set("hometown", options.hometown.trim());
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

export function fetchBirthdays(limit = 5): Promise<BirthdayBoard | null> {
  return getJson<BirthdayBoard>(`/birthdays?limit=${limit}`);
}

/** `MM-DD` → `10.15`. 연도를 안 붙이는 이유는 이 값이 "다가오는 날짜"라서다. */
export function formatMonthDay(monthDay: string): string {
  const [month, day] = monthDay.split("-");
  return `${Number(month)}.${Number(day)}`;
}

/** D-0은 「오늘」, 나머지는 `D-3`. 숫자만 쓰면 오늘이 D-0으로 묻힌다. */
export function formatDaysAway(daysAway: number): string {
  return daysAway === 0 ? "오늘" : `D-${daysAway}`;
}

export type OriginCount = {
  name: string;
  count: number;
  /** 그 지역 출신 선수 이름. 지역을 누르면 명단으로 펼친다. */
  members: string[];
};

export type Origins = {
  countries: OriginCount[];
  usStates: OriginCount[];
  /** 미국 사람인데 주를 모르는 수. */
  usStateUnknown: number;
  /** 출신을 아는 사람 / 전체 — **화면이 이 분모를 적는다.** */
  located: number;
  total: number;
};

export function fetchOrigins(): Promise<Origins | null> {
  return getJson<Origins>("/origins");
}

export type Trainers = {
  groups: OriginCount[];
  /** 학교·센터로 판정된 이름 — 사람과 갈라 적기 위한 표시다. */
  institutions: string[];
  known: number;
  total: number;
};

export function fetchTrainers(): Promise<Trainers | null> {
  return getJson<Trainers>("/trainers");
}

export type StaffMember = {
  name: string;
  /** 한글 링네임 — 관계자 표는 이 칸이 100% 차 있다. */
  koreanName: string | null;
  group: string | null;
  role: string | null;
  /** 링에 섰던 사람인가. */
  formerWrestler: boolean;
};

export type StaffDirectory = {
  members: StaffMember[];
  /** (구역, 인원) — CSV가 적은 조직도 순서 그대로다. */
  groups: { name: string; count: number }[];
  formerWrestlers: number;
  total: number;
};

export function fetchStaff(): Promise<StaffDirectory | null> {
  return getJson<StaffDirectory>("/staff");
}
