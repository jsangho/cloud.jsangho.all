import {
  authHeader,
  getRequestTimeoutMessage,
  isAbortError,
  parseApiError,
  requestTimeoutMs,
  shopBaseUrl,
} from "@/lib/api";

export type ShopItem = {
  code: string;
  name: string;
  description: string;
  price: number;
  category: string;
  isConsumable: boolean;
};

/**
 * `earned`는 적중 예측의 배점 합계, `spent`는 원장이 깎아낸 총액.
 * 화면에 보여줄 "보유 포인트"는 `balance`다 (`earned - spent`).
 */
export type Wallet = {
  earned: number;
  spent: number;
  balance: number;
};

export type InventoryItem = {
  id: number;
  itemCode: string;
  itemName: string;
  category: string;
  contextKey: string;
  isEquipped: boolean;
  acquiredAt: string;
};

export type PurchaseReceipt = {
  inventoryId: number;
  itemCode: string;
  price: number;
  balanceAfter: number;
};

async function requestJson<T>(url: string, init: RequestInit): Promise<T | null> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), requestTimeoutMs);
  try {
    const res = await fetch(url, { ...init, signal: controller.signal });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}

/** 카탈로그는 비로그인도 볼 수 있다. 실패·빈 목록 모두 `[]`. */
export async function fetchShopItems(): Promise<ShopItem[]> {
  const items = await requestJson<ShopItem[]>(`${shopBaseUrl}/items`, {});
  return Array.isArray(items) ? items : [];
}

export async function fetchWallet(token: string): Promise<Wallet | null> {
  return requestJson<Wallet>(`${shopBaseUrl}/wallet`, {
    headers: authHeader(token),
  });
}

export async function fetchInventory(token: string): Promise<InventoryItem[]> {
  const items = await requestJson<InventoryItem[]>(`${shopBaseUrl}/inventory`, {
    headers: authHeader(token),
  });
  return Array.isArray(items) ? items : [];
}

/**
 * 구매. 실패 사유를 화면에 다르게 보여줘야 해서 `null`이 아니라 `throw`한다.
 * 서버가 402(잔액 부족)·409(중복 보유)·410(판매 중단)으로 사유를 갈라 준다.
 */
export async function purchaseShopItem(
  token: string,
  itemCode: string,
  contextKey?: string,
): Promise<PurchaseReceipt> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), requestTimeoutMs);
  try {
    const res = await fetch(`${shopBaseUrl}/purchases`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeader(token) },
      body: JSON.stringify({ itemCode, contextKey: contextKey ?? "" }),
      signal: controller.signal,
    });
    if (!res.ok) {
      const body = (await res.json().catch(() => null)) as {
        detail?: string;
      } | null;
      throw new Error(parseApiError(body, res.status));
    }
    return (await res.json()) as PurchaseReceipt;
  } catch (error) {
    // 타임아웃·네트워크 오류의 브라우저 원문을 그대로 띄우지 않는다.
    if (isAbortError(error)) {
      throw new Error(getRequestTimeoutMessage());
    }
    if (error instanceof TypeError) {
      throw new Error("서버에 연결하지 못했습니다. 잠시 후 다시 시도해 주세요.");
    }
    throw error;
  } finally {
    clearTimeout(timer);
  }
}

export async function setItemEquipped(
  token: string,
  inventoryId: number,
  isEquipped: boolean,
): Promise<InventoryItem | null> {
  return requestJson<InventoryItem>(`${shopBaseUrl}/inventory/${inventoryId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...authHeader(token) },
    body: JSON.stringify({ isEquipped }),
  });
}
