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
  /** 여럿이 붙고 **중간에 탈락자가 나오는** 경기인가 — 럼블·챔버·배틀로얄. */
  eliminationMatch?: boolean;
  /** 몇 번으로 입장했는가. 0이면 없다. */
  entryNumber?: number;
  /** 내가 떨어뜨린 사람 수. */
  eliminations?: number;
  /** 최종 순위. 1이면 우승 — 분모는 `matchField`다. */
  place?: number;
  /**
   * 입장·탈락 전체. **진행 중인 응답에만 실린다** — 저장하지 않기 때문이다.
   * 문장이 아니라 구조로 오므로 문구는 화면이 만든다.
   */
  beats: CareerBeat[] | null;
  /** 그 주 수입(달러). 무소속 주차는 인디 개런티다 (§3-D50). */
  pay?: number;
  /** 방어 성공. **이긴 것과 지킨 것은 다른 사건이다** (§3-D73). */
  titleDefended?: boolean;
  /** 그 주에 반납한 벨트 (§3-D40). 길게 다치면 내려놓는다. */
  vacated?: string[];
  /** 다친 곳의 이름 (§3-D43). */
  injuryPart?: string | null;
  /** `earned`(실력으로) · `emergency`(공백을 메우러) (§3-D22-1). */
  callUp?: "earned" | "emergency" | null;
  /** 그 주가 연말 드래프트였는지 (§3-D54). */
  draftNight?: boolean;
  /** 그 주에 오르내린 스탯. 승리가 무엇을 남겼는지 (§3-D79). */
  statDelta?: Record<string, number>;
  /** 그 주에 쌓인 마모. */
  wearDelta?: number;
  /** 프로모가 먹혔는지 (§3-D41). `null`이면 프로모 주차가 아니다. */
  promoHit?: boolean | null;
};

/** 경기 진행 한 마디 (§3-D34). */
export type CareerBeat = {
  kind:
    | "enter"
    | "eliminate"
    | "win"
    /** §3-D81 모멘텀 타임라인 — 1:1 경기의 흐름. */
    | "move"
    | "reversal"
    /** §3-D91 — 그 사람의 기술. 많이 가진 선수일수록 자주 나온다. */
    | "signature"
    | "nearfall"
    | "kickout"
    | "finisher";
  name: string;
  /** 입장 순번. `enter`에만 채워진다. */
  number: number;
  /** 누가 탈락시켰는가(`eliminate`) · 무슨 기술로 끝냈는가(`finisher`). */
  by: string | null;
  /**
   * 그 순간 플레이어 쪽으로 기운 정도(0~100) — §3-D81.
   *
   * **레슬링은 위치가 정보가 아니다.** 두 사람이 링 한가운데 있으므로 좌표를 그려도
   * 읽을 것이 없고, 그 자리를 이 한 값이 대신한다.
   */
  momentum?: number;
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
  /** 돈과 계약 (§3-D73). 옛 응답에는 없어 옵셔널이다. */
  money?: CareerMoney | null;
  /** 그랜드슬램 진행도 (§3-D73). */
  grandSlam?: CareerGrandSlam | null;
  /** 다쳤던 곳들의 이름 (§3-D43). **몸은 기억한다.** */
  injuredParts?: string[];
  /** 왕관 등 벨트가 아닌 훈장 (§3-D33). */
  trophies?: CareerTrophy[];
  /** 지금 붙어 있는 상태 표식의 이름. 규칙이 읽는 신호는 오지 않는다. */
  flags?: string[];
  /**
   * **지금 이 세계선의 열여덟 벨트와 그 주인.**
   *
   * 리포트의 `champions`는 그 밤의 카드에 설 사람들이고 이쪽은 세계 전체다 —
   * 내가 못 보는 브랜드의 벨트도 주인이 바뀐다는 것이 §3-D38의 전부다.
   */
  champions?: CareerChampionGroup[];
  /** 이번 분기에 건 것 (§3-D80). 안 걸었으면 `null`. */
  goal?: string | null;
  /**
   * 지금 고를 수 있는 목표들. **비어 있으면 고를 때가 아니다** — NXT·무소속
   * 구간이거나 이미 이번 분기를 걸었다.
   */
  goalOptions?: CareerGoalOption[];
  /**
   * 재계약 협상의 선택지들 (§3-D84). **비어 있으면 협상 중이 아니다.**
   *
   * 제시 주급은 따로 오지 않는다 — `money.marketValue`가 곧 그 값이다.
   */
  offerOptions?: CareerOfferOption[];
  /**
   * 손에 든 머니 인 더 뱅크 가방 (§3-D85). **없으면 `null`이다.**
   *
   * 목표·협상과 달리 **진행을 막지 않는다** — 안 쓰고 '다음'을 눌러도 된다.
   * 화면은 이 값만 보고 "이번 주에 할 수 있는 것"에 자리를 낸다.
   */
  briefcase?: CareerBriefcase | null;
  /** 지금 시비를 걸 수 있는 자리 (§3-D86). 자리가 없거나 상대가 없으면 `null`. */
  callOut?: CareerCallOut | null;
  /** 지금 쓰는 피니셔 (§3-D88). **늘 온다** — 안 골랐으면 수플렉스다. */
  finisher?: CareerFinisher | null;
  /** 시그니처 칸과 값 (§3-D92). **늘 온다** — 기본 한 칸이다. */
  signature?: CareerSignature | null;
  /**
   * **다음 주에 무엇이 서는가** (§3-D81-3).
   *
   * `weekly_show` · `ple` · `special`이면 경기 밤이고, 그때 '다음' 버튼이
   * '경기 시작'으로 바뀐다 — FM이 경기 앞에서 멈추는 자리다.
   */
  nextKind?: string;
  /** 다음 주가 대회면 그 이름. */
  nextShow?: string | null;
  /** 로그 화면 하단에 상시 노출한다 (§3-D13). */
  disclaimer: string;
};

export type CareerContract = {
  weeklyPay: number;
  /** 연봉. **도메인이 곱한 값이다** — 화면이 52를 곱하면 두 곳이 갈린다. */
  annualPay: number;
  signedWeek: number;
  endsWeek: number;
  years: number;
  /** 만료까지 남은 주차. 0이면 이번이 협상 주차다. */
  weeksLeft: number;
};

export type CareerMoney = {
  balance: number;
  /** 무소속이면 `null`이다 (§3-D50) — 주급 0짜리 계약을 만들지 않는다. */
  contract: CareerContract | null;
  /** 지금 몸값. 맺고 있는 주급과 견주라고 함께 온다 — 둘이 갈리는 것이 재계약의 긴장이다. */
  marketValue: number;
  unsignedWeeks: number;
  /** 몇 주 뒤 잊히는가. 소속이 있으면 `null` — 무소속 구간의 유일한 시계다. */
  fadeInWeeks: number | null;
};

export type CareerTrophy = { code: string; week: number };

export type CareerChampionGroup = {
  /** `raw` · `smackdown` · `nxt` · `unified`. 브랜드 로고를 집는 데 쓴다. */
  brand: string;
  label: string;
  champions: CareerChampion[];
};

export type CareerChampion = {
  title: string;
  holder: string;
  /** 내가 감고 있는 벨트인지 — 화면이 내 줄을 짚는다. */
  mine: boolean;
};

export type CareerGoalOption = {
  code: string;
  label: string;
  blurb: string;
  /** 그 분기를 시작할 때 나가는 돈. 0이면 공짜다. */
  cost: number;
};

/**
 * 재계약 협상의 선택지 하나 (§3-D84).
 *
 * **거절 확률은 오지 않는다.** "등을 돌릴 수 있다"는 `blurb`가 말하고, 그 이상은
 * 수치라 화면에 뜨면 "더 부른다"가 도박이 아니라 계산이 된다 (§11-14).
 */
export type CareerOfferOption = {
  code: string;
  label: string;
  blurb: string;
  /** 그 선택지로 도장을 찍었을 때의 주급. 나간다면 0이다. */
  weeklyPay: number;
  /** 계약 연수. 0이면 계약을 맺지 않는다. */
  years: number;
};

/**
 * 손에 든 가방 (§3-D85).
 *
 * **챔피언의 인기도는 오지 않는다.** 그 값이 곧 승률의 힌트가 되고, 그러면
 * "지금 쓸까"는 판단이 아니라 계산이 된다 (§11-14). 오는 것은 이름과 시계뿐이고,
 * 긴장은 그 시계에서 나온다 — 미루면 규칙이 대신 쓴다.
 */
export type CareerBriefcase = {
  /** 겨누는 벨트의 이름 — 소속 브랜드의 월드 벨트. */
  title: string;
  /** 지금 그 벨트를 든 사람. */
  champion: string;
  /** 자동 현금화까지 남은 주차. 0이면 이번 주에 규칙이 쓴다. */
  weeksLeft: number;
  /** 이미 "쓴다"고 정했는가. 정한 뒤에는 무를 수 없다. */
  pending: boolean;
  /** 지금 뛰어들 수 있는가. 무소속이거나 이미 그 벨트를 감고 있으면 거짓. */
  canCashIn: boolean;
};

/** 고를 수 있는 피니셔 하나 (§3-D88). **수치가 없다** — 판정에 안 닿는다. */
export type CareerFinisherOption = { code: string; label: string; blurb: string };

/**
 * 지금 것을 그대로 쓰고 **다시 묻는 날만 미룬다** (2026-08-14 사용자 요청).
 *
 * 바꾸는 것만이 선택이 아니다 — 분기마다 자리가 열리므로 "이대로 간다"도 한 번의
 * 결정이다.
 */
export type FinisherHold = "quarter" | "year" | "forever";

/**
 * 지금 쓰는 피니셔와 바꿀 수 있는 자리 (§3-D88).
 *
 * **모두 수플렉스에서 시작한다.** 첫 분기가 지나야 바꿀 수 있고, 바꾼 뒤에도 한
 * 분기를 기다린다 — `weeksUntilChange`가 그 시계다.
 */
export type CareerFinisher = {
  code: string;
  name: string;
  blurb: string;
  /** 직접 지은 이름인지. */
  custom: boolean;
  canChange: boolean;
  /** **평생 쓰기로 못 박았는가** — 참이면 바꾸기 자리를 아예 안 낸다. */
  settled?: boolean;
  weeksUntilChange: number;
  options: CareerFinisherOption[];
  nameMin: number;
  nameMax: number;
};

/** 시그니처 칸 하나 (§3-D92). 이름이 비어 있으면 아직 *내* 기술이 아니다. */
export type CareerSignatureSlot = { index: number; name: string };

/**
 * 산 칸과 이름들, 그리고 값 (§3-D92).
 *
 * **한 칸으로 시작해 돈으로 늘린다.** 칸이 늘수록 경기에서 시그니처가 나올 확률이
 * 오르고(§3-D91), 그래서 칸값은 살 때마다 비싸진다.
 *
 * `canBuy` 같은 판단은 안 온다 — 값과 잔액이 함께 오므로 화면이 스스로 셈한다.
 */
export type CareerSignature = {
  slots: CareerSignatureSlot[];
  maxSlots: number;
  /** 다음 칸의 값. **`null`이면 다 열었다.** */
  expandCost: number | null;
  namingCost: number;
  /** 피니셔 이름을 직접 짓는 값 (§3-D88의 그 자리가 이제 유료다). */
  finisherNamingCost: number;
  money: number;
  nameMin: number;
  nameMax: number;
};

export type CareerGrandSlamGroup = { name: string; count: number };

export type CareerGrandSlam = {
  /** 0 미달 · 1 그랜드슬램 · 2 더블. **가장 적게 채운 그룹**이 정한다. */
  level: number;
  groups: CareerGrandSlamGroup[];
};

export type CareerRivalry = {
  rival: string;
  stage: string;
  heat: number;
  startedWeek: number;
  /**
   * `player`(내가 걸었다) · `rival`(상대가 걸어왔다) — §3-D86.
   *
   * **열기가 같아도 이야기가 다르다.** 옛 세이브에는 없어 기본은 `rival`이다.
   */
  openedBy?: "player" | "rival";
};

/**
 * 지금 시비를 걸 수 있는 자리 (§3-D86). **못 걸면 `null`이다.**
 *
 * 후보는 규칙이 상대를 뽑을 때 쓰는 것과 같은 풀에서 온다 — 급과 브랜드가 맞는
 * 사람만 선다. 세이브를 다시 열어도 같은 목록이다.
 */
export type CareerCallOut = {
  candidates: string[];
  /** 남은 대립 자리. 0이면 못 건다. */
  slotsLeft: number;
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
  stopReason:
    | "ready"
    | "event"
    | "ple"
    | "ended"
    | "recovered"
    | "tick"
    | "max_weeks"
    /** 새 분기가 열렸다 — 무엇에 걸지 정해야 간다 (§3-D80). */
    | "goal"
    /** 계약이 만료됐다 — 재계약에 답해야 간다 (§3-D84). **목표보다 앞선다.** */
    | "offer";
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

/**
 * 기사에 달린 댓글 한 줄 (§3-D87).
 *
 * **표는 반응이지 판정이 아니다** — 이 숫자로는 아무것도 계산되지 않는다.
 */
export type CareerNewsComment = {
  author: string;
  text: string;
  /** 추천 */
  up: number;
  /** 비추천 */
  down: number;
};

export type CareerNewsItem = {
  week: number;
  year: number;
  month: number;
  weekOfMonth: number;
  kind: string;
  headline: string;
  mood: "roar" | "jeer" | "split" | "hush" | "chant";
  crowdLine: string;
  /** 기사를 낸 가상 매체 (§3-D87). 옛 응답에는 없다. */
  outlet?: string;
  /** 신문 제목 — `headline`에 매체 말투만 입힌 것이라 새 사실은 없다. */
  title?: string;
  /** 기사 본문. **이미 일어난 일만 다시 말한다** — 언제·무엇·그 자리의 소리. */
  body?: string;
  /** 대중의 반응 다섯. 한 명은 늘 반대편에 선다. */
  comments?: CareerNewsComment[];
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

/**
 * 이번 분기에 걸 것을 정한다 (§3-D80).
 *
 * **`chooseEvent`와 따로 둔다.** 이벤트 응답은 벌어진 일에 답하는 것이고 이쪽은
 * 먼저 거는 것이라, 한 함수로 합치면 그 구분이 사라진다.
 */
export function setGoal(runId: number, goal: string): Promise<CareerAdvance> {
  return post<CareerAdvance>(`/runs/${runId}/goal`, { goal });
}

/** 체험판의 분기 목표 (§3-D80). 없으면 콜업 뒤 체험판이 통째로 막힌다. */
export function setGuestGoal(state: GuestRunState, goal: string): Promise<GuestAdvance> {
  return post<GuestAdvance>("/guest/goal", { state, goal });
}

/**
 * 재계약 협상에 답한다 (§3-D84).
 *
 * `setGoal`과 나란한 자리다 — 둘 다 **먼저 정하는 것**이고, 답하기 전에는 진행이
 * 막힌다. 협상 중이 아닌데 부르면 409다.
 */
export function answerOffer(runId: number, offer: string): Promise<CareerAdvance> {
  return post<CareerAdvance>(`/runs/${runId}/offer`, { offer });
}

/** 체험판의 재계약 협상 (§3-D84). 없으면 만료 주차에서 체험판이 통째로 막힌다. */
export function answerGuestOffer(state: GuestRunState, offer: string): Promise<GuestAdvance> {
  return post<GuestAdvance>("/guest/offer", { state, offer });
}

/**
 * 가방을 쓰기로 한다 (§3-D85).
 *
 * **고를 것이 없어 본문이 없다** — "지금 한다"는 사실 하나뿐이다. 목표·협상과 달리
 * 막힌 것을 푸는 답이 아니라 **안 해도 그만인 행동**이라, 안 부르고 '다음'을 눌러도
 * 아무 일도 일어나지 않는다.
 */
export function cashInBriefcase(runId: number): Promise<CareerAdvance> {
  return post<CareerAdvance>(`/runs/${runId}/cash-in`, {});
}

/**
 * 그 사람에게 시비를 건다 (§3-D86).
 *
 * **후보 목록 밖의 이름은 409다** — 급·브랜드 그림이 요청 한 줄로 무너지지 않게
 * 도메인이 막는다.
 */
export function callOutRival(runId: number, rival: string): Promise<CareerAdvance> {
  return post<CareerAdvance>(`/runs/${runId}/call-out`, { rival });
}

/** 체험판의 시비 걸기 (§3-D86). */
export function callOutGuestRival(state: GuestRunState, rival: string): Promise<GuestAdvance> {
  return post<GuestAdvance>("/guest/call-out", { state, rival });
}

/**
 * 피니셔를 바꾼다 (§3-D88).
 *
 * **두 갈래를 한 함수로 받는다** — 목록에서 고르면 `code`, 이름을 직접 지으면
 * `name`. 어느 쪽인지는 화면이 먼저 묻고 정한다.
 */
export function changeFinisher(
  runId: number,
  pick: { code?: string; name?: string; hold?: FinisherHold },
): Promise<CareerAdvance> {
  return post<CareerAdvance>(`/runs/${runId}/finisher`, {
    code: pick.code ?? "",
    name: pick.name ?? "",
    hold: pick.hold ?? "",
  });
}

/** 체험판의 피니셔 교체 (§3-D88). */
export function changeGuestFinisher(
  state: GuestRunState,
  pick: { code?: string; name?: string; hold?: FinisherHold },
): Promise<GuestAdvance> {
  return post<GuestAdvance>("/guest/finisher", {
    state,
    code: pick.code ?? "",
    name: pick.name ?? "",
    hold: pick.hold ?? "",
  });
}

/**
 * 시그니처 칸을 사거나 이름을 새긴다 (§3-D92).
 *
 * **셋을 한 함수로 받는다** — 칸 사기(`buy`) · 이름 새기기(`name`) · 지우기(`drop`).
 */
export function buySignature(
  runId: number,
  what: { slot?: number; name?: string; buy?: boolean; drop?: boolean },
): Promise<CareerAdvance> {
  return post<CareerAdvance>(`/runs/${runId}/signature`, {
    slot: what.slot ?? 0,
    name: what.name ?? "",
    buy: what.buy ?? false,
    drop: what.drop ?? false,
  });
}

/** 체험판의 시그니처 구매 (§3-D92). */
export function buyGuestSignature(
  state: GuestRunState,
  what: { slot?: number; name?: string; buy?: boolean; drop?: boolean },
): Promise<GuestAdvance> {
  return post<GuestAdvance>("/guest/signature", {
    state,
    slot: what.slot ?? 0,
    name: what.name ?? "",
    buy: what.buy ?? false,
    drop: what.drop ?? false,
  });
}

/** 체험판의 가방 현금화 (§3-D85). */
export function cashInGuestBriefcase(state: GuestRunState): Promise<GuestAdvance> {
  return post<GuestAdvance>("/guest/cash-in", { state });
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
