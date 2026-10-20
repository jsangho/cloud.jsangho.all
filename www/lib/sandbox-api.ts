import { apiBaseUrl, requestTimeoutMs } from "@/lib/api";

/**
 * 장난감 시뮬레이터 결과. **예측이 아니다** — 실제 예측은 `/ai-lab`이 한다.
 *
 * `score`를 함께 받는 이유는 화면이 근거를 적어야 하기 때문이다. 숫자만 보여 주면
 * 장난감 확률이 진짜처럼 읽힌다.
 */
export type SimContender = {
  name: string;
  titles: number;
  age: number | null;
  score: number;
};

export type SimResult = {
  a: SimContender;
  b: SimContender;
  winner: string;
  /** 0.15~0.85. 업셋이 항상 남는다. */
  probabilityA: number;
  /** 두 이름에서 나온 고정값 — 같은 쌍이면 항상 같은 결과다. */
  roll: number;
};

export async function simulateMatch(a: string, b: string): Promise<SimResult | null> {
  const url = `${apiBaseUrl}/api/sandbox/simulate?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}`;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), requestTimeoutMs);
  try {
    const res = await fetch(url, { signal: controller.signal });
    if (!res.ok) return null;
    return (await res.json()) as SimResult;
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}
