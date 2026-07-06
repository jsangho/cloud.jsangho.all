const STORAGE_KEY = "kayfabe-client-id";

function randomId() {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return `k-${Date.now()}-${Math.random().toString(36).slice(2, 11)}`;
}

/** 브라우저별 익명 예측 ID (서버 투표·SSE용) */
export function getPleClientId(): string {
  if (typeof window === "undefined") return "server";
  try {
    let id = localStorage.getItem(STORAGE_KEY);
    if (!id) {
      id = randomId();
      localStorage.setItem(STORAGE_KEY, id);
    }
    return id;
  } catch {
    return randomId();
  }
}
