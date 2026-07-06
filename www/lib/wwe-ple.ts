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
    month: 9,
    year: WWE_PLE_YEAR,
    slug: "money-in-the-bank",
    label: "Money in the Bank",
    dateLabel: "9.6",
    venue: "뉴올리언스",
    highlight: "MITB 래더",
  },
  {
    month: null,
    year: WWE_PLE_YEAR,
    slug: "king-queen-of-the-ring",
    label: "King & Queen of the Ring",
    dateLabel: null,
    venue: null,
    highlight: "토너먼트 PLE",
  },
  {
    month: null,
    year: WWE_PLE_YEAR,
    slug: "bad-blood",
    label: "Bad Blood",
    dateLabel: null,
    venue: null,
    highlight: "Hell in a Cell 중심",
  },
  {
    month: null,
    year: WWE_PLE_YEAR,
    slug: "survivor-series",
    label: "Survivor Series",
    dateLabel: null,
    venue: null,
    highlight: "팀 대항 시즌 피날레",
  },
] as const;

export type PleSlug = (typeof WWE_PLE_MONTHLY_ORDER)[number]["slug"];

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

export function getPleThemeClass(slug: string): string | undefined {
  return PLE_THEME_CLASS[slug];
}
