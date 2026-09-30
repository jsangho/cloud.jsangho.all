import type { BookmakerQuote } from "@/lib/wwe-ple-matches";

/** 영국·유럽 십진 배당(예: Betfair, William Hill) → 내재 승률 */
export function impliedWinPercentFromDecimal(decimalOdds: number): number {
  if (decimalOdds <= 1) return 50;
  return Math.round((1 / decimalOdds) * 1000) / 10;
}

/** 2자 시장 오버라운드 제거 후 정규화 (합 ≈ 100%) */
export function normalizedTwoWayMarket(
  decimalA: number,
  decimalB: number,
): { left: number; right: number } {
  const rawLeft = 1 / decimalA;
  const rawRight = 1 / decimalB;
  const total = rawLeft + rawRight;
  const left = Math.round((rawLeft / total) * 1000) / 10;
  const right = Math.round((rawRight / total) * 1000) / 10;
  return { left, right };
}

/** N자 시장 십진 배당 → 정규화 승률(%) */
export function normalizedMultiMarket(decimals: number[]): number[] {
  const raw = decimals.map((d) => 1 / d);
  const total = raw.reduce((a, b) => a + b, 0);
  return raw.map((r) => Math.round((r / total) * 1000) / 10);
}

/**
 * 여러 북메이커의 호가 → 합의 확률.
 *
 * **백엔드 `domain/services/odds_consensus.py`와 같은 규칙이다** — 북메이커마다 최신
 * 관측 하나만 세고, 선택지별 중앙값을 골라 다시 정규화한다. 두 언어에 같은 산식이
 * 두 벌 있는 것은 이 저장소가 이미 지고 있는 빚이고(`normalizedTwoWayMarket` ↔
 * `implied_probabilities`), 한쪽만 고치면 화면이 에이전트와 다른 숫자를 말한다.
 *
 * 쓸 호가가 없으면 `null` — 그 자리를 그럴듯한 숫자로 채우지 않는다.
 */
export function consensusFromQuotes(
  quotes: BookmakerQuote[],
  optionCount: number,
): { probabilities: number[]; books: string[]; dispersion: number } | null {
  const usable = latestPerBook(quotes)
    .filter((q) => q.decimals.length === optionCount && q.decimals.every((d) => d > 0))
    .map((q) => {
      const raw = q.decimals.map((d) => 1 / d);
      const total = raw.reduce((a, b) => a + b, 0);
      return { book: q.book, probabilities: raw.map((r) => r / total) };
    });
  if (usable.length === 0) return null;

  const merged = Array.from({ length: optionCount }, (_, i) =>
    median(usable.map((u) => u.probabilities[i])),
  );
  // 선택지마다 따로 고른 중앙값이라 합이 1이라는 보장이 없다.
  const total = merged.reduce((a, b) => a + b, 0);
  if (total <= 0) return null;
  const probabilities = merged.map((v) => v / total);

  const favorite = probabilities.indexOf(Math.max(...probabilities));
  const spread = usable.map((u) => u.probabilities[favorite]);
  return {
    probabilities,
    books: usable.map((u) => u.book),
    dispersion: Math.max(...spread) - Math.min(...spread),
  };
}

/** 북메이커마다 가장 최근 관측 하나만. 관측일이 없으면 가장 오래된 것으로 본다. */
function latestPerBook(quotes: BookmakerQuote[]): BookmakerQuote[] {
  const newest = new Map<string, BookmakerQuote>();
  for (const quote of quotes) {
    const current = newest.get(quote.book);
    if (!current || (quote.observedAt ?? "") >= (current.observedAt ?? "")) {
      newest.set(quote.book, quote);
    }
  }
  return [...newest.keys()].sort().map((book) => newest.get(book)!);
}

function median(values: number[]): number {
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 0 ? (sorted[mid - 1] + sorted[mid]) / 2 : sorted[mid];
}
