import type { PleSlug } from "@/lib/wwe-ple";
import { BRACKET_LABELS } from "@/lib/bracket-labels";

/**
 * 실제 방송 카드 기준 (WWE 2026).
 * 로얄 럼블 우승: 북메이커 상위 5명 + 「다른 선수」 6칸.
 * 그 외 다인전은 참가자 전원 표시.
 *
 * 경기 제목: 챔피언십 → belt명만, 기믹 → 기믹명, 일반 1v1 → 「Single Match」, 태그 → 「Tag Team Match」 등.
 */
export type PleCompetitor = {
  name: string;
  isChampion?: boolean;
};

type PleMatchBase = {
  id: string;
  title: string;
  cardVariant: "sideA" | "sideB";
};

export type PleMatchCardSingles = PleMatchBase & {
  format: "singles";
  left: PleCompetitor;
  right: PleCompetitor;
  bookmakerDecimal: { left: number; right: number };
};

export type PleMatchCardMulti = PleMatchBase & {
  format: "multi";
  competitors: PleCompetitor[];
  bookmakerDecimal?: number[];
};

export type PleMatchCard = PleMatchCardSingles | PleMatchCardMulti;

/** API·로컬 공통 — 방송 결과 (finished 경기) */
export type PleMatchResultHint = {
  winnerSide?: "left" | "right";
  winnerIndex?: number;
  winnerName?: string;
};

export function isMultiMatch(match: PleMatchCard): match is PleMatchCardMulti {
  return match.format === "multi";
}

function m2(
  id: string,
  title: string,
  cardVariant: "sideA" | "sideB",
  left: PleCompetitor,
  right: PleCompetitor,
  odds: { left: number; right: number },
): PleMatchCardSingles {
  return {
    id,
    title,
    cardVariant,
    format: "singles",
    left,
    right,
    bookmakerDecimal: odds,
  };
}

function mm(
  id: string,
  title: string,
  cardVariant: "sideA" | "sideB",
  competitors: PleCompetitor[],
  odds?: number[],
): PleMatchCardMulti {
  return {
    id,
    title,
    cardVariant,
    format: "multi",
    competitors,
    bookmakerDecimal: odds,
  };
}

/** 로얄 럼블 우승 — 북메이커 상위 5 + 기타 1칸 */
function rumbleWinner(
  id: string,
  title: string,
  cardVariant: "sideA" | "sideB",
  topFive: [string, string, string, string, string],
  odds: [number, number, number, number, number, number],
): PleMatchCardMulti {
  return mm(
    id,
    title,
    cardVariant,
    [
      ...topFive.map((name) => ({ name })),
      { name: BRACKET_LABELS.rumbleOther },
    ],
    [...odds],
  );
}

export const PLE_MATCH_CARDS: Record<PleSlug, PleMatchCard[]> = {
  "royal-rumble": [
    m2(
      "rr26-gunther-styles",
      "Career Threat Match",
      "sideA",
      { name: "Gunther" },
      { name: "AJ Styles" },
      { left: 1.45, right: 2.75 },
    ),
    m2(
      "rr26-undisputed",
      "Undisputed WWE Championship",
      "sideB",
      { name: "Drew McIntyre", isChampion: true },
      { name: "Sami Zayn" },
      { left: 1.5, right: 2.55 },
    ),
    rumbleWinner(
      "rr26-women-rumble",
      "Women's Royal Rumble Match",
      "sideA",
      [
        "Charlotte Flair",
        "Liv Morgan",
        "Tiffany Stratton",
        "Rhea Ripley",
        "Becky Lynch",
      ],
      [4.5, 5.5, 6.0, 8.0, 9.5, 12.0],
    ),
    rumbleWinner(
      "rr26-men-rumble",
      "Men's Royal Rumble Match",
      "sideB",
      ["Roman Reigns", "CM Punk", "John Cena", "Logan Paul", "Jey Uso"],
      [3.5, 4.5, 6.0, 8.0, 10.0, 14.0],
    ),
  ],

  "elimination-chamber": [
    mm(
      "ec26-women",
      "Women's Elimination Chamber Match",
      "sideA",
      [
        { name: "Rhea Ripley" },
        { name: "Tiffany Stratton" },
        { name: "Raquel Rodriguez" },
        { name: "Asuka" },
        { name: "Kiana James" },
        { name: "Alexa Bliss" },
      ],
      [2.4, 3.2, 4.5, 5.0, 8.0, 6.5],
    ),
    m2(
      "ec26-women-ic",
      "Women's Intercontinental Championship",
      "sideB",
      { name: "AJ Lee" },
      { name: "Becky Lynch", isChampion: true },
      { left: 2.0, right: 1.8 },
    ),
    m2(
      "ec26-whc",
      "World Heavyweight Championship",
      "sideA",
      { name: "CM Punk", isChampion: true },
      { name: "Finn Bálor" },
      { left: 1.55, right: 2.45 },
    ),
    mm(
      "ec26-men",
      "Men's Elimination Chamber Match",
      "sideB",
      [
        { name: "Randy Orton" },
        { name: "Cody Rhodes" },
        { name: "LA Knight" },
        { name: "Logan Paul" },
        { name: "Trick Williams" },
        { name: "Je'Von Evans" },
      ],
      [3.5, 2.8, 5.0, 4.0, 6.0, 7.5],
    ),
  ],

  "stand-and-deliver": [
    m2(
      "sad26-preshow",
      "Mixed Tag Match",
      "sideA",
      { name: "Sinclair, Hank & Tank, EK Prosper, Shiloh Hill" },
      { name: "BirthRight" },
      { left: 1.75, right: 2.05 },
    ),
    m2(
      "sad26-sol-zaria",
      "Single Match",
      "sideB",
      { name: "Sol Ruca" },
      { name: "Zaria" },
      { left: 1.85, right: 1.95 },
    ),
    m2(
      "sad26-women-na",
      "NXT Women's North American Championship",
      "sideA",
      { name: "Tatum Paxley", isChampion: true },
      { name: "Blake Monroe" },
      { left: 1.5, right: 2.6 },
    ),
    m2(
      "sad26-na",
      "NXT North American Championship",
      "sideB",
      { name: "Myles Borne", isChampion: true },
      { name: "Johnny Gargano" },
      { left: 1.65, right: 2.25 },
    ),
    m2(
      "sad26-tag",
      "NXT Tag Team Championship",
      "sideA",
      { name: "The Vanity Project", isChampion: true },
      { name: "Los Americanos" },
      { left: 1.7, right: 2.15 },
    ),
    mm(
      "sad26-women",
      "NXT Women's Championship",
      "sideB",
      [
        { name: "Lola Vice" },
        { name: "Jacy Jayne", isChampion: true },
        { name: "Kendal Grey" },
      ],
      [2.5, 2.2, 4.0],
    ),
    mm(
      "sad26-nxt",
      "NXT Championship",
      "sideA",
      [
        { name: "Tony D'Angelo" },
        { name: "Joe Hendry", isChampion: true },
        { name: "Ricky Saints" },
        { name: "Ethan Page" },
      ],
      [3.0, 2.4, 4.5, 5.5],
    ),
  ],

  wrestlemania: [
    m2(
      "wm42-n1-six",
      "Six-Man Tag Match",
      "sideA",
      { name: "LA Knight & The Usos" },
      { name: "IShowSpeed & The Vision" },
      { left: 1.85, right: 1.95 },
    ),
    m2(
      "wm42-n1-unsanctioned",
      "Unsanctioned Match",
      "sideB",
      { name: "Jacob Fatu" },
      { name: "Drew McIntyre" },
      { left: 1.9, right: 1.92 },
    ),
    mm(
      "wm42-n1-women-tag",
      "WWE Women's Tag Team Championship",
      "sideA",
      [
        { name: "Paige & Brie Bella" },
        { name: "Nia Jax & Lash Legend", isChampion: true },
        { name: "Alexa Bliss & Charlotte Flair" },
        { name: "Bayley & Lyra Valkyria" },
      ],
      [4.0, 2.8, 5.0, 5.5],
    ),
    m2(
      "wm42-n1-women-ic",
      "Women's Intercontinental Championship",
      "sideB",
      { name: "Becky Lynch" },
      { name: "AJ Lee", isChampion: true },
      { left: 1.95, right: 1.88 },
    ),
    m2(
      "wm42-n1-gunther-rollins",
      "Single Match",
      "sideA",
      { name: "Gunther" },
      { name: "Seth Rollins" },
      { left: 1.6, right: 2.35 },
    ),
    m2(
      "wm42-n1-women-world",
      "Women's World Championship",
      "sideB",
      { name: "Liv Morgan" },
      { name: "Stephanie Vaquer", isChampion: true },
      { left: 2.1, right: 1.75 },
    ),
    m2(
      "wm42-n1-undisputed",
      "Undisputed WWE Championship",
      "sideA",
      { name: "Cody Rhodes", isChampion: true },
      { name: "Randy Orton" },
      { left: 1.55, right: 2.5 },
    ),
    m2(
      "wm42-n2-femi-lesnar",
      "Single Match",
      "sideB",
      { name: "Oba Femi" },
      { name: "Brock Lesnar" },
      { left: 2.4, right: 1.58 },
    ),
    mm(
      "wm42-n2-ic-ladder",
      "Intercontinental Championship",
      "sideA",
      [
        { name: "Penta", isChampion: true },
        { name: "Je'Von Evans" },
        { name: "Dragon Lee" },
        { name: "Rey Mysterio" },
        { name: "Rusev" },
        { name: "JD McDonagh" },
      ],
      [2.5, 4.0, 5.5, 6.0, 7.0, 8.5],
    ),
    m2(
      "wm42-n2-us",
      "United States Championship",
      "sideB",
      { name: "Trick Williams" },
      { name: "Sami Zayn", isChampion: true },
      { left: 2.2, right: 1.68 },
    ),
    m2(
      "wm42-n2-street",
      "Street Fight",
      "sideA",
      { name: "Finn Bálor" },
      { name: "Dominik Mysterio" },
      { left: 1.8, right: 2.0 },
    ),
    m2(
      "wm42-n2-women",
      "WWE Women's Championship",
      "sideB",
      { name: "Rhea Ripley" },
      { name: "Jade Cargill", isChampion: true },
      { left: 2.3, right: 1.62 },
    ),
    m2(
      "wm42-n2-whc",
      "World Heavyweight Championship",
      "sideA",
      { name: "Roman Reigns" },
      { name: "CM Punk", isChampion: true },
      { left: 2.0, right: 1.8 },
    ),
  ],

  backlash: [
    m2(
      "bl26-danhausen",
      "Tag Team Match",
      "sideA",
      { name: "Danhausen & Minihausen" },
      { name: "The Miz & Kit Wilson" },
      { left: 1.7, right: 2.15 },
    ),
    m2(
      "bl26-iyo-asuka",
      "Single Match",
      "sideB",
      { name: "IYO SKY" },
      { name: "Asuka" },
      { left: 1.75, right: 2.1 },
    ),
    m2(
      "bl26-us",
      "United States Championship",
      "sideA",
      { name: "Trick Williams", isChampion: true },
      { name: "Sami Zayn" },
      { left: 1.65, right: 2.25 },
    ),
    m2(
      "bl26-breakker-rollins",
      "Single Match",
      "sideB",
      { name: "Bron Breakker" },
      { name: "Seth Rollins" },
      { left: 1.9, right: 1.92 },
    ),
    m2(
      "bl26-whc",
      "World Heavyweight Championship",
      "sideA",
      { name: "Roman Reigns", isChampion: true },
      { name: "Jacob Fatu" },
      { left: 1.45, right: 2.75 },
    ),
  ],

  "money-in-the-bank": [
    mm(
      "mitb26-women",
      "Women's Money in the Bank Ladder Match",
      "sideA",
      [
        { name: "Naomi" },
        { name: "Rhea Ripley" },
        { name: "Stephanie Vaquer" },
        { name: "Alexa Bliss" },
        { name: "Roxanne Perez" },
        { name: "Giulia" },
      ],
      [5.0, 4.0, 6.0, 7.0, 8.0, 9.0],
    ),
    m2(
      "mitb26-ic",
      "Intercontinental Championship",
      "sideB",
      { name: "Dominik Mysterio", isChampion: true },
      { name: "Octagón Jr." },
      { left: 1.45, right: 2.75 },
    ),
    m2(
      "mitb26-women-ic",
      "Women's Intercontinental Championship",
      "sideA",
      { name: "Becky Lynch" },
      { name: "Lyra Valkyria", isChampion: true },
      { left: 1.9, right: 1.92 },
    ),
    mm(
      "mitb26-men",
      "Men's Money in the Bank Ladder Match",
      "sideB",
      [
        { name: "Seth Rollins" },
        { name: "LA Knight" },
        { name: "Penta" },
        { name: "Solo Sikoa" },
        { name: "El Grande Americano" },
        { name: "Andrade" },
      ],
      [5.5, 4.5, 7.0, 6.0, 10.0, 12.0],
    ),
    m2(
      "mitb26-tag",
      "Tag Team Match",
      "sideA",
      { name: "Rhodes & Jey Uso" },
      { name: "Cena & Logan Paul" },
      { left: 1.85, right: 1.95 },
    ),
  ],

  "night-of-champions": [
    mm(
      "noc26-undisputed",
      "Undisputed WWE Championship",
      "sideA",
      [
        { name: "Cody Rhodes", isChampion: true },
        { name: "Gunther" },
        { name: "Sami Zayn" },
      ],
      [1.17, 7.0, 4.0],
    ),
    m2(
      "noc26-kotr",
      "King of the Ring Final",
      "sideB",
      { name: "Jey Uso" },
      { name: "Oba Femi" },
      { left: 1.77, right: 2.1 },
    ),
    m2(
      "noc26-qotr",
      "Queen of the Ring Final",
      "sideA",
      { name: "IYO SKY" },
      { name: "Liv Morgan" },
      { left: 1.17, right: 4.5 },
    ),
    m2(
      "noc26-women-us",
      "Women's United States Championship",
      "sideB",
      { name: "Jade Cargill" },
      { name: "Tiffany Stratton", isChampion: true },
      { left: 1.77, right: 2.1 },
    ),
    m2(
      "noc26-us",
      "United States Championship",
      "sideA",
      { name: "Trick Williams", isChampion: true },
      { name: "Ricky Saints" },
      { left: 1.03, right: 9.5 },
    ),
    m2(
      "noc26-cage",
      "Steel Cage Match",
      "sideB",
      { name: "Seth Rollins" },
      { name: "Bron Breakker" },
      { left: 1.83, right: 1.83 },
    ),
  ],

  "king-queen-of-the-ring": [
    m2(
      "kotr26-final",
      "Single Match",
      "sideB",
      { name: "Cody Rhodes" },
      { name: "Randy Orton" },
      { left: 1.7, right: 2.15 },
    ),
    m2(
      "qotr26-final",
      "Single Match",
      "sideA",
      { name: "Jade Cargill" },
      { name: "Asuka" },
      { left: 1.55, right: 2.45 },
    ),
  ],

  /** WWE SummerSlam 2026.8.1-2 미니애폴리스 U.S. Bank Stadium — 2026-07-01 기준 공식 확정 카드만 반영 (나머지는 미확정) */
  summerslam: [
    m2(
      "ss26-whc",
      "World Heavyweight Championship",
      "sideA",
      { name: "Roman Reigns", isChampion: true },
      { name: "Seth Rollins" },
      { left: 1.9, right: 1.9 },
    ),
    m2(
      "ss26-women-world",
      "Women's World Championship",
      "sideB",
      { name: "Liv Morgan", isChampion: true },
      { name: "IYO SKY" },
      { left: 1.9, right: 1.9 },
    ),
    m2(
      "ss26-hiac",
      "Hell in a Cell Match",
      "sideA",
      { name: "Brock Lesnar" },
      { name: "Oba Femi" },
      { left: 1.9, right: 1.9 },
    ),
  ],

  /** WWE Clash in Italy 2026.5.31 토리노 Inalpi Arena — 공식 카드 (2026-05-23 WWE/SNME 기준) */
  "clash-in-italy": [
    m2(
      "italy26-undisputed",
      "Undisputed WWE Championship",
      "sideA",
      { name: "Cody Rhodes", isChampion: true },
      { name: "Gunther" },
      { left: 1.55, right: 2.35 },
    ),
    m2(
      "italy26-whc-tribal",
      "World Heavyweight Championship — Tribal Combat",
      "sideB",
      { name: "Roman Reigns", isChampion: true },
      { name: "Jacob Fatu" },
      { left: 1.65, right: 2.2 },
    ),
    m2(
      "italy26-women",
      "WWE Women's Championship",
      "sideA",
      { name: "Rhea Ripley", isChampion: true },
      { name: "Jade Cargill" },
      { left: 1.58, right: 2.3 },
    ),
    m2(
      "italy26-women-ic",
      "Women's Intercontinental Championship",
      "sideB",
      { name: "Becky Lynch", isChampion: true },
      { name: "Sol Ruca" },
      { left: 1.62, right: 2.25 },
    ),
    m2(
      "italy26-lesnar-femi",
      "Single Match",
      "sideA",
      { name: "Brock Lesnar" },
      { name: "Oba Femi" },
      { left: 1.72, right: 2.05 },
    ),
  ],

  "bad-blood": [
    m2(
      "bb26-cell",
      "Hell in a Cell Match",
      "sideA",
      { name: "CM Punk" },
      { name: "Drew McIntyre" },
      { left: 1.85, right: 1.95 },
    ),
    m2(
      "bb26-women",
      "WWE Women's Championship",
      "sideB",
      { name: "Nia Jax", isChampion: true },
      { name: "Bayley" },
      { left: 1.5, right: 2.6 },
    ),
    m2(
      "bb26-priest-balor",
      "Single Match",
      "sideA",
      { name: "Damian Priest" },
      { name: "Finn Bálor" },
      { left: 1.8, right: 2.0 },
    ),
    m2(
      "bb26-women-world",
      "Women's World Championship",
      "sideB",
      { name: "Rhea Ripley" },
      { name: "Liv Morgan", isChampion: true },
      { left: 2.1, right: 1.72 },
    ),
    m2(
      "bb26-tag",
      "Tag Team Match",
      "sideA",
      { name: "Rhodes & Reigns" },
      { name: "Sikoa & Fatu" },
      { left: 1.7, right: 2.15 },
    ),
  ],

  "survivor-series": [
    m2(
      "ss26-women-wg",
      "Women's WarGames Match",
      "sideA",
      {
        name: "Team Ripley — Charlotte, Rhea, IYO SKY, Bliss, AJ Lee",
      },
      {
        name: "Team Lynch — Becky, Asuka, Kairi, Nia Jax, Lash Legend",
      },
      { left: 1.85, right: 1.95 },
    ),
    m2(
      "ss26-ic",
      "Intercontinental Championship",
      "sideB",
      { name: "Dominik Mysterio" },
      { name: "John Cena", isChampion: true },
      { left: 2.4, right: 1.58 },
    ),
    m2(
      "ss26-women-world",
      "Women's World Championship",
      "sideA",
      { name: "Stephanie Vaquer", isChampion: true },
      { name: "Nikki Bella" },
      { left: 1.55, right: 2.45 },
    ),
    m2(
      "ss26-men-wg",
      "Men's WarGames Match",
      "sideB",
      {
        name: "The Vision — Lesnar, McIntyre, Logan Paul, Breakker, Reed",
      },
      {
        name: "Team Rhodes — Punk, Cody, Roman, Jey Uso, Jimmy Uso",
      },
      { left: 2.2, right: 1.75 },
    ),
  ],
};

export function getPleMatches(slug: string): PleMatchCard[] {
  return PLE_MATCH_CARDS[slug as PleSlug] ?? [];
}
