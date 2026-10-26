import { CAREER_TRAINABLE, type CareerAbility, type CareerTrainable } from "@/lib/career-api";

/**
 * 서버 코드 → 화면 문구. **이 파일이 번역표의 유일한 자리다.**
 *
 * 값은 전부 백엔드 `StrEnum`·로그 `kind` 에서 실측해 온 것이다(`career_world.py` ·
 * `career_actions.py` · `career_engine.py`). 없는 코드를 추측해서 적어 두면 화면이
 * 서버가 보내지 않는 상태를 설명하게 된다 — 그래서 **모르는 코드는 원문을 그대로
 * 보여 준다**(`labelOf`). 빈칸이나 "기타" 로 뭉개면 새 코드가 들어왔을 때 아무도
 * 모른다.
 */
export const PHASE_LABEL: Readonly<Record<string, string>> = {
  in_season: "시즌 진행 중",
  settlement: "결산 대기",
  offseason: "다음 시즌 대기",
  ended: "종료",
};

export const STAT_LABEL: Readonly<Record<CareerTrainable, string>> = {
  in_ring: "기술",
  mic: "마이크",
  stamina: "체력",
  resilience: "회복력",
};

/**
 * 훈련 코드 → 능력치 칸. **두 이름이 다른 것은 의도다.**
 *
 * 요청에 담는 코드는 서버의 `TRAINABLE`(snake_case)이고, 응답의 능력치는 다른
 * 응답들과 같이 camelCase다. 한쪽을 다른 쪽에 맞추면 그 레이어의 관례가 깨지므로
 * 변환을 여기 한 줄로 둔다.
 */
export const ABILITY_KEY: Readonly<Record<CareerTrainable, keyof CareerAbility>> = {
  in_ring: "inRing",
  mic: "mic",
  stamina: "stamina",
  resilience: "resilience",
};

export const RELATION_LABEL: Readonly<Record<string, string>> = {
  rival: "라이벌",
  ally: "동맹",
  tag_team: "태그팀",
  mentor: "스승",
  protege: "제자",
};

export const STATUS_LABEL: Readonly<Record<string, string>> = {
  active: "정상",
  injured: "부상",
  retirement_pending: "은퇴 고민 중",
  retired: "은퇴",
};

export const SEVERITY_LABEL: Readonly<Record<string, string>> = {
  minor: "경상",
  serious: "중상",
  career_threatening: "커리어 위협",
};

export const ALIGNMENT_LABEL: Readonly<Record<string, string>> = {
  face: "선역",
  heel: "악역",
};

/** 은퇴 원인. 서버 `RetirementCause` 아홉 가지 그대로다. */
export const CAUSE_LABEL: Readonly<Record<string, string>> = {
  age_decline: "노쇠",
  repeated_injury: "부상 누적",
  severe_injury: "중대 부상",
  medical: "의학적 소견",
  voluntary: "자진 은퇴",
  poor_form: "부진",
  goal_complete: "목표 달성",
  requested: "본인 요청",
  offer_accepted: "제안 수락",
};

/** 기록 줄의 종류. 서버가 `LogEntry.kind` 로 쓰는 열넷이다. */
export const LOG_KIND_LABEL: Readonly<Record<string, string>> = {
  action: "행동",
  debut: "데뷔",
  event: "사건",
  injury: "부상",
  match: "경기",
  out: "결장",
  promoted: "승격",
  rest: "휴식",
  retired: "은퇴",
  season_end: "시즌 종료",
  season_start: "시즌 시작",
  title_defended: "타이틀 방어",
  title_vacated: "타이틀 공석",
  title_won: "타이틀 획득",
};

/** 미해결 사건의 종류. 서버 `career_events` · `career_relations` 가 내는 열하나다. */
export const EVENT_KIND_LABEL: Readonly<Record<string, string>> = {
  ally_offer: "동맹 제안",
  betrayal: "배신",
  decline: "기량 저하",
  event: "사건",
  last_ride: "마지막 질주",
  medical: "의학적 경고",
  poor_form: "부진",
  rival_taunt: "라이벌 도발",
  severe_injury: "중대 부상",
  tag_team_offer: "태그팀 제안",
  title_offer: "타이틀 제안",
};

/** 다음 경기 카드의 종류. `career_engine.book()` 이 내는 넷이다. */
export const CARD_KIND_LABEL: Readonly<Record<string, string>> = {
  rest: "경기 없음",
  single: "싱글 경기",
  tag: "태그 경기",
  title: "타이틀전",
};

/**
 * 모르는 코드는 **원문을 돌려준다.**
 *
 * 서버가 새 `kind` 를 내보냈을 때 화면이 빈칸을 그리면 그 줄이 사라진 것처럼
 * 보인다. 영문 코드가 그대로 보이는 쪽이 정직하고, 번역표에 뭘 더해야 하는지도
 * 바로 드러난다.
 */
export function labelOf(table: Readonly<Record<string, string>>, code: string): string {
  return table[code] ?? code;
}

export function deltaText(delta: CareerAbility): string {
  const sign = (n: number) => (n > 0 ? `+${n}` : `${n}`);
  return CAREER_TRAINABLE.map((key) => `${STAT_LABEL[key]} ${sign(delta[ABILITY_KEY[key]])}`).join(
    " · ",
  );
}
