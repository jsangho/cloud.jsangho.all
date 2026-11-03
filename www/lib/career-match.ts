/**
 * 커리어 경기 기록 — **P1 조회 API 의 응답 모양과, 화면이 그것을 읽는 순수 규칙.**
 *
 * 타입은 서버 스키마(`career_sandbox_schema.py` 의 `MatchSummarySchema` ·
 * `MatchDetailSchema` · `MatchNotFoundSchema`)를 그대로 옮겼다. 추측한 칸이 없다.
 *
 * ## 왜 `career-api.ts` 가 아니라 여기인가
 *
 * 이 파일은 **import 가 하나도 없다.** 그래서 `career-request-keys` 와 같은 방식
 * (`tsc` → CommonJS → `node --test`)으로 테스트할 수 있다 — `career-api.ts` 는
 * `@/lib/api` 를 import 해서 그 러너로 못 떨어뜨린다. 타입은 `career-api.ts` 가
 * 다시 내보낸다.
 *
 * ## 화면이 값을 만들지 않는다
 *
 * 승패·평점·확률·전후 상태는 전부 서버가 **저장해 둔 값**이다. 여기서 하는 계산은
 * 「after − before」 하나뿐이고, 그것도 두 저장값의 차를 보여 줄 뿐 새 사실이 아니다.
 * 태그전 개인 전적의 알려진 결함도 보정하지 않는다 — 팀 승패의 정본은 `winnerSide`.
 */

export type CareerMatchState = {
  popularity: number;
  condition: number;
  wins: number;
  losses: number;
  winStreak: number;
  losingStreak: number;
};

/** 시뮬레이션이 실제로 쓴 경기력 세 항. */
export type CareerMatchPower = { skill: number; draw: number; body: number };

export type CareerMatchParticipant = {
  name: string;
  /** `teams` 의 몇 번째 팀인가. 0 은 항상 플레이어 쪽이다. */
  side: number;
  power: CareerMatchPower;
  before: CareerMatchState;
  after: CareerMatchState;
};

export type CareerMatchHeat = {
  a: string;
  b: string;
  /** 경기 전 관계가 없었으면 `null` — 이 경기로 관계가 생겼다. */
  before: number | null;
  after: number;
};

/** 부상 한 건. 서버 `InjurySchema` 와 같은 모양(`CareerInjury`)이다. */
export type CareerMatchInjury = {
  kind: string;
  severity: string;
  season: number;
  week: number;
  weeksOut: number;
  recovered: boolean;
  recurrence: boolean;
  permanent: boolean;
};

/** 목록 한 줄. */
export type CareerMatchSummary = {
  id: string;
  season: number;
  week: number;
  brand: string;
  kind: string;
  reason: string;
  /** `[플레이어 팀, 상대 팀]`. */
  teams: string[][];
  winnerSide: number;
  title: string | null;
  titleChanged: boolean;
  finish: string;
  rating: number;
  /** 목록은 저장된 기록에서만 만들어져 지금은 늘 `true` 다(P1 보고). 분기에 쓰지 않는다. */
  hasDetail: boolean;
};

/** 경기 기록 한 장. */
export type CareerMatchDetail = {
  id: string;
  season: number;
  week: number;
  brand: string;
  kind: string;
  reason: string;
  title: string | null;
  titleChanged: boolean;
  teams: string[][];
  winnerSide: number;
  /** 플레이어 팀(`teams[0]`)의 경기 전 승리 확률. */
  probability: number;
  finish: string;
  rating: number;
  finisher: string | null;
  /** 핀폴이 아니면 `null`. */
  scorer: string | null;
  pinned: string | null;
  /** **저장 순서 그대로** — 이름으로 묶지 않는다(동명이인이 한 칸을 덮어쓴다). */
  participants: CareerMatchParticipant[];
  heat: CareerMatchHeat[];
  injury: CareerMatchInjury | null;
  popularityDelta: number;
};

export const CAREER_MATCH_MISSING_REASONS = ["before_records", "trimmed", "unexplained"] as const;
export type CareerMatchMissingReason = (typeof CAREER_MATCH_MISSING_REASONS)[number];

/** 상세 조회 결과. **세 갈래가 화면에서 다르게 그려진다.** */
export type CareerMatchLookup =
  | { status: "ok"; match: CareerMatchDetail }
  /** 내 커리어인데 그 경기 기록이 없다(404 + `missingReason` 칸). */
  | { status: "missing"; reason: CareerMatchMissingReason | null }
  /** 그 밖의 실패 — 없는 커리어·남의 커리어(404, 사유 칸 없음) · 5xx · 네트워크. */
  | { status: "error"; message: string };

// ── URL ─────────────────────────────────────────────────────────

/** 서버 경로 파라미터 상한(`Path(max_length=32)`). 넘으면 서버가 422 를 준다. */
export const MATCH_ID_MAX = 32;

/**
 * URL 의 `match` 값. **형식을 추측해 거르지 않는다** — 서버 id 형식(`s1w52:p`)을
 * 정규식으로 박으면 서버가 접미사를 늘릴 때 화면이 유효한 id 를 버린다. 비었는지와
 * 서버가 받아 줄 길이인지만 본다. 나머지는 서버가 404 로 답한다.
 */
export function matchParamStatus(raw: string | null): "none" | "valid" | "invalid" {
  if (raw == null) return "none";
  const value = raw.trim();
  if (value.length === 0) return "invalid";
  if (value.length > MATCH_ID_MAX || value !== raw) return "invalid";
  return "valid";
}

// ── 404 본문 ─────────────────────────────────────────────────────

/**
 * 404 본문이 **경기 기록 없음**인가. 서버는 그때만 `missingReason` 칸을 싣는다
 * (값이 `null` 이어도 칸은 있다). 칸이 없는 404 는 「없는 커리어 · 남의 커리어」다 —
 * 둘을 섞으면 남의 커리어가 「보존 기간이 지났다」로 보인다.
 *
 * 모르는 사유 문자열은 `null`(판정 불가)로 읽는다 — 서버가 사유를 늘려도 화면이
 * 엉뚱한 안내를 하지 않게.
 */
export function readMissingBody(
  body: unknown,
): { missing: true; reason: CareerMatchMissingReason | null } | { missing: false } {
  if (!body || typeof body !== "object" || !("missingReason" in body)) return { missing: false };
  const raw = (body as { missingReason?: unknown }).missingReason;
  const reason = CAREER_MATCH_MISSING_REASONS.find((r) => r === raw) ?? null;
  return { missing: true, reason };
}

/** 사유별 안내. `unexplained` 만 「데이터 확인이 필요하다」고 말한다. */
export function missingCopy(reason: CareerMatchMissingReason | null): {
  title: string;
  body: string;
  tone: "info" | "alert";
} {
  switch (reason) {
    case "before_records":
      return {
        title: "기록 도입 전 경기",
        body: "경기 상세 기록을 남기기 시작하기 전에 치른 경기입니다. 승패와 결과 문장은 커리어 기록에 그대로 남아 있습니다.",
        tone: "info",
      };
    case "trimmed":
      return {
        title: "보존 기간이 지난 경기",
        body: "상세 기록은 최근 104경기(두 시즌)까지만 보관합니다. 이 경기는 그보다 오래되어 지워졌고, 결과는 커리어 기록에 남아 있습니다.",
        tone: "info",
      };
    case "unexplained":
      return {
        title: "기록이 있어야 하는데 없습니다",
        body: "커리어 기록에는 이 경기가 있지만 상세 기록을 찾을 수 없습니다. 보존 기간 만료가 아니라 세이브 데이터 확인이 필요한 상태입니다.",
        tone: "alert",
      };
    default:
      return {
        title: "경기 기록을 찾을 수 없습니다",
        body: "이 주차에 치른 경기를 확인할 수 없습니다. 링크가 잘못됐거나 경기가 없던 주차일 수 있습니다.",
        tone: "info",
      };
  }
}

// ── 경기 전후 ────────────────────────────────────────────────────

export const MATCH_STATE_ROWS = [
  { key: "popularity", label: "인기도", upIsGood: true },
  { key: "condition", label: "컨디션", upIsGood: true },
  { key: "wins", label: "승리", upIsGood: true },
  { key: "losses", label: "패배", upIsGood: false },
  { key: "winStreak", label: "연승", upIsGood: true },
  { key: "losingStreak", label: "연패", upIsGood: false },
] as const satisfies readonly {
  key: keyof CareerMatchState;
  label: string;
  upIsGood: boolean;
}[];

export type StateChange = {
  key: keyof CareerMatchState;
  label: string;
  before: number;
  after: number;
  delta: number;
  /** 변화가 선수에게 좋은 쪽인가. 변화가 없으면 `null`. 패배·연패는 늘면 나쁘다. */
  good: boolean | null;
};

/** 참가자 한 명의 전후 여섯 줄. 순서는 `MATCH_STATE_ROWS` 가 정한다. */
export function stateChanges(p: Pick<CareerMatchParticipant, "before" | "after">): StateChange[] {
  return MATCH_STATE_ROWS.map(({ key, label, upIsGood }) => {
    const before = p.before[key];
    const after = p.after[key];
    const delta = after - before;
    return {
      key,
      label,
      before,
      after,
      delta,
      good: delta === 0 ? null : delta > 0 === upIsGood,
    };
  });
}

/** `+3` · `−2` · `±0`. 마이너스는 하이픈이 아니라 수학 기호를 쓴다(자릿수가 맞는다). */
export function signed(n: number): string {
  if (n > 0) return `+${n}`;
  if (n < 0) return `−${Math.abs(n)}`;
  return "±0";
}

// ── 팀 ───────────────────────────────────────────────────────────

/** 팀별 참가자 — **저장 순서를 지킨다.** `side` 로 가르되 각 팀 안의 순서는 그대로. */
export function participantsBySide(
  participants: readonly CareerMatchParticipant[],
): [CareerMatchParticipant[], CareerMatchParticipant[]] {
  return [participants.filter((p) => p.side === 0), participants.filter((p) => p.side === 1)];
}

/** 참가자 이름 옆에 붙는 역할. 핀폴이 아니면 `scorer`·`pinned` 가 `null` 이라 안 붙는다. */
export function participantRoles(
  match: Pick<CareerMatchDetail, "finisher" | "scorer" | "pinned">,
  name: string,
): string[] {
  const roles: string[] = [];
  if (match.scorer != null && match.scorer === name) roles.push("핀 승리");
  else if (match.finisher != null && match.finisher === name) roles.push("결정타");
  if (match.pinned != null && match.pinned === name) roles.push("핀 패배");
  return roles;
}

// ── 페이지 ───────────────────────────────────────────────────────

/** 목록 한 페이지. 서버 `limit` 상한(200) 안이다. */
export const MATCH_PAGE = 20;

/**
 * 다음 페이지가 있을 수 있는가. 서버가 `total` 을 주지 않으므로 **꽉 찬 페이지면
 * 있다고 본다** — 마지막 페이지가 정확히 꽉 차 있으면 다음 페이지가 빈 채로 열린다.
 * 그 빈 페이지는 「더 없음」으로 그린다.
 */
export function hasNextPage(rowsOnPage: number, limit: number = MATCH_PAGE): boolean {
  return rowsOnPage >= limit;
}

/** 지난 주 보고와 같은 주차의 기록인가 — 주간 보고 링크는 **이걸 통과한 id 만** 쓴다. */
export function recordForWeek(
  rows: readonly Pick<CareerMatchSummary, "id" | "season" | "week">[],
  season: number,
  week: number,
): string | null {
  return rows.find((r) => r.season === season && r.week === week)?.id ?? null;
}
