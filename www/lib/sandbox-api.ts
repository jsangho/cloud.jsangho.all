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

/** 커리어 런 하나. **브라우저가 들고 다닌다** — 서버는 저장하지 않는다. */
export type CareerState = {
  name: string;
  style: string;
  week: number;
  brand: string;
  popularity: number;
  wins: number;
  losses: number;
  reigns: string[];
  held: string | null;
  outWeeks: number;
  outcome: string | null;
};

export type CareerStep = {
  state: CareerState;
  week: number;
  kind: string;
  won: boolean | null;
  opponent: string | null;
  belt: string | null;
  promotedTo: string | null;
  injuredWeeks: number;
  popularityDelta: number;
  nextBelt: string | null;
  defending: boolean;
  /** 런의 최대 주차. **서버가 정한다** — 화면에 박아 두면 갈라진다(실제로 갈라졌다). */
  maxWeeks: number;
};

export async function careerStep(
  state: CareerState | { name: string; style: string },
  choice: "경기" | "도전",
): Promise<CareerStep | null> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), requestTimeoutMs);
  try {
    const res = await fetch(`${apiBaseUrl}/api/sandbox/career/step`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ state, choice }),
      signal: controller.signal,
    });
    if (!res.ok) return null;
    return (await res.json()) as CareerStep;
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}
