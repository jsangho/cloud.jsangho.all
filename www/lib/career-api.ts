import {
  getRequestTimeoutMessage,
  isAbortError,
  parseApiError,
  requestTimeoutMs,
  sandboxCareersBaseUrl,
} from "@/lib/api";

/**
 * 저장되는 커리어 — **세이브가 서버에 있고 소유자가 있다.**
 *
 * `sandbox-api.ts`의 `careerStep`과 다른 물건이다. 그쪽은 로그인 없이 상태를 들고
 * 가서 한 주를 돌려 보는 장난감이고 서버가 아무것도 저장하지 않는다. 이쪽은
 * 재접속해도 같은 세계가 남아 있고, 그래서 로그인이 필요하다.
 *
 * **상태를 프론트가 계산하지 않는다.** 능력치·승패·인기도는 전부 서버가 정하고
 * 화면은 받은 것을 그린다 — 행동 요청에 담는 것은 행동 코드와 대상뿐이다.
 */
export type CareerAbility = {
  inRing: number;
  mic: number;
  stamina: number;
  resilience: number;
};

/**
 * 은퇴 위험. **점수 칸이 없다 — 서버가 일부러 안 내보낸다.**
 *
 * 가중합을 퍼센트로 적으면 검증되지 않은 정밀도가 생긴다. 그래서 설명 가능한
 * 단계(`band`)와 근거(`reasons`)만 온다. 화면이 여기서 확률을 만들어 내지 않는다.
 */
export type CareerRisk = {
  band: string;
  reasons: string[];
};

export type CareerInjury = {
  kind: string;
  severity: string;
  season: number;
  week: number;
  weeksOut: number;
  recovered: boolean;
  recurrence: boolean;
  permanent: boolean;
};

export type CareerRetirement = {
  cause: string;
  season: number;
  week: number;
  age: number;
  wins: number;
  losses: number;
  held: string[];
  reigns: number;
  titles: string[];
  note: string;
};

/** 은퇴 **의사**. 확정(`CareerRetirement`)과 다른 칸이다. */
export type CareerIntent = {
  origin: string;
  cause: string;
  season: number;
  week: number;
  finalSeason: boolean;
};

export type CareerWrestler = {
  name: string;
  style: string;
  brand: string;
  age: number;
  debutAge: number;
  alignment: string;
  popularity: number;
  ability: CareerAbility;
  condition: number;
  status: string;
  wins: number;
  losses: number;
  reigns: string[];
  held: string[];
  outWeeks: number;
  isPlayer: boolean;
  injuries: CareerInjury[];
  /** 최근 능력치 변화. 시즌이 둘 미만이면 `null`. */
  trend: CareerAbility | null;
  intent: CareerIntent | null;
  retirement: CareerRetirement | null;
  risk: CareerRisk | null;
};

export type CareerRelationship = {
  a: string;
  b: string;
  kind: string;
  heat: number;
  startedWeek: number;
  lastWeek: number;
  history: string[];
  /**
   * **끓는 라이벌인가 — 서버가 판정한다.**
   *
   * `kind === "rival"` 로 라이벌을 세면 안 된다. 서버가 경기마다 진 쪽을 라이벌로
   * 올려서(`after_match`) 한 시즌만 돌면 상대 거의 전원이 그 kind 를 갖는다
   * (실측: 경기 30건 중 30건). 임계값은 서버에만 있고 이 칸은 판정만 담는다.
   */
  feud: boolean;
};

export type CareerTitle = {
  name: string;
  brand: string;
  requiredPopularity: number;
  holder: string | null;
  defenses: number;
  /** 재위 주차. 보유 중이 아니면 `null`. */
  reignWeeks: number | null;
};

export type CareerChoice = {
  code: string;
  label: string;
  /** 못 고르는 선택지도 내려온다 — 왜 못 고르는지 `note`가 적는다. */
  enabled: boolean;
  note: string;
};

export type CareerEvent = {
  id: string;
  kind: string;
  season: number;
  week: number;
  subject: string;
  other: string | null;
  headline: string;
  detail: string;
  choices: CareerChoice[];
};

export type CareerLogEntry = {
  season: number;
  week: number;
  kind: string;
  subject: string;
  summary: string;
  other: string | null;
  result: string | null;
  title: string | null;
};

export type CareerSeason = {
  season: number;
  wins: number;
  losses: number;
  age: number;
  ability: CareerAbility;
  abilityDelta: CareerAbility;
  titlesWon: string[];
  defenses: number;
  injuries: number;
  retired: string[];
  highlights: string[];
  riskBand: string;
};

/** 다음 경기. 경기가 없으면 `kind === "rest"`. */
export type CareerCard = {
  kind: string;
  opponent: string | null;
  title: string | null;
  partner: string | null;
  opponents: string[];
  note: string;
};

export type CareerWeekReport = {
  season: number;
  week: number;
  kind: string;
  opponent: string | null;
  won: boolean | null;
  title: string | null;
  titleChanged: boolean;
  finish: string | null;
  rating: number;
  popularityDelta: number;
  injured: string | null;
  injuredWeeks: number;
  promotedTo: string | null;
  openedEvents: string[];
  retired: boolean;
  riskBand: string;
  probability: number;
};

export type CareerSummary = {
  id: number;
  playerName: string;
  season: number;
  week: number;
  seasonWeeks: number;
  phase: string;
  createdAt: string;
  updatedAt: string;
};

export type CareerView = {
  id: number;
  season: number;
  week: number;
  /** 시즌 길이. **서버 값을 그대로 적는다** — 52를 화면에 박아 두지 않는다. */
  seasonWeeks: number;
  phase: string;
  actionPoints: number;
  maxActionPoints: number;
  player: CareerWrestler;
  nextCard: CareerCard;
  pending: CareerEvent[];
  titles: CareerTitle[];
  relationships: CareerRelationship[];
  roster: CareerWrestler[];
  seasons: CareerSeason[];
  recentLog: CareerLogEntry[];
  /** 마지막 주차 진행의 보고. 새로 만든 커리어면 `null`. */
  lastReport: CareerWeekReport | null;
};

/** 서버가 아는 주간 행동. 없는 코드는 422로 돌아온다. */
export const CAREER_ACTIONS = ["훈련", "프로모", "휴식", "관계", "협상"] as const;
export type CareerAction = (typeof CAREER_ACTIONS)[number];

/** 훈련 대상. 서버의 `TRAINABLE`과 같은 넷이다. */
export const CAREER_TRAINABLE = ["in_ring", "mic", "stamina", "resilience"] as const;
export type CareerTrainable = (typeof CAREER_TRAINABLE)[number];

/**
 * 쓰기 실패. **`inconclusive`가 재시도 방식을 가른다.**
 *
 * 타임아웃·네트워크 오류는 서버가 그 요청을 처리했는지 **알 수 없다**. 그 상태로
 * 새 키를 달아 다시 보내면 서버가 두 번째를 새 요청으로 보고 또 적용한다 — 그래서
 * 이 경우에만 **같은 키를 유지**한다.
 *
 * 서버가 4xx를 준 경우는 결론이 났다. 요청이 거부됐고 상태는 그대로이므로, 입력을
 * 고쳐 보낼 때는 **새 키**가 맞다(같은 키에 다른 내용이면 서버가 409를 준다).
 */
export class CareerWriteError extends Error {
  readonly inconclusive: boolean;

  constructor(message: string, inconclusive: boolean) {
    super(message);
    this.name = "CareerWriteError";
    this.inconclusive = inconclusive;
  }
}

/**
 * 요청 키 하나. **한 번의 사용자 의도에 하나**이고, 재전송에는 같은 값을 쓴다.
 *
 * 서버가 만들어서는 안 된다 — 서버가 매번 새로 만들면 모든 요청이 새 요청이라
 * 재시도를 식별할 수 없다.
 */
export function newCareerRequestId(): string {
  const c = globalThis.crypto;
  if (typeof c?.randomUUID === "function") return c.randomUUID();
  // 보안 컨텍스트가 아니면 `randomUUID`가 없다(LAN IP + http로 열었을 때). 키가
  // 겹치면 서로 다른 의도가 같은 응답을 받으므로 128비트를 그대로 쓴다.
  const bytes = new Uint8Array(16);
  c.getRandomValues(bytes);
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}

/**
 * 쓰기 요청. **`null`이 아니라 `throw`한다** — 실패 사유를 화면이 구별해야 한다.
 * 서버가 404(없는 커리어)·409(단계 불일치 · 요청 키 충돌)·422(입력 오류)로 갈라 준다.
 *
 * `requestId`를 주면 `Idempotency-Key` 헤더로 실린다. 서버는 쓰기 다섯 경로에서
 * 이 헤더를 **요구하므로**, 빼면 422가 돌아온다. 헤더인 이유는 쓰기 셋
 * (`advance`·`settle`·`next-season`)이 본문이 없어서다.
 */
async function mutate(
  path: string,
  options: { requestId?: string; body?: string } = {},
): Promise<CareerView> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), requestTimeoutMs);
  const headers: Record<string, string> = {};
  if (options.body != null) headers["Content-Type"] = "application/json";
  if (options.requestId != null) headers["Idempotency-Key"] = options.requestId;
  try {
    const res = await fetch(`${sandboxCareersBaseUrl}${path}`, {
      method: "POST",
      credentials: "include",
      headers,
      body: options.body,
      signal: controller.signal,
    });
    if (!res.ok) {
      const body = (await res.json().catch(() => null)) as { detail?: string } | null;
      // 서버가 답했다 — 결론이 났다. 5xx만 "처리됐는지 모른다"로 남는다.
      throw new CareerWriteError(parseApiError(body, res.status), res.status >= 500);
    }
    return (await res.json()) as CareerView;
  } catch (error) {
    // 타임아웃·네트워크 오류의 브라우저 원문을 그대로 띄우지 않는다.
    if (isAbortError(error)) throw new CareerWriteError(getRequestTimeoutMessage(), true);
    if (error instanceof TypeError) {
      throw new CareerWriteError("서버에 연결하지 못했습니다. 잠시 후 다시 시도해 주세요.", true);
    }
    throw error;
  } finally {
    clearTimeout(timer);
  }
}

async function read<T>(path: string): Promise<T | null> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), requestTimeoutMs);
  try {
    const res = await fetch(`${sandboxCareersBaseUrl}${path}`, {
      credentials: "include",
      signal: controller.signal,
    });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}

/** 내 커리어 목록. 실패·빈 목록 모두 `[]`. */
export async function fetchCareers(): Promise<CareerSummary[]> {
  const rows = await read<CareerSummary[]>("");
  return Array.isArray(rows) ? rows : [];
}

/** 현재 상태. **재접속 복구가 이 호출 하나다.** */
export async function fetchCareer(careerId: number): Promise<CareerView | null> {
  return read<CareerView>(`/${careerId}`);
}

/**
 * 새 커리어. **요청 키를 받지 않는다 — 서버도 요구하지 않는다.**
 *
 * 멱등 키의 범위가 `(사용자, 커리어, 키)`이고 생성에는 커리어가 아직 없다. 다른
 * 범위를 하나 더 만드는 대신 범위를 좁게 유지했다 — 중복 생성은 세이브가 하나 더
 * 생기는 것이고 진행 중인 세계가 망가지는 일이 아니라서, 화면의 버튼 비활성화로
 * 충분하다고 봤다. (고치려면 `(사용자, 키)` 범위가 따로 필요하다.)
 */
export async function createCareer(input: {
  name: string;
  style: string;
  age: number;
  /** 주면 같은 세계가 재현된다. 안 주면 서버가 만든다. */
  seed?: number;
}): Promise<CareerView> {
  return mutate("", {
    body: JSON.stringify({
      name: input.name,
      style: input.style,
      age: input.age,
      seed: input.seed ?? null,
    }),
  });
}

/**
 * 주간 행동 하나. 보내는 것은 코드와 대상뿐 — 효과는 서버가 정한다.
 *
 * `requestId`가 같으면 서버가 **한 번만 적용하고** 최초 응답을 그대로 준다.
 */
export async function performCareerAction(
  careerId: number,
  action: CareerAction,
  target: string | undefined,
  requestId: string,
): Promise<CareerView> {
  return mutate(`/${careerId}/actions`, {
    requestId,
    body: JSON.stringify({ action, target: target ?? null }),
  });
}

/** 한 주 진행. 같은 `requestId`의 재전송은 **주차를 넘기지 않는다.** */
export async function advanceCareerWeek(careerId: number, requestId: string): Promise<CareerView> {
  return mutate(`/${careerId}/advance`, { requestId });
}

export async function resolveCareerEvent(
  careerId: number,
  eventId: string,
  choice: string,
  requestId: string,
): Promise<CareerView> {
  return mutate(`/${careerId}/events/${encodeURIComponent(eventId)}`, {
    requestId,
    body: JSON.stringify({ choice }),
  });
}

/** 시즌 결산. 나이가 여기서만 오른다. */
export async function settleCareerSeason(careerId: number, requestId: string): Promise<CareerView> {
  return mutate(`/${careerId}/settle`, { requestId });
}

export async function startNextCareerSeason(
  careerId: number,
  requestId: string,
): Promise<CareerView> {
  return mutate(`/${careerId}/next-season`, { requestId });
}

/** 커리어 기록. 최근 것부터, 페이지로 끊어서. */
export async function fetchCareerLog(
  careerId: number,
  options: { season?: number; limit?: number; offset?: number } = {},
): Promise<CareerLogEntry[]> {
  const query = new URLSearchParams();
  if (options.season != null) query.set("season", String(options.season));
  query.set("limit", String(options.limit ?? 50));
  query.set("offset", String(options.offset ?? 0));
  const rows = await read<CareerLogEntry[]>(`/${careerId}/log?${query.toString()}`);
  return Array.isArray(rows) ? rows : [];
}
