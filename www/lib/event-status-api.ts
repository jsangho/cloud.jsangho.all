import { pleEventsBaseUrl, requestTimeoutMs } from "@/lib/api";

/**
 * 대회 `status` 드리프트 점검 — **관리자 전용**.
 *
 * 날짜가 지났는데 `status`가 `upcoming`으로 남은 대회를 찾아 보여주고(미리보기),
 * 요청하면 `finished`로 넘긴다. 그동안 이 일은 사람이 돌리는 스크립트
 * (`close_past_events.py`)밖에 없었고, 잊으면 **아무 에러도 나지 않는 채로** 뒤
 * 단계가 0건을 낸다.
 *
 * 토큰은 httpOnly 쿠키라 `credentials: "include"`로 실어 보낸다.
 */

const maintenanceBaseUrl = `${pleEventsBaseUrl}/maintenance/status-drift`;

/**
 * 판정 한 단어. 서버(`domain/services/event_status_drift.py`)가 고른다.
 *
 * 유니온으로 좁히지 않고 `string`으로 두는 이유: 서버가 다섯째 값을 추가한 날
 * 화면이 조용히 틀린 라벨을 붙이는 대신 **그 값을 그대로 보여주게** 하려는 것이다.
 */
export type EventStatusDriftItem = {
  slug: string;
  status: string;
  startDate: string | null;
  endDate: string | null;
  verdict: string;
};

export type EventStatusDrift = {
  /** 판정 기준일(UTC). 대회 당일은 지난 것으로 보지 않는다. */
  today: string;
  items: EventStatusDriftItem[];
  /** 닫아야 할 대회 수. */
  pending: number;
  /** `null`이면 **쓰지 않았다** — 0("쓸 게 없었다")과 다르다. */
  written: number | null;
};

async function request(url: string, init: RequestInit): Promise<EventStatusDrift> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), requestTimeoutMs);
  try {
    const res = await fetch(url, {
      ...init,
      credentials: "include",
      signal: controller.signal,
    });
    if (!res.ok) {
      const data = (await res.json().catch(() => null)) as { detail?: string } | null;
      throw new Error(data?.detail ?? `요청 실패 (${res.status})`);
    }
    const data = (await res.json()) as Partial<EventStatusDrift>;
    return {
      today: data.today ?? "",
      items: Array.isArray(data.items) ? data.items : [],
      pending: data.pending ?? 0,
      written: data.written ?? null,
    };
  } finally {
    clearTimeout(timer);
  }
}

/** 미리보기 — 아무것도 쓰지 않는다. */
export function fetchEventStatusDrift(): Promise<EventStatusDrift> {
  return request(maintenanceBaseUrl, { method: "GET" });
}

/** 날짜가 지난 대회의 `status`만 `finished`로 넘긴다. 다시 불러도 안전하다(멱등). */
export function closePastEvents(): Promise<EventStatusDrift> {
  return request(`${maintenanceBaseUrl}/close`, { method: "POST" });
}
