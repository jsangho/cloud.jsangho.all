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
