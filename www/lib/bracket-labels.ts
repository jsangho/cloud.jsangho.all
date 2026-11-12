/** Match bracket UI copy (UTF-8) */
export const BRACKET_LABELS = {
  championTitle: "챔피언",
  siteVote: "사이트 투표",
  bookmaker: "북메이커 승률",
  myPick: "내 예측",
  bookNote: "북메이커: 십진 배당에서 마진을 걷어낸 승률 (참고용, 투표와 별도)",
  /** 관측일·출처가 없는 옛 배당 칸 — 백엔드가 예측 근거에서 뺀다(`pre_event_quotes`) */
  bookUnsourced: "출처·관측일이 없는 배당이라 AI 예측에는 쓰지 않습니다",
  percentSep: "·",
  noVotesYet: "아직 투표 없음",
  participants: "참가자",
  /** 로얄 럼블 우승 예측 6번째 칸 */
  rumbleOther: "다른 선수",
  /** 대진에 자리는 있는데 참가자가 아직 발표되지 않은 칸 (위키의 TBD) */
  tbd: "미정",
  /** 접힌 근거 블록 — AI 예측 아래에서 투표·배당을 연다 */
  evidenceShow: "근거 더 보기 (투표 · 배당)",
  evidenceHide: "근거 접기",
  win: "승",
  loss: "패",
  liveResults: "실시간 결과",
  trophy: "🏆",
} as const;
