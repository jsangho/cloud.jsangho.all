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

/**
 * 북메이커 한 곳이 **한 시점에** 건 소수 배당 한 벌.
 *
 * `decimals`의 순서는 선택지 순서다 — 단일전 `[left, right]`, 다인전은 참가자 순서.
 *
 * WWE는 스포츠가 아니라 엔터테인먼트 스페셜 시장이라 공개 배당 API(The Odds API ·
 * SportsGameOdds 등)가 다루지 않는다. 호가는 사람이 확인해 여기에 적는다.
 *
 * `observedAt`이 값의 일부다 — 배당은 움직인다. 언제 본 값인지를 적지 않으면 같은
 * 북메이커의 두 관측이 서로 다른 북메이커처럼 세어져 합의가 왜곡된다.
 */
export type BookmakerQuote = {
  book: string;
  decimals: number[];
  /** `YYYY-MM-DD` */
  observedAt?: string;
  sourceUrl?: string;
};

export type PleMatchCardSingles = PleMatchBase & {
  format: "singles";
  left: PleCompetitor;
  right: PleCompetitor;
  /**
   * 배당이 없을 수 있다 — multi와 같다. 시장이 아직 안 열린 대회가 있고
   * (AAA 공동 개최 `worlds-collide`), 그 자리를 그럴듯한 숫자로 채우면
   * 북메이커 승률 막대가 근거 없는 값을 사실처럼 그린다.
   */
  bookmakerDecimal?: { left: number; right: number };
  /** 북메이커별 호가. 있으면 `bookmakerDecimal`보다 우선한다. */
  bookmakerQuotes?: BookmakerQuote[];
};

export type PleMatchCardMulti = PleMatchBase & {
  format: "multi";
  competitors: PleCompetitor[];
  bookmakerDecimal?: number[];
  bookmakerQuotes?: BookmakerQuote[];
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
  odds?: { left: number; right: number },
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

/**
 * 호가를 여러 개 아는 단일전. `m2`와 달리 `bookmakerDecimal`을 적지 않는다 —
 * 합의는 호가에서 계산하므로, 같은 사실을 두 칸에 적어 두면 언젠가 어긋난다.
 */
function mq(
  id: string,
  title: string,
  cardVariant: "sideA" | "sideB",
  left: PleCompetitor,
  right: PleCompetitor,
  quotes: BookmakerQuote[],
): PleMatchCardSingles {
  return { id, title, cardVariant, format: "singles", left, right, bookmakerQuotes: quotes };
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
    [...topFive.map((name) => ({ name })), { name: BRACKET_LABELS.rumbleOther }],
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
      ["Charlotte Flair", "Liv Morgan", "Tiffany Stratton", "Rhea Ripley", "Becky Lynch"],
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
      [{ name: "Lola Vice" }, { name: "Jacy Jayne", isChampion: true }, { name: "Kendal Grey" }],
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

  // `Money in the Bank (2026)` rev 1378774435(2026-10-06)의 `matchN` 그대로 — 다섯이다.
  // 이전 다섯 경기는 2025 카드를 베낀 픽스처였다(실재하지 않는 IC·여성IC·태그 셋이
  // 섞여 있었다). 2026-09-22에 위키 대진으로 교체했다.
  //
  // **2026-10-06에 대진이 닫혔다 — `TBD`가 0칸이다.** 래더 둘의 마지막 칸이
  // 채워졌고(남자 Kevin Owens · 여자 Tiffany Stratton), 여성 세계왕좌전은
  // 「Becky Lynch or Liv Morgan」이라는 미결 표기가 아니라 **3자 경기**로 확정됐다
  // (stip5 = Triple threat match). 배당은 WHC 한 경기에만 있다 — 나머지는
  // 시장이 열리지 않았고, 지어내지 않는다.
  "money-in-the-bank": [
    mm("mitb26-men", "Men's Money in the Bank Ladder Match", "sideB", [
      { name: "Bron Breakker" },
      { name: "Je'Von Evans" },
      { name: "Trick Williams" },
      { name: "Penta" },
      { name: "CM Punk" },
      { name: "Kevin Owens" },
    ]),
    // 배당 출처: BetOnline · **2026-10-05 12:00PM 관측** · 미국식 호가를 소수로 옮겼다
    // (Perez -150 · Lash +125 · Stratton +300 · Sol +850 · Jacy +1,200 · Lola +1,200).
    // https://www.wweleaks.org/2026/10/mitb-2026-betting-update-5th-october-afternoon.html
    //
    // **`bookmakerQuotes`가 아니라 `bookmakerDecimal`로 적는다.** 호가 배열을 쓰려면
    // `mq` 같은 새 생성자가 필요한데, 픽스처 리더(`ple_fixture_file.py`)가 `m2`·`mm`·
    // `rumbleWinner` 셋만 알아서 **그 경기를 통째로 못 본다** — 동기화 스크립트가
    // 멀쩡한 경기를 「신규」로 다시 만들어 버린다. 그 버그를 고치기 전까지는 늘리지 않는다.
    //
    // 순서는 위 참가자 순서와 **반드시** 같아야 한다 — 길이가 선택지 수와 다르면
    // `odds_consensus`가 그 호가를 조용히 버린다.
    mm(
      "mitb26-women",
      "Women's Money in the Bank Ladder Match",
      "sideA",
      [
        { name: "Sol Ruca" },
        { name: "Lola Vice" },
        { name: "Jacy Jayne" },
        { name: "Roxanne Perez" },
        { name: "Lash Legend" },
        { name: "Tiffany Stratton" },
      ],
      [9.5, 13.0, 13.0, 1.67, 2.25, 4.0],
    ),
    mq(
      "mitb26-whc",
      "World Heavyweight Championship",
      "sideB",
      { name: "Roman Reigns", isChampion: true },
      { name: "LA Knight" },
      // BetOnline이 MITB 2026 시장을 연 유일한 북메이커다 (2026-09-30 확인).
      // 이틀 사이에 Knight가 +350 → +600으로 밀렸다 — 라인 흐름 자체가 정보라
      // 옛 관측을 지우지 않고 남긴다. 합의는 최신 것만 센다.
      [
        {
          book: "BetOnline",
          decimals: [1.17, 4.5],
          observedAt: "2026-09-26",
          sourceUrl: "https://www.wweleaks.org/2026/09/mitb-2026-betting-september-26th.html",
        },
        {
          book: "BetOnline",
          decimals: [1.07, 7.0],
          observedAt: "2026-09-27",
          sourceUrl: "https://www.wweleaks.org/2026/09/mitb-2026-odds-update-27-september.html",
        },
      ],
    ),
    m2("mitb26-reed-femi", "Single Match", "sideA", { name: "Bronson Reed" }, { name: "Oba Femi" }),
    mm("mitb26-women-world", "Women's World Championship", "sideB", [
      { name: "Stephanie Vaquer", isChampion: true },
      { name: "Becky Lynch" },
      { name: "Liv Morgan" },
    ]),
  ],

  "night-of-champions": [
    mm(
      "noc26-undisputed",
      "Undisputed WWE Championship",
      "sideA",
      [{ name: "Cody Rhodes", isChampion: true }, { name: "Gunther" }, { name: "Sami Zayn" }],
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

  /**
   * WWE SummerSlam 2026.8.1-2 미니애폴리스 U.S. Bank Stadium — 방송 종료 후 실제 카드 12경기.
   * 배당은 Sky Bet 프리쇼 라인(소수 환산). 공개 배당을 찾지 못한 경기는 1.9/1.9 중립값이고,
   * 다인전은 배당을 넣지 않았다 — 없는 값을 지어내지 않는다.
   */
  summerslam: [
    m2(
      "ss26-n1-women-world",
      "Women's World Championship",
      "sideA",
      { name: "Liv Morgan", isChampion: true },
      { name: "IYO SKY" },
      { left: 1.73, right: 1.91 },
    ),
    m2(
      "ss26-n1-six-man",
      "Six-Man Tag Match",
      "sideB",
      { name: "LA Knight, Solo Sikoa & Royce Keys" },
      { name: "The Bloodline" },
      { left: 1.9, right: 1.9 },
    ),
    m2(
      "ss26-n1-gunther-aldis",
      "Single Match",
      "sideA",
      { name: "Gunther" },
      { name: "Nick Aldis" },
      { left: 1.9, right: 1.9 },
    ),
    m2(
      "ss26-n1-six-woman",
      "Six-Woman Tag Match",
      "sideB",
      { name: "Fatal Influence" },
      { name: "The Bella Twins & Paige" },
      { left: 1.9, right: 1.9 },
    ),
    m2(
      "ss26-n1-undisputed",
      "Undisputed WWE Championship",
      "sideA",
      { name: "CM Punk", isChampion: true },
      { name: "Cody Rhodes" },
      { left: 1.22, right: 4.33 },
    ),
    m2(
      "ss26-n1-hiac",
      "Hell in a Cell Match",
      "sideB",
      { name: "Oba Femi" },
      { name: "Brock Lesnar" },
      { left: 1.04, right: 8.5 },
    ),
    mm("ss26-n2-contender", "Undisputed WWE Championship — No.1 Contender Fatal 4-Way", "sideA", [
      { name: "Kevin Owens" },
      { name: "Finn Bálor" },
      { name: "Gunther" },
      { name: "Sami Zayn" },
    ]),
    m2(
      "ss26-n2-us",
      "WWE United States Championship",
      "sideB",
      { name: "Trick Williams", isChampion: true },
      { name: "Baron Corbin" },
      { left: 1.3, right: 3.25 },
    ),
    mm("ss26-n2-women-ladder", "Interim WWE Women's Championship — Ladder Match", "sideA", [
      { name: "Chelsea Green" },
      { name: "Charlotte Flair" },
      { name: "Jade Cargill" },
      { name: "Lash Legend" },
      { name: "Tiffany Stratton" },
    ]),
    m2(
      "ss26-n2-pole",
      "Human Monies on a Pole Match",
      "sideB",
      { name: "Danhausen" },
      { name: "Dominik Mysterio" },
      { left: 1.9, right: 1.9 },
    ),
    m2(
      "ss26-n2-ic",
      "WWE Intercontinental Championship",
      "sideA",
      { name: "Penta", isChampion: true },
      { name: "Chad Gable" },
      { left: 5.0, right: 1.14 },
    ),
    m2(
      "ss26-n2-whc",
      "World Heavyweight Championship",
      "sideB",
      { name: "Roman Reigns", isChampion: true },
      { name: "Seth Rollins" },
      { left: 1.14, right: 5.0 },
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

  // `Worlds Collide (2026)` rev 1376055676의 Matches 절 그대로 (2026-09-22 확인).
  // **AAA 공동 개최**라 루차 선수가 절반이다. 배당은 어디에도 없어 넣지 않았다 —
  // 그럴듯한 숫자를 채우면 북메이커 막대가 근거 없는 값을 사실처럼 그린다.
  "worlds-collide": [
    m2(
      "wc26-reina",
      "AAA Reina de Reinas Championship",
      "sideA",
      { name: "La Catalina", isChampion: true },
      { name: "Roxanne Perez" },
    ),
    m2(
      "wc26-tag",
      "Tag Team Match",
      "sideB",
      { name: "Lucha Brothers — Penta & Rey Fénix" },
      { name: "Los Perros del Mal — Daga & Berto" },
    ),
    m2(
      "wc26-trios-women",
      "Trios Match",
      "sideA",
      { name: "Las Tóxicas — Flammer, La Hiedra, Maravilla" },
      { name: "Fatal Influence — Jacy Jayne, Fallon Henley, Lainey Reid" },
    ),
    m2(
      "wc26-dragon-lee",
      "Single Match",
      "sideB",
      { name: "Dragon Lee" },
      { name: "Jack Cartwheel" },
    ),
    m2(
      "wc26-atomicos",
      "Relevos Atómicos de Locura",
      "sideA",
      { name: "Mr. Iguana, La Parka, Adelicious & Mascarita Sagrada" },
      { name: "The Vanity Project & Mini Abismo Negro" },
    ),
    mm("wc26-cruiserweight", "AAA World Cruiserweight #1 Contender", "sideB", [
      { name: "Axiom" },
      { name: "Mini Vikingo" },
      { name: "Je'Von Evans" },
      { name: "EK Prosper" },
    ]),
    m2(
      "wc26-trios-men",
      "Trios Match",
      "sideA",
      { name: "CM Punk, Rey Mysterio & El Grande Americano" },
      { name: "Omos, Dominik Mysterio & JD McDonagh" },
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

  // ── NXT 계열 (2026-09-29 추가) ────────────────────────────────────────────
  // 아래 넷은 `PLE_MATCH_CARDS`에 항목이 아예 없어서 `sync_ple_cards_from_wiki.py`가
  // 매번 "픽스처에 항목이 없다"로 건너뛰던 대회다. 항목이 있어야 그 도구가 id
  // 접두사를 읽고 일할 수 있다.
  //
  // **배당은 넣지 않았다.** 위키에 없는 값이고, 그럴듯한 숫자를 채우면 북메이커
  // 막대가 근거 없는 값을 사실처럼 그린다 (`worlds-collide`와 같은 이유).
  //
  // 끝난 셋은 위키 Results 절의 **참가자만** 옮겼다 — 승자는 옮기지 않는다.
  // 결과는 이 파일이 아니라 결과 경로가 들고 있다.

  // `NXT Vengeance Day (2026)` rev 1374830448 · 2026-03-07 올랜도 WWE PC
  "vengeance-day": [
    m2("vd26-street", "Street Fight", "sideB", { name: "Blake Monroe" }, { name: "Jaida Parker" }),
    m2(
      "vd26-dangelo-lennox",
      "Single Match",
      "sideA",
      { name: "Tony D'Angelo" },
      { name: "Dion Lennox" },
    ),
    m2(
      "vd26-women-na",
      "NXT Women's North American Championship",
      "sideB",
      { name: "Tatum Paxley" },
      { name: "Izzi Dame", isChampion: true },
    ),
    m2(
      "vd26-underground",
      "NXT Underground Match",
      "sideA",
      { name: "Lola Vice" },
      { name: "Kelani Jordan" },
    ),
    m2(
      "vd26-nxt",
      "NXT Championship",
      "sideB",
      { name: "Joe Hendry", isChampion: true },
      { name: "Ricky Saints" },
    ),
  ],

  // `NXT The Great American Bash (2026)` rev 1366584485 · 2026-06-28 올랜도 WWE PC
  "great-american-bash": [
    m2(
      "gab26-nxt",
      "NXT Championship",
      "sideB",
      { name: "Tony D'Angelo", isChampion: true },
      { name: "Naraku" },
    ),
    m2(
      "gab26-women-na",
      "NXT Women's North American Championship",
      "sideA",
      { name: "Zaria", isChampion: true },
      { name: "Tatum Paxley" },
    ),
    m2(
      "gab26-hill-angels",
      "Single Match",
      "sideB",
      { name: "Shiloh Hill" },
      { name: "Tristan Angels" },
    ),
    // 이 벨트는 2026-09-29에 **폐지로 확정돼 챔피언 보드에서 지웠다.** 경기 자체는
    // 실제로 열렸으므로 제목을 위키 표기 그대로 남긴다 — 보드에 없다고 과거를
    // 고쳐 쓰지 않는다.
    m2(
      "gab26-women-speed",
      "WWE Women's Speed Championship",
      "sideA",
      { name: "Wren Sinclair", isChampion: true },
      { name: "Arianna Grace" },
    ),
    m2(
      "gab26-shugars-lennox",
      "Single Match",
      "sideB",
      { name: "Saquon Shugars" },
      { name: "Dion Lennox" },
    ),
    m2(
      "gab26-na",
      "NXT North American Championship",
      "sideA",
      { name: "Myles Borne", isChampion: true },
      { name: "Tavion Heights" },
    ),
    m2(
      "gab26-women",
      "NXT Women's Championship",
      "sideB",
      { name: "Kendal Grey" },
      { name: "Lola Vice", isChampion: true },
    ),
  ],

  // `NXT Heatwave (2026)` rev 1377147141 · 2026-08-30 텍사스 에딘버그
  heatwave: [
    // 벨트 둘을 **통합**하는 경기라 제목이 한 벨트를 가리키지 않는다. 한쪽 벨트
    // 이름만 적으면 나머지 하나가 화면에서 사라진다.
    mm("hw26-winner-takes-all", "Winner Takes All Triple Threat", "sideB", [
      { name: "Zaria", isChampion: true },
      { name: "Wren Sinclair", isChampion: true },
      { name: "Kali Armstrong" },
    ]),
    m2(
      "hw26-tag",
      "NXT Tag Team Championship",
      "sideA",
      { name: "The Vanity Project — Brad Baylor & Ricky Smokes" },
      { name: "Myles Borne & Tavion Heights", isChampion: true },
    ),
    m2(
      "hw26-submission",
      "Submission Match",
      "sideB",
      { name: "Jaida Parker" },
      { name: "Nattie" },
    ),
    m2(
      "hw26-women",
      "NXT Women's Championship",
      "sideA",
      { name: "Kelani Jordan" },
      { name: "Kendal Grey", isChampion: true },
    ),
    m2(
      "hw26-na",
      "NXT North American Championship",
      "sideB",
      { name: "Jackson Drake" },
      { name: "Myles Borne", isChampion: true },
    ),
    mm("hw26-nxt", "NXT Championship", "sideA", [
      { name: "Grayson Waller" },
      { name: "Tony D'Angelo", isChampion: true },
      { name: "Cruz Montana" },
      { name: "Zilla Fatu" },
    ]),
  ],

  // `Crown Jewel (2026)` rev 1372805732 · 2026-11-07 리야드
  //
  // **참가자가 사람 이름이 아니라 자리 이름이다.** 크라운 주얼은 두 브랜드의
  // 챔피언끼리 붙이는 형식이라, 11/7에 그 벨트를 들고 있는 사람이 나간다 — 위키도
  // 아직 모른다. 위키가 적은 그대로 두는 이유는 그것이 **실제로 발표된 대진**이기
  // 때문이다. 이름을 지어 넣으면 확정되지 않은 것이 확정된 것처럼 보인다.
  //
  // 챔피언이 정해지면 위키가 이 칸을 사람 이름으로 바꾼다. 그때
  // `sync_ple_cards_from_wiki.py`는 이름이 통째로 달라져 **기존 경기를 못 알아보고**
  // 새 id를 제안하며 아래 둘을 `위키 대진에 없음`으로 보고한다. 지우지는 않으므로,
  // 그 드라이런을 보고 사람이 이름만 갈아 끼우면 된다.
  "crown-jewel": [
    m2(
      "cj26-crown-jewel",
      "WWE Crown Jewel Championship",
      "sideB",
      { name: "Raw's World Heavyweight Champion" },
      { name: "SmackDown's Undisputed WWE Champion" },
    ),
    m2(
      "cj26-women-crown-jewel",
      "WWE Women's Crown Jewel Championship",
      "sideA",
      { name: "Raw's Women's World Champion" },
      { name: "SmackDown's WWE Women's Champion" },
    ),
  ],

  // `Wrestlepalooza (2026)` · 2026-12-12 퍼스 RAC Arena · **대진 미발표**.
  // 위키 문서에 `Matches` 절이 없다(Production·See also·References·External links뿐,
  // 2026-09-29 확인). 통산 6번째이고 북미 밖 개최는 처음이다.
  wrestlepalooza: [],

  // `NXT Halloween Havoc (2026)` · 2026-10-31 · **대진 미발표**.
  // 위키 문서에 `Matches` 절 자체가 없다(Background·References·External links뿐,
  // 2026-09-29 확인). 빈 배열로 두는 이유는 `getPleMatches`가 `[]`를 돌려주어
  // 화면이 "대진 미발표"로 뜨기 때문이다 — 추측 카드를 채우지 않는다.
  //
  // 대진이 발표되면 `sync_ple_cards_from_wiki.py --event halloween-havoc`가
  // 채운다. 다만 경기가 0건이라 id 접두사를 읽을 자리가 없으므로, 그 도구는
  // `ple_match_id_prefixes.py`의 `hh26`을 쓴다.
  "halloween-havoc": [],
};

export function getPleMatches(slug: string): PleMatchCard[] {
  return PLE_MATCH_CARDS[slug as PleSlug] ?? [];
}
