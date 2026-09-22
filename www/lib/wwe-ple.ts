/** 2026 WWE PLE. month가 null이면 일정 추후 공개(TBD). */
export const WWE_PLE_YEAR = 2026 as const;

export type PleEvent = {
  month: number | null;
  year: typeof WWE_PLE_YEAR;
  slug: string;
  label: string;
  dateLabel: string | null;
  venue: string | null;
  highlight: string;
  /**
   * 목록·내비게이션에서 **감춘다**. 기본은 노출(`undefined`)이다.
   *
   * 올해 열리지 않는 대회를 지우는 대신 감추는 자리다. 지워 버리면 경기 카드·테마·
   * 상세와 그 대회에 달린 예측이 함께 사라지고, 나중에 열릴 때 전부 다시 만들어야
   * 한다. 데이터는 그대로 두고 화면에서만 빼면 **한 줄로 되돌릴 수 있다.**
   *
   * `undefined`(노출)와 `true`(감춤) 둘뿐이다 — `false`를 쓰지 않는 이유는 열한
   * 대회에 같은 줄을 붙이지 않기 위해서다.
   */
  unlisted?: true;
};

export const WWE_PLE_MONTHLY_ORDER: readonly PleEvent[] = [
  {
    month: 1,
    year: WWE_PLE_YEAR,
    slug: "royal-rumble",
    label: "Royal Rumble",
    dateLabel: "1.31",
    venue: "사우디 리야드",
    highlight: "WrestleMania 42 출전권 걸림",
  },
  {
    month: 2,
    year: WWE_PLE_YEAR,
    slug: "elimination-chamber",
    label: "Elimination Chamber",
    dateLabel: "2.28",
    venue: "시카고",
    highlight: "챔버 우승자의 Mania 각",
  },
  {
    month: 4,
    year: WWE_PLE_YEAR,
    slug: "stand-and-deliver",
    label: "Stand & Deliver",
    dateLabel: "4.4",
    venue: null,
    highlight: "NXT 플래그십 PLE",
  },
  {
    month: 4,
    year: WWE_PLE_YEAR,
    slug: "wrestlemania",
    label: "WrestleMania 42",
    dateLabel: "4.18–19",
    venue: "라스베이거스",
    highlight: "시즌 최대 이벤트",
  },
  {
    month: 5,
    year: WWE_PLE_YEAR,
    slug: "backlash",
    label: "Backlash",
    dateLabel: "5.9",
    venue: "탬파",
    highlight: "WrestleMania 42 여파",
  },
  {
    month: 5,
    year: WWE_PLE_YEAR,
    slug: "clash-in-italy",
    label: "Clash in Italy",
    dateLabel: "5.31",
    venue: "토리노",
    highlight: "국제 PLE",
  },
  {
    month: 6,
    year: WWE_PLE_YEAR,
    slug: "night-of-champions",
    label: "Night of Champions",
    dateLabel: "6.27",
    venue: "리야드",
    highlight: "챔피언십 중심 PLE",
  },
  {
    month: 8,
    year: WWE_PLE_YEAR,
    slug: "summerslam",
    label: "SummerSlam",
    dateLabel: "8.1–2",
    venue: "미니애폴리스",
    highlight: "2 Nights",
  },
  {
    // WWE가 2026-06-08에 9.6 → 10.10으로 옮겼다. 사상 첫 10월 MITB이고,
    // 그래서 이 목록에서 유일하게 SummerSlam **뒤에** 온다.
    // 낡은 9.6을 두면 `parsePleStartDate`가 9월 7일부터 이 카드를 "종료"로 굳혀
    // 실제로는 한 달 넘게 남은 대회의 예측이 닫힌다.
    month: 10,
    year: WWE_PLE_YEAR,
    slug: "money-in-the-bank",
    label: "Money in the Bank",
    dateLabel: "10.10",
    venue: "뉴올리언스",
    highlight: "MITB 래더",
  },
  {
    month: 11,
    year: WWE_PLE_YEAR,
    slug: "crown-jewel",
    label: "Crown Jewel",
    dateLabel: "11.7",
    venue: "사우디 리야드",
    highlight: "리야드 시즌 스타디움",
  },
  {
    // 11.28 — 위키 인포박스로 확인했다(`Survivor Series: WarGames (2026)`
    // rev 1376063302). 예전에는 일정 미정이라 `month: null`이었다.
    month: 11,
    year: WWE_PLE_YEAR,
    slug: "survivor-series",
    label: "Survivor Series",
    dateLabel: "11.28",
    venue: "휴스턴",
    highlight: "팀 대항 시즌 피날레",
  },
  {
    month: 12,
    year: WWE_PLE_YEAR,
    slug: "wrestlepalooza",
    label: "Wrestlepalooza",
    dateLabel: "12.12",
    venue: "호주 퍼스",
    highlight: "첫 북미 밖 개최",
  },
  {
    month: null,
    year: WWE_PLE_YEAR,
    slug: "king-queen-of-the-ring",
    label: "King & Queen of the Ring",
    dateLabel: null,
    venue: null,
    highlight: "토너먼트 PLE",
    // 2026년에는 독립 PLE가 아니었다 — 6/1~6/27 토너먼트였고 결승은 Night of
    // Champions(6/27)에서 열렸다. **흡수는 이미 되어 있다**: 그 두 경기가
    // `night-of-champions` 카드의 `noc26-kotr`·`noc26-qotr`다.
    unlisted: true,
  },
  {
    month: null,
    year: WWE_PLE_YEAR,
    slug: "bad-blood",
    label: "Bad Blood",
    dateLabel: null,
    venue: null,
    highlight: "Hell in a Cell 중심",
    // 2026년에는 열리지 않는다(2026-09-22 확인). 데이터는 남기고 화면에서만 뺀다 —
    // 추후 열리면 이 한 줄을 지우면 된다.
    unlisted: true,
  },
] as const;

export type PleSlug = (typeof WWE_PLE_MONTHLY_ORDER)[number]["slug"];

/**
 * 화면에 내놓는 대회만. **목록·내비게이션은 전부 이것을 쓴다.**
 *
 * `WWE_PLE_MONTHLY_ORDER`는 데이터이고 이쪽이 표시용이다. 둘을 가르지 않으면
 * 감춘 대회가 어느 목록 하나에 남아 그 화면만 어긋난다.
 */
export const WWE_PLE_LISTED: readonly PleEvent[] = WWE_PLE_MONTHLY_ORDER.filter(
  (event) => !event.unlisted,
);

/**
 * 서버가 준 대회 행을 걸러낼 때 쓴다 — DB에는 감춘 대회도 그대로 있다.
 *
 * **카탈로그에 없는 slug는 노출로 본다.** 서버가 우리가 모르는 대회를 새로 알려
 * 왔다면 그것을 감추는 것이 아니라 보여 주는 쪽이 맞다.
 */
export function isPleListed(slug: string): boolean {
  return getPleBySlug(slug)?.unlisted !== true;
}

export function isPleTbd(ple: PleEvent): boolean {
  return ple.month === null;
}

export function formatPleMonth(month: number | null): string {
  return month === null ? "TBD" : `${month}월`;
}

export function formatPleSchedule(ple: PleEvent): string {
  if (isPleTbd(ple)) {
    return "일정 추후 공개";
  }
  const datePart = ple.dateLabel ? `📅 ${ple.dateLabel}` : null;
  if (datePart && ple.venue) {
    return `${datePart} | ${ple.venue}`;
  }
  return datePart ?? ple.venue ?? "";
}

export function getPleBySlug(slug: string) {
  return WWE_PLE_MONTHLY_ORDER.find((e) => e.slug === slug);
}

/** PLE 카드 시그니처 테마 (slug → CSS modifier) */
export const PLE_THEME_CLASS: Record<string, string> = {
  "royal-rumble": "ple-card--royal-rumble",
  "elimination-chamber": "ple-card--elimination-chamber",
  wrestlemania: "ple-card--wrestlemania",
  "stand-and-deliver": "ple-card--nxt",
  backlash: "ple-card--backlash",
  "clash-in-italy": "ple-card--international",
  "night-of-champions": "ple-card--champions",
  summerslam: "ple-card--summerslam",
  "money-in-the-bank": "ple-card--mitb",
};

export type PleStatusVariant = "deadline" | "done" | "ended" | "open" | "tbd";

export type PleStatusBadge = {
  label: string;
  variant: PleStatusVariant;
};

function parsePleStartDate(ple: PleEvent): Date | null {
  if (!ple.dateLabel) return null;
  const first = ple.dateLabel.split("–")[0]?.trim() ?? "";
  const [monthStr, dayStr] = first.split(".");
  const month = Number(monthStr);
  const day = Number(dayStr);
  if (!month || !day) return null;
  return new Date(ple.year, month - 1, day, 23, 59, 59);
}

function daysUntil(date: Date): number {
  const now = new Date();
  const start = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const end = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  return Math.ceil((end.getTime() - start.getTime()) / (1000 * 60 * 60 * 24));
}

/** 카드 뱃지용 예측 상태 (날짜 기반; 참여 완료는 클라이언트에서 덮어씀) */
export function getPleStatusBadge(ple: PleEvent): PleStatusBadge {
  if (isPleTbd(ple)) {
    return { label: "일정 대기", variant: "tbd" };
  }

  const eventDate = parsePleStartDate(ple);
  if (!eventDate) {
    return { label: "예측 가능", variant: "open" };
  }

  const days = daysUntil(eventDate);
  if (days < 0) {
    return { label: "종료", variant: "ended" };
  }
  if (days <= 3) {
    return { label: `D-${days} 마감임박`, variant: "deadline" };
  }
  return { label: "예측 가능", variant: "open" };
}

/** 이벤트까지 남은 일수 (오늘 0, 지났으면 음수, 날짜 미정이면 null) */
export function getPleCountdownDays(ple: PleEvent): number | null {
  const eventDate = parsePleStartDate(ple);
  if (!eventDate) return null;
  return daysUntil(eventDate);
}

export function getPleThemeClass(slug: string): string | undefined {
  return PLE_THEME_CLASS[slug];
}

/** 그리드 상단에 크게 강조할 이벤트 — 마감임박 우선, 없으면 가장 가까운 예측 가능 이벤트 */
export function pickFeaturedPle(events: readonly PleEvent[] = WWE_PLE_LISTED): PleEvent | null {
  const upcoming = events
    .map((event) => ({ event, badge: getPleStatusBadge(event) }))
    .filter(({ badge }) => badge.variant === "deadline" || badge.variant === "open");

  if (upcoming.length === 0) return null;

  const deadline = upcoming.find(({ badge }) => badge.variant === "deadline");
  return (deadline ?? upcoming[0]).event;
}
