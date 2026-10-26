import type { CareerLogEntry, CareerRelationship, CareerWrestler } from "@/lib/career-api";

/**
 * 기록에서 화면이 읽을 것을 **골라내는** 함수들. 새로 만들어 내지 않는다.
 *
 * ## 왜 파생이 필요한가
 *
 * 서버에 경기 전용 조회 API가 없다. 경기는 커리어 로그의 `kind === "match"` 줄로
 * 들어오고(`career_engine.py`), 타이틀 이동도 같은 로그의 `title_won` ·
 * `title_defended` · `title_vacated` 줄이다. 그래서 「경기 및 대진」과 「타이틀」
 * 탭은 로그를 **골라 보는** 화면이다 — 별도 엔드포인트를 추측해서 부르지 않는다.
 *
 * ## 이 파일이 하지 않는 일
 *
 * 승패·재위 주차·방어 횟수를 다시 계산하지 않는다. 그 값은 서버가 `player.wins` ·
 * `title.reignWeeks` · `title.defenses` 로 이미 보내고, 로그를 세어 만든 두 번째
 * 숫자가 그것과 어긋나면 화면이 둘 중 어느 쪽도 설명할 수 없게 된다.
 */

/** 기록 한 줄에 붙는 키. **서버가 id를 주지 않는다** — 중복 표시 방지는 이 키가 한다. */
export function logKey(entry: CareerLogEntry, index: number): string {
  return `${entry.season}:${entry.week}:${entry.kind}:${index}`;
}

export type MatchRow = {
  key: string;
  season: number;
  week: number;
  /** 로그의 `subject` — 경기 로그는 플레이어 이름이 들어온다. */
  subject: string;
  opponent: string | null;
  /** `result` 가 `"win"`·`"loss"` 가 아니면 `null`. 추측하지 않는다. */
  won: boolean | null;
  /** 타이틀전이면 벨트 이름. 서버가 이 칸으로 타이틀전 여부를 말한다. */
  title: string | null;
  /** 경기 유형과 승리 방식이 들어 있는 서버 문장. **파싱하지 않고 그대로 쓴다.** */
  summary: string;
  /** 현재 관계 데이터에 라이벌로 잡히는 상대인가. 아래 주의 참조. */
  rival: boolean;
};

/**
 * 플레이어와 **끓는 라이벌 관계인 상대 이름들.**
 *
 * `relation.feud` 를 쓴다 — **`kind === "rival"` 로 세지 않는다.** 서버가 경기마다
 * 진 쪽을 라이벌 kind 로 올리기 때문에(`career_relations.after_match`) 그 칸으로
 * 세면 상대 거의 전원이 라이벌이 되고 필터가 뜻을 잃는다(실측: 경기 30건 중 30건이
 * 라이벌전으로 잡혔다). 끓는 선을 가르는 임계값은 서버에만 있고, 화면은 서버가
 * 내린 판정만 읽는다 — 60을 여기 적으면 설정을 바꿨을 때 화면만 거짓말을 한다.
 *
 * **주의 — 이것은 "지금" 의 관계다.** 서버는 관계의 현재 상태만 보내고 경기 당시의
 * 관계는 저장하지 않는다. 그래서 과거 경기에 붙는 라이벌 표시는 "그 상대는 지금
 * 라이벌이다" 라는 뜻이고, 화면도 그렇게 적는다.
 */
export function rivalNames(
  relationships: readonly CareerRelationship[],
  player: string,
): ReadonlySet<string> {
  const names = new Set<string>();
  for (const relation of relationships) {
    if (!relation.feud) continue;
    if (relation.a === player) names.add(relation.b);
    else if (relation.b === player) names.add(relation.a);
  }
  return names;
}

export function toMatchRows(
  log: readonly CareerLogEntry[],
  rivals: ReadonlySet<string>,
): MatchRow[] {
  const rows: MatchRow[] = [];
  log.forEach((entry, index) => {
    if (entry.kind !== "match") return;
    rows.push({
      key: logKey(entry, index),
      season: entry.season,
      week: entry.week,
      subject: entry.subject,
      opponent: entry.other,
      won: entry.result === "win" ? true : entry.result === "loss" ? false : null,
      title: entry.title,
      summary: entry.summary,
      rival: entry.other != null && rivals.has(entry.other),
    });
  });
  return rows;
}

export type MatchFilter = "all" | "normal" | "title" | "rival";

export function matchesFilter(row: MatchRow, filter: MatchFilter): boolean {
  if (filter === "all") return true;
  if (filter === "title") return row.title != null;
  if (filter === "rival") return row.rival;
  return row.title == null && !row.rival;
}

/** 타이틀 기록에 들어가는 로그 종류 셋. 서버가 쓰는 이름 그대로다. */
export const TITLE_LOG_KINDS = ["title_won", "title_defended", "title_vacated"] as const;

export type TitleLogRow = {
  key: string;
  season: number;
  week: number;
  kind: string;
  subject: string;
  title: string;
  summary: string;
};

/** 타이틀 관련 기록만. `title` 칸이 빈 줄은 어느 벨트인지 모르므로 버린다. */
export function toTitleRows(log: readonly CareerLogEntry[]): TitleLogRow[] {
  const rows: TitleLogRow[] = [];
  log.forEach((entry, index) => {
    if (!TITLE_LOG_KINDS.includes(entry.kind as (typeof TITLE_LOG_KINDS)[number])) return;
    if (!entry.title) return;
    rows.push({
      key: logKey(entry, index),
      season: entry.season,
      week: entry.week,
      kind: entry.kind,
      subject: entry.subject,
      title: entry.title,
      summary: entry.summary,
    });
  });
  return rows;
}

/** 대시보드가 「주요 커리어 이벤트」로 뽑는 종류. 행동·휴식 같은 잔줄은 뺀다. */
export const MILESTONE_KINDS = [
  "debut",
  "title_won",
  "title_defended",
  "title_vacated",
  "injury",
  "promoted",
  "retired",
  "season_end",
] as const;

export function isMilestone(entry: CareerLogEntry): boolean {
  return MILESTONE_KINDS.includes(entry.kind as (typeof MILESTONE_KINDS)[number]);
}

/** 로스터에 실제로 있는 브랜드들. 브랜드 목록을 화면에 박아 두지 않는다. */
export function brandsOf(roster: readonly CareerWrestler[]): string[] {
  return [...new Set(roster.map((w) => w.brand))].sort((a, b) => a.localeCompare(b, "ko-KR"));
}

export function isRetired(wrestler: CareerWrestler): boolean {
  // `retirement` 칸이 정본이다 — `status` 는 "은퇴 고민 중"(미확정)과 섞이기 쉽다.
  return wrestler.retirement != null || wrestler.status === "retired";
}

/**
 * 은퇴 선수의 커리어 업적. **로그에서 센 횟수이고 서버 집계가 아니다.**
 *
 * 서버는 선수별 방어 횟수를 따로 보내지 않는다(`title.defenses` 는 그 벨트의 현재
 * 재위 기준이다). 그래서 이 수는 "읽어 온 기록에서 센 것" 이고, 화면도 분모 대신
 * 그 사실을 함께 적는다.
 */
export type CareerHonours = {
  titleWins: TitleLogRow[];
  defenses: TitleLogRow[];
  vacated: TitleLogRow[];
};

export function honoursOf(log: readonly CareerLogEntry[], name: string): CareerHonours {
  const rows = toTitleRows(log).filter((row) => row.subject === name);
  return {
    titleWins: rows.filter((row) => row.kind === "title_won"),
    defenses: rows.filter((row) => row.kind === "title_defended"),
    vacated: rows.filter((row) => row.kind === "title_vacated"),
  };
}

/** 한 선수의 관계 전부. 플레이어든 NPC든 같은 규칙으로 고른다. */
export function relationsOf(
  relationships: readonly CareerRelationship[],
  name: string,
): { other: string; relation: CareerRelationship }[] {
  const rows: { other: string; relation: CareerRelationship }[] = [];
  for (const relation of relationships) {
    if (relation.a === name) rows.push({ other: relation.b, relation });
    else if (relation.b === name) rows.push({ other: relation.a, relation });
  }
  return rows;
}
