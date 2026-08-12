/**
 * 커리어 시뮬레이터 API 클라이언트 (`/api/career/*`).
 *
 * 백엔드 계약은 `fastapi/apps/wwe_game/_docs/career-simulator-harness.md` §7이다.
 *
 * **두 갈래가 같은 응답 모양을 쓴다.** 로그인 플레이는 서버가 세이브를 들고 있고,
 * 체험판(`/guest/*`)은 브라우저가 `state`를 통째로 들고 다니며 매 요청에 실어 보낸다
 * (§3-D8). 화면 입장에서 다른 것은 **`state`를 보관해야 하는가**뿐이라, 진행 결과를
 * 읽는 코드는 한 벌로 유지된다.
 *
 * `null`은 "없음"이고 `throw`는 진짜 실패다 — 진행 중인 커리어가 아직 없는 것은
 * 정상이므로 `readCurrentRun()`은 null을 돌려준다.
 */

import { apiBaseUrl, parseApiError, requestTimeoutMs } from "@/lib/api";

const careerBaseUrl = `${apiBaseUrl}/api/career`;

// ── 응답 타입 (백엔드 `career_schema.py`와 1:1) ──────────────

export type CareerModeCode = "yearly" | "quarterly" | "monthly" | "weekly";
export type StepMode = "auto" | "tick";

export type CareerMode = {
  code: CareerModeCode;
  label: string;
  weeksPerTick: number;
  ticks: number;
  eventBudget: number;
  /** 비로그인으로 플레이할 수 있는지. `yearly`·`quarterly`만 참이다 (§3-D8). */
  guestAllowed: boolean;
};

export type CareerPreset = {
  source: string;
  gender: "male" | "female";
  playStyle: string;
  playStyleLabel: string;
  /** 목록 밖 출신은 `OTHER`다 — 비어 있지 않다 (§3-D10-1). */
  country: string;
};

/** 경기력 드롭다운 한 줄. 앞 셋은 파워·스피드·운영 고정, 넷째만 스타일마다 다르다. */
export type CareerSkill = { name: string; value: number };

export type CareerStats = {
  popularity: number;
  inRing: number;
  micWork: number;
  backstage: number;
  alignment: number;
  wear: number;
  playStyle: string;
  playStyleLabel: string;
  skills: CareerSkill[];
};

export type CareerTeam = {
  /** 화면에 그대로 쓰는 이름. 이름 없는 태그팀은 "A & B"다. */
  label: string;
  name: string;
  members: string[];
  kind: "tag_team" | "stable";
  formedWeek: number;
};

export type CareerWeek = {
  /** 커리어 통산 주차(1~1560). 정렬·키에 쓴다. */
  week: number;
  /** 게임 달력이 되읽은 날짜 — 화면은 "2년차 9월 2주"로 말한다. */
  year: number;
  month: number;
  weekOfMonth: number;
  kind: "weekly_show" | "promo" | "ple" | "special" | "off";
  result: "win" | "loss" | "draw" | null;
  narration: string;
  show: string | null;
  titleAtStake: string | null;
  /** 그 주차에 붙은 상대. 경기 없는 주차는 null. */
  opponent: string | null;
  /** 경기 형식 — "로열럼블 매치"처럼 화면에 그대로 쓴다. */
  matchKind: string | null;
  matchLabel: string | null;
  /** 참가 인원. 여럿이 붙는 경기는 상대 한 명을 말하면 안 된다. */
  matchField: number;
  /** 댄하우젠의 저주로 진 경기. 평범한 패배와 다르게 그린다. */
  cursed: boolean;
  /** 그 경기의 별점 (§3-D56). 경기가 없는 주차는 0이다. */
  stars: number;
  /**
   * 탈락 경기의 한 줄 요약 — "17번으로 입장 · 3명 탈락 · 우승(30인)".
   * **다시 연 로그에도 이것만은 남는다** (§3-D34).
   */
  matchSummary: string | null;
  /**
   * 자격이 아니라 **권리로** 선 타이틀전 (§3-D36).
   * `earned` = 럼블·챔버 우승 도전권 · `briefcase` = 가방을 썼다.
   */
  titleShotFrom: "earned" | "briefcase" | null;
  /** 킹 앤 퀸 오브 더 링의 회전 (§3-D33). 0이면 토너먼트 경기가 아니다. */
  tournamentRound: number;
  /**
   * 입장·탈락 전체. **진행 중인 응답에만 실린다** — 저장하지 않기 때문이다.
   * 문장이 아니라 구조로 오므로 문구는 화면이 만든다.
   */
  beats: CareerBeat[] | null;
};

/** 경기 진행 한 마디 (§3-D34). */
export type CareerBeat = {
  kind: "enter" | "eliminate" | "win";
  name: string;
  /** 입장 순번. `enter`에만 채워진다. */
  number: number;
  /** 누가 탈락시켰는가. `eliminate`에만 채워진다. */
  by: string | null;
};

export type CareerRunView = {
  id: number | null;
  /** 내 링네임. 탈락 타임라인에서 내 줄을 짚는 데 쓴다 (§3-D34). */
  name: string;
  week: number;
  year: number;
  age: number;
  brand: string;
  mode: CareerModeCode;
  status: string;
  endReason: string | null;
  stats: CareerStats;
  condition: string;
  titlesHeld: string[];
  titlesWon: string[];
  team: CareerTeam | null;
  rivalries: CareerRivalry[];
  /** 로그 화면 하단에 상시 노출한다 (§3-D13). */
  disclaimer: string;
};

export type CareerRivalry = {
  rival: string;
  stage: string;
  heat: number;
  startedWeek: number;
};

export type CareerChoice = { code: string; label: string };

export type CareerPendingEvent = {
  code: string;
  title: string;
  body: string;
  choices: CareerChoice[];
};

export type CareerAdvance = {
  run: CareerRunView;
  weeks: CareerWeek[];
  /** `recovered` = 부상에서 돌아왔다 (§3-D37) — 부상 구간은 통째로 흘러가고 여기서 끊긴다. */
  stopReason: "ready" | "event" | "ple" | "ended" | "recovered" | "tick" | "max_weeks";
  pendingEvent: CareerPendingEvent | null;
};

/** 체험판 응답 — 로그인 쪽에 **세이브 전체**가 붙는다. 저장은 브라우저가 한다. */
export type GuestAdvance = CareerAdvance & { state: GuestRunState };

/**
 * 브라우저가 보관하는 세이브. **안을 들여다보지 않는다** — 서버가 준 것을 그대로
 * 되돌려 보내는 불투명한 값이다. 필드를 읽기 시작하면 규칙이 프론트로 새고,
 * 그건 §4-18(프론트에 판정을 복제하지 않는다)이 막는 것이다.
 */
export type GuestRunState = Record<string, unknown>;

export type CareerNewsItem = {
  week: number;
  year: number;
  month: number;
  weekOfMonth: number;
  kind: string;
  headline: string;
  mood: "roar" | "jeer" | "split" | "hush" | "chant";
  crowdLine: string;
};

export type CareerNewsPage = {
  items: CareerNewsItem[];
  total: number;
  offset: number;
  hasMore: boolean;
};

export type CareerLogPage = {
  entries: CareerWeek[];
  total: number;
  offset: number;
  hasMore: boolean;
};

/**
 * 그 밤의 리포트 (§3-D45). **뉴스와 다르다** — 뉴스는 커리어의 기억이고 이쪽은
 * 한 밤의 카드다: 그날 벨트를 누가 들고 있었고 그 무렵 세계에 무슨 일이 있었는지.
 */
/** 그날 밤의 다른 경기 한 줄 (§3-D52). **내 경기는 여기 없다** — 로그 줄이 그 자리다. */
export type CareerCardMatch = {
  left: string;
  right: string;
  /** `left` · `right` 중 하나. 배경 경기에 무승부는 없다. */
  winner: string;
  /** 걸린 벨트의 표시 이름. 타이틀전이 아니면 null. */
  title: string | null;
  /** 그날 밤 벨트에 새 주인이 생겼는지. `title`이 있을 때만 뜻이 있다. */
  changedHands: boolean;
  /** 빈 벨트를 두고 붙은 경기 — 앞 챔피언이 링을 떠났다. */
  vacant: boolean;
  /** 그 경기의 별점 (0~5, 0.25 눈금). */
  stars: number;
  /** 경기 형식. 싱글이면 null. */
  matchLabel: string | null;
};

export type CareerShowReport = {
  week: number;
  show: string;
  isMajor: boolean;
  result: "win" | "loss" | "draw" | null;
  opponent: string | null;
  matchLabel: string | null;
  titleAtStake: string | null;
  narration: string;
  champions: { title: string; holder: string; mine: boolean }[];
  around: string[];
  /** 그날 밤의 다른 경기들, 오프너부터 (§3-D52). */
  card: CareerCardMatch[];
  /** 그 밤의 평점 — 카드의 평균. */
  stars: number;
  /** 그 밤의 경기장 (§3-D69). 서술이 쓴 것과 같은 값이다. */
  venue: string;
  /** 그 밤의 로고 키 (§3-D71). `/ple/<key>.png`에 있다. 없으면 빈 문자열. */
  logo: string;
  /** 며칠에 걸쳐 열렸는가. 이틀이면 카드가 두 배다. */
  nights: number;
};

/** 그 주차의 리포트. **대회 주차가 아니면 404이므로 null로 접는다.** */
export async function readReport(runId: number, week: number): Promise<CareerShowReport | null> {
  try {
    return await request<CareerShowReport>(`/runs/${runId}/report?week=${week}`);
  } catch (error) {
    if (error instanceof CareerApiError && error.status === 404) return null;
    throw error;
  }
}

export type StartRunInput = {
  name: string;
  mode: CareerModeCode;
  basedOn?: string;
  gender?: "male" | "female";
  country?: string;
  playStyle?: string;
};

// ── 요청 ─────────────────────────────────────────────────────

/**
 * 커리어 API 호출 실패. **상태 코드를 들고 있다** — 화면이 409(선택이 먼저다)와
 * 404(없는 커리어)를 다르게 처리해야 한다.
 */
export class CareerApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "CareerApiError";
    this.status = status;
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), requestTimeoutMs);
  try {
    const res = await fetch(`${careerBaseUrl}${path}`, {
      ...init,
      // httpOnly 쿠키가 교차 출처 요청에 실리려면 반드시 필요하다.
      credentials: "include",
      signal: controller.signal,
      headers: init.body ? { "Content-Type": "application/json" } : undefined,
    });
    if (!res.ok) {
      // `ApiErrorBody`는 lib/api.ts 안에만 있다. 좁게 단언해 넘긴다.
      const body = (await res.json().catch(() => null)) as { detail?: string } | null;
      throw new CareerApiError(parseApiError(body, res.status), res.status);
    }
    return (await res.json()) as T;
  } finally {
    clearTimeout(timer);
  }
}

function post<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, { method: "POST", body: JSON.stringify(body) });
}

// ── 메타 (인증 불필요) ───────────────────────────────────────

export function readModes(): Promise<CareerMode[]> {
  return request<CareerMode[]>("/modes");
}

export function readPresets(): Promise<CareerPreset[]> {
  return request<CareerPreset[]>("/presets");
}

// ── 로그인 플레이 ────────────────────────────────────────────

export function startRun(input: StartRunInput): Promise<CareerAdvance> {
  return post<CareerAdvance>("/runs", input);
}

/** 진행 중인 세이브. **아직 시작 안 한 상태는 정상이므로 null이다.** */
export async function readCurrentRun(): Promise<CareerAdvance | null> {
  return request<CareerAdvance | null>("/runs/current");
}

/** '다음'. 대기 이벤트가 있으면 409로 막힌다 (§11-2). */
export function advanceRun(runId: number, step: StepMode = "auto"): Promise<CareerAdvance> {
  return post<CareerAdvance>(`/runs/${runId}/advance`, { step });
}

export function chooseEvent(runId: number, choice: string): Promise<CareerAdvance> {
  return post<CareerAdvance>(`/runs/${runId}/choices`, { choice });
}

export function readLog(runId: number, offset = 0, limit = 50): Promise<CareerLogPage> {
  return request<CareerLogPage>(`/runs/${runId}/log?offset=${offset}&limit=${limit}`);
}

export function readNews(runId: number, offset = 0, limit = 50): Promise<CareerNewsPage> {
  return request<CareerNewsPage>(`/runs/${runId}/news?offset=${offset}&limit=${limit}`);
}

/** 스스로 커리어를 닫는다 — 은퇴 조건 중 하나다 (§3-D16). */
export function retireRun(runId: number): Promise<CareerAdvance> {
  return request<CareerAdvance>(`/runs/${runId}`, { method: "DELETE" });
}

// ── 체험판 (§3-D8 · 인증 불필요) ─────────────────────────────

export function startGuestRun(input: StartRunInput & { seed?: number }): Promise<GuestAdvance> {
  return post<GuestAdvance>("/guest/runs", input);
}

/**
 * 다시 열었을 때의 화면 상태. **진행하지 않는다** — 로그인 쪽 `readCurrentRun()`의 짝이다.
 *
 * 이게 없던 동안 재개는 `advanceGuestRun(state, "tick")`를 대신 썼고, 새로고침 한 번이
 * 한 틱(분기 모드면 12주)을 태웠다. 대기 이벤트가 있으면 409라 세이브까지 지워졌다.
 */
export function resumeGuestRun(state: GuestRunState): Promise<GuestAdvance> {
  return post<GuestAdvance>("/guest/resume", { state });
}

export function advanceGuestRun(
  state: GuestRunState,
  step: StepMode = "auto",
): Promise<GuestAdvance> {
  return post<GuestAdvance>("/guest/advance", { state, step });
}

/**
 * 체험판의 그 밤 리포트 (§3-D51). **대회 주차가 아니면 404이므로 null로 접는다.**
 *
 * 로그인 쪽 `readReport()`의 짝이지만 **돌려받는 것이 좁다** — 체험판 세이브에는 로그가
 * 없어(§3-D8) 내 경기 기록(승패·상대·서술)이 비어 온다. 화면이 그 줄을 이미 들고 있어
 * 리포트가 채우는 것은 배경(그날의 벨트·그 무렵)뿐이다.
 */
export async function readGuestReport(
  state: GuestRunState,
  week: number,
  night: { opponent: string | null; titleAtStake: string | null },
): Promise<CareerShowReport | null> {
  try {
    return await post<CareerShowReport>("/guest/report", {
      state,
      week,
      // 서버에 로그가 없어 그 줄의 사실을 화면이 알려 준다 (§3-D52) — 카드가 내 상대를
      // 같은 밤에 두 번 세우거나, 내가 도전한 벨트를 다시 걸지 않게 하는 데만 쓰인다.
      opponent: night.opponent,
      titleAtStake: night.titleAtStake,
    });
  } catch (error) {
    if (error instanceof CareerApiError && error.status === 404) return null;
    throw error;
  }
}

/**
 * 체험판 인박스 (§3-D67). **배경 소식만 온다** — 내 로그가 서버에 없기 때문이다(§3-D8).
 *
 * 로그인 쪽 `readNews()`의 짝이지만 담기는 것이 좁다: 세계 벨트·대립·팀·명부는 시드에서
 * 되짚히고, 내 대관·부상·턴은 주차 로그에서만 나온다.
 */
export function readGuestNews(state: GuestRunState): Promise<CareerNewsPage> {
  return post<CareerNewsPage>("/guest/news", { state });
}

export function chooseGuestEvent(state: GuestRunState, choice: string): Promise<GuestAdvance> {
  return post<GuestAdvance>("/guest/choices", { state, choice });
}
